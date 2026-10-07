"""Exact rational numeric constants: the compiler's only constant folder.

A value is a (Fraction, category) pair. The category is False for an integer
constant, True for a floating constant and 'negative_zero' for a floating zero
with its sign bit set. Binding caches use declaration identity. This module
never follows a declaration recursively or evaluates calls.

Arithmetic is exact: nothing wraps and nothing rounds until `materialize`
fits a use to its destination. No exact value is infinite or NaN. A float
division or remainder by zero raises, and a finite value too large for its
float destination is refused by `ieee_bits`.

Resource caps come from SPEC Appendix C. The work-credit and cache-size caps
listed there are not enforced here.
"""
from fractions import Fraction
import struct
from a7.ast_nodes import NodeKind, LiteralKind, UnaryOp, BinaryOp

MAX_DECIMAL_EXPONENT = 4096
MAX_COMPONENT_BITS = 131072
MAX_TRANSIENT_BITS = 262144

_ARITHMETIC = {BinaryOp.ADD, BinaryOp.SUB, BinaryOp.MUL, BinaryOp.DIV, BinaryOp.MOD}
_BITWISE = {BinaryOp.BIT_AND, BinaryOp.BIT_OR, BinaryOp.BIT_XOR, BinaryOp.BIT_SHL, BinaryOp.BIT_SHR}


class ExactArithmeticError(ValueError):
    pass


def _float_literal(raw_text):
    """Exact value of a float token, refusing an exponent beyond the cap.

    The exponent is checked on the token text: `Fraction('1e999999999')`
    would first build a billion-digit integer.
    """
    text = raw_text.replace('_', '')
    mantissa, _, exponent = text.lower().partition('e')
    if exponent and abs(int(exponent)) > MAX_DECIMAL_EXPONENT:
        raise ExactArithmeticError(
            f'Float literal exponent exceeds the limit of {MAX_DECIMAL_EXPONENT}'
        )
    value = Fraction(text)
    return value, ('negative_zero' if not value and text.startswith('-') else True)


def _negative(value, category):
    return value < 0 or category == 'negative_zero'


def _fold_bitwise(operator, left, right):
    """Bitwise and shift operators on mathematical integers, or None."""
    (lv, lf), (rv, rf) = left, right
    if lf or rf:
        # A floating-category operand is the checker's integer-type error.
        return None
    a, b = lv.numerator, rv.numerator
    if operator == BinaryOp.BIT_AND:
        return Fraction(a & b), False
    if operator == BinaryOp.BIT_OR:
        return Fraction(a | b), False
    if operator == BinaryOp.BIT_XOR:
        return Fraction(a ^ b), False
    if b < 0:
        raise ExactArithmeticError('Constant shift count is negative')
    if operator == BinaryOp.BIT_SHL:
        if a.bit_length() + b > MAX_TRANSIENT_BITS:
            raise ExactArithmeticError(
                f'Exact constant exceeds the limit of {MAX_COMPONENT_BITS} bits'
            )
        return Fraction(a << b), False
    # Every bit is shifted out once the count passes the operand's length.
    if b > a.bit_length():
        return Fraction(-1 if a < 0 else 0), False
    return Fraction(a >> b), False


def _fold_arithmetic(operator, left, right):
    """Exact `+ - * / %`, or None for an integer division by zero."""
    (lv, lf), (rv, rf) = left, right
    floating = bool(lf or rf)
    ln, rn = _negative(lv, lf), _negative(rv, rf)
    if operator == BinaryOp.ADD:
        result, negative_zero = lv + rv, ln and rn
    elif operator == BinaryOp.SUB:
        result, negative_zero = lv - rv, ln and not rn
    elif operator == BinaryOp.MUL:
        result, negative_zero = lv * rv, ln != rn
    else:
        if not rv:
            if not floating:
                # The safety pass owns integer zero divisors and reports
                # them as an unproven divisor.
                return None
            raise ExactArithmeticError(
                'Constant division by zero' if operator == BinaryOp.DIV
                else 'Constant remainder by zero'
            )
        quotient = lv / rv
        truncated = abs(quotient.numerator) // quotient.denominator
        if quotient < 0:
            truncated = -truncated
        if operator == BinaryOp.DIV:
            result = quotient if floating else Fraction(truncated)
            negative_zero = ln != rn
        else:
            result, negative_zero = lv - truncated * rv, ln
    if floating and not result and negative_zero:
        return result, 'negative_zero'
    return result, floating


