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
    INTEGER_RANGES,
    PrimitiveType,
    ReferenceType,
    SIGNED_INTEGER_WIDTHS,
    SliceType,
    Type,
    TypeKind,
    UnionType,
    UNSIGNED_INTEGER_WIDTHS,
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


# Aliases onto the canonical a7.types.INTEGER_RANGES table. Values flow from
# the single source; the old names stay so the many uses below are untouched.
SIGNED_RANGES = {name: INTEGER_RANGES[name] for name in SIGNED_INTEGER_WIDTHS}
UNSIGNED_RANGES = {name: INTEGER_RANGES[name] for name in UNSIGNED_INTEGER_WIDTHS}

# Aggregate elements without a tracked field path retain the older conservative
# loop invalidation of their base. Field paths invalidate only that field.
DEL_TARGET_BASE_ATTRS = {
    NodeKind.FIELD_ACCESS: "object",
    NodeKind.INDEX: "object",
    NodeKind.SLICE: "object",
    NodeKind.DEREF: "pointer",
}

EXIT_KINDS = {NodeKind.RETURN, NodeKind.BREAK, NodeKind.CONTINUE}
LOOP_KINDS = {NodeKind.WHILE, NodeKind.FOR, NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED}

# Headline message for each safety obligation kind. Kinds not listed use the
# message of their diagnostic code. Division, index and slice obligations carry
# no diagnostic code: no existing TypeErrorType describes them. Their hint
# comes from the `_error` call site, which knows the operand.
OBLIGATION_MESSAGES = {
    "DIVISOR_NONZERO": "Divisor not proven non-zero",
    "INDEX_IN_BOUNDS": "Index not proven in bounds",
    "SLICE_IN_BOUNDS": "Slice bounds not proven",
    "REF_NON_NIL": "Reference not proven non-nil",
}


class SafetyError(TypeCheckError):
    """A safety obligation the proof pass could not discharge.

    `hint` names the guard shape the pass accepts for this obligation and
    takes the place of the advice text of the diagnostic code.
    """

    hint: Optional[str] = None


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
    allocations: frozenset[str] = frozenset()
    # Possible children of a selected holder constrain reads, but deleting a
    # selected child must not mark every possible concrete child as freed.
    selected_allocations: frozenset[str] = frozenset()


@dataclass
class FactMap:
    """Facts per expression node, variable and reference field path.

    `by_symbol` is keyed by declaration key (see `SafetyProofPass._bind_names`),
    so two variables with the same name never share a fact.
    """

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


