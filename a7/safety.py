"""Internal safety proof and backend-plan analysis for A7.

This pass owns value facts and risky-operation approval. The type checker
answers base type questions; this analysis turns those typed expressions into
obligations, discharges the obligations from local facts, and records the exact
operations the backend is allowed to lower.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class Obligation:
    kind: ObligationKind
    node_id: int
    span: Optional[SourceSpan]
    operand_type: Optional[Type]
    required_proof: str
    diagnostic_code: TypeErrorType


@dataclass(frozen=True)
class ProofResult:
    proven: bool
    obligation: Obligation
    reason: str


@dataclass
class BackendPlan:
    approved: dict[int, ProofResult] = field(default_factory=dict)

    def approve(self, result: ProofResult) -> None:
        self.approved[result.obligation.node_id] = result

    def require(self, node: ASTNode, operation: str) -> ProofResult:
        result = self.approved.get(id(node))
        if result is None or not result.proven:
            raise KeyError(f"backend operation '{operation}' is not approved")
        return result

    def is_approved(self, node: ASTNode) -> bool:
        result = self.approved.get(id(node))
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
        self.current_file = "<unknown>"
        self.source_lines: list[str] = []

    def analyze(self, program: ASTNode, filename: str = "<unknown>") -> BackendPlan:
        self.current_file = filename
        self.errors = []
        self.obligations = []
        self.results = []
        self.backend_plan = BackendPlan()
        self.facts = FactMap()
        self._visit_program(program)
        return self.backend_plan

    def _type(self, node: Optional[ASTNode]) -> Optional[Type]:
        return self.node_types.get(id(node)) if node is not None else None

    def _error(self, obligation: Obligation, reason: str) -> None:
        self.results.append(ProofResult(False, obligation, reason))
        self.errors.append(
            TypeCheckError.from_type(
                obligation.diagnostic_code,
                span=obligation.span,
                filename=self.current_file,
                source_lines=self.source_lines,
                context=f"{obligation.required_proof}: {reason}",
            )
        )

    def _prove(self, obligation: Obligation, reason: str) -> None:
        result = ProofResult(True, obligation, reason)
        self.results.append(result)
        self.backend_plan.approve(result)

    def _obligation(
        self,
        kind: ObligationKind,
        node: ASTNode,
        operand_type: Optional[Type],
        required: str,
        code: TypeErrorType,
    ) -> Obligation:
        obligation = Obligation(kind, id(node), node.span, operand_type, required, code)
        self.obligations.append(obligation)
        return obligation

    def _visit_program(self, node: ASTNode) -> None:
        for decl in node.declarations or []:
            self._visit_decl(decl)

    def _visit_decl(self, node: ASTNode) -> None:
        if node.kind == NodeKind.FUNCTION and node.body:
            self.facts.by_symbol = {}
            for param in node.parameters or []:
                if param.name:
                    self.facts.set_symbol(param.name, self._fact_from_type_node(param.param_type))
            self._visit_stmt(node.body)
        elif node.kind in {NodeKind.CONST, NodeKind.VAR} and node.value:
            fact = self._visit_expr(node.value)
            if node.name:
                self.facts.set_symbol(node.name, fact)

    def _visit_stmt(self, node: ASTNode) -> None:
        if node.kind == NodeKind.BLOCK:
            saved = self.facts.copy_symbols()
            for stmt in node.statements or []:
                self._visit_stmt(stmt)
                self._learn_after_stmt(stmt)
            self.facts.restore_symbols(saved)
        elif node.kind in {NodeKind.VAR, NodeKind.CONST}:
            fact = self._visit_expr(node.value) if node.value else ValueFact(initialized=False)
            if node.name:
                self.facts.set_symbol(node.name, fact)
        elif node.kind == NodeKind.ASSIGNMENT:
            rhs = self._visit_expr(node.value) if node.value else ValueFact()
            if node.target:
                target_fact = self._visit_expr(node.target)
                if getattr(node, "implicit_deref_target", False):
                    self._prove_ref_non_nil_for_node(
                        node,
                        target_fact,
                        self._type(node.target),
                        "reference must be proven non-nil before assignment through it",
                    )
                if node.target.kind == NodeKind.IDENTIFIER and node.target.name:
                    self.facts.set_symbol(node.target.name, rhs)
            if node.operator in {AssignOp.DIV_ASSIGN, AssignOp.MOD_ASSIGN} and node.value:
                self._prove_nonzero_divisor(node, node.value)
        elif node.kind == NodeKind.EXPRESSION_STMT and node.expression:
            self._visit_expr(node.expression)
        elif node.kind == NodeKind.RETURN and node.value:
            self._visit_expr(node.value)
        elif node.kind == NodeKind.IF_STMT:
            self._visit_expr(node.condition)
            then_facts = self._facts_from_condition(node.condition, positive=True)
            saved = self.facts.copy_symbols()
            self.facts.by_symbol.update(then_facts)
            if node.then_stmt:
                self._visit_stmt(node.then_stmt)
            self.facts.restore_symbols(saved)
            if node.else_stmt:
                self._visit_stmt(node.else_stmt)
        elif node.kind == NodeKind.WHILE:
            self._visit_expr(node.condition)
            body_facts = self._facts_from_condition(node.condition, positive=True)
            saved = self.facts.copy_symbols()
            self.facts.by_symbol.update(body_facts)
            if node.body:
                self._visit_stmt(node.body)
            self.facts.restore_symbols(saved)
        elif node.kind == NodeKind.FOR:
            saved = self.facts.copy_symbols()
            if node.init:
                self._visit_stmt(node.init)
            if node.condition:
                self._visit_expr(node.condition)
            if node.body:
                self._visit_stmt(node.body)
            if node.update:
                self._visit_stmt(node.update)
            self.facts.restore_symbols(saved)
        elif node.kind in {NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED}:
            self._visit_expr(node.iterable)
            saved = self.facts.copy_symbols()
            if node.index_var:
                self.facts.set_symbol(node.index_var, ValueFact(interval=IntegerInterval(0, None), nonzero=False))
            if node.body:
                self._visit_stmt(node.body)
            self.facts.restore_symbols(saved)
        elif node.kind == NodeKind.MATCH:
            self._visit_expr(node.expression)
            for case in node.cases or []:
                for stmt in case.statements or ([] if case.statement is None else [case.statement]):
                    self._visit_stmt(stmt)
            for stmt in node.else_case or []:
                self._visit_stmt(stmt)
        elif node.kind == NodeKind.DEFER:
            if node.statement:
                self._visit_stmt(node.statement)
            elif node.expression:
                self._visit_expr(node.expression)
        elif node.kind == NodeKind.DEL and node.expression:
            self._visit_expr(node.expression)

    def _visit_expr(self, node: Optional[ASTNode]) -> ValueFact:
        if node is None:
            return ValueFact()
        fact = ValueFact()
        if node.kind == NodeKind.LITERAL:
            fact = self._literal_fact(node)
        elif node.kind == NodeKind.IDENTIFIER:
            fact = self.facts.symbol(node.name)
        elif node.kind == NodeKind.UNARY:
            operand = self._visit_expr(node.operand)
            fact = self._unary_fact(node, operand)
        elif node.kind == NodeKind.BINARY:
            left = self._visit_expr(node.left)
            right = self._visit_expr(node.right)
            fact = self._binary_fact(node, left, right)
            if node.operator in {BinaryOp.DIV, BinaryOp.MOD} and node.right:
                self._prove_nonzero_divisor(node, node.right)
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
            for arg in node.arguments or []:
                self._visit_expr(arg)
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
        return ValueFact(maybe_nil=isinstance(type_, ReferenceType))

    def _fact_from_type_node(self, node: Optional[ASTNode]) -> ValueFact:
        if node is None:
            return ValueFact()
        if node.kind == NodeKind.TYPE_POINTER:
            return ValueFact(non_nil=True)
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
            if node.operator == BinaryOp.DIV and left.nonzero and right.nonzero:
                return ValueFact(nonzero=True)
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
            if node.operator == BinaryOp.DIV and left.nonzero and right.nonzero:
                return ValueFact(nonzero=True)
            return ValueFact()
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
        obligation = self._obligation(ObligationKind.CAST, node, source_type, "cast must be classified and range-proven", TypeErrorType.UNSAFE_CAST)
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
        return ValueFact()

    def _type_from_cast_target(self, node: ASTNode) -> Optional[Type]:
        return getattr(node, "cast_target_type", None)

    def _prove_nonzero_divisor(self, node: ASTNode, divisor: ASTNode) -> None:
        fact = self.facts.node(divisor)
        obligation = self._obligation(ObligationKind.DIVISOR_NONZERO, node, self._type(divisor), "division/modulo divisor must be non-zero", TypeErrorType.UNSAFE_CAST)
        if fact.nonzero or (fact.interval and fact.interval.is_nonzero()):
            self._prove(obligation, "divisor is proven non-zero")
        else:
            self._error(obligation, "divisor may be zero")

    def _prove_index(self, node: ASTNode, obj: ValueFact, idx: ValueFact) -> None:
        obligation = self._obligation(ObligationKind.INDEX_IN_BOUNDS, node, self._type(node.index), "index must satisfy 0 <= index < len", TypeErrorType.INDEX_NOT_INTEGER)
        length = self._object_length(node.object, obj)
        interval = idx.interval
        if length is not None and interval is not None and interval.contains(0, length - 1):
            self._prove(obligation, "index is in bounds")
        else:
            self._error(obligation, "index bounds are not proven")

    def _prove_slice(self, node: ASTNode, obj: ValueFact, start: ValueFact, end: ValueFact) -> None:
        obligation = self._obligation(ObligationKind.SLICE_IN_BOUNDS, node, self._type(node.object), "slice must satisfy 0 <= start <= end <= len", TypeErrorType.INDEX_NOT_INTEGER)
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
        obligation = self._obligation(ObligationKind.REF_NON_NIL, node, operand_type, required, TypeErrorType.CANNOT_DEREFERENCE)
        if fact.non_nil:
            self._prove(obligation, "reference is non-nil")
        else:
            self._error(obligation, "reference may be nil")

    def _prove_integer_overflow(self, node: ASTNode, fact: ValueFact) -> None:
        # Overflow policy is represented in the obligation model, but full
        # range-safe arithmetic is intentionally left for a dedicated follow-up.
        # Today the pass proves concrete casts/division/index/ref obligations
        # and does not block existing arithmetic-heavy examples.
        return
        result_type = self._type(node)
        if not isinstance(result_type, PrimitiveType) or result_type.name not in INTEGER_RANGES:
            return
        if fact.interval is None or fact.interval.lower is None or fact.interval.upper is None:
            return
        obligation = self._obligation(ObligationKind.INTEGER_OVERFLOW, node, result_type, "fixed-width integer arithmetic must stay in range", TypeErrorType.UNSAFE_CAST)
        if self._range_fits(fact.interval, result_type):
            self._prove(obligation, "integer result range fits type")
        else:
            self._error(obligation, "integer arithmetic overflow is not proven impossible")

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

    def _learn_after_stmt(self, node: ASTNode) -> None:
        if node.kind != NodeKind.IF_STMT or node.condition is None or node.then_stmt is None:
            return
        if not self._always_returns(node.then_stmt):
            return
        self.facts.by_symbol.update(self._facts_from_condition(node.condition, positive=False))

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
        if literal is not None:
            if positive and condition.operator in {BinaryOp.GE, BinaryOp.GT}:
                lower = literal if condition.operator == BinaryOp.GE else literal + 1
                facts[name] = ValueFact(interval=IntegerInterval(lower, interval.upper if interval else None), nonzero=lower > 0, non_nil=current.non_nil, maybe_nil=current.maybe_nil)
            elif not positive and condition.operator in {BinaryOp.LT, BinaryOp.LE}:
                lower = literal if condition.operator == BinaryOp.LT else literal + 1
                facts[name] = ValueFact(interval=IntegerInterval(lower, interval.upper if interval else None), nonzero=lower > 0, non_nil=current.non_nil, maybe_nil=current.maybe_nil)
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
        if node is None:
            return None
        if node.kind == NodeKind.LITERAL and node.literal_kind == LiteralKind.INTEGER and isinstance(node.literal_value, int):
            return node.literal_value
        if node.kind == NodeKind.UNARY and node.operator == UnaryOp.NEG:
            value = self._int_literal(node.operand)
            return -value if value is not None else None
        return None
