"""Experimental exact rational numeric constants. No resource-policy qualification.

Values are (Fraction, floating-category) pairs. Binding caches use declaration
identity. This module never follows a declaration recursively or evaluates calls.
"""
from fractions import Fraction
import struct
from a7.ast_nodes import NodeKind, LiteralKind, UnaryOp, BinaryOp


def evaluate(root, lookup, bindings):
    """Evaluate one expression with an explicit postorder stack, or return None."""
    if root is None:
        return None
    values = {}
    stack = [(root, False)]
    while stack:
        node, ready = stack.pop()
        key = id(node)
        saved = getattr(node, 'exact_constant', None)
        if saved is not None:
            values[key] = saved
        elif node.kind == NodeKind.LITERAL:
            if node.literal_kind == LiteralKind.INTEGER:
                values[key] = (Fraction(node.literal_value), False)
            elif node.literal_kind == LiteralKind.FLOAT:
                value = Fraction(node.raw_text)
                floating = 'negative_zero' if not value and node.raw_text.startswith('-') else True
                values[key] = (value, floating)
            else:
                return None
        elif node.kind == NodeKind.IDENTIFIER:
            symbol = lookup(node.name)
            value = bindings.get(id(symbol.node)) if symbol and symbol.node else None
            if value is None:
                return None
            values[key] = value
        elif node.kind == NodeKind.UNARY and node.operator == UnaryOp.NEG:
            if not ready:
                stack.extend([(node, True), (node.operand, False)])
            else:
                value, floating = values[id(node.operand)]
                values[key] = (-value, ('negative_zero' if floating != 'negative_zero' else True) if floating and not value else floating)
        elif node.kind == NodeKind.BINARY and node.operator in {BinaryOp.ADD, BinaryOp.SUB, BinaryOp.MUL, BinaryOp.DIV, BinaryOp.MOD}:
            if not ready:
                stack.extend([(node, True), (node.right, False), (node.left, False)])
            else:
                left, lf = values[id(node.left)]
                right, rf = values[id(node.right)]
                if node.operator == BinaryOp.ADD:
                    result = left + right
                elif node.operator == BinaryOp.SUB:
                    result = left - right
                elif node.operator == BinaryOp.MUL:
                    result = left * right
                else:
                    if not right:
                        raise ExactArithmeticError('Exact constant division or remainder by zero')
                    quotient = left / right
                    truncated = abs(quotient.numerator) // quotient.denominator
                    if quotient < 0:
                        truncated = -truncated
                    result = (quotient if lf or rf else Fraction(truncated)) if node.operator == BinaryOp.DIV else left - truncated * right
                floating = bool(lf or rf)
                if not result and floating:
                    ln = left < 0 or lf == 'negative_zero'
                    rn = right < 0 or rf == 'negative_zero'
                    negative = (ln != rn) if node.operator in {BinaryOp.MUL, BinaryOp.DIV} else ln if node.operator == BinaryOp.MOD else (ln and (rn if node.operator == BinaryOp.ADD else not rn))
                    if negative:
                        floating = 'negative_zero'
                values[key] = (result, floating)
        else:
            return None
    return values[id(root)]


class ExactArithmeticError(ValueError):
    pass


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