class ExitFrame:
    """One block or loop between a statement and its function.

    A block frame holds the block's pending `defer` statements. A loop frame
    carries the loop node, and the states at each `continue` when the loop has
    an update statement to prove against them.
    """

    __slots__ = ("loop", "defers", "continues")

    def __init__(self, loop: Optional[ASTNode] = None):
        self.loop = loop
        self.defers: list[ASTNode] = []
        self.continues: list[tuple[dict[str, ValueFact], set[str]]] = []


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
        self.exact_effect_bodies: dict[str, ASTNode] = {}
        self.exact_effect_reasons: dict[str, set[str]] = {}
        self.function_deletes: dict[str, bool] = {}
        self.function_field_writes: dict[str, dict[int, set[str]]] = {}
        self.function_deleted_globals: dict[str, set[str]] = {}
        self.symbol_types: dict[str, Type] = {}
        self.file_variables: set[str] = set()
        self._reset_bindings()

    def _reset_bindings(self) -> None:
        # (id(node), name) -> declaration key, for identifiers and declarations.
        self.keys: dict[tuple[int, str], str] = {}
        # id(scope owner node) -> keys declared in that scope.
        self.scope_keys: dict[int, list[str]] = {}
        # `defer` nodes that are direct statements of a block.
        self.block_defers: set[int] = set()
        self.frames: list[ExitFrame] = []
        # Frames below this index belong to the scope whose defers are running.
        self.defer_floor = 0
        # Keys that some fact names in `upper_length_of`. Grows only.
        self.length_targets: set[str] = set()
        # (node id, operation) pairs already reported or refused. A deferred
        # statement is proven once per scope exit.
        self.reported: set[tuple[int, str]] = set()
        self.refused_nonwrap: set[tuple[int, str]] = set()

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
        self._reset_bindings()
        self._bind_names(program)
        self._visit_program(program)
        return self.backend_plan

    def _type(self, node: Optional[ASTNode]) -> Optional[Type]:
        return self.node_types.get(id(node)) if node is not None else None

    def _error(self, obligation: Obligation, reason: str, hint: Optional[str] = None) -> None:
        self.results.append(ProofResult(False, obligation, reason))
        key = (obligation.node_id, obligation.backend_operation)
        if key in self.reported:
            return
        self.reported.add(key)
        context = f"{obligation.required_proof}: {reason}"
        headline = OBLIGATION_MESSAGES.get(obligation.kind.name)
        if obligation.diagnostic_code is not None:
            error = SafetyError.from_type(
                obligation.diagnostic_code,
                span=obligation.span,
                filename=self.current_file,
                source_lines=self.source_lines,
                custom_message=headline,
                context=context,
            )
        else:
            error = SafetyError(
                f"{headline} ({context})",
                span=obligation.span,
                filename=self.current_file,
                source_lines=self.source_lines,
            )
        error.hint = hint
        self.errors.append(error)

    @staticmethod
    def _guard_subject(operand: Optional[ASTNode], placeholder: str, *, fields: bool = False) -> tuple[str, str]:
        """A guard can refine a binding or a field path rooted in a binding."""
        names = []
        while fields and operand is not None and operand.kind == NodeKind.FIELD_ACCESS:
            names.append(operand.field)
            operand = operand.object
        if operand is not None and operand.kind == NodeKind.IDENTIFIER and operand.name:
            return ".".join([operand.name, *reversed(names)]), ""
        return placeholder, f"Copy the value to a local '{placeholder}' first; proofs track local variables only. "

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

    def _key(self, node: ASTNode, name: Optional[str] = None) -> str:
        """Declaration key of an identifier or declaration. A file-scope name is its own key."""
        name = node.name if name is None else name
        return self.keys.get((id(node), name), name)

    def _bind_names(self, program: ASTNode) -> None:
        """Give each local declaration its own key and resolve identifiers to it.

        A parameter, local, loop variable, match capture or nested function
        gets the key `name#n`. An identifier resolves to the innermost such
        declaration in scope where it is written, and keeps its bare name when
        only a file-scope declaration matches. Scopes follow
        `NameResolutionPass`. An initializer is resolved before its name is
        bound, so `x := x + 1` reads the outer `x`.
        """
        bound: dict[str, list[str]] = {}
        open_scopes: list[tuple[int, list[str]]] = []
        count = 0
        work: list[tuple[str, object]] = [("visit", decl) for decl in reversed(program.declarations or [])]
        while work:
            action, item = work.pop()
            if action == "open":
                open_scopes.append((id(item), []))
                continue
            if action == "close":
                for name in open_scopes.pop()[1]:
                    bound[name].pop()
                continue
            if action == "declare":
                node, name = item
                count += 1
                key = f"{name}#{count}"
                owner, names = open_scopes[-1]
                names.append(name)
                bound.setdefault(name, []).append(key)
                self.keys[(id(node), name)] = key
                self.scope_keys.setdefault(owner, []).append(key)
                continue
            node = item
            kind = node.kind
            if kind == NodeKind.IDENTIFIER:
                if bound.get(node.name):
                    self.keys[(id(node), node.name)] = bound[node.name][-1]
                continue
            children = []
            for value in vars(node).values():
                if isinstance(value, ASTNode):
                    children.append(("visit", value))
                elif isinstance(value, list):
                    children.extend(("visit", child) for child in value if isinstance(child, ASTNode))
            steps: list[tuple[str, object]]
            if kind == NodeKind.FUNCTION:
                steps = [("declare", (node, node.name))] if open_scopes and node.name and (id(node), node.name) not in self.keys else []
                steps.append(("open", node))
                steps.extend(("declare", (param, param.name)) for param in node.parameters or [] if param.name)
                if node.body:
                    steps.append(("visit", node.body))
                steps.append(("close", None))
            elif kind == NodeKind.BLOCK:
                statements = node.statements or []
                self.block_defers.update(id(stmt) for stmt in statements if stmt.kind == NodeKind.DEFER)
                steps = [("open", node)]
                steps.extend(("declare", (stmt, stmt.name)) for stmt in statements if stmt.kind == NodeKind.FUNCTION and stmt.name)
                steps.extend(("visit", stmt) for stmt in statements)
                steps.append(("close", None))
            elif kind in {NodeKind.VAR, NodeKind.CONST}:
                steps = children
                if open_scopes and node.name:
                    steps.append(("declare", (node, node.name)))
            elif kind in {NodeKind.IF_STMT, NodeKind.WHILE}:
                steps = [("visit", node.condition)] if node.condition else []
                for branch in (node.then_stmt, node.else_stmt, node.body):
                    if branch is None:
                        continue
                    if branch.kind == NodeKind.BLOCK:
                        steps.append(("visit", branch))
                    else:
                        steps.extend([("open", branch), ("visit", branch), ("close", None)])
            elif kind == NodeKind.FOR:
                steps = [("open", node)]
                steps.extend(("visit", part) for part in (node.init, node.condition, node.update, node.body) if part)
                steps.append(("close", None))
            elif kind in {NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED}:
                steps = [("visit", node.iterable)] if node.iterable else []
                steps.append(("open", node))
                steps.extend(("declare", (node, name)) for name in (node.index_var, node.iterator) if name)
                if node.body:
                    steps.append(("visit", node.body))
                steps.append(("close", None))
            elif kind in {NodeKind.MATCH, NodeKind.MATCH_EXPR}:
                steps = [("visit", node.expression)] if node.expression else []
                for case in node.cases or []:
                    steps.append(("open", case))
                    for pattern in case.patterns or []:
                        captures = pattern.kind == NodeKind.PATTERN_ENUM or (
                            pattern.kind == NodeKind.PATTERN_IDENTIFIER and pattern.is_capture_pattern
                        )
                        if captures and pattern.name:
                            steps.append(("declare", (pattern, pattern.name)))
                        else:
                            steps.append(("visit", pattern))
                    body = [case.statement, case.expression, *(case.statements or [])]
                    steps.extend(("visit", part) for part in body if part)
                    steps.append(("close", None))
                if isinstance(node.else_case, ASTNode):
                    steps.append(("visit", node.else_case))
                elif node.else_case:
                    steps = [*steps, ("open", node), *(("visit", stmt) for stmt in node.else_case), ("close", None)]
            else:
                steps = children
            work.extend(reversed(steps))

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
        # Function keys include nested declarations and lexical shadowing.
        self.file_variables = {d.name for d in node.declarations or [] if d.kind == NodeKind.VAR and d.name}
        bodies = {}
        declarations = list(node.declarations or [])
        while declarations:
            declaration = declarations.pop()
            if declaration.kind == NodeKind.FUNCTION:
                bodies[self._key(declaration)] = declaration
            for value in vars(declaration).values():
                if isinstance(value, ASTNode):
                    declarations.append(value)
                elif isinstance(value, list):
                    declarations.extend(item for item in value if isinstance(item, ASTNode))
        self.function_field_writes = {name: {} for name in bodies}
        calls: dict[str, set[str]] = {}
        for name, decl in bodies.items():
            deletes = False
            deleted_globals: set[str] = set()
            callees: set[str] = set()
            stack = [decl.body] if decl.body else []
            while stack:
                item = stack.pop()
                if item.kind == NodeKind.FUNCTION:
                    continue
                deletes |= item.kind == NodeKind.DEL
                if item.kind == NodeKind.DEL:
                    deleted_key = self._place_key(item.expression)
                    if deleted_key and deleted_key.split(".")[0] in self.file_variables:
                        deleted_globals.add(deleted_key)
                if item.kind == NodeKind.CALL and item.function:
                    callee = item.function
                    if getattr(item, "stdlib_canonical", None):
                        pass
                    elif callee.kind == NodeKind.IDENTIFIER:
                        callees.add(self._key(callee))
                    else:
                        deletes = True
                for value in vars(item).values():
                    if isinstance(value, ASTNode):
                        stack.append(value)
                    elif isinstance(value, list):
                        stack.extend(v for v in value if isinstance(v, ASTNode))
            self.function_deleted_globals[name] = deleted_globals
            self.function_deletes[name] = deletes
            calls[name] = callees
        changed = True
        while changed:
            changed = False
            for name, callees in calls.items():
                writes = self._field_write_summary(bodies[name])
                if writes != self.function_field_writes[name]:
                    self.function_field_writes[name] = writes
                    changed = True
                inherited = set().union(*(self.function_deleted_globals.get(c, set()) for c in callees))
                if not inherited.issubset(self.function_deleted_globals[name]):
                    self.function_deleted_globals[name].update(inherited)
                    changed = True
                if not self.function_deletes[name] and any(self.function_deletes.get(c, True) for c in callees):
                    self.function_deletes[name] = True
                    changed = True
        self._classify_exact_effects(bodies)
        for decl in node.declarations or []:
            self._visit_decl(decl)

    def _classify_exact_effects(self, bodies: dict[str, ASTNode]) -> None:
        # Completeness covers the whole body, including every nested known call.
        self.exact_effect_bodies = bodies
        self.exact_effect_reasons = {}
        dependencies = {}
        branch_counts = {}
        own_work = {}
        supported = {NodeKind.BLOCK, NodeKind.VAR, NodeKind.CONST,
                     NodeKind.ASSIGNMENT, NodeKind.EXPRESSION_STMT, NodeKind.RETURN,
                     NodeKind.IF_STMT, NodeKind.DEFER, NodeKind.DEL,
                     NodeKind.IDENTIFIER, NodeKind.LITERAL, NodeKind.FIELD_ACCESS,
                     NodeKind.BINARY, NodeKind.UNARY, NodeKind.CAST, NodeKind.CALL}
        for name, function in bodies.items():
            reasons = set()
            callees = []
            branches = 0
            work_nodes = 0
            for param in function.parameters or []:
                if not isinstance(self._type(param), (ReferenceType, PrimitiveType)) and (param.param_type is None or param.param_type.kind not in {NodeKind.TYPE_POINTER, NodeKind.TYPE_PRIMITIVE}):
                    reasons.add("by-value aggregate parameter")
            pending = [function.body]
            while pending:
                node = pending.pop()
                if node is None:
                    continue
                if node.kind.name.startswith("TYPE_"):
                    continue
                work_nodes += 1
                if node.kind not in supported:
                    reasons.add(node.kind.name.lower())
                    continue
                branches += node.kind == NodeKind.IF_STMT
                if isinstance(self._type(node), ReferenceType) and node.kind not in {NodeKind.IDENTIFIER, NodeKind.FIELD_ACCESS, NodeKind.LITERAL, NodeKind.VAR, NodeKind.CONST, NodeKind.ASSIGNMENT}:
                    reasons.add("unrepresented reference expression")
                if node.kind == NodeKind.BINARY and node.operator in {BinaryOp.AND, BinaryOp.OR}:
                    reasons.add("short-circuit expression")
                if node.kind == NodeKind.IDENTIFIER and self._key(node) in self.file_variables:
                    reasons.add("global storage")
                if node.kind == NodeKind.RETURN and isinstance(self._type(node.value), ReferenceType):
                    reasons.add("returned reference")
                if node.kind in {NodeKind.VAR, NodeKind.CONST, NodeKind.ASSIGNMENT} and node.value is not None and not isinstance(self._type(node.value), (ReferenceType, PrimitiveType)) and not (node.value.kind == NodeKind.LITERAL and node.value.literal_kind == LiteralKind.NIL):
                    reasons.add("aggregate value copy")
                if node.kind == NodeKind.ASSIGNMENT and getattr(node, "implicit_deref_target", False):
                    reasons.add("scalar borrow write")
                if node.kind == NodeKind.CALL:
                    canonical = getattr(node, "stdlib_canonical", None)
                    if canonical and canonical not in {"std.io.print", "std.io.println"}:
                        reasons.add("unrepresented stdlib effects")
                    if not canonical:
                        target = self._key(node.function) if node.function and node.function.kind == NodeKind.IDENTIFIER else None
                        if target not in bodies:
                            reasons.add("unknown callee")
                        else:
                            callees.append(target)
                    pending.extend(node.arguments or [])
                    continue
                for value in vars(node).values():
                    if isinstance(value, ASTNode):
                        pending.append(value)
                    elif isinstance(value, list):
                        pending.extend(item for item in value if isinstance(item, ASTNode))
            self.exact_effect_reasons[name] = reasons
            dependencies[name] = callees
            branch_counts[name] = min(branches, 2)
            own_work[name] = work_nodes
        work_budget = max(1, sum(own_work.values()))
        expanded_work = dict(own_work)
        changed = True
        while changed:
            changed = False
            for name, callees in dependencies.items():
                count = own_work[name]
                for callee in callees:
                    count += expanded_work[callee]
                    if count > work_budget:
                        count = work_budget + 1
                        break
                if count != expanded_work[name]:
                    expanded_work[name] = count
                    changed = True
        self.exact_effect_work_budget = work_budget
        self.exact_effect_work = expanded_work
        for name, count in expanded_work.items():
            if count > work_budget:
                self.exact_effect_reasons[name].add("transitive effect expansion exceeds source-sized work budget")
        own_branches = dict(branch_counts)
        changed = True
        while changed:
            changed = False
            for name, callees in dependencies.items():
                count = min(2, own_branches[name] + sum(branch_counts[c] for c in callees))
                if count != branch_counts[name]:
                    branch_counts[name] = count
                    changed = True
        self.exact_effect_branch_counts = branch_counts
        for name, count in branch_counts.items():
            if count > 1:
                self.exact_effect_reasons[name].add("more than one transitive conditional occurrence")
        changed = True
        while changed:
            changed = False
            for name, callees in dependencies.items():
                if not self.exact_effect_reasons[name] and any(self.exact_effect_reasons[c] for c in callees):
                    self.exact_effect_reasons[name].add("incomplete known callee")
                    changed = True

    def _exact_call_name(self, call: ASTNode, captured: Optional[list[tuple[ValueFact, Optional[str]]]] = None) -> Optional[str]:
        callee = call.function
        name = self._key(callee) if callee and callee.kind == NodeKind.IDENTIFIER else None
        if name not in self.exact_effect_reasons or self.exact_effect_reasons[name]:
            return None
        for index, arg in enumerate(call.arguments or []):
            key = captured[index][1] if captured and captured[index][1] is not None else self._place_key(arg)
            fact = captured[index][0] if captured else self.facts.symbol(key)
            prefixes = [key + "."] if key else []
            prefixes.extend(f"@allocation:{identity}." for identity in fact.allocations)
            if any(len(fact.allocations) > 1 and any(place.startswith(prefix) for prefix in prefixes)
                   for place, fact in self.facts.by_symbol.items()):
                return None
            if index not in getattr(call, "implicit_ref_args", set()) and isinstance(self._type(arg), ReferenceType):
                if arg.kind not in {NodeKind.IDENTIFIER, NodeKind.FIELD_ACCESS} or len(fact.allocations) != 1:
                    return None
        return name

    def _apply_legacy_reference_effects(self, node: ASTNode, index: int, arg: ASTNode, fact: ValueFact) -> None:
        key = self._place_key(arg)
        callee = node.function
        writes = self.function_field_writes.get(self._key(callee)) if callee and callee.kind == NodeKind.IDENTIFIER else None
        if key and not getattr(node, "stdlib_canonical", None):
            prefixes = [key]
            prefixes.extend(f"@allocation:{identity}" for identity in fact.allocations)
            for path in (writes.get(index, set()) if writes is not None else {""}):
                for prefix in prefixes:
                    target = prefix + ("." + path if path else "")
                    self._forget_names({name for name in self.facts.by_symbol
                                        if (path and name == target) or name.startswith(target + ".")})
        function_type = self._type(node.function)
        reference_parameter = isinstance(function_type, FunctionType) and index < len(function_type.param_types) and isinstance(function_type.param_types[index], ReferenceType)
        if isinstance(self._type(arg), ReferenceType) and reference_parameter and self._calls_deleting_function(node):
            self.moved_symbols.update(f"@allocation:{identity}" for identity in fact.allocations)
            if key and self.facts.symbol(key).allocations == fact.allocations:
                self.moved_symbols.add(key)

    def _replay_exact_effects(self, call: ASTNode, name: str, arguments: list[tuple[ValueFact, Optional[str]]]) -> None:
        # Actions capture values separately from storage. Each branch owns its
        # state; deletion never becomes a write to the parameter's caller slot.
        initial = ([("enter", self.exact_effect_bodies[name], arguments)],
                   dict(self.facts.by_symbol), set(self.moved_symbols), {}, {}, [], [])
        paths = [initial]
        exits = []
        serial = 0
        while paths:
            work, storage, moved, values, places, bindings, scopes = paths.pop()
            while work:
                action, node, extra = work.pop()
                if action == "enter":
                    serial += 1
                    mapping = {}
                    for index, param in enumerate(node.parameters or []):
                        fact, place = extra[index]
                        key = f"effect:{serial}:{self._key(param)}"
                        mapping[self._key(param)] = key
                        storage[key] = fact
                        if place is not None and not fact.allocations:
                            # An implicit aggregate borrow is a storage alias.
                            storage[key] = replace(fact, non_nil=True, allocations=frozenset({f"storage:{place}"}))
                    bindings.append(mapping)
                    scopes.append([])
                    work.extend([("leave", node, None), ("stmt", node.body, None)])
                    continue
                if action == "leave":
                    bindings.pop()
                    scopes.pop()
                    continue
                if action == "scope_end":
                    deferred = scopes.pop()
                    work.extend(("stmt", item, None) for item in deferred)
                    continue
                if action == "return":
                    deferred = []
                    while work and work[-1][0] != "leave":
                        popped, _, _ = work.pop()
                        if popped == "scope_end":
                            deferred.extend(reversed(scopes.pop()))
                    deferred.extend(reversed(scopes[-1]))
                    scopes[-1] = []
                    work.extend(("stmt", item, None) for item in reversed(deferred))
                    continue
                if action == "stmt":
                    if node is None:
                        continue
                    kind = node.kind
                    if kind == NodeKind.BLOCK:
                        scopes.append([])
                        work.append(("scope_end", node, None))
                        work.extend(("stmt", item, None) for item in reversed(node.statements or []))
                    elif kind == NodeKind.DEFER:
                        scopes[-1].append(node.statement)
                    elif kind == NodeKind.RETURN:
                        work.append(("return", node, None))
                        if node.value:
                            work.append(("expr", node.value, None))
                    elif kind == NodeKind.IF_STMT:
                        work.extend([("branch", node, None), ("expr", node.condition, None)])
                    elif kind in {NodeKind.VAR, NodeKind.CONST}:
                        key = f"effect:{serial}:{self._key(node)}"
                        bindings[-1][self._key(node)] = key
                        work.extend([("store", node, key), ("expr", node.value, None)])
                    elif kind == NodeKind.ASSIGNMENT:
                        work.append(("store", node, None))
                        # Assignment evaluates its RHS before its target base.
                        if node.target.kind == NodeKind.FIELD_ACCESS:
                            work.append(("target", node.target, None))
                        work.append(("expr", node.value, None))
                    elif kind == NodeKind.DEL:
                        work.extend([("delete", node, None), ("expr", node.expression, None)])
                    elif kind == NodeKind.EXPRESSION_STMT:
                        work.append(("expr", node.expression, None))
                    continue
                if action == "branch":
                    condition = node.condition
                    refinement = None
                    if condition.kind == NodeKind.BINARY and condition.operator in {BinaryOp.EQ, BinaryOp.NE}:
                        left, right = condition.left, condition.right
                        if right and right.kind == NodeKind.LITERAL and right.literal_kind == LiteralKind.NIL:
                            refinement = (places.get(id(left)), condition.operator == BinaryOp.NE)
                        elif left and left.kind == NodeKind.LITERAL and left.literal_kind == LiteralKind.NIL:
                            refinement = (places.get(id(right)), condition.operator == BinaryOp.NE)
                    for positive, body in [(False, node.else_stmt), (True, node.then_stmt)]:
                        branch_storage = dict(storage)
                        if refinement and refinement[0]:
                            key, non_nil_when_true = refinement
                            fact = branch_storage.get(key, ValueFact())
                            non_nil = positive == non_nil_when_true
                            if not non_nil and fact.non_nil:
                                continue
                            branch_storage[key] = replace(fact, non_nil=non_nil, maybe_nil=not non_nil)
                        paths.append((work + [("stmt", body, None)], branch_storage, set(moved),
                                      dict(values), dict(places), [dict(b) for b in bindings],
                                      [list(s) for s in scopes]))
                    break
                if action == "target":
                    work.extend([("field", node, True), ("expr", node.object, None)])
                    continue
                if action == "store":
                    target = node.target if node.kind == NodeKind.ASSIGNMENT else None
                    key = extra or (places.get(id(target)) if target.kind == NodeKind.FIELD_ACCESS else
                                    bindings[-1].get(self._key(target), self._key(target)))
                    fact = values.get(id(node.value), ValueFact())
                    storage[key] = fact if isinstance(self._type(node.value), ReferenceType) or fact.maybe_nil else ValueFact()
                    moved.discard(key)
                    continue
                if action == "delete":
                    fact = values.get(id(node.expression), ValueFact())
                    moved.update(f"@allocation:{identity}" for identity in fact.allocations)
                    key = places.get(id(node.expression))
                    if key:
                        moved.add(key)
                    continue
                if action == "expr":
                    if node is None:
                        continue
                    if node.kind == NodeKind.IDENTIFIER:
                        key = bindings[-1].get(self._key(node), self._key(node))
                        places[id(node)] = key
                        fact = storage.get(key, ValueFact())
                        values[id(node)] = fact
                        if key in moved or any(f"@allocation:{a}" in moved for a in fact.allocations | fact.selected_allocations):
                            obligation = self._obligation(ObligationKind.MOVE_VALID, node, f"callee_live:{id(call)}", self._type(node), "callee value must still be live", TypeErrorType.USE_AFTER_MOVE)
                            self._error(obligation, f"'{node.name}' was moved or deleted earlier")
                    elif node.kind == NodeKind.LITERAL:
                        values[id(node)] = self._literal_fact(node)
                    elif node.kind == NodeKind.FIELD_ACCESS:
                        work.extend([("field", node, False), ("expr", node.object, None)])
                    elif node.kind == NodeKind.CALL:
                        work.append(("invoke", node, None))
                        work.extend(("expr", arg, None) for arg in reversed(node.arguments or []))
                    else:
                        values[id(node)] = ValueFact()
                        children = [value for value in vars(node).values() if isinstance(value, ASTNode) and not value.kind.name.startswith("TYPE_")]
                        work.extend(("expr", child, None) for child in reversed(children))
                    continue
                if action == "field":
                    base = values.get(id(node.object), ValueFact())
                    root = places.get(id(node.object))
                    if isinstance(self._type(node.object), ReferenceType):
                        if not base.non_nil:
                            obligation = self._obligation(ObligationKind.REF_NON_NIL, node, f"callee_non_nil:{id(call)}", self._type(node.object), "callee field access must remain non-nil", TypeErrorType.CANNOT_DEREFERENCE)
                            self._error(obligation, "reference may be nil after caller aliases are substituted")
                        if len(base.allocations) == 1:
                            identity = next(iter(base.allocations))
                            root = identity.removeprefix("storage:") if identity.startswith("storage:") else f"@allocation:{identity}"
                    key = (root or "") + "." + node.field
                    places[id(node)] = key
                    if not extra:
                        fact = storage.get(key)
                        if fact is None:
                            fact = ValueFact(maybe_nil=True, allocations=frozenset({f"field:{key}"})) if isinstance(self._type(node), ReferenceType) else ValueFact()
                            storage[key] = fact
                        values[id(node)] = fact
                        if key in moved or any(f"@allocation:{a}" in moved for a in fact.allocations | fact.selected_allocations):
                            obligation = self._obligation(ObligationKind.MOVE_VALID, node, f"callee_live:{id(call)}", self._type(node), "callee field value must still be live", TypeErrorType.USE_AFTER_MOVE)
                            self._error(obligation, f"'{node.field}' was moved or deleted earlier")
                    continue
                if action == "invoke":
                    values[id(node)] = ValueFact()
                    if not getattr(node, "stdlib_canonical", None):
                        callee = self.exact_effect_bodies[self._key(node.function)]
                        args = []
                        borrowed = getattr(node, "implicit_ref_args", set())
                        for index, arg in enumerate(node.arguments or []):
                            fact = values.get(id(arg), ValueFact())
                            if isinstance(self._type(arg), ReferenceType) and index not in borrowed and not fact.non_nil:
                                obligation = self._obligation(ObligationKind.REF_NON_NIL, arg, f"callee_argument:{id(call)}", self._type(arg), "callee reference argument must remain non-nil", TypeErrorType.CANNOT_DEREFERENCE)
                                self._error(obligation, "reference may be nil after caller aliases are substituted")
                            args.append((fact, places.get(id(arg)) if index in borrowed else None))
                        work.append(("enter", callee, args))
                    continue
            else:
                exits.append((storage, moved))
        if exits:
            joined, dead = exits[0]
            for storage, moved in exits[1:]:
                joined = self._join_facts(joined, storage)
                dead |= moved
            self.facts.by_symbol = {key: fact for key, fact in joined.items() if not key.startswith("effect:")}
            self.moved_symbols = {key for key in dead if not key.startswith("effect:")}

    def _parameter_origins(self, node: Optional[ASTNode], aliases: dict[str, frozenset[tuple[int, bool]]]) -> frozenset[tuple[int, bool]]:
        origins: set[tuple[int, bool]] = set()
        pending = [(node, True)]
        while pending:
            current, exact = pending.pop()
            if current is None:
                continue
            if current.kind == NodeKind.IDENTIFIER:
                origins.update((index, exact and direct) for index, direct in aliases.get(self._key(current), ()))
            elif current.kind == NodeKind.FIELD_ACCESS:
                pending.append((current.object, False))
            elif current.kind == NodeKind.IF_EXPR:
                pending.extend([(current.then_expr, exact), (current.else_expr, exact)])
            elif current.kind == NodeKind.MATCH_EXPR:
                pending.extend((getattr(case, "expression", None), exact) for case in current.cases or [])
                if isinstance(current.else_case, ASTNode):
                    pending.append((current.else_case, exact))
        return frozenset(origins)

    def _field_write_summary(self, function: ASTNode) -> dict[int, set[str]]:
        # Local reference rebinding changes which parameter a later field write
        # can reach. Branches join possible origins; loops iterate a finite set
        # of parameter indices, not increasingly long access paths.
        aliases = {self._key(param): frozenset({(index, True)})
                   for index, param in enumerate(function.parameters or [])}
        writes: dict[int, set[str]] = {}
        frames: list[tuple[ASTNode, list[ASTNode]]] = []
        work = [("visit", function.body, None)]
        while work:
            action, node, state = work.pop()
            if action == "restore_exit":
                aliases = state
                continue
            if action == "block_end":
                _, deferred = frames.pop()
                work.extend(("visit", stmt, None) for stmt in deferred)
                continue
            if action == "loop_start":
                frames.append((node, []))
                work.extend([("loop_end", node, None), ("loop", node, dict(aliases)),
                             ("visit", node.update, None), ("visit", node.body, None),
                             ("visit", node.condition, None)])
                continue
            if action == "loop_end":
                frames.pop()
                continue
            if action == "bind":
                key, value = state
                aliases[key] = self._parameter_origins(value, aliases)
                continue
            if action in {"other", "fall_other"}:
                before, branches = state
                branches.append(dict(aliases))
                aliases = ({key: before.get(key, frozenset()) | aliases.get(key, frozenset())
                            for key in before.keys() | aliases.keys()}
                           if action == "fall_other" else dict(before))
                continue
            if action == "join":
                before, branches = state
                branches.append(aliases)
                aliases = {key: frozenset().union(*(branch.get(key, frozenset()) for branch in branches))
                           for key in set().union(*(branch.keys() for branch in branches))}
                continue
            if action == "loop":
                before = state
                joined = {key: before.get(key, frozenset()) | aliases.get(key, frozenset())
                          for key in before.keys() | aliases.keys()}
                aliases = joined
                if joined != before:
                    work.extend([("loop", node, dict(joined)), ("visit", node.update, None),
                                 ("visit", node.body, None), ("visit", node.condition, None)])
                continue
            if node is None or node.kind == NodeKind.FUNCTION:
                continue
            if node.kind == NodeKind.BLOCK:
                frames.append((node, []))
                work.append(("block_end", node, None))
                work.extend(("visit", stmt, None) for stmt in reversed(node.statements or []))
                continue
            if node.kind == NodeKind.DEFER:
                frames[-1][1].append(node.statement)
                continue
            if node.kind in EXIT_KINDS:
                deferred = []
                for owner, registered in reversed(frames):
                    if node.kind != NodeKind.RETURN and owner.kind in LOOP_KINDS and node.label in {None, owner.label}:
                        break
                    deferred.extend(reversed(registered))
                work.append(("restore_exit", node, dict(aliases)))
                work.extend(("visit", stmt, None) for stmt in reversed(deferred))
            if node.kind == NodeKind.MATCH:
                frame = (dict(aliases), [dict(aliases)] if not node.else_case else [])
                actions = [("visit", node.expression, None)]
                for case in node.cases or []:
                    statements = case.statements or ([] if case.statement is None else [case.statement])
                    last = statements[-1] if statements else None
                    while last is not None and last.kind == NodeKind.BLOCK and last.statements:
                        last = last.statements[-1]
                    branch_action = "fall_other" if last is not None and last.kind == NodeKind.FALL else "other"
                    actions.extend([("visit", case, None), (branch_action, node, frame)])
                actions.extend(("visit", stmt, None) for stmt in node.else_case or [])
                actions.append(("join", node, frame))
                work.extend(reversed(actions))
                continue
            if node.kind == NodeKind.IF_STMT:
                frame = (dict(aliases), [])
                work.extend([("join", node, frame), ("visit", node.else_stmt, None),
                             ("other", node, frame), ("visit", node.then_stmt, None),
                             ("visit", node.condition, None)])
                continue
            if node.kind in LOOP_KINDS:
                work.extend([("loop_start", node, None), ("visit", node.init, None)])
                continue
            targets = []
            if node.kind == NodeKind.ASSIGNMENT:
                targets.append((node.target, ""))
                if node.target and node.target.kind == NodeKind.IDENTIFIER and not getattr(node, "implicit_deref_target", False):
                    work.append(("bind", node, (self._key(node.target), node.value)))
            elif node.kind in {NodeKind.VAR, NodeKind.CONST}:
                if isinstance(self._type(node.value), ReferenceType):
                    work.append(("bind", node, (self._key(node), node.value)))
            elif node.kind == NodeKind.CALL and not getattr(node, "stdlib_canonical", None):
                callee = node.function
                summary = self.function_field_writes.get(self._key(callee)) if callee and callee.kind == NodeKind.IDENTIFIER else None
                for index, argument in enumerate(node.arguments or []):
                    targets.extend((argument, path) for path in (summary.get(index, set()) if summary is not None else {""}))
            for target, suffix in targets:
                fields = []
                while target is not None and target.kind == NodeKind.FIELD_ACCESS:
                    fields.append(target.field)
                    target = target.object
                for index, exact in self._parameter_origins(target, aliases):
                    if fields or node.kind == NodeKind.CALL:
                        path = ".".join([*reversed(fields), *([suffix] if suffix else [])]) if exact else ""
                        writes.setdefault(index, set()).add(path)
            children = []
            for value in vars(node).values():
                if isinstance(value, ASTNode):
                    children.append(value)
                elif isinstance(value, list):
                    children.extend(child for child in value if isinstance(child, ASTNode))
            work.extend(("visit", child, None) for child in reversed(children))
        return writes

    def _visit_decl(self, node: ASTNode) -> None:
        if node.kind == NodeKind.FUNCTION and node.body:
            self.moved_symbols = set()
            self.symbol_types = {}
            self.frames = []
            self.defer_floor = 0
            self.facts.by_symbol = dict(self.const_facts)
            for param in node.parameters or []:
                if param.name:
                    key = self._key(param)
                    fact = self._fact_from_type_node(param.param_type)
                    if isinstance(self._type(param), ReferenceType) or param.param_type and param.param_type.kind == NodeKind.TYPE_POINTER:
                        fact = replace(fact, allocations=frozenset({f"parameter:{key}"}))
                    self.facts.set_symbol(key, fact)
                    if param.param_type and param.param_type.type_name in INTEGER_RANGES:
                        self.symbol_types[key] = PrimitiveType(param.param_type.type_name)
            self._visit_stmt(node.body)
        elif node.kind == NodeKind.VAR and node.value:
            self.current_stmt_span = node.span
            fact = self._visit_expr(node.value)
            if node.name:
                self.facts.set_symbol(node.name, fact)

    def _calls_deleting_function(self, call: ASTNode) -> bool:
        """True unless the declaration-bound callee is known not to delete."""
        callee = call.function
        if callee is None or callee.kind != NodeKind.IDENTIFIER:
            return True
        return self.function_deletes.get(self._key(callee), True)

    def _loop_effects(self, loop: ASTNode) -> tuple[set[str], set[str], bool]:
        """Keys a loop can write, keys it can delete, and whether a `break` can leave it.

        Assignments forget their declaration or field path. Deletion also
        invalidates aliases to the allocation. Untracked element deletion
        retains conservative base invalidation. Calls invalidate globals and
        referenced arguments. Deferred statements participate in the same scan.

        A `break` counts when it is unlabeled and outside every nested loop
        (one in a match arm targets the loop), or labeled: a labeled `break`
        in a nested loop can name this loop.

        Nested function bodies are skipped: their effects are their own. The
        walk uses an explicit stack and calls no visitor.
        """
        written: set[str] = set()
        deleted: set[str] = set()
        has_break = False
        stack = [(loop, False)]
        while stack:
            current, nested = stack.pop()
            if current.kind == NodeKind.FUNCTION:
                continue
            if current.kind == NodeKind.BREAK:
                has_break = has_break or bool(current.label) or not nested
            elif current.kind == NodeKind.ASSIGNMENT:
                target = current.target
                key = self._place_key(target)
                if key:
                    written.add(key)
            elif current.kind == NodeKind.DEL:
                key = self._place_key(current.expression)
                target = current.expression
                while key is None and target is not None:
                    attr = DEL_TARGET_BASE_ATTRS.get(target.kind)
                    target = getattr(target, attr, None) if attr else None
                    key = self._place_key(target)
                if key:
                    written.add(key)
                    deleted.add(key)
            elif current.kind == NodeKind.CALL:
                if not getattr(current, "stdlib_canonical", None):
                    written.update(self.file_variables)
                signature = self._type(current.function)
                parameters = signature.param_types if isinstance(signature, FunctionType) else []
                may_delete = self._calls_deleting_function(current)
                for i, arg in enumerate(current.arguments or []):
                    if arg.kind != NodeKind.IDENTIFIER:
                        continue
                    is_ref = isinstance(self._type(arg), ReferenceType)
                    if is_ref or i in getattr(current, "implicit_ref_args", set()):
                        written.add(self._key(arg))
                    if may_delete and is_ref and i < len(parameters) and isinstance(parameters[i], ReferenceType):
                        deleted.add(self._key(arg))
            nested = nested or (current is not loop and current.kind in LOOP_KINDS)
            for value in vars(current).values():
                if isinstance(value, ASTNode):
                    stack.append((value, nested))
                elif isinstance(value, list):
                    stack.extend((child, nested) for child in value if isinstance(child, ASTNode))
        return written, deleted, has_break

    def _invalidate_length_relations(self, key: str) -> None:
        if key not in self.length_targets:
            return
        for other, fact in list(self.facts.by_symbol.items()):
            if fact.upper_length_of == key:
                self.facts.set_symbol(other, replace(fact, upper_length_of=None))

    def _forget_names(self, keys: set[str]) -> None:
        affected = set(keys)
        for name in self.facts.by_symbol:
            if any(name.startswith(key + ".") for key in keys):
                affected.add(name)
        for key in affected:
            self._invalidate_length_relations(key)
            # A key with no entry is already unknown: a local the loop
            # declares later, or a file-scope variable.
            if key in self.facts.by_symbol:
                self.facts.set_symbol(key, replace(self._default_fact_for_type(self.symbol_types.get(key)),
                                                   allocations=self.facts.symbol(key).allocations,
                                                   selected_allocations=self.facts.symbol(key).selected_allocations))

    def _join_facts(self, left: dict[str, ValueFact], right: dict[str, ValueFact]) -> dict[str, ValueFact]:
        joined = {}
        for name in left.keys() | right.keys():
            a, b = left.get(name, ValueFact()), right.get(name, ValueFact())
            if a is b:
                joined[name] = a
                continue
            interval = None
            if a.interval and b.interval:
                lo = min(a.interval.lower, b.interval.lower) if a.interval.lower is not None and b.interval.lower is not None else None
                hi = max(a.interval.upper, b.interval.upper) if a.interval.upper is not None and b.interval.upper is not None else None
                interval = IntegerInterval(lo, hi)
            joined[name] = ValueFact(interval=interval, nonzero=a.nonzero and b.nonzero,
                                     known_length=a.known_length if a.known_length == b.known_length else None,
                                     upper_length_of=a.upper_length_of if a.upper_length_of == b.upper_length_of else None,
                                     non_nil=a.non_nil and b.non_nil, maybe_nil=a.maybe_nil or b.maybe_nil,
                                     initialized=a.initialized and b.initialized, moved=a.moved or b.moved,
                                     allocations=a.allocations | b.allocations,
                                     selected_allocations=a.selected_allocations | b.selected_allocations)
        return joined

    def _place_key(self, node: Optional[ASTNode]) -> Optional[str]:
        fields = []
        while node is not None and node.kind == NodeKind.FIELD_ACCESS:
            fields.append(node)
            node = node.object
        if node is None or node.kind != NodeKind.IDENTIFIER:
            return None
        key = self._key(node)
        for access in reversed(fields):
            if isinstance(self._type(access.object), ReferenceType):
                allocations = self.facts.symbol(key).allocations
                if len(allocations) == 1:
                    key = f"@allocation:{next(iter(allocations))}"
            key += "." + access.field
        return key

    def _store_value(self, key: str, value: Optional[ASTNode], fact: ValueFact) -> None:
        # Struct copies retain the allocation identities of their reference fields.
        children = {}
        pending = [(key, value)]
        while pending:
            prefix, current = pending.pop()
            source_key = self._place_key(current)
            if source_key:
                children.update({prefix + name[len(source_key):]: item
                                 for name, item in self.facts.by_symbol.items()
                                 if name.startswith(source_key + ".")})
            if current is not None and current.kind == NodeKind.STRUCT_INIT:
                for member in current.field_inits or []:
                    if member.name is None:
                        continue
                    child = prefix + "." + member.name
                    member_fact = self.facts.node(member.value)
                    children[child] = member_fact if isinstance(self._type(member.value), ReferenceType) or member_fact.maybe_nil else ValueFact()
                    pending.append((child, member.value))
        for name in list(self.facts.by_symbol):
            if name.startswith(key + "."):
                del self.facts.by_symbol[name]
                self.moved_symbols.discard(name)
        if "." in key and not isinstance(self._type(value), ReferenceType) and not fact.maybe_nil:
            fact = ValueFact()
        self.facts.set_symbol(key, fact)
        self.facts.by_symbol.update(children)
        self.moved_symbols.discard(key)

    def _delete_place(self, key: str) -> None:
        fact = self.facts.symbol(key)
        self.moved_symbols.update(f"@allocation:{identity}" for identity in fact.allocations)
        self.moved_symbols.add(key)

    def _check_reference_alive(self, node: ASTNode, fact: ValueFact, key: Optional[str]) -> None:
        if key in self.moved_symbols or any(
                f"@allocation:{identity}" in self.moved_symbols for identity in fact.allocations | fact.selected_allocations):
            name = node.name if node.kind == NodeKind.IDENTIFIER else node.field
            self._error_moved_symbol(node, name, "moved/deleted values cannot be read")

    def _visit_stmt(self, node: ASTNode) -> None:
        if node.kind != NodeKind.BLOCK and node.span is not None:
            self.current_stmt_span = node.span
        if node.kind == NodeKind.BLOCK:
            statements = node.statements or []
            self.frames.append(ExitFrame())
            for stmt in statements:
                self._visit_stmt(stmt)
            frame = self.frames.pop()
            # A deferred statement runs when the block ends, so it is proven
            # against the state there and its writes and deletes reach the
            # statements after the block. A block that ends in `ret`, `break`
            # or `continue` proved its defers at that exit.
            if frame.defers and statements[-1].kind not in EXIT_KINDS:
                floor = self.defer_floor
                self.defer_floor = len(self.frames)
                for deferred in reversed(frame.defers):
                    self._visit_stmt(deferred)
                self.defer_floor = floor
            for key in self.scope_keys.get(id(node), ()):
                self.facts.by_symbol.pop(key, None)
                self.moved_symbols.discard(key)
        elif node.kind in {NodeKind.VAR, NodeKind.CONST}:
            fact = self._visit_expr(node.value) if node.value else self._default_fact_for_type(self._type(node))
            if node.name:
                key = self._key(node)
                self._invalidate_length_relations(key)
                self._store_value(key, node.value, fact)
                self.symbol_types[key] = self._type(node) or self._type(node.value)
                self.moved_symbols.discard(key)
        elif node.kind == NodeKind.ASSIGNMENT:
            rhs = self._visit_expr(node.value) if node.value else ValueFact()
            if node.target:
                target_fact = (
                    self._visit_expr(node.target.object if node.target.kind == NodeKind.FIELD_ACCESS else node.target)
                    if getattr(node, "implicit_deref_target", False) or node.target.kind != NodeKind.IDENTIFIER
                    else self.facts.symbol(self._key(node.target))
                )
                if getattr(node, "implicit_deref_target", False):
                    self._prove_ref_non_nil_for_node(
                        node,
                        target_fact,
                        self._type(node.target),
                        "reference must be proven non-nil before assignment through it",
                        node.target,
                    )
                if node.target.kind == NodeKind.IDENTIFIER and node.target.name:
                    if node.operator != AssignOp.ASSIGN:
                        result = self._default_fact_for_type(self._type(node.target))
                        operations = {AssignOp.ADD_ASSIGN: IntegerInterval.add, AssignOp.SUB_ASSIGN: IntegerInterval.sub, AssignOp.MUL_ASSIGN: IntegerInterval.mul}
                        operation = operations.get(node.operator)
                        if operation:
                            nonwrap = node.operator.name.lower() + "_nonwrap"
                            interval = operation(target_fact.interval, rhs.interval) if target_fact.interval and rhs.interval else None
                            if self._range_fits(interval, self._type(node.target)):
                                if (id(node), nonwrap) not in self.refused_nonwrap:
                                    obligation = self._obligation(
                                        ObligationKind.INTEGER_OVERFLOW,
                                        node,
                                        nonwrap,
                                        self._type(node.target),
                                        "compound assignment result must fit the target type range",
                                        None,
                                    )
                                    self._prove(obligation, "result interval fits the target type range")
                                result = ValueFact(interval=interval, nonzero=interval.is_nonzero())
                            else:
                                self._refuse_nonwrap(node, nonwrap)
                        rhs = result
                    if not getattr(node, "implicit_deref_target", False):
                        key = self._key(node.target)
                        self._invalidate_length_relations(key)
                        self._store_value(key, node.value, rhs)
                elif node.target.kind == NodeKind.FIELD_ACCESS:
                    if node.operator != AssignOp.ASSIGN:
                        self._visit_expr(node.target)
                    if getattr(node.target, "implicit_deref_object", False):
                        self._prove_ref_non_nil_for_node(
                            node.target, target_fact, self._type(node.target.object),
                            "reference must be proven non-nil before field assignment", node.target.object)
                    key = self._place_key(node.target)
                    if key:
                        self._store_value(key, node.value, rhs)
            if node.operator in {AssignOp.DIV_ASSIGN, AssignOp.MOD_ASSIGN} and node.value:
                self._prove_nonzero_divisor(node, node.value, node.operator.name.lower())
        elif node.kind == NodeKind.EXPRESSION_STMT and node.expression:
            self._visit_expr(node.expression)
        elif node.kind in EXIT_KINDS:
            if node.kind == NodeKind.RETURN and node.value:
                self._visit_expr(node.value)
            # Frames this exit leaves, innermost first: every frame for `ret`,
            # the frames above the target loop for `break` and `continue`.
            pending: list[ASTNode] = []
            target: Optional[ExitFrame] = None
            for index in range(len(self.frames) - 1, self.defer_floor - 1, -1):
                frame = self.frames[index]
                if node.kind != NodeKind.RETURN and frame.loop is not None and node.label in {None, frame.loop.label}:
                    target = frame
                    break
                pending.extend(reversed(frame.defers))
            feeds_update = node.kind == NodeKind.CONTINUE and target is not None and target.loop.update is not None
            if pending or feeds_update:
                # The defers of those frames run here, last registered first.
                # Statements after the exit keep the state
                # from before it, so a `ret` in one match arm does not apply
                # its defers to the state after the match.
                saved = self.facts.copy_symbols()
                moved = set(self.moved_symbols)
                floor = self.defer_floor
                self.defer_floor = len(self.frames)
                for deferred in pending:
                    self._visit_stmt(deferred)
                self.defer_floor = floor
                if feeds_update:
                    target.continues.append((self.facts.by_symbol, self.moved_symbols))
                self.facts.restore_symbols(saved)
                self.moved_symbols = moved
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
            self.frames.append(ExitFrame(node))
            if node.init:
                self._visit_stmt(node.init)
            # The head state holds each time the condition is evaluated: the
            # entry state, with every key the loop can write forgotten and
            # every key it can delete marked moved. The body is proven once
            # against it, so no fixed point is needed.
            written, deleted, has_break = self._loop_effects(node)
            for key in deleted:
                self._delete_place(key)
            self._forget_names(written)
            head = self.facts.copy_symbols()
            head_moved = set(self.moved_symbols)
            if node.condition:
                self._visit_expr(node.condition)
                self.facts.by_symbol.update(self._facts_from_condition(node.condition, positive=True))
            if node.body:
                self._visit_stmt(node.body)
            frame = self.frames.pop()
            if node.update:
                for facts, continue_moved in frame.continues:
                    self.facts.by_symbol = self._join_facts(self.facts.by_symbol, facts)
                    self.moved_symbols.update(continue_moved)
                self._visit_stmt(node.update)
            # The loop may run zero times, and a `break` leaves from a state
            # the head state covers, so nothing the body established survives.
            # The false condition holds after the loop only when no `break`
            # can leave with it still true.
            self.facts.restore_symbols(head)
            self.moved_symbols = head_moved
            if node.condition and not has_break:
                self.facts.by_symbol.update(self._facts_from_condition(node.condition, positive=False))
            for key in self.scope_keys.get(id(node), ()):
                self.facts.by_symbol.pop(key, None)
                self.moved_symbols.discard(key)
        elif node.kind in {NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED}:
            iterable_fact = self._visit_expr(node.iterable)
            self.frames.append(ExitFrame(node))
            written, deleted, _ = self._loop_effects(node)
            for key in deleted:
                self._delete_place(key)
            self._forget_names(written)
            head = self.facts.copy_symbols()
            head_moved = set(self.moved_symbols)
            if node.index_var:
                length = self._object_length(node.iterable, iterable_fact)
                self.facts.set_symbol(self._key(node, node.index_var), ValueFact(interval=IntegerInterval(0, length - 1 if length is not None else None), nonzero=False))
            if node.iterator:
                iterable_type = self._type(node.iterable)
                element_type = iterable_type.element_type if isinstance(iterable_type, (ArrayType, SliceType)) else None
                self.facts.set_symbol(self._key(node, node.iterator), self._default_fact_for_type(element_type))
            if node.body:
                self._visit_stmt(node.body)
            self.frames.pop()
            # Same exit rule as `while`: zero iterations are possible.
            self.facts.restore_symbols(head)
            self.moved_symbols = head_moved
        elif node.kind == NodeKind.MATCH:
            self._visit_expr(node.expression)
            saved = self.facts.copy_symbols()
            moved = set(self.moved_symbols)
            joined = dict(saved)  # A non-exhaustive match can execute no arm.
            all_moved = set(moved)
            # A payload capture has its own key and no entry, so it starts
            # unknown whatever an outer variable of the same name holds.
            branches = [case.statements or ([] if case.statement is None else [case.statement]) for case in node.cases or []]
            branches.append(node.else_case or [])
            fallen: Optional[tuple[dict[str, ValueFact], set[str]]] = None
            for statements in branches:
                self.facts.restore_symbols(dict(saved))
                self.moved_symbols = set(moved)
                if fallen is not None:
                    # The arm above ends in `fall`, so this arm also starts
                    # from that arm's end state.
                    self.facts.by_symbol = self._join_facts(self.facts.by_symbol, fallen[0])
                    self.moved_symbols.update(fallen[1])
                for stmt in statements:
                    self._visit_stmt(stmt)
                last = statements[-1] if statements else None
                if last is not None and last.kind == NodeKind.BLOCK and last.statements:
                    last = last.statements[-1]
                falls = last is not None and last.kind == NodeKind.FALL
                fallen = (self.facts.by_symbol, self.moved_symbols) if falls else None
                joined = self._join_facts(joined, self.facts.by_symbol)
                all_moved.update(self.moved_symbols)
            self.facts.restore_symbols(joined)
            self.moved_symbols = all_moved
        elif node.kind == NodeKind.DEFER and node.statement:
            if id(node) in self.block_defers:
                self.frames[-1].defers.append(node.statement)
            else:
                # The only statement of a branch or match arm: that scope ends
                # here, so the deferred statement runs now.
                self._visit_stmt(node.statement)
        elif node.kind == NodeKind.DEL and node.expression:
            target = node.expression
            if target.kind == NodeKind.IDENTIFIER and self._key(target) in self.moved_symbols:
                self._error_moved_symbol(target, target.name, "a value can be deleted only once")
            else:
                self._visit_expr(target)
            self._mark_deleted(target)
        elif node.kind == NodeKind.FUNCTION and node.body:
            # A nested function starts from the file-scope constant facts, like
            # a top-level one, and leaves the enclosing function's state intact.
            saved = self.facts.copy_symbols()
            saved_moved = self.moved_symbols
            saved_frames = self.frames
            saved_floor = self.defer_floor
            self.moved_symbols = set()
            self.frames = []
            self.defer_floor = 0
            self.facts.by_symbol = dict(self.const_facts)
            for param in node.parameters or []:
                if param.name:
                    key = self._key(param)
                    fact = self._fact_from_type_node(param.param_type)
                    if param.param_type and param.param_type.kind == NodeKind.TYPE_POINTER:
                        fact = replace(fact, allocations=frozenset({f"parameter:{key}"}))
                    self.facts.set_symbol(key, fact)
            self._visit_stmt(node.body)
            self.facts.restore_symbols(saved)
            self.moved_symbols = saved_moved
            self.frames = saved_frames
            self.defer_floor = saved_floor

    def _visit_expr(self, node: Optional[ASTNode]) -> ValueFact:
        if node is None:
            return ValueFact()
        root = node
        pending = [("visit", node, None)]
        while pending:
            action, node, context = pending.pop()
            if action == "exact_finish":
                name, captured = context
                if self._exact_call_name(node, captured) == name:
                    self._replay_exact_effects(node, name, captured)
                else:
                    # Argument evaluation can introduce selected identities.
                    # This call gets legacy effects once, with no partial replay.
                    for index, arg in enumerate(node.arguments or []):
                        self._apply_legacy_reference_effects(node, index, arg, captured[index][0])
                continue
            if action == "global_effects":
                for key in context:
                    self._delete_place(key)
                self._forget_names(self.file_variables)
                continue
            if action == "call_start":
                exact_name = self._exact_call_name(node)
                captured = []
                if exact_name:
                    pending.append(("exact_finish", node, (exact_name, captured)))
                borrowed = getattr(node, "implicit_ref_args", set())
                function_type = self._type(node.function)
                if not exact_name and not getattr(node, "stdlib_canonical", None):
                    callee = node.function
                    deleted_globals = self.function_deleted_globals.get(self._key(callee), set()) if callee and callee.kind == NodeKind.IDENTIFIER else self.file_variables
                    pending.append(("global_effects", node, deleted_globals))
                for i, arg in reversed(list(enumerate(node.arguments or []))):
                    pending.append(("call_arg", node, (i, arg, borrowed, function_type, exact_name, captured)))
                    pending.append(("visit", arg, None))
                continue
            if action == "call_arg":
                i, arg, borrowed, function_type, exact_name, captured = context
                if exact_name:
                    fact = self.facts.node(arg)
                    captured.append((replace(fact, non_nil=True) if i in borrowed else fact, self._place_key(arg) if i in borrowed else None))
                if not exact_name:
                    self._apply_legacy_reference_effects(node, i, arg, self.facts.node(arg))
                arg_fact = self.facts.node(arg)
                is_ref_parameter = isinstance(function_type, FunctionType) and i < len(function_type.param_types) and isinstance(function_type.param_types[i], ReferenceType)
                if isinstance(self._type(arg), ReferenceType) and is_ref_parameter:
                    self._prove_ref_non_nil_for_node(node, arg_fact, self._type(arg), "reference argument must be proven non-nil", arg)
                elif i in borrowed and arg.kind == NodeKind.IDENTIFIER:
                    self._invalidate_length_relations(self._key(arg))
                    key = self._key(arg)
                    self.facts.set_symbol(key, replace(self._default_fact_for_type(self._type(arg)),
                                                       allocations=self.facts.symbol(key).allocations,
                                                   selected_allocations=self.facts.symbol(key).selected_allocations))
                continue
            if action == "visit":
                pending.append(("finish", node, None))
                if node.kind == NodeKind.CALL:
                    # Borrow invalidation remains ordered between arguments.
                    # Global and exact body effects follow argument evaluation.
                    pending.append(("call_start", node, None))
                    children = [node.function]
                elif node.kind in {NodeKind.UNARY, NodeKind.ADDRESS_OF}:
                    children = [node.operand]
                elif node.kind == NodeKind.BINARY:
                    children = [node.left, node.right]
                elif node.kind == NodeKind.CAST:
                    children = [node.expression]
                elif node.kind == NodeKind.INDEX:
                    children = [node.object, node.index]
                elif node.kind == NodeKind.SLICE:
                    children = [node.object, node.start, node.end]
                elif node.kind == NodeKind.FIELD_ACCESS:
                    children = [node.object]
                elif node.kind == NodeKind.DEREF:
                    children = [node.pointer]
                elif node.kind == NodeKind.ARRAY_INIT:
                    children = node.elements or []
                elif node.kind == NodeKind.STRUCT_INIT:
                    children = [init.value for init in node.field_inits or []]
                elif node.kind == NodeKind.IF_EXPR:
                    children = [node.condition, node.then_expr, node.else_expr]
                elif node.kind == NodeKind.MATCH_EXPR:
                    children = [node.expression]
                    children.extend(getattr(case, "expression", None) for case in node.cases or [])
                    if isinstance(node.else_case, ASTNode):
                        children.append(node.else_case)
                else:
                    children = []
                pending.extend(("visit", child, None) for child in reversed(children) if child is not None)
                continue
            fact = ValueFact()
            if node.kind == NodeKind.LITERAL:
                fact = self._literal_fact(node)
            elif node.kind == NodeKind.IDENTIFIER:
                key = self._key(node)
                fact = self.facts.symbol(key)
                self._check_reference_alive(node, fact, key)
            elif node.kind == NodeKind.UNARY:
                operand = self.facts.node(node.operand)
                fact = self._unary_fact(node, operand)
            elif node.kind == NodeKind.BINARY:
                left = self.facts.node(node.left)
                right = self.facts.node(node.right)
                fact = self._binary_fact(node, left, right)
                if node.operator in {BinaryOp.DIV, BinaryOp.MOD} and node.right:
                    self._prove_nonzero_divisor(node, node.right, node.operator.name.lower())
                if node.operator in {BinaryOp.ADD, BinaryOp.SUB, BinaryOp.MUL}:
                    self._prove_integer_overflow(node, fact)
            elif node.kind == NodeKind.CAST:
                source = self.facts.node(node.expression)
                fact = self._cast_fact(node, source)
            elif node.kind == NodeKind.INDEX:
                obj_fact = self.facts.node(node.object)
                idx_fact = self.facts.node(node.index)
                self._prove_index(node, obj_fact, idx_fact)
            elif node.kind == NodeKind.SLICE:
                obj_fact = self.facts.node(node.object)
                start_fact = self.facts.node(node.start) if node.start else ValueFact(interval=IntegerInterval.exact(0))
                end_fact = self.facts.node(node.end) if node.end else ValueFact(interval=IntegerInterval.exact(obj_fact.known_length), known_length=obj_fact.known_length) if obj_fact.known_length is not None else ValueFact()
                self._prove_slice(node, obj_fact, start_fact, end_fact)
                fact = self._slice_fact(node, obj_fact, start_fact, end_fact)
            elif node.kind == NodeKind.FIELD_ACCESS:
                obj = self.facts.node(node.object)
                if getattr(node, "implicit_deref_object", False):
                    self._prove_ref_non_nil_for_node(
                        node,
                        obj,
                        self._type(node.object),
                        "reference must be proven non-nil before field access through it",
                        node.object,
                    )
                key = self._place_key(node)
                fact = self.facts.symbol(key)
                if key and key not in self.facts.by_symbol and isinstance(self._type(node), ReferenceType):
                    fact = ValueFact(maybe_nil=True, allocations=frozenset({f"field:{key}"}))
                    self.facts.set_symbol(key, fact)
                alive_key = key
                if (key and isinstance(self._type(node.object), ReferenceType)
                        and isinstance(self._type(node), ReferenceType) and len(obj.allocations) > 1
                        and fact.allocations == frozenset({f"field:{key}"})):
                    # Only synthetic selected-field facts follow the candidates.
                    # Explicit stores retain their own identity. Saved aliases
                    # keep these dependencies as they were when captured.
                    identities = set()
                    for identity in sorted(obj.allocations):
                        child_key = f"@allocation:{identity}.{node.field}"
                        child = self.facts.symbol(child_key)
                        identities.update(child.allocations | child.selected_allocations or {f"field:{child_key}"})
                        if child_key in self.moved_symbols:
                            alive_key = child_key
                    fact = replace(fact, selected_allocations=frozenset(identities))
                    self.facts.set_symbol(key, fact)
                self._check_reference_alive(node, fact, alive_key)
                object_type = self._type(node.object)
                if node.field == "ptr" and (isinstance(object_type, (ArrayType, SliceType))
                                             or isinstance(object_type, PrimitiveType) and object_type.name == "string"):
                    fact = ValueFact(non_nil=True)
                if node.field == "len" and obj.known_length is not None:
                    fact = ValueFact(interval=IntegerInterval.exact(obj.known_length), known_length=None, nonzero=obj.known_length != 0)
            elif node.kind == NodeKind.ADDRESS_OF:
                fact = ValueFact(non_nil=True, maybe_nil=False)
            elif node.kind == NodeKind.DEREF:
                ptr_fact = self.facts.node(node.pointer)
                self._prove_ref_non_nil(node, ptr_fact)
            elif node.kind == NodeKind.ARRAY_INIT:
                fact = ValueFact(known_length=len(node.elements or []), non_nil=True)
            elif node.kind == NodeKind.MATCH_EXPR:
                branches = [getattr(case, "expression", None) for case in node.cases or []]
                if isinstance(node.else_case, ASTNode):
                    branches.append(node.else_case)
                branch_facts = [self.facts.node(branch) for branch in branches if branch is not None]
                if branch_facts:
                    fact = branch_facts[0]
                    for branch_fact in branch_facts[1:]:
                        fact = self._join_facts({"value": fact}, {"value": branch_fact})["value"]
            elif node.kind == NodeKind.IF_EXPR:
                fact = self._join_facts({"value": self.facts.node(node.then_expr)},
                                        {"value": self.facts.node(node.else_expr)})["value"]
            elif node.kind == NodeKind.NEW_EXPR:
                fact = ValueFact(maybe_nil=True, allocations=frozenset({f"new:{id(node)}"}))
            self.facts.set_node(node, fact)
        return self.facts.node(root)

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
            # `-MIN` wraps to `MIN`, so an interval past the type's maximum
            # says nothing about the result.
            result_type = self._type(node)
            if isinstance(result_type, PrimitiveType) and result_type.name in INTEGER_RANGES and not self._range_fits(interval, result_type):
                return self._default_fact_for_type(result_type)
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
            if divisor.kind == NodeKind.LITERAL:
                hint = "The divisor is the constant 0; divide by a non-zero value"
            else:
                name, copy_first = self._guard_subject(divisor, "d")
                hint = (
                    f"{copy_first}Guard the divisor: 'if {name} != 0 {{ ... }}' around the division, "
                    f"or an early 'if {name} == 0 {{ ret ... }}' before it"
                )
            self._error(obligation, "divisor may be zero", hint)

    def _prove_index(self, node: ASTNode, obj: ValueFact, idx: ValueFact) -> None:
        obligation = self._obligation(ObligationKind.INDEX_IN_BOUNDS, node, "index", self._type(node.index), "index must satisfy 0 <= index < len", None)
        length = self._object_length(node.object, obj)
        interval = idx.interval
        relative_bound = (idx.upper_length_of is not None and node.object is not None
                          and node.object.kind == NodeKind.IDENTIFIER
                          and idx.upper_length_of == self._key(node.object)
                          and interval is not None and interval.is_nonnegative())
        if relative_bound or (length is not None and interval is not None and interval.contains(0, length - 1)):
            self._prove(obligation, "index is in bounds")
        else:
            if node.index is not None and node.index.kind == NodeKind.LITERAL and length is not None:
                hint = f"This array has {length} elements; valid indexes are 0 to {length - 1}"
            else:
                name, copy_first = self._guard_subject(node.index, "i")
                if length is not None:
                    bound = str(length)
                else:
                    # `i < xs.len` is tracked only for a slice held in a variable.
                    slice_name, copy_slice = self._guard_subject(node.object, "xs")
                    bound = f"{slice_name}.len"
                    copy_first = copy_slice or copy_first
                hint = f"{copy_first}Guard the index: 'if {name} < {bound} {{ ... }}' around the access"
            self._error(obligation, "index bounds are not proven", hint)

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
            if length is None:
                hint = (
                    "Slice bounds are proven only against a known length: slice the fixed-size array "
                    "itself, for example 'if end <= 5 { ... xs[0..end] ... }' for a '[5]T' array"
                )
            else:
                name, _ = self._guard_subject(node.end, "end")
                hint = (
                    f"Guard each variable bound against a constant, one comparison per 'if': "
                    f"'if {name} <= {length} {{ ... xs[0..{name}] ... }}'; a variable start needs "
                    f"its own 'if start <= K', with K no greater than the smallest end"
                )
            self._error(obligation, "slice bounds are not proven", hint)

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
            node.pointer,
        )

    def _prove_ref_non_nil_for_node(
        self,
        node: ASTNode,
        fact: ValueFact,
        operand_type: Optional[Type],
        required: str,
        reference: Optional[ASTNode],
    ) -> None:
        obligation = self._obligation(ObligationKind.REF_NON_NIL, node, "deref", operand_type, required, TypeErrorType.CANNOT_DEREFERENCE)
        if fact.non_nil:
            self._prove(obligation, "reference is non-nil")
        else:
            name, copy_first = self._guard_subject(reference, "p", fields=True)
            self._error(
                obligation,
                "reference may be nil",
                f"{copy_first}Check the reference first: 'if {name} != nil {{ ... }}' around the use, "
                f"or an early 'if {name} == nil {{ ret ... }}' before it",
            )

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
        operations = {
            BinaryOp.ADD: IntegerInterval.add,
            BinaryOp.SUB: IntegerInterval.sub,
            BinaryOp.MUL: IntegerInterval.mul,
        }
        nonwrap = node.operator.name.lower() + "_nonwrap"
        left = self.facts.node(node.left)
        right = self.facts.node(node.right)
        if not left.interval or not right.interval:
            self._refuse_nonwrap(node, nonwrap)
            return
        interval = operations[node.operator](left.interval, right.interval)
        obligation = self._obligation(
            ObligationKind.INTEGER_OVERFLOW,
            node,
            nonwrap,
            result_type,
            "arithmetic result must fit the result type range",
            None,
        )
        if not self._range_fits(interval, result_type):
            self._refuse_nonwrap(node, nonwrap)
        elif (id(node), nonwrap) not in self.refused_nonwrap:
            self._prove(obligation, "result interval fits the result type range")

    def _refuse_nonwrap(self, node: ASTNode, operation: str) -> None:
        """Keep the wrapping lowering for `node`, whatever another proof of it found.

        A deferred statement is proven once per scope exit. One exit where the
        result may overflow withdraws the approval for all of them.
        """
        self.refused_nonwrap.add((id(node), operation))
        self.backend_plan.approved.pop((id(node), operation), None)

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
        """True when control never reaches the statement after `node`: it ends in `ret`, `break` or `continue`."""
        while node.kind == NodeKind.BLOCK:
            statements = node.statements or []
            if not statements:
                return False
            node = statements[-1]
        return node.kind in EXIT_KINDS

    def _facts_from_condition(self, condition: Optional[ASTNode], *, positive: bool) -> dict[str, ValueFact]:
        if condition is None or condition.kind != NodeKind.BINARY:
            return {}
        field_guard = condition.left is not None and condition.left.kind == NodeKind.FIELD_ACCESS
        if field_guard and not (condition.right and condition.right.kind == NodeKind.LITERAL
                                and condition.right.literal_kind == LiteralKind.NIL):
            return {}
        name = self._place_key(condition.left)
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
            target = self._key(condition.right.object)
            self.length_targets.add(target)
            facts[name] = replace(facts.get(name, current), upper_length_of=target)
        if self._zero_literal(condition.right):
            if (positive and condition.operator == BinaryOp.NE) or (not positive and condition.operator == BinaryOp.EQ):
                facts[name] = ValueFact(interval=interval, nonzero=True, non_nil=current.non_nil, maybe_nil=current.maybe_nil)
        if condition.right and condition.right.kind == NodeKind.LITERAL and condition.right.literal_kind == LiteralKind.NIL:
            if positive and condition.operator == BinaryOp.NE:
                facts[name] = replace(current, non_nil=True, maybe_nil=False)
            elif not positive and condition.operator == BinaryOp.EQ:
                facts[name] = replace(current, non_nil=True, maybe_nil=False)
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
        key = self._place_key(node)
        if key:
            self._delete_place(key)

    def _error_moved_symbol(self, node: ASTNode, name: str, required: str) -> None:
        obligation = self._obligation(
            ObligationKind.MOVE_VALID,
            node,
            "move",
            self._type(node),
            required,
            TypeErrorType.USE_AFTER_MOVE,
        )
        self._error(obligation, f"'{name}' was moved or deleted earlier")
