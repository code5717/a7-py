"""Exact rational numeric constants: the compiler's only constant folder.

A value is a (Fraction, category) pair. The category is False for an integer
constant, True for a floating constant and 'negative_zero' for a floating zero
with its sign bit set. Binding caches use declaration identity. This module
never follows a declaration recursively or evaluates calls.

Arithmetic is exact: nothing wraps and nothing rounds until `materialize`
fits a use to its destination. No exact value is infinite or NaN. A float
division or remainder by zero raises, and a finite value too large for its
float destination is refused by `ieee_bits`.

Resource accounting is compilation-owned; operations preflight conservative
component growth and charge deterministic limb work.
"""
from enum import Enum
from fractions import Fraction
from dataclasses import dataclass
import weakref
from collections import deque
import struct
from a7.ast_nodes import NodeKind, LiteralKind, UnaryOp, BinaryOp

MAX_DECIMAL_EXPONENT = 4096
MAX_COMPONENT_BITS = 131072
MAX_TRANSIENT_BITS = 262144

_ARITHMETIC = {BinaryOp.ADD, BinaryOp.SUB, BinaryOp.MUL, BinaryOp.DIV, BinaryOp.MOD}
_BITWISE = {BinaryOp.BIT_AND, BinaryOp.BIT_OR, BinaryOp.BIT_XOR, BinaryOp.BIT_SHL, BinaryOp.BIT_SHR}


class ExactArithmeticError(ValueError):
    pass


class ExactResourceCategory(Enum):
    INITIALIZER_WORK = 'initializer_work'
    COMPILATION_WORK = 'compilation_work'
    RETAINED_PAYLOAD = 'retained_payload'
    COMPONENT_BITS = 'component_bits'
    TRANSIENT_BITS = 'transient_bits'
    DEPENDENCY_DEPTH = 'dependency_depth'


class ExactResourceError(ExactArithmeticError):
    def __init__(self, message, *, category=None, initializer_owner=None):
        super().__init__(message)
        self.category = category
        self.initializer_owner = initializer_owner


@dataclass(frozen=True)
class ExactPolicy:
    component_bits: int = 131072
    transient_bits: int = 262144
    initializer_credits: int = 1 << 24
    compilation_credits: int = 1 << 32
    retained_bytes: int = 16 << 20
    dependency_depth: int = 65536
    value_characters: int = 256
    diagnostic_characters: int = 2048
    dependency_links: int = 32


class ExactBudget:
    """One compilation, persistent initializer accounts and owned cache entries."""
    def __init__(self, policy=None):
        self.policy = policy or ExactPolicy()
        self.total = 0
        self.initializers = {}
        self.owners = {}
        self.labels = {}
        self.references = {}
        self.current = None
        self.retained = {}
        self.payload = 0
        self.releases = deque()
        self.watched = {}

    def bind(self, node):
        self.current = self.owners.get(id(node), id(node))
        return self

    def charge(self, amount, operation, compilation_only=False):
        amount = max(1, amount)
        local = self.initializers.get(self.current, 0)
        if not compilation_only and local + amount > self.policy.initializer_credits:
            raise ExactResourceError(f'Exact constant resource limit: {operation} exceeds initializer credits {self.policy.initializer_credits} in {self.labels.get(self.current, "expression")}', category=ExactResourceCategory.INITIALIZER_WORK, initializer_owner=self.current)
        if self.total + amount > self.policy.compilation_credits:
            raise ExactResourceError(f'Exact constant resource limit: {operation} exceeds compilation credits {self.policy.compilation_credits}', category=ExactResourceCategory.COMPILATION_WORK, initializer_owner=self.current)
        if not compilation_only:
            self.initializers[self.current] = local + amount
        self.total += amount

    def retain(self, key, exact, owner=None):
        # Finalizers enqueue only; accounting drains the queue iteratively.
        while self.releases:
            released = self.releases.popleft()
            self.payload -= self.retained.pop(released, 0)
            self.watched.pop(released, None)
        cost = 0 if exact is None else 64 + (exact[0].numerator.bit_length()+7)//8 + (exact[0].denominator.bit_length()+7)//8
        updated = self.payload - self.retained.get(key, 0) + cost
        if updated > self.policy.retained_bytes:
            raise ExactResourceError(f'Exact constant resource limit: retained payload exceeds {self.policy.retained_bytes} bytes', category=ExactResourceCategory.RETAINED_PAYLOAD, initializer_owner=self.current)
        self.payload = updated
        if cost:
            self.retained[key] = cost
            if owner is not None and key not in self.watched:
                self.watched[key] = weakref.finalize(owner, self.releases.append, key)
        else:self.retained.pop(key, None)

    def hit(self, exact):
        self.charge(_limbs(exact[0].numerator.bit_length()+exact[0].denominator.bit_length()), 'cache reference', True)

    def bound(self, bits, operation, scratch=False):
        limit = self.policy.transient_bits if scratch else self.policy.component_bits
        if bits > limit:
            raise ExactResourceError(f'Exact constant resource limit: {operation} exceeds the limit of {limit} bits', category=(ExactResourceCategory.TRANSIENT_BITS if scratch else ExactResourceCategory.COMPONENT_BITS), initializer_owner=self.current)


