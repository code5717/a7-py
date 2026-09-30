"""Internal safety proof and backend-plan analysis for A7.

This pass owns value facts and risky-operation approval. The type checker
answers base type questions; this analysis turns those typed expressions into
obligations, discharges the obligations from local facts, and records the exact
operations the backend is allowed to lower.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum, auto
import math
from typing import Optional

from a7.ast_nodes import ASTNode, AssignOp, BinaryOp, LiteralKind, NodeKind, UnaryOp
from a7.cast_classifier import CastClass, CastDecision, classify_cast
from a7.errors import SourceSpan, TypeCheckError, TypeErrorType
from a7.symbol_table import SymbolTable
from a7.types import (
    ArrayType,
    FunctionType,
    PrimitiveType,
    ReferenceType,
    SliceType,
    Type,
    TypeKind,
    UnionType,
)


class TypeCategory(Enum):
    SIGNED_INTEGER = auto()
    UNSIGNED_INTEGER = auto()
    FLOAT = auto()
    BOOLEAN = auto()
    REF = auto()
    POINTER = auto()
    ARRAY = auto()
    SLICE = auto()
    STRUCT = auto()
    ENUM = auto()
    UNION = auto()
    FUNCTION = auto()
    GENERIC = auto()
    OTHER = auto()


SIGNED_RANGES = {
    "i8": (-(2**7), 2**7 - 1),
    "i16": (-(2**15), 2**15 - 1),
    "i32": (-(2**31), 2**31 - 1),
    "i64": (-(2**63), 2**63 - 1),
    "isize": (-(2**63), 2**63 - 1),
}
UNSIGNED_RANGES = {
    "u8": (0, 2**8 - 1),
    "u16": (0, 2**16 - 1),
    "u32": (0, 2**32 - 1),
    "u64": (0, 2**64 - 1),
    "usize": (0, 2**64 - 1),
}
INTEGER_RANGES = {**SIGNED_RANGES, **UNSIGNED_RANGES}

# Headline message for each safety obligation kind. Kinds not listed use the
# message of their diagnostic code. Division, index and slice obligations carry
# no diagnostic code: no existing TypeErrorType describes them, and each of the
# near matches prints a hint about casts or index types.
# Deferred statement kinds whose facts are left alone after the defer site.
# `zig.py: _emit_statement_inline` lowers every other kind to `defer void;`,
# which Zig rejects, so dropping facts for those cannot change the result of a
# program that builds today. These four lower to real Zig: a block, a `del`
# (`examples/011_memory.a7` builds and runs one), a call and an expression
# statement.
DEFER_HAVOC_EXCLUDED_KINDS = {
    NodeKind.BLOCK,
    NodeKind.DEL,
    NodeKind.CALL,
    NodeKind.EXPRESSION_STMT,
}

# Node kinds a `del` operand can be reduced through to reach the identifier
# whose fact the `del` destroys. Assignment targets are not reduced: writing
# through a base (`b.value = 0`, `arr[0] = 0`, `s[0:1] = ...`, `p.* = 0`)
# cannot invalidate any fact this pass holds about the base, because every
# fact is keyed by a plain identifier name (`FactMap.by_symbol`) and no fact
# is derived from a field or element value. See `_deferred_assigned_symbols`.
DEL_TARGET_BASE_ATTRS = {
    NodeKind.FIELD_ACCESS: "object",
    NodeKind.INDEX: "object",
    NodeKind.SLICE: "object",
    NodeKind.DEREF: "pointer",
}

OBLIGATION_MESSAGES = {
    "DIVISOR_NONZERO": "Divisor not proven non-zero",
    "INDEX_IN_BOUNDS": "Index not proven in bounds",
    "SLICE_IN_BOUNDS": "Slice bounds not proven",
    "REF_NON_NIL": "Reference not proven non-nil",
}


def categorize_type(type_: Type) -> TypeCategory:
    if isinstance(type_, PrimitiveType):
        if type_.name in SIGNED_RANGES:
            return TypeCategory.SIGNED_INTEGER
        if type_.name in UNSIGNED_RANGES:
            return TypeCategory.UNSIGNED_INTEGER
        if type_.name in {"f32", "f64"}:
            return TypeCategory.FLOAT
        if type_.name == "bool":
            return TypeCategory.BOOLEAN
    if isinstance(type_, ReferenceType):
        return TypeCategory.REF
    if type_.kind is TypeKind.POINTER:
        return TypeCategory.POINTER
    if isinstance(type_, ArrayType):
        return TypeCategory.ARRAY
    if isinstance(type_, SliceType):
        return TypeCategory.SLICE
    if type_.kind is TypeKind.STRUCT:
        return TypeCategory.STRUCT
    if type_.kind is TypeKind.ENUM:
        return TypeCategory.ENUM
    if isinstance(type_, UnionType):
        return TypeCategory.UNION
    if isinstance(type_, FunctionType):
        return TypeCategory.FUNCTION
    if type_.kind in {TypeKind.GENERIC_PARAM, TypeKind.GENERIC_INSTANCE, TypeKind.TYPE_SET}:
        return TypeCategory.GENERIC
    return TypeCategory.OTHER


@dataclass(frozen=True)
class IntegerInterval:
    lower: Optional[int] = None
    upper: Optional[int] = None

    @classmethod
    def exact(cls, value: int) -> "IntegerInterval":
        return cls(value, value)

    def contains(self, low: int, high: int) -> bool:
        return self.lower is not None and self.upper is not None and low <= self.lower and self.upper <= high

    def is_nonzero(self) -> bool:
        return (self.upper is not None and self.upper < 0) or (self.lower is not None and self.lower > 0)

    def is_nonnegative(self) -> bool:
        return self.lower is not None and self.lower >= 0

    def add(self, other: "IntegerInterval") -> "IntegerInterval":
        lo = None if self.lower is None or other.lower is None else self.lower + other.lower
        hi = None if self.upper is None or other.upper is None else self.upper + other.upper
        return IntegerInterval(lo, hi)

    def sub(self, other: "IntegerInterval") -> "IntegerInterval":
        lo = None if self.lower is None or other.upper is None else self.lower - other.upper
        hi = None if self.upper is None or other.lower is None else self.upper - other.lower
        return IntegerInterval(lo, hi)

    def mul(self, other: "IntegerInterval") -> "IntegerInterval":
        if None in {self.lower, self.upper, other.lower, other.upper}:
            return IntegerInterval()
        values = [
            self.lower * other.lower,
            self.lower * other.upper,
            self.upper * other.lower,
            self.upper * other.upper,
        ]
        return IntegerInterval(min(values), max(values))


@dataclass(frozen=True)
class ValueFact:
    interval: Optional[IntegerInterval] = None
    nonzero: bool = False
    known_length: Optional[int] = None
    upper_length_of: Optional[str] = None
    non_nil: bool = False
    maybe_nil: bool = False
    initialized: bool = True
    moved: bool = False
    enum_discriminant: Optional[str] = None


@dataclass
class FactMap:
    by_node: dict[int, ValueFact] = field(default_factory=dict)
    by_symbol: dict[str, ValueFact] = field(default_factory=dict)

    def node(self, node: Optional[ASTNode]) -> ValueFact:
        if node is None:
            return ValueFact()
        return self.by_node.get(id(node), ValueFact())

    def symbol(self, name: Optional[str]) -> ValueFact:
        if not name:
            return ValueFact()
        return self.by_symbol.get(name, ValueFact())

    def set_node(self, node: ASTNode, fact: ValueFact) -> None:
        self.by_node[id(node)] = fact

    def set_symbol(self, name: str, fact: ValueFact) -> None:
        self.by_symbol[name] = fact

    def copy_symbols(self) -> dict[str, ValueFact]:
        return dict(self.by_symbol)

    def restore_symbols(self, saved: dict[str, ValueFact]) -> None:
        self.by_symbol = saved


class ObligationKind(Enum):
    CAST = auto()
    DIVISOR_NONZERO = auto()
    INDEX_IN_BOUNDS = auto()
    SLICE_IN_BOUNDS = auto()
    REF_NON_NIL = auto()
    INTEGER_OVERFLOW = auto()
    UNION_FIELD = auto()
    MOVE_VALID = auto()


@dataclass(frozen=True)
class Obligation:
    kind: ObligationKind
    node_id: int
    backend_operation: str
    span: Optional[SourceSpan]
    operand_type: Optional[Type]
    required_proof: str
    diagnostic_code: Optional[TypeErrorType]


@dataclass(frozen=True)
class ProofResult:
    proven: bool
    obligation: Obligation
    reason: str


@dataclass
class BackendPlan:
    approved: dict[tuple[int, str], ProofResult] = field(default_factory=dict)

    def approve(self, result: ProofResult) -> None:
        key = (result.obligation.node_id, result.obligation.backend_operation)
        self.approved[key] = result

    def require(self, node: ASTNode, operation: str) -> ProofResult:
        result = self.approved.get((id(node), operation))
        if result is None or not result.proven:
            raise KeyError(f"backend operation '{operation}' is not approved")
        return result

    def is_approved(self, node: ASTNode, operation: str) -> bool:
        result = self.approved.get((id(node), operation))
        return bool(result and result.proven)


class SafetyProofPass:
    """Collect and prove risky-operation obligations from typed AST facts."""

    def __init__(self, symbols: SymbolTable, node_types: dict[int, Type]):
        self.symbols = symbols
        self.node_types = node_types
        self.facts = FactMap()
        self.obligations: list[Obligation] = []
        self.results: list[ProofResult] = []
        self.backend_plan = BackendPlan()
        self.errors: list[TypeCheckError] = []
        self.moved_symbols: set[str] = set()
        self.const_facts: dict[str, ValueFact] = {}
        self.current_stmt_span: Optional[SourceSpan] = None
        self.current_file = "<unknown>"
        self.source_lines: list[str] = []
        self.function_deletes: dict[str, bool] = {}
        self.symbol_types: dict[str, Type] = {}
        self.deferred_effects: list[set[str]] = []
        self.deferred_deletes: list[set[str]] = []

    def analyze(self, program: ASTNode, filename: str = "<unknown>") -> BackendPlan:
        self.current_file = filename
        self.errors = []
        self.obligations = []
        self.results = []
        self.backend_plan = BackendPlan()
        self.facts = FactMap()
        self.moved_symbols = set()
        self.const_facts = {}
        self.current_stmt_span = None
        self.function_deletes = {}
        self.symbol_types = {}
        self.deferred_effects = []
        self.deferred_deletes = []
        self._visit_program(program)
        return self.backend_plan

    def _type(self, node: Optional[ASTNode]) -> Optional[Type]:
        return self.node_types.get(id(node)) if node is not None else None

    def _error(self, obligation: Obligation, reason: str) -> None:
        self.results.append(ProofResult(False, obligation, reason))
        context = f"{obligation.required_proof}: {reason}"
        headline = OBLIGATION_MESSAGES.get(obligation.kind.name)
        if obligation.diagnostic_code is not None:
            error = TypeCheckError.from_type(
                obligation.diagnostic_code,
                span=obligation.span,
                filename=self.current_file,
                source_lines=self.source_lines,
                custom_message=headline,
                context=context,
            )
        else:
            error = TypeCheckError(
                f"{headline} ({context})",
                span=obligation.span,
                filename=self.current_file,
                source_lines=self.source_lines,
            )
        self.errors.append(error)

    def _prove(self, obligation: Obligation, reason: str) -> None:
        result = ProofResult(True, obligation, reason)
        self.results.append(result)
        self.backend_plan.approve(result)

    def _obligation(
        self,
        kind: ObligationKind,
        node: ASTNode,
        operation: str,
        operand_type: Optional[Type],
        required: str,
        code: Optional[TypeErrorType],
    ) -> Obligation:
        obligation = Obligation(kind, id(node), operation, self._obligation_span(node), operand_type, required, code)
        self.obligations.append(obligation)
        return obligation

    def _obligation_span(self, node: ASTNode) -> Optional[SourceSpan]:
        """Span of the operation, else of its right operand, else of the statement.

        BINARY nodes have no span (PAR-04), so a division reports the divisor.
        """
        if node.span is not None:
            return node.span
        for attr in ("right", "index", "end", "operand", "expression"):
            child = getattr(node, attr, None)
            if isinstance(child, ASTNode) and child.span is not None:
                return child.span
        return self.current_stmt_span

    def _visit_program(self, node: ASTNode) -> None:
        # File-scope `::` constants cannot change, so their facts are computed
        # once and seeded into every function. File-scope `:=` variables are
        # never seeded.
        for decl in node.declarations or []:
            if decl.kind == NodeKind.CONST and decl.value:
                self.current_stmt_span = decl.span
                fact = self._visit_expr(decl.value)
                if decl.name:
                    self.const_facts[decl.name] = fact
                    self.facts.set_symbol(decl.name, fact)
        # Unknown function values may release their reference arguments. Known
        # bodies without deletion retain pointer identity across field writes.
        bodies = {d.name: d for d in node.declarations or [] if d.kind == NodeKind.FUNCTION}
        calls: dict[str, set[str]] = {}
        for name, decl in bodies.items():
            deletes = False
            callees: set[str] = set()
            stack = [decl.body] if decl.body else []
            while stack:
                item = stack.pop()
                if item.kind == NodeKind.FUNCTION:
                    continue
                deletes |= item.kind == NodeKind.DEL
                if item.kind == NodeKind.CALL and item.function:
                    callee = item.function
                    if getattr(item, "stdlib_canonical", None):
                        pass
                    elif callee.kind == NodeKind.IDENTIFIER:
                        callees.add(callee.name)
                    else:
                        deletes = True
                for value in vars(item).values():
                    if isinstance(value, ASTNode):
                        stack.append(value)
                    elif isinstance(value, list):
                        stack.extend(v for v in value if isinstance(v, ASTNode))
            self.function_deletes[name] = deletes
            calls[name] = callees
        changed = True
        while changed:
            changed = False
            for name, callees in calls.items():
                if not self.function_deletes[name] and any(self.function_deletes.get(c, True) for c in callees):
                    self.function_deletes[name] = True
                    changed = True
        for decl in node.declarations or []:
            self._visit_decl(decl)

    def _visit_decl(self, node: ASTNode) -> None:
        if node.kind == NodeKind.FUNCTION and node.body:
            self.moved_symbols = set()
            self.symbol_types = {}
            self.facts.by_symbol = dict(self.const_facts)
            for param in node.parameters or []:
                if param.name:
                    self.facts.set_symbol(param.name, self._fact_from_type_node(param.param_type))
                    if param.param_type and param.param_type.type_name in INTEGER_RANGES:
                        self.symbol_types[param.name] = PrimitiveType(param.param_type.type_name)
            self._visit_stmt(node.body)
        elif node.kind == NodeKind.VAR and node.value:
            self.current_stmt_span = node.span
            fact = self._visit_expr(node.value)
            if node.name:
                self.facts.set_symbol(node.name, fact)

    def _deferred_assigned_symbols(self, statement: ASTNode) -> set[str]:
        """Names whose facts a deferred statement can destroy.

        Two cases:

        * Plain or compound assignment to a **bare identifier** (`x = 0`,
          `x += 1`) replaces the variable, so its fact goes. An assignment
          whose target is a field, index, slice or dereference writes
          *through* the base and contributes nothing: every fact this pass
          holds is stored in `FactMap.by_symbol` under a plain identifier
          name, and none is derived from a field or element value, so
          `b.value = 0` cannot make `b` nil, shorten `b` or widen its
          interval. Dropping the base there only over-rejects.
        * `del` frees the memory the reference names, which does invalidate
          the reference, so the operand is reduced through a field, index,
          slice or deref base to the identifier and that identifier's fact
          is dropped.

        Nested function bodies are skipped: their assignments are their own.
        The walk uses an explicit stack and calls no visitor, so it adds no
        recursion.
        """
        names: set[str] = set()
        stack = [statement]
        while stack:
            current = stack.pop()
            if current.kind == NodeKind.FUNCTION:
                continue
            if current.kind == NodeKind.ASSIGNMENT:
                target = current.target
                if target is not None and target.kind == NodeKind.IDENTIFIER and target.name:
                    names.add(target.name)
            elif current.kind == NodeKind.DEL:
                target = current.expression
                while target is not None:
                    if target.kind == NodeKind.IDENTIFIER:
                        if target.name:
                            names.add(target.name)
                        break
                    attr = DEL_TARGET_BASE_ATTRS.get(target.kind)
                    if attr is None:
                        break
                    target = getattr(target, attr, None)
            if current.kind == NodeKind.CALL:
                for i, arg in enumerate(current.arguments or []):
                    if i in getattr(current, "implicit_ref_args", set()) or isinstance(self._type(arg), ReferenceType):
                        if arg.kind == NodeKind.IDENTIFIER:
                            names.add(arg.name)
            for value in vars(current).values():
                if isinstance(value, ASTNode):
                    stack.append(value)
                elif isinstance(value, list):
                    stack.extend(child for child in value if isinstance(child, ASTNode))
        return names

    def _deleted_names(self, statement: ASTNode) -> set[str]:
        names: set[str] = set()
        stack = [statement]
        while stack:
            current = stack.pop()
            if current.kind == NodeKind.FUNCTION:
                continue
            if current.kind == NodeKind.DEL:
                target = current.expression
                while target is not None:
                    if target.kind == NodeKind.IDENTIFIER:
                        names.add(target.name)
                        break
                    attr = DEL_TARGET_BASE_ATTRS.get(target.kind)
                    target = getattr(target, attr, None) if attr else None
            if current.kind == NodeKind.CALL:
                callee = current.function
                callee_name = callee.name if callee and callee.kind == NodeKind.IDENTIFIER else None
                signature = self._type(callee)
                if self.function_deletes.get(callee_name, True) and isinstance(signature, FunctionType):
                    for arg, parameter in zip(current.arguments or [], signature.param_types):
                        if isinstance(parameter, ReferenceType) and isinstance(self._type(arg), ReferenceType) and arg.kind == NodeKind.IDENTIFIER:
                            names.add(arg.name)
            for value in vars(current).values():
                if isinstance(value, ASTNode):
                    stack.append(value)
                elif isinstance(value, list):
                    stack.extend(child for child in value if isinstance(child, ASTNode))
        return names

    def _invalidate_length_relations(self, name: str) -> None:
        for key, fact in list(self.facts.by_symbol.items()):
            if fact.upper_length_of == name:
                self.facts.set_symbol(key, replace(fact, upper_length_of=None))

    def _forget_names(self, names: set[str]) -> None:
        for name in names:
            self._invalidate_length_relations(name)
            self.facts.set_symbol(name, self._default_fact_for_type(self.symbol_types.get(name)))

    def _join_facts(self, left: dict[str, ValueFact], right: dict[str, ValueFact]) -> dict[str, ValueFact]:
        joined = {}
        for name in left.keys() & right.keys():
            a, b = left[name], right[name]
            interval = None
            if a.interval and b.interval:
                lo = min(a.interval.lower, b.interval.lower) if a.interval.lower is not None and b.interval.lower is not None else None
                hi = max(a.interval.upper, b.interval.upper) if a.interval.upper is not None and b.interval.upper is not None else None
                interval = IntegerInterval(lo, hi)
            joined[name] = ValueFact(interval=interval, nonzero=a.nonzero and b.nonzero,
                                     known_length=a.known_length if a.known_length == b.known_length else None,
                                     upper_length_of=a.upper_length_of if a.upper_length_of == b.upper_length_of else None,
                                     non_nil=a.non_nil and b.non_nil, maybe_nil=a.maybe_nil or b.maybe_nil,
                                     initialized=a.initialized and b.initialized, moved=a.moved or b.moved)
        return joined

    def _visit_stmt(self, node: ASTNode) -> None:
        if node.kind != NodeKind.BLOCK and node.span is not None:
            self.current_stmt_span = node.span
        if node.kind == NodeKind.BLOCK:
            names_before = set(self.facts.by_symbol)
            shadowed: dict[str, ValueFact] = {}
            shadowed_moved: dict[str, bool] = {}
            saved_types = dict(self.symbol_types)
            self.deferred_effects.append(set())
            self.deferred_deletes.append(set())
            for stmt in node.statements or []:
                if stmt.kind in {NodeKind.VAR, NodeKind.CONST} and stmt.name:
                    # Save the outer value at the declaration, after any earlier
                    # writes in this block, rather than at block entry.
                    shadowed[stmt.name] = self.facts.symbol(stmt.name)
                    shadowed_moved[stmt.name] = stmt.name in self.moved_symbols
                    self.moved_symbols.discard(stmt.name)
                self._visit_stmt(stmt)
            self._forget_names(self.deferred_effects.pop())
            deleted = self.deferred_deletes.pop()
            self.moved_symbols.update(deleted)
            for name in list(self.facts.by_symbol):
                if name not in names_before:
                    self.facts.by_symbol.pop(name, None)
                    self.moved_symbols.discard(name)
                elif name in shadowed:
                    self.facts.set_symbol(name, shadowed[name])
                    if shadowed_moved[name] or name in deleted:
                        self.moved_symbols.add(name)
                    else:
                        self.moved_symbols.discard(name)
            self.symbol_types = saved_types
        elif node.kind in {NodeKind.VAR, NodeKind.CONST}:
            fact = self._visit_expr(node.value) if node.value else self._default_fact_for_type(self._type(node))
            if node.name:
                self._invalidate_length_relations(node.name)
                self.facts.set_symbol(node.name, fact)
                self.symbol_types[node.name] = self._type(node) or self._type(node.value)
        elif node.kind == NodeKind.ASSIGNMENT:
            rhs = self._visit_expr(node.value) if node.value else ValueFact()
            if node.target:
                target_fact = (
                    self._visit_expr(node.target)
                    if getattr(node, "implicit_deref_target", False) or node.target.kind != NodeKind.IDENTIFIER
                    else self.facts.symbol(node.target.name)
                )
                if getattr(node, "implicit_deref_target", False):
                    self._prove_ref_non_nil_for_node(
                        node,
                        target_fact,
                        self._type(node.target),
                        "reference must be proven non-nil before assignment through it",
                    )
                if node.target.kind == NodeKind.IDENTIFIER and node.target.name:
                    if node.operator != AssignOp.ASSIGN:
                        result = self._default_fact_for_type(self._type(node.target))
                        if target_fact.interval and rhs.interval:
                            operations = {AssignOp.ADD_ASSIGN: IntegerInterval.add, AssignOp.SUB_ASSIGN: IntegerInterval.sub, AssignOp.MUL_ASSIGN: IntegerInterval.mul}
                            operation = operations.get(node.operator)
                            if operation:
                                interval = operation(target_fact.interval, rhs.interval)
                                if self._range_fits(interval, self._type(node.target)):
                                    obligation = self._obligation(
                                        ObligationKind.INTEGER_OVERFLOW,
                                        node,
                                        node.operator.name.lower() + "_nonwrap",
                                        self._type(node.target),
                                        "compound assignment result must fit the target type range",
                                        None,
                                    )
                                    self._prove(obligation, "result interval fits the target type range")
                                    result = ValueFact(interval=interval, nonzero=interval.is_nonzero())
                        rhs = result
                    if not getattr(node, "implicit_deref_target", False):
                        self._invalidate_length_relations(node.target.name)
                        self.facts.set_symbol(node.target.name, rhs)
                        self.moved_symbols.discard(node.target.name)
            if node.operator in {AssignOp.DIV_ASSIGN, AssignOp.MOD_ASSIGN} and node.value:
                self._prove_nonzero_divisor(node, node.value, node.operator.name.lower())
        elif node.kind == NodeKind.EXPRESSION_STMT and node.expression:
            self._visit_expr(node.expression)
        elif node.kind == NodeKind.RETURN and node.value:
            self._visit_expr(node.value)
        elif node.kind == NodeKind.IF_STMT:
            self._visit_expr(node.condition)
            saved = self.facts.copy_symbols()
            moved = set(self.moved_symbols)
            self.facts.by_symbol.update(self._facts_from_condition(node.condition, positive=True))
            if node.then_stmt:
                self._visit_stmt(node.then_stmt)
            then_state = self.facts.copy_symbols()
            then_moved = set(self.moved_symbols)
            self.facts.restore_symbols(dict(saved))
            self.moved_symbols = set(moved)
            self.facts.by_symbol.update(self._facts_from_condition(node.condition, positive=False))
            if node.else_stmt:
                self._visit_stmt(node.else_stmt)
            if node.then_stmt and self._always_returns(node.then_stmt):
                pass  # Only the else path reaches the following statement.
            elif node.else_stmt and self._always_returns(node.else_stmt):
                self.facts.restore_symbols(then_state)
                self.moved_symbols = then_moved
            else:
                self.facts.by_symbol = self._join_facts(then_state, self.facts.by_symbol)
                self.moved_symbols.update(then_moved)
        elif node.kind in {NodeKind.WHILE, NodeKind.FOR}:
            local_name = node.init.name if node.init and node.init.kind in {NodeKind.VAR, NodeKind.CONST} else None
            outer_fact = self.facts.by_symbol.get(local_name) if local_name else None
            outer_type = self.symbol_types.get(local_name) if local_name else None
            outer_moved = local_name in self.moved_symbols if local_name else False
            if node.init:
                self._visit_stmt(node.init)
            # Invalidate before visiting the body: it represents any iteration,
            # not just the first. Learn only facts established by its guard.
            changed = self._deferred_assigned_symbols(node)
            self._forget_names(changed)
            self.moved_symbols.update(self._deleted_names(node))
            if node.condition:
                self._visit_expr(node.condition)
                self.facts.by_symbol.update(self._facts_from_condition(node.condition, positive=True))
            if node.body:
                self._visit_stmt(node.body)
            if node.update:
                self._visit_stmt(node.update)
            self._forget_names(changed)
            if local_name:
                if outer_fact is None:
                    self.facts.by_symbol.pop(local_name, None)
                else:
                    self.facts.set_symbol(local_name, outer_fact)
                if outer_type is None:
                    self.symbol_types.pop(local_name, None)
                else:
                    self.symbol_types[local_name] = outer_type
                if outer_moved:
                    self.moved_symbols.add(local_name)
                else:
                    self.moved_symbols.discard(local_name)
        elif node.kind in {NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED}:
            iterable_fact = self._visit_expr(node.iterable)
            changed = self._deferred_assigned_symbols(node)
            self._forget_names(changed)
            self.moved_symbols.update(self._deleted_names(node))
            saved = self.facts.copy_symbols()
            if node.index_var:
                length = self._object_length(node.iterable, iterable_fact)
                self.facts.set_symbol(node.index_var, ValueFact(interval=IntegerInterval(0, length - 1 if length is not None else None), nonzero=False))
            if node.iterator:
                # A fresh binding: its fact comes from the element type only,
                # never from an outer variable with the same name.
                iterable_type = self._type(node.iterable)
                element_type = iterable_type.element_type if isinstance(iterable_type, (ArrayType, SliceType)) else None
                self.facts.set_symbol(node.iterator, self._default_fact_for_type(element_type))
            if node.body:
                self._visit_stmt(node.body)
            self.facts.restore_symbols(saved)
            self._forget_names(changed)
        elif node.kind == NodeKind.MATCH:
            self._visit_expr(node.expression)
            saved = self.facts.copy_symbols()
            moved = set(self.moved_symbols)
            joined = dict(saved)  # A non-exhaustive match can execute no arm.
            all_moved = set(moved)
            branches = [case.statements or ([] if case.statement is None else [case.statement]) for case in node.cases or []]
            branches.append(node.else_case or [])
            for statements in branches:
                self.facts.restore_symbols(dict(saved))
                self.moved_symbols = set(moved)
                for stmt in statements:
                    self._visit_stmt(stmt)
                joined = self._join_facts(joined, self.facts.by_symbol)
                all_moved.update(self.moved_symbols)
            self.facts.restore_symbols(joined)
            self.moved_symbols = all_moved
        elif node.kind == NodeKind.DEFER:
            if node.statement:
                if self.deferred_effects:
                    self.deferred_effects[-1].update(self._deferred_assigned_symbols(node.statement))
                    self.deferred_deletes[-1].update(self._deleted_names(node.statement))
                saved = self.facts.copy_symbols()
                moved = set(self.moved_symbols)
                self._visit_stmt(node.statement)
                self.facts.restore_symbols(saved)
                self.moved_symbols = moved
                # Deferred writes cannot establish a fact at the defer site.
                # Loop entry already forgets effects from previous iterations.
                if node.statement.kind not in DEFER_HAVOC_EXCLUDED_KINDS:
                    self._forget_names(self._deferred_assigned_symbols(node.statement))
            elif node.expression:
                self._visit_expr(node.expression)
        elif node.kind == NodeKind.DEL and node.expression:
            self._visit_expr(node.expression)
            self._mark_deleted(node.expression)
        elif node.kind == NodeKind.FUNCTION and node.body:
            # A nested function starts from the file-scope constant facts, like
            # a top-level one, and leaves the enclosing function's state intact.
            saved = self.facts.copy_symbols()
            saved_moved = self.moved_symbols
            self.moved_symbols = set()
            self.facts.by_symbol = dict(self.const_facts)
            for param in node.parameters or []:
                if param.name:
                    self.facts.set_symbol(param.name, self._fact_from_type_node(param.param_type))
            self._visit_stmt(node.body)
            self.facts.restore_symbols(saved)
            self.moved_symbols = saved_moved

    def _visit_expr(self, node: Optional[ASTNode]) -> ValueFact:
        if node is None:
            return ValueFact()
        fact = ValueFact()
        if node.kind == NodeKind.LITERAL:
            fact = self._literal_fact(node)
        elif node.kind == NodeKind.IDENTIFIER:
            if node.name in self.moved_symbols:
                self._error_moved_symbol(node, node.name)
            fact = self.facts.symbol(node.name)
        elif node.kind == NodeKind.UNARY:
            operand = self._visit_expr(node.operand)
            fact = self._unary_fact(node, operand)
        elif node.kind == NodeKind.BINARY:
            left = self._visit_expr(node.left)
            right = self._visit_expr(node.right)
            fact = self._binary_fact(node, left, right)
            if node.operator in {BinaryOp.DIV, BinaryOp.MOD} and node.right:
                self._prove_nonzero_divisor(node, node.right, node.operator.name.lower())
            if node.operator in {BinaryOp.ADD, BinaryOp.SUB, BinaryOp.MUL}:
                self._prove_integer_overflow(node, fact)
        elif node.kind == NodeKind.CAST:
            source = self._visit_expr(node.expression)
            fact = self._cast_fact(node, source)
        elif node.kind == NodeKind.INDEX:
            obj_fact = self._visit_expr(node.object)
            idx_fact = self._visit_expr(node.index)
            self._prove_index(node, obj_fact, idx_fact)
        elif node.kind == NodeKind.SLICE:
            obj_fact = self._visit_expr(node.object)
            start_fact = self._visit_expr(node.start) if node.start else ValueFact(interval=IntegerInterval.exact(0))
            end_fact = self._visit_expr(node.end) if node.end else ValueFact(interval=IntegerInterval.exact(obj_fact.known_length), known_length=obj_fact.known_length) if obj_fact.known_length is not None else ValueFact()
            self._prove_slice(node, obj_fact, start_fact, end_fact)
            fact = self._slice_fact(node, obj_fact, start_fact, end_fact)
        elif node.kind == NodeKind.FIELD_ACCESS:
            obj = self._visit_expr(node.object)
            if getattr(node, "implicit_deref_object", False):
                self._prove_ref_non_nil_for_node(
                    node,
                    obj,
                    self._type(node.object),
                    "reference must be proven non-nil before field access through it",
                )
            if node.field == "ptr":
                fact = ValueFact(non_nil=True)
            if node.field == "len" and obj.known_length is not None:
                fact = ValueFact(interval=IntegerInterval.exact(obj.known_length), known_length=None, nonzero=obj.known_length != 0)
        elif node.kind == NodeKind.ADDRESS_OF:
            self._visit_expr(node.operand)
            fact = ValueFact(non_nil=True, maybe_nil=False)
        elif node.kind == NodeKind.DEREF:
            ptr_fact = self._visit_expr(node.pointer)
            self._prove_ref_non_nil(node, ptr_fact)
        elif node.kind == NodeKind.CALL:
            self._visit_expr(node.function)
            borrowed = getattr(node, "implicit_ref_args", set())
            function_type = self._type(node.function)
            callee_name = node.function.name if node.function and node.function.kind == NodeKind.IDENTIFIER else None
            for i, arg in enumerate(node.arguments or []):
                arg_fact = self._visit_expr(arg)
                is_ref_parameter = isinstance(function_type, FunctionType) and i < len(function_type.param_types) and isinstance(function_type.param_types[i], ReferenceType)
                if isinstance(self._type(arg), ReferenceType) and is_ref_parameter:
                    self._prove_ref_non_nil_for_node(node, arg_fact, self._type(arg), "reference argument must be proven non-nil")
                    if self.function_deletes.get(callee_name, True) and arg.kind == NodeKind.IDENTIFIER:
                        self.facts.set_symbol(arg.name, ValueFact(maybe_nil=True))
                        self.moved_symbols.add(arg.name)
                elif i in borrowed and arg.kind == NodeKind.IDENTIFIER:
                    self._invalidate_length_relations(arg.name)
                    self.facts.set_symbol(arg.name, self._default_fact_for_type(self._type(arg)))
        elif node.kind == NodeKind.ARRAY_INIT:
            for element in node.elements or []:
                self._visit_expr(element)
            fact = ValueFact(known_length=len(node.elements or []), non_nil=True)
        elif node.kind == NodeKind.NEW_EXPR:
            fact = ValueFact(maybe_nil=True)
        elif node.kind == NodeKind.STRUCT_INIT:
            for init in node.field_inits or []:
                if init.value:
                    self._visit_expr(init.value)
        elif node.kind == NodeKind.IF_EXPR:
            self._visit_expr(node.condition)
            self._visit_expr(node.then_expr)
            self._visit_expr(node.else_expr)
        elif node.kind == NodeKind.MATCH_EXPR:
            self._visit_expr(node.expression)
            for case in node.cases or []:
                expr = getattr(case, "expression", None)
                if expr:
                    self._visit_expr(expr)
            if isinstance(node.else_case, ASTNode):
                self._visit_expr(node.else_case)
        self.facts.set_node(node, fact)
        return fact

    def _default_fact_for_type(self, type_: Optional[Type]) -> ValueFact:
        if isinstance(type_, PrimitiveType) and type_.name in INTEGER_RANGES:
            lo, hi = INTEGER_RANGES[type_.name]
            return ValueFact(interval=IntegerInterval(lo, hi), nonzero=False)
        if isinstance(type_, ArrayType):
            return ValueFact(known_length=type_.size)
        return ValueFact(maybe_nil=isinstance(type_, ReferenceType))

    def _fact_from_type_node(self, node: Optional[ASTNode]) -> ValueFact:
        if node is None:
            return ValueFact()
        if node.kind == NodeKind.TYPE_POINTER:
            return ValueFact(non_nil=True)
        name = getattr(node, "type_name", None)
        if name in INTEGER_RANGES:
            return ValueFact(interval=IntegerInterval(*INTEGER_RANGES[name]))
        return ValueFact()

    def _literal_fact(self, node: ASTNode) -> ValueFact:
        if node.literal_kind == LiteralKind.INTEGER and isinstance(node.literal_value, int):
            return ValueFact(interval=IntegerInterval.exact(node.literal_value), nonzero=node.literal_value != 0)
        if node.literal_kind == LiteralKind.FLOAT and isinstance(node.literal_value, (int, float)):
            return ValueFact(nonzero=node.literal_value != 0.0)
        if node.literal_kind == LiteralKind.STRING and isinstance(node.literal_value, str):
            return ValueFact(known_length=len(node.literal_value), non_nil=True)
        if node.literal_kind == LiteralKind.NIL:
            return ValueFact(maybe_nil=True)
        return ValueFact()

    def _unary_fact(self, node: ASTNode, operand: ValueFact) -> ValueFact:
        if node.operator == UnaryOp.NEG and operand.interval and operand.interval.lower is not None and operand.interval.upper is not None:
            interval = IntegerInterval(-operand.interval.upper, -operand.interval.lower)
            return ValueFact(interval=interval, nonzero=interval.is_nonzero())
        return ValueFact()

    def _binary_fact(self, node: ASTNode, left: ValueFact, right: ValueFact) -> ValueFact:
        if not left.interval or not right.interval:
            return ValueFact()
        if node.operator == BinaryOp.ADD:
            interval = left.interval.add(right.interval)
        elif node.operator == BinaryOp.SUB:
            interval = left.interval.sub(right.interval)
        elif node.operator == BinaryOp.MUL:
            interval = left.interval.mul(right.interval)
        elif node.operator in {BinaryOp.DIV, BinaryOp.MOD} and right.interval and right.interval.is_nonzero():
            interval = IntegerInterval()
        else:
            return ValueFact()
        result_type = self._type(node)
        if isinstance(result_type, PrimitiveType) and result_type.name in INTEGER_RANGES and not self._range_fits(interval, result_type):
            return self._default_fact_for_type(result_type)
        return ValueFact(interval=interval, nonzero=interval.is_nonzero())

    def _cast_fact(self, node: ASTNode, source_fact: ValueFact) -> ValueFact:
        source_type = self._type(node.expression)
        target_type = self._type(node) or self._type_from_cast_target(node)
        decision = classify_cast(
            source_type,
            target_type,
            source_nonnegative=bool(source_fact.interval and source_fact.interval.is_nonnegative()),
        ) if source_type is not None and target_type is not None else None
        if (
            decision is not None
            and not decision.allowed
            and isinstance(source_type, PrimitiveType)
            and isinstance(target_type, PrimitiveType)
            and source_type.name in INTEGER_RANGES
            and target_type.name in INTEGER_RANGES
            and self._range_fits(source_fact.interval, target_type)
        ):
            decision = CastDecision(CastClass.PROVABLE_NARROWING, "integer value range is proven to fit target")
        obligation = self._obligation(ObligationKind.CAST, node, "cast", source_type, "cast must be classified and range-proven", TypeErrorType.UNSAFE_CAST)
        if decision is None or not decision.allowed:
            self._error(obligation, decision.reason if decision else "unknown source or target type")
        elif decision.kind is CastClass.PROVABLE_NARROWING and not self._range_fits(source_fact.interval, target_type):
            self._error(obligation, "cast target range is not proven")
        elif isinstance(source_type, PrimitiveType) and source_type.name in {"f32", "f64"} and isinstance(target_type, PrimitiveType) and target_type.name in INTEGER_RANGES and not self._float_to_int_is_proven(node.expression, target_type):
            self._error(obligation, "float-to-int cast requires finite integral range proof")
        else:
            node.cast_decision = decision
            node.cast_source_type = source_type
            node.cast_target_type = target_type
            self._prove(obligation, decision.reason)
        if isinstance(target_type, PrimitiveType) and target_type.name in INTEGER_RANGES and self._range_fits(source_fact.interval, target_type):
            return ValueFact(interval=source_fact.interval, nonzero=source_fact.nonzero)
        if decision is not None and decision.allowed and source_type == target_type:
            return source_fact
        return ValueFact()

    def _type_from_cast_target(self, node: ASTNode) -> Optional[Type]:
        return getattr(node, "cast_target_type", None)

    def _prove_nonzero_divisor(self, node: ASTNode, divisor: ASTNode, operation: str) -> None:
        fact = self.facts.node(divisor)
        obligation = self._obligation(ObligationKind.DIVISOR_NONZERO, node, operation, self._type(divisor), "division/modulo divisor must be non-zero", None)
        if fact.nonzero or (fact.interval and fact.interval.is_nonzero()):
            self._prove(obligation, "divisor is proven non-zero")
        else:
            self._error(obligation, "divisor may be zero")

    def _prove_index(self, node: ASTNode, obj: ValueFact, idx: ValueFact) -> None:
        obligation = self._obligation(ObligationKind.INDEX_IN_BOUNDS, node, "index", self._type(node.index), "index must satisfy 0 <= index < len", None)
        length = self._object_length(node.object, obj)
        interval = idx.interval
        relative_bound = (idx.upper_length_of is not None and node.object is not None
                          and node.object.kind == NodeKind.IDENTIFIER
                          and idx.upper_length_of == node.object.name
                          and interval is not None and interval.is_nonnegative())
        if relative_bound or (length is not None and interval is not None and interval.contains(0, length - 1)):
            self._prove(obligation, "index is in bounds")
        else:
            self._error(obligation, "index bounds are not proven")

    def _prove_slice(self, node: ASTNode, obj: ValueFact, start: ValueFact, end: ValueFact) -> None:
        obligation = self._obligation(ObligationKind.SLICE_IN_BOUNDS, node, "slice", self._type(node.object), "slice must satisfy 0 <= start <= end <= len", None)
        length = self._object_length(node.object, obj)
        si = start.interval
        ei = end.interval
        if (
            length is not None
            and si is not None
            and ei is not None
            and si.lower is not None
            and ei.upper is not None
            and si.lower >= 0
            and ei.upper <= length
            and si.upper is not None
            and ei.lower is not None
            and si.upper <= ei.lower
        ):
            self._prove(obligation, "slice range is in bounds")
        else:
            self._error(obligation, "slice bounds are not proven")

    def _slice_fact(self, node: ASTNode, obj: ValueFact, start: ValueFact, end: ValueFact) -> ValueFact:
        if start.interval and end.interval and start.interval.lower is not None and end.interval.upper is not None and start.interval.lower == start.interval.upper and end.interval.lower == end.interval.upper:
            return ValueFact(known_length=end.interval.upper - start.interval.lower, non_nil=True)
        return ValueFact(non_nil=True)

    def _object_length(self, node: Optional[ASTNode], fact: ValueFact) -> Optional[int]:
        type_ = self._type(node)
        if isinstance(type_, ArrayType):
            return type_.size
        if fact.known_length is not None:
            return fact.known_length
        return None

    def _prove_ref_non_nil(self, node: ASTNode, fact: ValueFact) -> None:
        self._prove_ref_non_nil_for_node(
            node,
            fact,
            self._type(node.pointer),
            "reference must be proven non-nil before dereference",
        )

    def _prove_ref_non_nil_for_node(
        self,
        node: ASTNode,
        fact: ValueFact,
        operand_type: Optional[Type],
        required: str,
    ) -> None:
        obligation = self._obligation(ObligationKind.REF_NON_NIL, node, "deref", operand_type, required, TypeErrorType.CANNOT_DEREFERENCE)
        if fact.non_nil:
            self._prove(obligation, "reference is non-nil")
        else:
            self._error(obligation, "reference may be nil")

    def _prove_integer_overflow(self, node: ASTNode, fact: ValueFact) -> None:
        # Wrapping stays the default lowering. When both operand intervals are
        # known and the raw result fits the result type, approve a non-wrapping
        # lowering for the release backend. `fact` cannot be used here:
        # _binary_fact clamps overflowing results to the full type range, so
        # the raw interval is recomputed from the operand node facts.
        result_type = self._type(node)
        if not isinstance(result_type, PrimitiveType) or result_type.name not in INTEGER_RANGES:
            return
        if node.left is None or node.right is None:
            return
        left = self.facts.node(node.left)
        right = self.facts.node(node.right)
        if not left.interval or not right.interval:
            return
        operations = {
            BinaryOp.ADD: IntegerInterval.add,
            BinaryOp.SUB: IntegerInterval.sub,
            BinaryOp.MUL: IntegerInterval.mul,
        }
        operation = operations.get(node.operator)
        if operation is None:
            return
        interval = operation(left.interval, right.interval)
        obligation = self._obligation(
            ObligationKind.INTEGER_OVERFLOW,
            node,
            node.operator.name.lower() + "_nonwrap",
            result_type,
            "arithmetic result must fit the result type range",
            None,
        )
        if self._range_fits(interval, result_type):
            self._prove(obligation, "result interval fits the result type range")

    def _range_fits(self, interval: Optional[IntegerInterval], target_type: Optional[Type]) -> bool:
        if not isinstance(target_type, PrimitiveType) or target_type.name not in INTEGER_RANGES or interval is None:
            return False
        low, high = INTEGER_RANGES[target_type.name]
        return interval.contains(low, high)

    def _float_to_int_is_proven(self, node: Optional[ASTNode], target_type: Type) -> bool:
        if node is None or node.kind != NodeKind.LITERAL or node.literal_kind != LiteralKind.FLOAT:
            return False
        value = node.literal_value
        if not isinstance(value, (int, float)) or not math.isfinite(value) or int(value) != value:
            return False
        low, high = INTEGER_RANGES[getattr(target_type, "name", "")]
        return low <= int(value) <= high

    def _always_returns(self, node: ASTNode) -> bool:
        if node.kind == NodeKind.RETURN:
            return True
        if node.kind == NodeKind.BLOCK:
            statements = node.statements or []
            return bool(statements) and self._always_returns(statements[-1])
        return False

    def _facts_from_condition(self, condition: Optional[ASTNode], *, positive: bool) -> dict[str, ValueFact]:
        if condition is None or condition.kind != NodeKind.BINARY:
            return {}
        name = condition.left.name if condition.left and condition.left.kind == NodeKind.IDENTIFIER else None
        if not name:
            return {}
        literal = self._int_literal(condition.right)
        current = self.facts.symbol(name)
        interval = current.interval
        facts: dict[str, ValueFact] = {}
        rhs = self.facts.node(condition.right).interval
        if literal is not None:
            rhs = IntegerInterval.exact(literal)
        op = condition.operator
        if not positive:
            op = {BinaryOp.GE: BinaryOp.LT, BinaryOp.GT: BinaryOp.LE, BinaryOp.LE: BinaryOp.GT, BinaryOp.LT: BinaryOp.GE, BinaryOp.EQ: BinaryOp.NE, BinaryOp.NE: BinaryOp.EQ}.get(op, op)
        if rhs:
            lo, hi = (interval.lower, interval.upper) if interval else (None, None)
            if op in {BinaryOp.GE, BinaryOp.GT, BinaryOp.EQ} and rhs.lower is not None:
                lower = rhs.lower + (1 if op == BinaryOp.GT else 0)
                lo = max(lo, lower) if lo is not None else lower
            if op in {BinaryOp.LE, BinaryOp.LT, BinaryOp.EQ} and rhs.upper is not None:
                upper = rhs.upper - (1 if op == BinaryOp.LT else 0)
                hi = min(hi, upper) if hi is not None else upper
            narrowed = IntegerInterval(lo, hi)
            facts[name] = replace(current, interval=narrowed, nonzero=current.nonzero or narrowed.is_nonzero())
        if (op == BinaryOp.LT and condition.right and condition.right.kind == NodeKind.FIELD_ACCESS
                and condition.right.field == "len" and condition.right.object
                and condition.right.object.kind == NodeKind.IDENTIFIER
                and isinstance(self._type(condition.right.object), (ArrayType, SliceType))):
            facts[name] = replace(facts.get(name, current), upper_length_of=condition.right.object.name)
        if self._zero_literal(condition.right):
            if (positive and condition.operator == BinaryOp.NE) or (not positive and condition.operator == BinaryOp.EQ):
                facts[name] = ValueFact(interval=interval, nonzero=True, non_nil=current.non_nil, maybe_nil=current.maybe_nil)
        if condition.right and condition.right.kind == NodeKind.LITERAL and condition.right.literal_kind == LiteralKind.NIL:
            if positive and condition.operator == BinaryOp.NE:
                facts[name] = ValueFact(interval=interval, non_nil=True)
            elif not positive and condition.operator == BinaryOp.EQ:
                facts[name] = ValueFact(interval=interval, non_nil=True)
        return facts

    def _zero_literal(self, node: Optional[ASTNode]) -> bool:
        if node is None or node.kind != NodeKind.LITERAL:
            return False
        if node.literal_kind == LiteralKind.INTEGER:
            return node.literal_value == 0
        if node.literal_kind == LiteralKind.FLOAT:
            return node.literal_value == 0.0
        return False

    def _int_literal(self, node: Optional[ASTNode]) -> Optional[int]:
        sign = 1
        while node is not None and node.kind == NodeKind.UNARY and node.operator == UnaryOp.NEG:
            sign = -sign
            node = node.operand
        if node is not None and node.kind == NodeKind.LITERAL and node.literal_kind == LiteralKind.INTEGER and isinstance(node.literal_value, int):
            return -node.literal_value if sign < 0 else node.literal_value
        return None

    def _mark_deleted(self, node: ASTNode) -> None:
        if node.kind == NodeKind.IDENTIFIER and node.name:
            self.moved_symbols.add(node.name)

    def _error_moved_symbol(self, node: ASTNode, name: str) -> None:
        obligation = self._obligation(
            ObligationKind.MOVE_VALID,
            node,
            "move",
            self._type(node),
            "moved/deleted values cannot be read",
            TypeErrorType.USE_AFTER_MOVE,
        )
        self._error(obligation, f"'{name}' was moved or deleted earlier")
