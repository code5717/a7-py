"""Cast classification for A7 semantic checks and Zig lowering."""

from dataclasses import dataclass
from enum import Enum, auto

from a7.types import (
    FLOAT_BIT_WIDTHS,
    FunctionType,
    PrimitiveType,
    ReferenceType,
    SIGNED_INTEGER_WIDTHS,
    Type,
    TypeKind,
    UNSIGNED_INTEGER_WIDTHS,
)


class CastClass(Enum):
    """Semantic category assigned to a cast expression."""

    LOSSLESS = auto()
    EXPLICIT_NUMERIC = auto()
    PROVABLE_NARROWING = auto()
    FORBIDDEN = auto()


@dataclass(frozen=True)
class CastDecision:
    """Result of classifying one cast expression."""

    kind: CastClass
    reason: str

    @property
    def allowed(self) -> bool:
        return self.kind is not CastClass.FORBIDDEN


# Aliases onto the canonical a7.types width tables. Copies keep the previous
# isolation (mutating these never touches the canonical dicts); the old
# names stay so classify_cast is untouched.
_SIGNED_BITS = dict(SIGNED_INTEGER_WIDTHS)
_UNSIGNED_BITS = dict(UNSIGNED_INTEGER_WIDTHS)
_FLOAT_BITS = dict(FLOAT_BIT_WIDTHS)


def classify_cast(source: Type, target: Type, *, source_nonnegative: bool = False) -> CastDecision:
    """Classify an A7 cast under the Phase 1 hybrid cast boundary."""
    if source.kind is TypeKind.UNKNOWN or target.kind is TypeKind.UNKNOWN:
        return CastDecision(CastClass.FORBIDDEN, "unknown source or target type")

    if isinstance(source, (ReferenceType, FunctionType)) or isinstance(target, (ReferenceType, FunctionType)):
        return CastDecision(CastClass.FORBIDDEN, "casts involving references or functions are forbidden")

    if not isinstance(source, PrimitiveType) or not isinstance(target, PrimitiveType):
        return CastDecision(CastClass.FORBIDDEN, "only primitive numeric casts are supported")

    if not source.is_numeric() or not target.is_numeric():
        return CastDecision(CastClass.FORBIDDEN, "only primitive numeric casts are supported")

    if source.equals(target):
        return CastDecision(CastClass.LOSSLESS, "source and target types are identical")

    if _is_lossless_numeric_cast(source.name, target.name):
        return CastDecision(CastClass.LOSSLESS, "lossless numeric cast")

    if source.name in _SIGNED_BITS and target.name in _UNSIGNED_BITS:
        if source_nonnegative:
            return CastDecision(CastClass.PROVABLE_NARROWING, "signed value is proven non-negative")
        return CastDecision(CastClass.FORBIDDEN, "signed-to-unsigned cast requires a non-negative proof")

    if source.name in _UNSIGNED_BITS and target.name in _SIGNED_BITS:
        if _UNSIGNED_BITS[source.name] < _SIGNED_BITS[target.name]:
            return CastDecision(CastClass.LOSSLESS, "unsigned value fits target signed range")
        return CastDecision(CastClass.FORBIDDEN, "unsigned-to-signed cast requires an upper-bound proof")

    if source.name in _SIGNED_BITS and target.name in _SIGNED_BITS:
        return CastDecision(CastClass.FORBIDDEN, "narrowing signed cast requires a range proof")

    if source.name in _UNSIGNED_BITS and target.name in _UNSIGNED_BITS:
        return CastDecision(CastClass.FORBIDDEN, "narrowing unsigned cast requires a range proof")

    return CastDecision(CastClass.EXPLICIT_NUMERIC, "explicit numeric cast")


def _is_lossless_numeric_cast(source: str, target: str) -> bool:
    if source in _SIGNED_BITS and target in _SIGNED_BITS:
        return _SIGNED_BITS[target] >= _SIGNED_BITS[source]
    if source in _UNSIGNED_BITS and target in _UNSIGNED_BITS:
        return _UNSIGNED_BITS[target] >= _UNSIGNED_BITS[source]
    if source in _UNSIGNED_BITS and target in _SIGNED_BITS:
        return _SIGNED_BITS[target] > _UNSIGNED_BITS[source]
    if source in _FLOAT_BITS and target in _FLOAT_BITS:
        return _FLOAT_BITS[target] >= _FLOAT_BITS[source]
    return False