def _limbs(bits):
    return max(1, (bits+63)//64)


def _integer(operator, a, b, budget, scratch=False):
    """Preflight and charge the actual bigint operation before allocating it."""
    ba, bb = a.bit_length(), b.bit_length()
    if operator in ('add', 'sub', 'and', 'or', 'xor'):
        budget.bound(max(ba, bb)+1, operator, scratch)
        budget.charge(max(_limbs(ba), _limbs(bb)), operator)
    elif operator == 'mul':
        budget.bound(ba+bb, operator, scratch)
        budget.charge(_limbs(ba)*_limbs(bb), operator)
    elif operator in ('div', 'divmod'):
        budget.charge(_limbs(ba)*_limbs(bb), operator)
    elif operator in ('left', 'right'):
        if b < 0:raise ExactArithmeticError('Constant shift count is negative')
        bits = ba+b if operator == 'left' else max(0, ba-b)
        if operator == 'left':budget.bound(bits, 'left shift', scratch)
        budget.charge(_limbs(bits), operator+' shift')
    if operator == 'add':return a+b
    if operator == 'sub':return a-b
    if operator == 'mul':return a*b
    if operator == 'div':return a//b
    if operator == 'divmod':return divmod(a,b)
    if operator == 'left':return a<<b
    if operator == 'right':return (-1 if a < 0 else 0) if b>ba else a>>b
    if operator == 'and':return a&b
    if operator == 'or':return a|b
    return a^b


def _fraction(numerator, denominator, budget):
    # The public constructor performs one gcd-based normalization. Charge that
    # policy row on its unreduced inputs; do not normalize twice.
    budget.charge(2*_limbs(numerator.bit_length())*_limbs(denominator.bit_length()), 'gcd reduction')
    result = Fraction(numerator, denominator)
    budget.bound(max(result.numerator.bit_length(), result.denominator.bit_length()), 'reduced value')
    return result


def _float_literal(raw_text, budget):
    text = raw_text.replace('_', '')
    mantissa, _, exponent = text.lower().partition('e')
    if exponent and abs(int(exponent)) > MAX_DECIMAL_EXPONENT:
        raise ExactArithmeticError(f'Float literal exponent exceeds the limit of {MAX_DECIMAL_EXPONENT}')
    whole, dot, fraction = mantissa.partition('.')
    digits = (whole + fraction).lstrip('+-').lstrip('0') or '0'
    mantissa_bound = (len(digits)*332193+99999)//100000
    budget.bound(mantissa_bound, 'float mantissa')
    scan_limbs = _limbs(mantissa_bound)
    # Decimal token length is bounded by the lexer. Compare its normalized
    # spelling with limb thresholds before converting the mantissa itself.
    while scan_limbs > 1:
        threshold = str(1 << (64 * (scan_limbs - 1)))
        if (len(digits), digits) >= (len(threshold), threshold):
            break
        scan_limbs -= 1
    budget.charge(scan_limbs, 'literal scan')
    numerator = int(digits)
    if mantissa.startswith('-'):numerator = -numerator
    if not numerator:
        return Fraction(0), ('negative_zero' if text.startswith('-') else True)
    scale = int(exponent or '0') - len(fraction)
    power, factor, count = 1, 10, abs(scale)
    while count:
        if count & 1:power = _integer('mul', power, factor, budget)
        count >>= 1
        if count:factor = _integer('mul', factor, factor, budget)
    if scale == 0:
        value = Fraction(numerator)
    elif scale > 0:
        value = Fraction(_integer('mul', numerator, power, budget))
    else:
        value = _fraction(numerator, power, budget)
    return value, ('negative_zero' if not value and text.startswith('-') else True)


def _negative(value, category):
    return value.numerator < 0 or category == 'negative_zero'


def _fold_bitwise(operator, left, right, budget):
    (lv, lf), (rv, rf) = left, right
    if lf or rf:return None
    op = {BinaryOp.BIT_AND:'and', BinaryOp.BIT_OR:'or', BinaryOp.BIT_XOR:'xor', BinaryOp.BIT_SHL:'left', BinaryOp.BIT_SHR:'right'}[operator]
    return Fraction(_integer(op, lv.numerator, rv.numerator, budget)), False


def _fold_arithmetic(operator, left, right, budget):
    (lv, lf), (rv, rf) = left, right
    floating = bool(lf or rf)
    a,b,c,d = lv.numerator,lv.denominator,rv.numerator,rv.denominator
    ln,rn = _negative(lv,lf),_negative(rv,rf)
    if operator in (BinaryOp.ADD,BinaryOp.SUB):
        negative_zero = ln and (rn if operator==BinaryOp.ADD else not rn)
        op = 'add' if operator==BinaryOp.ADD else 'sub'
        if b==d==1:
            result = Fraction(_integer(op,a,c,budget,scratch=floating))
        else:
            # Check all unreduced scratch before allocating any cross-product.
            budget.bound(max(a.bit_length()+d.bit_length(),c.bit_length()+b.bit_length())+1,'rational sum',True)
            budget.bound(b.bit_length()+d.bit_length(),'rational denominator',True)
            left_product=_integer('mul',a,d,budget,True);right_product=_integer('mul',c,b,budget,True)
            denominator=_integer('mul',b,d,budget,True)
            result=_fraction(_integer(op,left_product,right_product,budget,True),denominator,budget)
    elif operator==BinaryOp.MUL:
        budget.bound(a.bit_length()+c.bit_length(),'multiply')
        budget.bound(b.bit_length()+d.bit_length(),'multiply denominator')
        numerator=_integer('mul',a,c,budget)
        result=Fraction(numerator) if b==d==1 else _fraction(numerator,_integer('mul',b,d,budget),budget)
        negative_zero=ln!=rn
    else:
        if not c:
            if not floating:return None
            raise ExactArithmeticError('Constant division by zero' if operator==BinaryOp.DIV else 'Constant remainder by zero')
        if not floating:
            # Integer remainder needs no separately allocated quotient.
            if operator==BinaryOp.MOD:
                budget.charge(_limbs(a.bit_length())*_limbs(c.bit_length()),'remainder')
                result=Fraction(abs(a)%abs(c)*(-1 if a<0 else 1))
            else:
                truncated=_integer('div',abs(a),abs(c),budget)
                if (a<0)!=(c<0):truncated=-truncated
                result=Fraction(truncated)
        else:
            budget.bound(a.bit_length()+d.bit_length(),'rational division')
            budget.bound(b.bit_length()+c.bit_length(),'rational division denominator')
            quotient=_fraction(_integer('mul',a,d,budget),_integer('mul',b,c,budget),budget)
            if operator==BinaryOp.DIV:result=quotient
            else:
                truncated=_integer('div',abs(quotient.numerator),quotient.denominator,budget)
                if quotient.numerator<0:truncated=-truncated
                # Compute remainder as exact a/b - trunc(a/b / c/d) * c/d.
                budget.bound(truncated.bit_length()+c.bit_length(),'remainder product')
                product=_integer('mul',truncated,c,budget)
                budget.bound(max(a.bit_length()+d.bit_length(),product.bit_length()+b.bit_length())+1,'remainder sum',True)
                budget.bound(b.bit_length()+d.bit_length(),'remainder denominator',True)
                numerator=_integer('sub',_integer('mul',a,d,budget,True),_integer('mul',product,b,budget,True),budget,True)
                result=_fraction(numerator,_integer('mul',b,d,budget,True),budget)
        negative_zero=ln!=rn if operator==BinaryOp.DIV else ln
    budget.bound(max(result.numerator.bit_length(), result.denominator.bit_length()), 'reduced value')
    return result, 'negative_zero' if floating and not result and negative_zero else floating


def evaluate(root, lookup, bindings, budget=None):
    """Evaluate one expression with an explicit postorder stack, or return None.

    None means "not an exact constant". ExactArithmeticError means the
    expression is a constant the language rejects; the offending node is
    marked `exact_failed` so a second walk does not report it again.
    """
    if root is None:
        return None
    budget = budget or ExactBudget()
    values = {}
    stack = [(root, False)]
    token = object()
    try:
        while stack:
            node, ready = stack.pop()
            if getattr(node, 'exact_failed', False):
                return None
            key = id(node)
            saved = getattr(node, 'exact_constant', None)
            try:
                if saved is not None:
                    budget.hit(saved)
                    values[key] = saved
                elif node.kind == NodeKind.LITERAL:
                    if node.literal_kind == LiteralKind.INTEGER:
                        budget.bound(node.literal_value.bit_length(), "integer literal")
                        budget.charge(_limbs(node.literal_value.bit_length()), "literal scan")
                        values[key] = (Fraction(node.literal_value), False)
                    elif node.literal_kind == LiteralKind.FLOAT:
                        values[key] = _float_literal(node.raw_text, budget)
                    else:
                        return None
                elif node.kind == NodeKind.IDENTIFIER:
                    symbol = lookup(node.name)
                    value = bindings.get(id(symbol.node)) if symbol and symbol.node else None
                    if value is None:
                        return None
                    budget.hit(value)
                    budget.references.setdefault(budget.current, set()).add(id(symbol.node))
                    values[key] = value
                elif node.kind == NodeKind.FIELD_ACCESS and node.object is not None and node.object.kind == NodeKind.IDENTIFIER:
                    symbol = lookup(f"{node.object.name}.{node.field}")
                    value = bindings.get(id(symbol.node)) if symbol and symbol.node else None
                    if value is None:
                        return None
                    budget.hit(value)
                    budget.references.setdefault(budget.current, set()).add(id(symbol.node))
                    values[key] = value
                    budget.retain(("ast", id(node)), value, node)
                    node.exact_constant = value
                elif node.kind == NodeKind.UNARY and node.operator == UnaryOp.NEG:
                    # `~` is not folded here: `flags & ~1` on a `u8` relies on
                    # the typed operator, and -2 would not fit `u8`.
                    if not ready:
                        stack.extend([(node, True), (node.operand, False)])
                        continue
                    value, category = values.pop(id(node.operand))
                    budget.retain(("evaluation", token, id(node.operand)), None)
                    budget.charge(_limbs(value.numerator.bit_length()), "negation")
                    if category and not value:
                        values[key] = (value, True if category == 'negative_zero' else 'negative_zero')
                    else:
                        values[key] = (-value, category)
                elif node.kind == NodeKind.BINARY and node.operator in _ARITHMETIC | _BITWISE:
                    if not ready:
                        stack.extend([(node, True), (node.right, False), (node.left, False)])
                        continue
                    fold = _fold_arithmetic if node.operator in _ARITHMETIC else _fold_bitwise
                    result = fold(node.operator, values[id(node.left)], values[id(node.right)], budget)
                    budget.retain(("evaluation", token, id(node.left)), None)
                    budget.retain(("evaluation", token, id(node.right)), None)
                    values.pop(id(node.left), None)
                    values.pop(id(node.right), None)
                    if result is None:
                        return None
                    if max(result[0].numerator.bit_length(), result[0].denominator.bit_length()) > budget.policy.component_bits:
                        raise ExactResourceError(
                            f'Exact constant exceeds the limit of {budget.policy.component_bits} bits',
                            category=ExactResourceCategory.COMPONENT_BITS,
                            initializer_owner=budget.current
                        )
                    values[key] = result
                else:
                    return None
                budget.retain(("evaluation", token, key), values[key])
            except ExactArithmeticError:
                node.exact_failed = True
                raise
        return values[id(root)]
    finally:
        for key in values:
            budget.retain(("evaluation", token, key), None)


def compare(operator, left, right, budget=None):
    """Compare reduced values with bounded cross-products."""
    budget = budget or ExactBudget()
    a,b=left[0],right[0]
    budget.bound(a.numerator.bit_length()+b.denominator.bit_length(),'comparison',True)
    budget.bound(b.numerator.bit_length()+a.denominator.bit_length(),'comparison',True)
    budget.charge(_limbs(a.numerator.bit_length())*_limbs(b.denominator.bit_length()) + _limbs(b.numerator.bit_length())*_limbs(a.denominator.bit_length()), 'cross comparison')
    l = a.numerator*b.denominator
    r = b.numerator*a.denominator
    if operator==BinaryOp.EQ:return l==r
    if operator==BinaryOp.NE:return l!=r
    if operator==BinaryOp.LT:return l<r
    if operator==BinaryOp.LE:return l<=r
    if operator==BinaryOp.GT:return l>r
    return l>=r


def _render_integer(number):
    bits=number.bit_length()
    estimated=(bits*30103+99999)//100000+1
    if estimated<=600:
        try:text=str(number)
        except ValueError:text=hex(number)
        if len(text)<=100:return text
    text=hex(number)
    return f'{text[:32]}...{text[-24:]} ({(bits+3)//4} hex digits, {bits} bits, ~10^{max(0,estimated-1)})'


def render(value, policy=None):
    text=_render_integer(value.numerator)
    if value.denominator!=1:text+='/'+_render_integer(value.denominator)
    limit = (policy or ExactPolicy()).value_characters
    return text if len(text)<=limit else text[:limit//2-2]+"..."+text[-(limit-limit//2-1):]


def ieee_bits(exact, width, budget=None):
    """Round a rational directly to IEEE nearest, ties to even, using integers."""
    budget = budget or ExactBudget()
    value, category = exact
    budget.charge(_limbs(value.numerator.bit_length()+value.denominator.bit_length()), "rounding scan")
    precision, emin, emax, bias = (24, -126, 127, 127) if width == 32 else (53, -1022, 1023, 1023)
    sign = _integer('left', int(value.numerator < 0 or category == 'negative_zero'), width - 1, budget)
    numerator, denominator = abs(value.numerator), value.denominator
    if not numerator:
        return sign
    exponent = numerator.bit_length() - denominator.bit_length()
    budget.charge(max(_limbs(numerator.bit_length()), _limbs(denominator.bit_length())), 'rounding exponent comparison')
    if exponent >= 0:
        if numerator < _integer('left', denominator, exponent, budget):
            exponent -= 1
    elif _integer('left', numerator, -exponent, budget) < denominator:
        exponent -= 1
    # Quantize at the normal exponent or at the subnormal spacing.
    shift = max(exponent, emin) - (precision - 1)
    if shift >= 0:
        denominator = _integer('left', denominator, shift, budget)
    else:
        numerator = _integer('left', numerator, -shift, budget)
    significand, remainder = _integer('divmod', numerator, denominator, budget)
    twice = _integer('mul', 2, remainder, budget)
    budget.charge(max(_limbs(twice.bit_length()), _limbs(denominator.bit_length())), 'rounding comparison')
    round_up = twice > denominator
    if not round_up:
        budget.charge(max(_limbs(twice.bit_length()), _limbs(denominator.bit_length())), 'rounding equality comparison')
        round_up = twice == denominator and bool(_integer('and', significand, 1, budget))
    if round_up:
        significand = _integer('add', significand, 1, budget)
    carry = _integer('left', 1, precision, budget)
    budget.charge(max(_limbs(significand.bit_length()), _limbs(carry.bit_length())), 'rounding carry comparison')
    if significand == carry:
        significand = _integer('right', significand, 1, budget)
        exponent += 1
    if exponent > emax:
        raise ExactArithmeticError(f'Finite exact constant overflows f{width}')
    leading = _integer('left', 1, precision - 1, budget)
    budget.charge(max(_limbs(significand.bit_length()), _limbs(leading.bit_length())), 'rounding normal comparison')
    if significand < leading:
        return _integer('or', sign, significand, budget)
    encoded_exponent = _integer('left', max(exponent, emin) + bias, precision - 1, budget)
    trailing = _integer('sub', significand, leading, budget)
    return _integer('or', _integer('or', sign, encoded_exponent, budget), trailing, budget)


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


def materialize(node, exact, integer=False, width=None, budget=None):
    """Replace one use; retain its rational until its destination is known."""
    budget = budget or ExactBudget()
    value, floating = exact
    budget.retain(("ast", id(node)), exact, node)
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
            bits = ieee_bits(exact, target, budget)
        except ExactResourceError:
            raise
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
