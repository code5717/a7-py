"""Experimental exact rational numeric constants. No resource-policy qualification.

Values are (Fraction, floating-category) pairs. Binding caches use declaration
identity. This module never follows a declaration recursively or evaluates calls.

Non-finite floats (inf, -inf, NaN) cannot live in a Fraction, so a float
operation whose per-operation f64 result is non-finite stores the sentinel
(Fraction(0), True) as its value and records the truth in two node
attributes: `exact_nonfinite` ('inf', 'ninf' or 'nan') and `exact_f64` (the
f64 value). Single float literals never carry `exact_nonfinite`, so a lone
overflowing literal still rejects at materialization instead of silently
becoming infinity. Every node the walk visits also gets `exact_f64`, the
per-operation f64 mirror the runtime computes, which comparison folding
reads instead of comparing raw rationals.
"""
from fractions import Fraction
import math
import struct
from a7.ast_nodes import NodeKind, LiteralKind, UnaryOp, BinaryOp


def _nonfinite_kind(f):
    """Classify an f64 value, or return None when it is finite."""
    if math.isnan(f):
        return 'nan'
    if math.isinf(f):
        return 'inf' if f > 0 else 'ninf'
    return None


def _float_or_inf(value):
    """float() that saturates to signed infinity instead of raising."""
    try:
        return float(value)
    except OverflowError:
        return float('inf') if value > 0 else float('-inf')


def _shadow_of(node, pair):
    """Per-operation f64 mirror of an exact value.

    Prefers the stamp the walk left on the node (per-operation rounded);
    derives from the pair only for nodes that never fold (finite pairs).
    """
    nn = getattr(node, 'exact_nonfinite', None)
    if nn == 'nan':
        return float('nan')
    if nn == 'inf':
        return float('inf')
    if nn == 'ninf':
        return float('-inf')
    stamped = getattr(node, 'exact_f64', None)
    if stamped is not None:
        return stamped
    return _float_or_inf(pair[0])


