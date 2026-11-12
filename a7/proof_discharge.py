"""Proof-discharge boundary: obligation records, backend plan, milestone ledger.

Owns the contract between collectors (safety facts/obligations, semantic
graph checks, constant-fold oracles) and consumers (diagnostics, Zig
codegen). This is not a verified-compiler claim: records are internal
evidence for rewrite-facing milestones in
``docs/plan/packets/P-PROOF-discharge-milestones.md``.

No function in this module calls itself or forms a call cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from a7.errors import SourceSpan, TypeCheckError, TypeErrorType
from a7.types import Type


# Headline message for each safety obligation kind. Kinds not listed use the
# message of their diagnostic code. Division, index and slice obligations carry
# no diagnostic code: no existing TypeErrorType describes them.
OBLIGATION_MESSAGES = {
    "DIVISOR_NONZERO": "Divisor not proven non-zero",
    "INDEX_IN_BOUNDS": "Index not proven in bounds",
    "SLICE_IN_BOUNDS": "Slice bounds not proven",
    "REF_NON_NIL": "Reference not proven non-nil",
    "INITIALIZED": "Function value may be used before assignment",
}


class SafetyError(TypeCheckError):
    """A safety obligation the proof pass could not discharge.

    `hint` names the guard shape the pass accepts for this obligation and
    takes the place of the advice text of the diagnostic code.
    """

    hint: Optional[str] = None


class ObligationKind(Enum):
    CAST = auto()
    DIVISOR_NONZERO = auto()
    INDEX_IN_BOUNDS = auto()
    SLICE_IN_BOUNDS = auto()
    REF_NON_NIL = auto()
    INTEGER_OVERFLOW = auto()
    UNION_FIELD = auto()
    MOVE_VALID = auto()
    INITIALIZED = auto()


class DischargeKind(Enum):
    """Named rewrite-facing discharge milestones (P-PROOF)."""

    CONSTANT_FOLD_CONGRUENCE = auto()
    RECURSION_BAN = auto()
    MATCH_EXHAUSTIVENESS = auto()


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

    def require(self, node, operation: str) -> ProofResult:
        result = self.approved.get((id(node), operation))
        if result is None or not result.proven:
            raise KeyError(f"backend operation '{operation}' is not approved")
        return result

    def is_approved(self, node, operation: str) -> bool:
        result = self.approved.get((id(node), operation))
        return bool(result and result.proven)


@dataclass(frozen=True)
class DischargeRecord:
    """One prove-or-reject outcome for a named discharge kind."""

    kind: DischargeKind | str
    proven: bool
    evidence: str
    subject: Optional[str] = None
    span: Optional[SourceSpan] = None


class DischargeLedger:
    """Append-only ledger of discharge records (kind, evidence, or reject)."""

    def __init__(self) -> None:
        self.records: list[DischargeRecord] = []

    def discharge(
        self,
        kind: DischargeKind | str,
        evidence: str,
        *,
        subject: Optional[str] = None,
        span: Optional[SourceSpan] = None,
    ) -> DischargeRecord:
        record = DischargeRecord(kind, True, evidence, subject, span)
        self.records.append(record)
        return record

    def reject(
        self,
        kind: DischargeKind | str,
        evidence: str,
        *,
        subject: Optional[str] = None,
        span: Optional[SourceSpan] = None,
    ) -> DischargeRecord:
        record = DischargeRecord(kind, False, evidence, subject, span)
        self.records.append(record)
        return record

    def of_kind(self, kind: DischargeKind | str) -> list[DischargeRecord]:
        return [record for record in self.records if record.kind == kind]

    def proven_of(self, kind: DischargeKind | str) -> list[DischargeRecord]:
        return [record for record in self.of_kind(kind) if record.proven]

    def rejected_of(self, kind: DischargeKind | str) -> list[DischargeRecord]:
        return [record for record in self.of_kind(kind) if not record.proven]


def wrap_signed(value: int, bits: int) -> int:
    """Two's-complement wrap into ``bits`` (independent integer wrap oracle)."""
    mask = (1 << bits) - 1
    return (value & mask) - (1 << bits) if value & (1 << (bits - 1)) else value & mask


def wrap_unsigned(value: int, bits: int) -> int:
    return value & ((1 << bits) - 1)


def apply_int_op(op: str, left: int, right: int) -> int:
    if op == "add":
        return left + right
    if op == "sub":
        return left - right
    if op == "mul":
        return left * right
    raise ValueError(f"unsupported pinned wrap op: {op}")


def oracle_int_wrap(bits: int, signed: bool, op: str, left: int, right: int) -> int:
    """Independent wrap model for pinned + - * cases (not the compiler)."""
    raw = apply_int_op(op, left, right)
    return wrap_signed(raw, bits) if signed else wrap_unsigned(raw, bits)


# Pinned native wrap cases: (label, a7_type, op_token, left, right).
# Expected values come only from ``oracle_int_wrap``, never from this table.
PINNED_INT_WRAP_CASES: tuple[tuple[str, str, str, int, int], ...] = (
    ("i32-add-overflow", "i32", "+", 2147483647, 1),
    ("i32-sub-underflow", "i32", "-", -2147483648, 1),
    ("i32-mul-wrap", "i32", "*", 65536, 65536),
    ("u32-add-wrap", "u32", "+", 4294967295, 1),
    ("u8-add-wrap", "u8", "+", 255, 1),
    ("i8-add-wrap", "i8", "+", 127, 1),
)


_OP_TOKEN_TO_NAME = {"+": "add", "-": "sub", "*": "mul"}


def pinned_int_wrap_oracle(label: str, type_name: str, op_token: str, left: int, right: int) -> int:
    bits = {"i8": 8, "u8": 8, "i32": 32, "u32": 32}[type_name]
    signed = type_name.startswith("i")
    return oracle_int_wrap(bits, signed, _OP_TOKEN_TO_NAME[op_token], left, right)


def apply_float_op(op: str, left: float, right: float) -> float:
    if op == "add":
        return left + right
    if op == "sub":
        return left - right
    if op == "mul":
        return left * right
    raise ValueError(f"unsupported pinned float op: {op}")


# Selected float oracle cases for the typed IEEE path (exact constants refuse
# destination overflow). expected=None means NaN.
PINNED_FLOAT_CASES: tuple[tuple[str, float, float, str, float | None], ...] = (
    ("f64-mul-inf", 1.0e308, 10.0, "mul", float("inf")),
    ("f64-inf-minus-inf-nan", float("inf"), float("inf"), "sub", None),
    ("f64-add-finite", 1.0, 2.0, "add", 3.0),
)


def record_congruence(
    ledger: DischargeLedger,
    subject: str,
    evidence: str,
    *,
    matched: bool,
) -> DischargeRecord:
    """Record CONSTANT_FOLD_CONGRUENCE only after an external match decision."""
    if matched:
        return ledger.discharge(
            DischargeKind.CONSTANT_FOLD_CONGRUENCE,
            evidence,
            subject=subject,
        )
    return ledger.reject(
        DischargeKind.CONSTANT_FOLD_CONGRUENCE,
        evidence,
        subject=subject,
    )


def record_safety_result(ledger: DischargeLedger, result: ProofResult) -> DischargeRecord:
    """Mirror a safety ProofResult into the observational discharge ledger."""
    kind_name = result.obligation.kind.name
    if result.proven:
        return ledger.discharge(kind_name, result.reason, span=result.obligation.span)
    return ledger.reject(kind_name, result.reason, span=result.obligation.span)
