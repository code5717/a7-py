"""
Exact constant evaluation for literal folding.

The preprocessor folds operators whose operands are literals. A fold is an
optimization only: when this module returns None the node stays unfolded and
the backend emits the expression, so run-time (or Zig comptime) evaluation
decides the result exactly as it would without folding.

Rules:
- Integers use Python ints, so there is no precision loss. `/` and `%`
  truncate toward zero, matching Zig `@divTrunc` and `@rem`.
- An integer result folds only when it fits the node's type. Without a type
  entry the checker's literal default, i32, is used.
- Shifts fold only when 0 <= amount < width of that type.
- Floats fold in IEEE double precision, the type of every A7 float literal.
  A non-finite result (infinity or NaN) is a value like any other and folds:
  leaving it unfolded would hand the expression to Zig, which evaluates bare
  float literals as `comptime_float`, that is f128, where an f64 overflow is
  an ordinary finite number and every answer derived from it changes.
"""

import math
from typing import Optional, Union

from .ast_nodes import BinaryOp, UnaryOp
from .types import INTEGER_BIT_WIDTHS, PrimitiveType, SIGNED_INTEGER_WIDTHS, Type

Number = Union[int, float]

# Alias onto the canonical a7.types tables. Values flow from the single
# source; the old name stays so integer_layout and its callers are untouched.
_INTEGER_LAYOUT = {
    name: (width, name in SIGNED_INTEGER_WIDTHS)
    for name, width in INTEGER_BIT_WIDTHS.items()
}

_DEFAULT_INTEGER_TYPE = 'i32'


def integer_layout(type_: Optional[Type]) -> Optional[tuple]:
    """Return (width, min, max) for an integer type, or None.

    A missing type (None) uses the literal default i32. Any other
    non-integer type returns None, which blocks integer folding.
    """
    if type_ is None:
        name = _DEFAULT_INTEGER_TYPE
    elif isinstance(type_, PrimitiveType) and type_.name in _INTEGER_LAYOUT:
        name = type_.name
    else:
        return None
    width, signed = _INTEGER_LAYOUT[name]
    if signed:
        return width, -(1 << (width - 1)), (1 << (width - 1)) - 1
    return width, 0, (1 << width) - 1


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _fit_integer(result: int, type_: Optional[Type]) -> Optional[int]:
    layout = integer_layout(type_)
    if layout is None:
        return None
    _, low, high = layout
    if low <= result <= high:
        return result
    return None


def truncating_divmod(left: int, right: int) -> tuple:
    """Quotient rounded toward zero and the matching remainder."""
    quotient = abs(left) // abs(right)
    if (left < 0) != (right < 0):
        quotient = -quotient
    return quotient, left - quotient * right


def fold_unary(op: UnaryOp, value, type_: Optional[Type]) -> Optional[Number]:
    """Fold numeric negation. Returns None when the node must stay unfolded."""
    if op != UnaryOp.NEG or not _is_number(value):
        return None
    if _is_int(value):
        return _fit_integer(-value, type_)
    return -value


def fold_binary(op: BinaryOp, left, right, type_: Optional[Type]) -> Optional[Number]:
    """Fold a numeric binary operator on two literal values.

    Returns None when the operator is not numeric arithmetic or bitwise, or
    when the result cannot be represented by the node's type.
    """
    if not (_is_number(left) and _is_number(right)):
        return None

    if _is_int(left) and _is_int(right):
        return _fold_integer_binary(op, left, right, type_)

    try:
        if op == BinaryOp.ADD:
            result = left + right
        elif op == BinaryOp.SUB:
            result = left - right
        elif op == BinaryOp.MUL:
            result = left * right
        elif op == BinaryOp.DIV and right != 0:
            result = left / right
        elif op == BinaryOp.MOD and right != 0:
            result = math.nan if math.isinf(left) else math.fmod(left, right)
        else:
            return None
    except (ZeroDivisionError, OverflowError):
        # An int operand too large for a Python float has no f64 value to
        # fold to; leave the expression alone.
        return None
    return float(result)


def _fold_integer_binary(op: BinaryOp, left: int, right: int,
                         type_: Optional[Type]) -> Optional[int]:
    layout = integer_layout(type_)
    if layout is None:
        return None
    width = layout[0]

    if op == BinaryOp.ADD:
        result = left + right
    elif op == BinaryOp.SUB:
        result = left - right
    elif op == BinaryOp.MUL:
        result = left * right
    elif op == BinaryOp.DIV and right != 0:
        result = truncating_divmod(left, right)[0]
    elif op == BinaryOp.MOD and right != 0:
        result = truncating_divmod(left, right)[1]
    elif op == BinaryOp.BIT_AND:
        result = left & right
    elif op == BinaryOp.BIT_OR:
        result = left | right
    elif op == BinaryOp.BIT_XOR:
        result = left ^ right
    elif op == BinaryOp.BIT_SHL and 0 <= right < width:
        result = left << right
    elif op == BinaryOp.BIT_SHR and 0 <= right < width:
        result = left >> right
    else:
        return None
    return _fit_integer(result, type_)