def _ieee_binary(operator, fl, fr):
    """One f64 operation with IEEE edge semantics; never raises."""
    if math.isnan(fl) or math.isnan(fr):
        return float('nan')
    try:
        if operator == BinaryOp.ADD:
            return fl + fr
        if operator == BinaryOp.SUB:
            return fl - fr
        if operator == BinaryOp.MUL:
            return fl * fr
        if operator == BinaryOp.DIV:
            return fl / fr
        # MOD mirrors const_eval.fold_binary: NaN for an infinite dividend.
        if math.isinf(fl):
            return float('nan')
        return math.fmod(fl, fr)
    except (ZeroDivisionError, ValueError):
        if operator == BinaryOp.DIV and fl != 0.0:
            return math.copysign(float('inf'), fl) * math.copysign(1.0, fr)
        return float('nan')


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
                node.exact_f64 = _float_or_inf(node.literal_value)
            elif node.literal_kind == LiteralKind.FLOAT:
                value = Fraction(node.raw_text)
                floating = 'negative_zero' if not value and node.raw_text.startswith('-') else True
                values[key] = (value, floating)
                node.exact_f64 = float(node.raw_text)
            else:
                return None
        elif node.kind == NodeKind.IDENTIFIER:
            symbol = lookup(node.name)
            value = bindings.get(id(symbol.node)) if symbol and symbol.node else None
            if value is None:
                return None
            values[key] = value
            # A use inherits a non-finite declaration's truth, since the
            # sentinel pair alone cannot tell infinity from NaN.
            decl_nonfinite = getattr(symbol.node, 'exact_nonfinite', None) if symbol and symbol.node else None
            if decl_nonfinite is not None:
                node.exact_nonfinite = decl_nonfinite
            node.exact_f64 = _shadow_of(symbol.node, value) if symbol and symbol.node else _float_or_inf(value[0])
        elif node.kind == NodeKind.UNARY and node.operator == UnaryOp.NEG:
            if not ready:
                stack.extend([(node, True), (node.operand, False)])
            else:
                value, floating = values[id(node.operand)]
                values[key] = (-value, ('negative_zero' if floating != 'negative_zero' else True) if floating and not value else floating)
                operand_shadow = _shadow_of(node.operand, values[id(node.operand)])
                node.exact_f64 = -operand_shadow
                operand_nonfinite = getattr(node.operand, 'exact_nonfinite', None)
                if operand_nonfinite is not None:
                    if operand_nonfinite == 'inf':
                        operand_nonfinite = 'ninf'
                    elif operand_nonfinite == 'ninf':
                        operand_nonfinite = 'inf'
                    node.exact_nonfinite = operand_nonfinite
                    values[key] = (Fraction(0), True)
        elif node.kind == NodeKind.BINARY and node.operator in {BinaryOp.ADD, BinaryOp.SUB, BinaryOp.MUL, BinaryOp.DIV, BinaryOp.MOD}:
            if not ready:
                stack.extend([(node, True), (node.right, False), (node.left, False)])
            else:
                left, lf = values[id(node.left)]
                right, rf = values[id(node.right)]
                float_ctx = bool(lf or rf)
                left_nonfinite = getattr(node.left, 'exact_nonfinite', None)
                right_nonfinite = getattr(node.right, 'exact_nonfinite', None)
                fl = _shadow_of(node.left, (left, lf))
                fr = _shadow_of(node.right, (right, rf))
                if left_nonfinite is not None or right_nonfinite is not None:
                    # A non-finite operand makes the exact rational
                    # meaningless; fold in f64 exactly like the runtime does.
                    f = _ieee_binary(node.operator, fl, fr)
                    node.exact_nonfinite = _nonfinite_kind(f) or 'nan'
                    node.exact_f64 = f
                    values[key] = (Fraction(0), True)
                elif node.operator in {BinaryOp.ADD, BinaryOp.SUB, BinaryOp.MUL}:
                    if node.operator == BinaryOp.ADD:
                        result = left + right
                    elif node.operator == BinaryOp.SUB:
                        result = left - right
                    else:
                        result = left * right
                    if (
                        not lf and not rf
                        and result.denominator == 1
                        and left.denominator == 1 and right.denominator == 1
                        and -(2 ** 31) <= left.numerator < 2 ** 31
                        and -(2 ** 31) <= right.numerator < 2 ** 31
                    ):
                        # Both operands fit i32, so the fold wraps the way the
                        # runtime operator does instead of growing unbounded.
                        result = Fraction(((result.numerator + 2 ** 31) % 2 ** 32) - 2 ** 31)
                    floating = bool(lf or rf)
                    if not result and floating:
                        ln = left < 0 or lf == 'negative_zero'
                        rn = right < 0 or rf == 'negative_zero'
                        if node.operator == BinaryOp.ADD:
                            negative = ln and rn
                        else:
                            negative = ln and not rn
                        if negative:
                            floating = 'negative_zero'
                    values[key] = (result, floating)
                    f = _ieee_binary(node.operator, fl, fr) if float_ctx else _float_or_inf(result)
                    non = _nonfinite_kind(f) if float_ctx else None
                    node.exact_f64 = f
                    if non is not None:
                        # Finite rationals overflowed f64: the truth is now
                        # the infinite shadow, not the exact quotient.
                        node.exact_nonfinite = non
                        values[key] = (Fraction(0), True)
                else:
                    if not right:
                        if not float_ctx:
                            # An integer zero divisor is the safety pass's
                            # proof domain, not the evaluator's: return
                            # non-exact so the DIVISOR_NONZERO diagnostic
                            # reports it instead.
                            return None
                        # A float zero divisor folds per IEEE: x/0 is signed
                        # infinity, 0/0 and x%0 are NaN.
                        f = _ieee_binary(node.operator, fl, fr)
                        node.exact_nonfinite = _nonfinite_kind(f) or 'nan'
                        node.exact_f64 = f
                        values[key] = (Fraction(0), True)
                    else:
                        quotient = left / right
                        truncated = abs(quotient.numerator) // quotient.denominator
                        if quotient < 0:
                            truncated = -truncated
                        result = (quotient if lf or rf else Fraction(truncated)) if node.operator == BinaryOp.DIV else left - truncated * right
                        floating = bool(lf or rf)
                        if not result and floating:
                            ln = left < 0 or lf == 'negative_zero'
                            rn = right < 0 or rf == 'negative_zero'
                            negative = (ln != rn) if node.operator == BinaryOp.DIV else ln
                            if negative:
                                floating = 'negative_zero'
                        values[key] = (result, floating)
                        f = _ieee_binary(node.operator, fl, fr) if float_ctx else _float_or_inf(result)
                        non = _nonfinite_kind(f) if float_ctx else None
                        node.exact_f64 = f
                        if non is not None:
                            node.exact_nonfinite = non
                            values[key] = (Fraction(0), True)
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
        nonfinite = getattr(node, 'exact_nonfinite', None)
        if nonfinite is not None:
            # The f64 truth was recorded at fold time; single literals never
            # carry this mark, so a lone overflowing literal still rejects
            # below instead of silently becoming infinity.
            if nonfinite == 'nan':
                bits = 0x7FF8000000000000 if target == 64 else 0x7FC00000
                literal_value = float('nan')
            else:
                sign = 1 if nonfinite == 'ninf' else 0
                bits = (0x7FF0000000000000 if target == 64 else 0x7F800000) | (sign << (target - 1))
                literal_value = float('-inf') if sign else float('inf')
            node.exact_float_bits = (target, bits)
            node.literal_value = literal_value
            node.raw_text = repr(literal_value)
            node.left = node.right = node.operand = None
            node.name = None
            return
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