def evaluate(root, lookup, bindings):
    """Evaluate one expression with an explicit postorder stack, or return None.

    None means "not an exact constant". ExactArithmeticError means the
    expression is a constant the language rejects; the offending node is
    marked `exact_failed` so a second walk does not report it again.
    """
    if root is None:
        return None
    values = {}
    stack = [(root, False)]
    while stack:
        node, ready = stack.pop()
        if getattr(node, 'exact_failed', False):
            return None
        key = id(node)
        saved = getattr(node, 'exact_constant', None)
        try:
            if saved is not None:
                values[key] = saved
            elif node.kind == NodeKind.LITERAL:
                if node.literal_kind == LiteralKind.INTEGER:
                    values[key] = (Fraction(node.literal_value), False)
                elif node.literal_kind == LiteralKind.FLOAT:
                    values[key] = _float_literal(node.raw_text)
                else:
                    return None
            elif node.kind == NodeKind.IDENTIFIER:
                symbol = lookup(node.name)
                value = bindings.get(id(symbol.node)) if symbol and symbol.node else None
                if value is None:
                    return None
                values[key] = value
            elif node.kind == NodeKind.FIELD_ACCESS and node.object is not None and node.object.kind == NodeKind.IDENTIFIER:
                symbol = lookup(f"{node.object.name}.{node.field}")
                value = bindings.get(id(symbol.node)) if symbol and symbol.node else None
                if value is None:
                    return None
                values[key] = value
                node.exact_constant = value
            elif node.kind == NodeKind.UNARY and node.operator == UnaryOp.NEG:
                # `~` is not folded here: `flags & ~1` on a `u8` relies on
                # the typed operator, and -2 would not fit `u8`.
                if not ready:
                    stack.extend([(node, True), (node.operand, False)])
                    continue
                value, category = values[id(node.operand)]
                if category and not value:
                    values[key] = (value, True if category == 'negative_zero' else 'negative_zero')
                else:
                    values[key] = (-value, category)
            elif node.kind == NodeKind.BINARY and node.operator in _ARITHMETIC | _BITWISE:
                if not ready:
                    stack.extend([(node, True), (node.right, False), (node.left, False)])
                    continue
                fold = _fold_arithmetic if node.operator in _ARITHMETIC else _fold_bitwise
                result = fold(node.operator, values[id(node.left)], values[id(node.right)])
                if result is None:
                    return None
                if max(result[0].numerator.bit_length(), result[0].denominator.bit_length()) > MAX_COMPONENT_BITS:
                    raise ExactArithmeticError(
                        f'Exact constant exceeds the limit of {MAX_COMPONENT_BITS} bits'
                    )
                values[key] = result
            else:
                return None
        except ExactArithmeticError:
            node.exact_failed = True
            raise
    return values[id(root)]


def compare(operator, left, right):
    """Compare two exact values. The two float zeros are equal."""
    a, b = left[0], right[0]
    if operator == BinaryOp.EQ:
        return a == b
    if operator == BinaryOp.NE:
        return a != b
    if operator == BinaryOp.LT:
        return a < b
    if operator == BinaryOp.LE:
        return a <= b
    if operator == BinaryOp.GT:
        return a > b
    return a >= b


def _render_integer(number):
    """Decimal text with the middle elided once it passes 39 digits.

    Python refuses `str()` on an integer longer than 4300 digits, so the
    digits come from integer division instead.
    """
    if number.bit_length() <= 128:
        return str(number)
    magnitude = abs(number)
    digits = int(magnitude.bit_length() * 0.30103) + 1
    while 10 ** (digits - 1) > magnitude:
        digits -= 1
    while 10 ** digits <= magnitude:
        digits += 1
    sign = '-' if number < 0 else ''
    head = magnitude // 10 ** (digits - 12)
    tail = magnitude % 10 ** 12
    return f'{sign}{head}...{tail:012d} ({digits} digits)'


def render(value):
    """Bounded text of an exact value for diagnostics."""
    if value.denominator == 1:
        return _render_integer(value.numerator)
    return f'{_render_integer(value.numerator)}/{_render_integer(value.denominator)}'


def ieee_bits(exact, width):
    """Round a rational directly to IEEE nearest, ties to even, using integers."""
    value, category = exact
    precision, emin, emax, bias = (24, -126, 127, 127) if width == 32 else (53, -1022, 1023, 1023)
    sign = int(value < 0 or category == 'negative_zero') << (width - 1)
    numerator, denominator = abs(value.numerator), value.denominator
    if not numerator:
        return sign
    exponent = numerator.bit_length() - denominator.bit_length()
    if exponent >= 0:
        if numerator < denominator << exponent:
            exponent -= 1
    elif numerator << -exponent < denominator:
        exponent -= 1
    # Quantize at the normal exponent or at the subnormal spacing.
    shift = max(exponent, emin) - (precision - 1)
    if shift >= 0:
        denominator <<= shift
    else:
        numerator <<= -shift
    significand, remainder = divmod(numerator, denominator)
    if 2 * remainder > denominator or (2 * remainder == denominator and significand & 1):
        significand += 1
    if significand == 1 << precision:
        significand >>= 1
        exponent += 1
    if exponent > emax:
        raise ExactArithmeticError(f'Finite exact constant overflows f{width}')
    if significand < 1 << (precision - 1):
        return sign | significand
    return sign | ((max(exponent, emin) + bias) << (precision - 1)) | (significand - (1 << (precision - 1)))


def expression_span(root):
    """Locate the first source operand when an operator has no parser span."""
    stack = [root]
    while stack:
        node = stack.pop()
        if node.span is not None:
            return node.span
        for name in ('right', 'left', 'operand'):
            child = getattr(node, name, None)
            if child is not None:
                stack.append(child)
    return None


def materialize(node, exact, integer=False, width=None):
    """Replace one use; retain its rational until its destination is known."""
    value, floating = exact
    node.span = expression_span(node)
    node.exact_constant = exact
    node.exact_materialized = True
    node.kind = NodeKind.LITERAL
    node.literal_kind = LiteralKind.FLOAT if (floating or width) and not integer else LiteralKind.INTEGER
    node.exact_float_bits = None
    node.exact_float_error = None
    if node.literal_kind == LiteralKind.INTEGER:
        node.literal_value = value.numerator
        node.raw_text = str(value.numerator)
    else:
        target = width or 64
        try:
            bits = ieee_bits(exact, target)
        except ExactArithmeticError as error:
            # A later integer or float destination may still replace this use.
            node.exact_float_error = str(error)
            node.literal_value = 0.0
            node.raw_text = '0.0'
        else:
            node.exact_float_bits = (target, bits)
            node.literal_value = struct.unpack('>f' if target == 32 else '>d', bits.to_bytes(target // 8, 'big'))[0]
            node.raw_text = repr(node.literal_value)
    node.left = node.right = node.operand = None
    node.name = None
