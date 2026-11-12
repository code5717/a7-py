"""Policy limits reject at semantic analysis before oversized arithmetic runs."""
from fractions import Fraction

import pytest

import a7.exact_constants as constants
import a7.passes.type_checker as checker
from a7.ast_nodes import BinaryOp
from a7.exact_constants import ExactBudget, ExactPolicy, ExactResourceError
from conftest import expect_exit, expect_ok, parse_program


def test_conservative_product_preflight_precedes_python_multiplication():
    class Operand(int):
        def __mul__(self, other):
            pytest.fail('oversized product allocated')
    budget = ExactBudget(ExactPolicy(component_bits=8))
    with pytest.raises(ExactResourceError, match='8 bits'):
        constants._integer('mul', Operand(8), Operand(16), budget)
    assert budget.total == 0
    assert constants._integer('mul', 8, 8, budget) == 64


def test_rational_scratch_preflight_precedes_fraction_construction(monkeypatch):
    left, right = (Fraction(1, 2), True), (Fraction(1, 3), True)
    def forbidden(*args):
        pytest.fail('Fraction constructed before scratch preflight')
    monkeypatch.setattr(constants, 'Fraction', forbidden)
    with pytest.raises(ExactResourceError, match='3 bits'):
        constants._fold_arithmetic(BinaryOp.ADD, left, right,
                                  ExactBudget(ExactPolicy(transient_bits=3)))


def test_cache_credits_scan_combined_components_once():
    budget = ExactBudget()
    budget.hit((Fraction(1, 1 << 63), True))
    assert budget.total == 2
    budget.hit((Fraction(1), False))
    assert budget.total == 3
    assert budget.initializers == {}


def test_retained_entries_count_each_owner_and_release_replacements():
    budget = ExactBudget(ExactPolicy(retained_bytes=146))
    exact = (Fraction(1 << 63), False)
    budget.retain(('binding', 1), exact)
    assert budget.payload == 73
    budget.retain(('ast', 2), exact)
    assert budget.payload == 146
    with pytest.raises(ExactResourceError, match='retained payload'):
        budget.retain(('ast', 3), exact)
    assert budget.payload == 146
    budget.retain(('ast', 2), None)
    assert budget.payload == 73
    budget.retain(('binding', 1), (Fraction(1), False))
    assert budget.payload == 66


def test_evaluator_releases_temporary_values_after_resource_failure():
    node = parse_program('X :: 8 * 16\n').declarations[0].value
    budget = ExactBudget(ExactPolicy(component_bits=8))
    with pytest.raises(ExactResourceError):
        constants.evaluate(node, lambda name: None, {}, budget)
    assert budget.payload == 0
    assert not budget.retained


@pytest.mark.parametrize('source', [
    'main :: fn() { a: [4]i32 }\n',
    'main :: fn() { x: i32 = 1 + 2 + 3 }\n',
])
def test_retention_failure_is_located_semantic_error(monkeypatch, tmp_path, source):
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(retained_bytes=1)))
    result = expect_exit(source, tmp_path, 6, 'retained payload')
    assert len(result.failure.details) == 1
    error = result.failure.details[0]
    assert error["span"]["start_line"] == 1
    assert error["file"] == str(tmp_path / "main.a7")
    assert not (tmp_path / "main-debug.zig").exists()


def test_default_conservative_product_boundary(tmp_path):
    source = 'main :: fn() { x: i32 = ((1 << 65535) * (1 << 65536)) >> 131071 }\n'
    expect_exit(source, tmp_path, 6, '131072 bits')
    expect_ok('main :: fn() { x: i32 = ((1 << 65535) * (1 << 65535)) >> 131070 }\n', tmp_path)


@pytest.mark.parametrize('limit,fragment', [
    ({'initializer_credits': 2}, 'initializer credits'),
    ({'compilation_credits': 2}, 'compilation credits'),
])
def test_compiler_work_limit_is_located(monkeypatch, tmp_path, limit, fragment):
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(**limit)))
    result = expect_exit('main :: fn() { x: i32 = 1 + 2 + 3 }\n', tmp_path, 6, fragment)
    assert result.failure.details[0]['file'] == str(tmp_path / 'main.a7')
    assert result.failure.details[0]['span']['start_line'] == 1
    assert not (tmp_path / 'main-debug.zig').exists()


def test_initializer_accounts_persist_and_are_independent():
    first, second = object(), object()
    budget = ExactBudget(ExactPolicy(initializer_credits=2, compilation_credits=4))
    budget.bind(first).charge(2, 'first operation')
    budget.bind(second).charge(1, 'second operation')
    with pytest.raises(ExactResourceError, match='initializer credits'):
        budget.bind(first).charge(1, 'revisited first operation')
    budget.bind(second).charge(1, 'revisited second operation')
    assert budget.total == 4
    with pytest.raises(ExactResourceError, match='compilation credits'):
        budget.hit((Fraction(1), False))


def test_rounding_resource_error_is_not_float_overflow(monkeypatch, tmp_path):
    # Literal scan, rounding scan, exponent comparison, two shifts and
    # division already need at least six credits before later rounding work.
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(initializer_credits=5)))
    result = expect_exit('main :: fn() { x: f32 = 1 }\n', tmp_path, 6, 'initializer credits')
    messages = ' '.join(error['message'] for error in result.failure.details)
    assert 'overflows f32' not in messages
    assert 'type mismatch' not in messages.lower()


def test_host_decimal_limit_does_not_escape_value_renderer():
    import sys
    previous = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(640)
        text = constants.render(Fraction(1 << 20000))
    finally:
        sys.set_int_max_str_digits(previous)
    assert len(text) <= 256
    assert '5001 hex digits' in text
    assert '20001 bits' in text


def test_default_initializer_budget_with_size_legal_operations(tmp_path):
    # B has 32768 bits (512 limbs). B*B has 65535 bits (1024 limbs).
    # Each multiply/divide pair charges 512*512 + 1024*512 = 786432.
    # 22 pairs cost 17301504 > 2**24; 20 cost 15728640 with headroom.
    # All component preflights stay below 65537 bits, below C3=131072.
    for count, accepted in ((22, False), (20, True)):
        expression = 'B' + ' * B / B' * count
        source = f'B :: 1 << 32767\nmain :: fn() {{ x: i32 = ({expression}) >> 32767 }}\n'
        directory = tmp_path / str(count)
        directory.mkdir()
        if accepted:
            expect_ok(source, directory)
        else:
            result = expect_exit(source, directory, 6, 'initializer credits 16777216')
            assert result.failure.details[0]['span']['start_line'] == 2


def test_dependency_depth_limits_chain_but_not_wide_graph(monkeypatch, tmp_path):
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(dependency_depth=3)))
    chain = 'A :: B\nB :: C\nC :: D\nD :: 1\nmain :: fn() { x: i32 = A }\n'
    result = expect_exit(chain, tmp_path, 6, 'dependency depth exceeds 3')
    assert result.failure.details[0]['span']['start_line'] == 1
    directory = tmp_path / 'wide'
    directory.mkdir()
    expect_ok('A :: D\nB :: D\nC :: D\nD :: 1\nmain :: fn() { x: i32 = A + B + C }\n', directory)


def test_dependency_diagnostic_keeps_both_ends_with_long_names(monkeypatch, tmp_path):
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(dependency_depth=40)))
    names = [f'N{i:02}_' + 'x' * 96 for i in range(41)]
    source = '\n'.join(f'{name} :: {names[i+1] if i+1<len(names) else "1"}' for i, name in enumerate(names))
    result = expect_exit(source + '\nmain :: fn() {}\n', tmp_path, 6, 'dependency depth exceeds 40')
    message = result.failure.details[0]['message']
    assert len(message) <= 2048
    assert 'N00_' in message and 'N40_' in message
    assert 'N20_' not in message
    assert '...' in message


def test_rejected_retention_replacement_preserves_existing_owner():
    budget = ExactBudget(ExactPolicy(retained_bytes=66))
    key = ('binding', 1)
    budget.retain(key, (Fraction(1), False))
    with pytest.raises(ExactResourceError, match='retained payload'):
        budget.retain(key, (Fraction(1 << 63), False))
    assert budget.payload == 66 and budget.retained[key] == 66


def test_chain_cannot_reset_initializer_budget_at_each_link(monkeypatch, tmp_path):
    # Four literal scans and three additions exceed four credits; each
    # separate two-literal initializer needs only three arithmetic credits.
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(initializer_credits=4)))
    expect_exit('A :: 1 + 2 + 3 + 4\nmain :: fn() {}\n', tmp_path, 6, 'initializer credits 4')
    directory = tmp_path / 'split'
    directory.mkdir()
    expect_ok('A :: 1 + 2\nB :: 3 + 4\nmain :: fn() {}\n', directory)


def test_compilation_budget_includes_references_across_bindings(monkeypatch, tmp_path):
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(compilation_credits=4)))
    expect_exit('A :: 1\nB :: A\nC :: A\nmain :: fn() {}\n', tmp_path, 6, 'compilation credits 4')
    directory = tmp_path / 'single'
    directory.mkdir()
    expect_ok('A :: 1\nmain :: fn() {}\n', directory)


def test_runtime_short_circuit_keeps_semantic_arithmetic_diagnostic(monkeypatch, tmp_path):
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(component_bits=8)))
    expect_exit('main :: fn() { x := false and (8 * 16 == 128) }\n', tmp_path, 6, '8 bits')
    directory = tmp_path / 'valid'
    directory.mkdir()
    expect_ok('main :: fn() { x := false and (8 * 8 == 64) }\n', directory)


def test_asymmetric_comparison_charges_each_actual_product():
    # (2**64)/3 versus 1/(2**128+1): cross products cost 2*3 and 1*1.
    # The sum is seven; twice the larger product would incorrectly be twelve.
    budget = ExactBudget()
    assert constants.compare(BinaryOp.GT, (Fraction(1 << 64, 3), True),
                             (Fraction(1, (1 << 128) + 1), True), budget)
    assert budget.total == 7


@pytest.mark.parametrize('left,right,expected', [(-17, 5, -2), (17, -5, 2)])
def test_integer_remainder_uses_one_component_division_charge(left, right, expected):
    budget = ExactBudget(ExactPolicy(initializer_credits=1))
    assert constants._fold_arithmetic(BinaryOp.MOD, (Fraction(left), False),
                                     (Fraction(right), False), budget) == (Fraction(expected), False)
    assert budget.total == 1



def test_exact_depth_does_not_limit_runtime_global_dependencies(monkeypatch, tmp_path):
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(dependency_depth=1)))
    expect_ok("""a: i32 = b
b: i32 = c
c: i32 = 1
main :: fn() { x := a }
""", tmp_path)
    directory = tmp_path / 'strings'
    directory.mkdir()
    expect_ok("""A :: B
B :: C
C :: "value"
main :: fn() { x := A }
""", directory)


@pytest.mark.parametrize('source', [
    'make :: fn(seed: $T) [1]$T { values: [1]$T = [1]; ret values }\n'
    'main :: fn() { seed: f32; value := make(seed) }\n',
    'take :: fn(first: $T, second: $T) {}\n'
    'main :: fn() { value: f32; take(value, 1) }\n',
])
def test_generic_float_fitting_preserves_resource_diagnostic(monkeypatch, tmp_path, source):
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(initializer_credits=5)))
    result = expect_exit(source, tmp_path, 6, 'initializer credits 5')
    errors = result.failure.details
    assert any('resource limit' in error['message'] and error['file'] == str(tmp_path / 'main.a7') for error in errors)
    assert not any('overflows f32' in error['message'] for error in errors)
    assert not (tmp_path / 'main-debug.zig').exists()


def test_transient_failure_keeps_binding_payload_owned():
    budget = ExactBudget(ExactPolicy(component_bits=8))
    binding = (Fraction(1 << 6), False)
    budget.retain(('binding', 1), binding)
    node = parse_program('X :: 8 * 16\n').declarations[0].value
    with pytest.raises(ExactResourceError):
        constants.evaluate(node, lambda name: None, {}, budget)
    assert budget.payload == 66
    assert budget.retained == {('binding', 1): 66}


def test_shared_child_expression_keeps_both_consumers():
    node = parse_program('X :: (1 + 2) * (3 + 4)\n').declarations[0].value
    node.right = node.left
    budget = ExactBudget()
    assert constants.evaluate(node, lambda name: None, {}, budget) == (Fraction(9), False)
    assert budget.payload == 0


def test_float_mantissa_credit_precedes_decimal_conversion(monkeypatch):
    def forbidden(*args):
        pytest.fail('decimal conversion executed after exhausted work budget')
    monkeypatch.setattr(constants, 'int', forbidden, raising=False)
    with pytest.raises(ExactResourceError, match='literal scan'):
        constants._float_literal('123.0', ExactBudget(ExactPolicy(initializer_credits=0)))


@pytest.mark.parametrize('fraction,bits,equalities,tie_bits,increments', [
    (Fraction(1) + Fraction(1, 1 << 25), 0x3F800000, 1, 0, 0),
    (Fraction(1) + Fraction(1, 1 << 24), 0x3F800000, 1, 1, 0),
    (Fraction(1) + Fraction(3, 1 << 25), 0x3F800001, 0, 0, 1),
])
def test_rounding_charges_only_executed_halfway_tests(fraction, bits, equalities, tie_bits, increments):
    class ObservedBudget(ExactBudget):
        def __init__(self):
            super().__init__()
            self.operations = []
        def charge(self, amount, operation, compilation_only=False):
            super().charge(amount, operation, compilation_only)
            self.operations.append((operation, amount))
    budget = ObservedBudget()
    assert constants.ieee_bits((fraction, True), 32, budget) == bits
    assert budget.operations.count(('rounding equality comparison', 1)) == equalities
    assert budget.operations.count(('and', 1)) == tie_bits
    assert budget.operations.count(('add', 1)) == increments


def test_diamond_charges_actual_exact_dependency_pops(monkeypatch, tmp_path):
    class ObservedBudget(ExactBudget):
        def __init__(self):
            super().__init__()
            self.visits = 0
        def charge(self, amount, operation, compilation_only=False):
            super().charge(amount, operation, compilation_only)
            if operation == 'exact dependency worklist visits':
                self.visits += amount
    budget = ObservedBudget()
    monkeypatch.setattr(checker, 'ExactBudget', lambda: budget)
    expect_ok('A :: B + C\nB :: D\nC :: D\nD :: 1\nmain :: fn() {}\n', tmp_path)
    # A/B/C each enter and finish; shared D enters, finishes, and is popped
    # once more as an already-completed dependency of C.
    assert budget.visits == 9


def test_local_exact_alias_chain_uses_same_depth_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(dependency_depth=3)))
    expect_exit('main :: fn() { A :: 1; B :: A; C :: B; D :: C }\n', tmp_path, 6, 'dependency depth exceeds 3')
    directory = tmp_path / 'valid'
    directory.mkdir()
    expect_ok('main :: fn() { A :: 1; B :: A; C :: B }\n', directory)


@pytest.mark.parametrize('text,credits', [
    ('9999999999999999999e0', 1),
    ('10000000000000000000e0', 1),
    ('18446744073709551615e0', 1),
    ('18446744073709551616e0', 2),
])
def test_decimal_scan_uses_exact_limb_threshold_before_conversion(text, credits):
    budget = ExactBudget(ExactPolicy(initializer_credits=credits))
    value, floating = constants._float_literal(text, budget)
    assert value == Fraction(text)
    assert floating is True
    assert budget.total == credits
    with pytest.raises(ExactResourceError, match='literal scan'):
        constants._float_literal(text, ExactBudget(ExactPolicy(initializer_credits=credits - 1)))


def test_zero_scaling_preserves_sign_and_exponent_limit():
    budget = ExactBudget(ExactPolicy(initializer_credits=1))
    assert constants._float_literal('-0e4096', budget) == (Fraction(0), 'negative_zero')
    assert budget.total == 1
    with pytest.raises(constants.ExactArithmeticError, match='exponent exceeds'):
        constants._float_literal('-0e4097', ExactBudget())


def test_shadowed_local_chains_keep_declaration_identity(monkeypatch, tmp_path):
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(dependency_depth=3)))
    expect_ok('main :: fn() { A :: 1; B :: A; C :: B; if true { A :: 2; B :: A; C :: B } }\n', tmp_path)
    directory = tmp_path / 'extends_outer'
    directory.mkdir()
    expect_exit('main :: fn() { A :: 1; B :: A; if true { B :: B; C :: B } }\n', directory, 6, 'dependency depth exceeds 3')


@pytest.mark.parametrize('source,cap,line', [
    ('E :: enum { A = 1 }\nmain :: fn() {}\n', 1, 1),
    ('C :: 1\nf :: fn(x: i32) { match x { case C: {} else: {} } }\nmain :: fn() {}\n', 100, 2),
])
def test_enum_and_pattern_retention_failure_stays_located(monkeypatch, tmp_path, source, cap, line):
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(retained_bytes=cap)))
    result = expect_exit(source, tmp_path, 6, 'retained payload')
    assert len(result.failure.details) == 1
    error = result.failure.details[0]
    assert error['span']['start_line'] == line
    assert error['file'] == str(tmp_path / 'main.a7')
    assert not (tmp_path / 'main-debug.zig').exists()


def test_typed_value_aliases_are_not_exact_dependency_chains(monkeypatch, tmp_path):
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(dependency_depth=1)))
    expect_ok('main :: fn() { value: i32 = 1; A :: value; B :: A; C :: B; D :: C }\n', tmp_path)


def test_failed_exact_binding_still_charges_dependency_visits(monkeypatch, tmp_path):
    class ObservedBudget(ExactBudget):
        def __init__(self):
            super().__init__(ExactPolicy(component_bits=8))
            self.visits = 0
        def charge(self, amount, operation, compilation_only=False):
            super().charge(amount, operation, compilation_only)
            if operation == 'exact dependency worklist visits':
                self.visits += amount
    budget = ObservedBudget()
    monkeypatch.setattr(checker, 'ExactBudget', lambda: budget)
    result = expect_exit('A :: 8 * 16\nmain :: fn() {}\n', tmp_path, 6, '8 bits')
    assert len(result.failure.details) == 1
    assert budget.visits == 2


def test_integral_rational_sum_uses_rational_scratch_bound():
    budget = ExactBudget(ExactPolicy(component_bits=8, transient_bits=16))
    assert constants._fold_arithmetic(BinaryOp.SUB, (Fraction(128), True),
                                     (Fraction(128), True), budget) == (Fraction(0), True)
    with pytest.raises(ExactResourceError, match='8 bits'):
        constants._fold_arithmetic(BinaryOp.SUB, (Fraction(128), False),
                                   (Fraction(128), False), ExactBudget(ExactPolicy(component_bits=8)))


def test_same_compiler_resets_budget_between_compilations(monkeypatch, tmp_path):
    from a7.compile import A7Compiler
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(compilation_credits=64)))
    compiler = A7Compiler()
    bad, good = tmp_path / 'bad.a7', tmp_path / 'good.a7'
    bad.write_text('A :: ' + ' + '.join(['1'] * 40) + '\nmain :: fn() {}\n')
    good.write_text('A :: 1\nmain :: fn() { value: i32 = A }\n')
    failed = compiler.compile_file_detailed(str(bad), str(tmp_path / 'bad.zig'))
    assert int(failed.exit_code) == 6
    assert any('compilation credits 64' in error['message'] for error in failed.failure.details)
    assert int(compiler.compile_file_detailed(str(good), str(tmp_path / 'good.zig')).exit_code) == 0

    assert 'const value: i32 = 1;' in (tmp_path / 'good.zig').read_text()


def test_imported_bindings_share_compilation_budget(monkeypatch, tmp_path):
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(compilation_credits=4)))
    standalone = tmp_path / 'standalone'
    standalone.mkdir()
    expect_ok('A :: 1\n', standalone, is_library=True)
    consumer = tmp_path / 'consumer'
    consumer.mkdir()
    expect_ok('B :: 1\nmain :: fn() {}\n', consumer)
    (tmp_path / 'helper.a7').write_text('A :: 1\n')
    expect_exit('h :: import "helper"\nB :: h.A\nmain :: fn() {}\n', tmp_path, 6, 'compilation credits 4')


@pytest.mark.parametrize('imported', [False, True])
def test_mixed_scope_exact_chain_keeps_depth(monkeypatch, tmp_path, imported):
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(dependency_depth=3)))
    if imported:
        (tmp_path / 'helper.a7').write_text('A :: 1\n')
        prefix, reference = 'h :: import "helper"\n', 'h.A'
    else:
        prefix, reference = 'A :: 1\n', 'A'
    expect_ok(prefix + f'main :: fn() {{ B :: {reference}; C :: B }}\n', tmp_path)
    result = expect_exit(prefix + f'main :: fn() {{ B :: {reference}; C :: B; D :: C }}\n', tmp_path, 6, 'dependency depth exceeds 3')
    assert result.failure.details[0]['span']['start_line'] == 2


def test_chain_lending_releases_ast_cache_after_arithmetic_failure(monkeypatch, tmp_path):
    class ObservedBudget(ExactBudget):
        def __init__(self):
            super().__init__(ExactPolicy(component_bits=8))
            self.ast_releases = set()
        def retain(self, key, exact, owner=None):
            was_retained = key in self.retained
            super().retain(key, exact, owner)
            if key[0] == 'ast' and exact is None and was_retained:
                self.ast_releases.add(key)
    budget = ObservedBudget()
    monkeypatch.setattr(checker, 'ExactBudget', lambda: budget)
    expect_exit('B :: 8\nmain :: fn() { x: i32 = B * 8 * 16 }\n', tmp_path, 6, '8 bits')
    assert budget.ast_releases
    assert not (budget.ast_releases & budget.retained.keys())
    assert not any(key[0] == 'evaluation' for key in budget.retained)
    assert sum(cost for key, cost in budget.retained.items() if key[0] == 'binding') == 66


def test_wide_rational_diagnostic_keeps_both_components():
    text = constants.render(Fraction(1 << 10000, (1 << 10001) + 1))
    assert len(text) <= 256
    assert text.count('0x') == 2
    assert '/' in text and text.count('hex digits') == 2


def test_long_exact_alias_chain_compiles_at_low_recursion_limit(tmp_path):
    import subprocess
    import sys
    source = tmp_path / 'chain.a7'
    source.write_text('\n'.join(f'A{i} :: A{i+1}' for i in range(299)) + '\nA299 :: 1\nmain :: fn() { x: i32 = A0 }\n')
    script = '''import sys
from a7.compile import A7Compiler
compiler = A7Compiler()
sys.setrecursionlimit(100)
result = compiler.compile_file_detailed(sys.argv[1], sys.argv[2])
raise SystemExit(int(result.exit_code))
'''
    process = subprocess.run([sys.executable, '-c', script, str(source), str(tmp_path / 'chain.zig')], capture_output=True, text=True)
    assert process.returncode == 0, process.stdout + process.stderr
    assert (tmp_path / 'chain.zig').exists()


def test_nondependency_resource_message_obeys_whole_message_cap(monkeypatch, tmp_path):
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(initializer_credits=1, diagnostic_characters=80)))
    name = 'constant_' + 'x' * 91
    result = expect_exit(f'{name} :: 1 + 2\nmain :: fn() {{}}\n', tmp_path, 6, 'Exact constant resource limit')
    message = result.failure.details[0]['message']
    assert len(message) <= 80
    assert '...' in message
    assert result.failure.details[0]['span']['start_line'] == 1


def test_deferred_float_fit_charges_cached_reference_before_rounding():
    # Exercise the named deferred-fit boundary with an already cached shared
    # generic literal. Full compiler generic failure tests above cover routing.
    from a7.symbol_table import SymbolTable
    from a7.types import I32, F32
    for cap, accepted in ((0, False), (64, True)):
        value = parse_program('X :: 1\n').declarations[0].value
        value.exact_constant = (Fraction(1), False)
        before = (value.kind, value.literal_value, value.exact_constant)
        visitor = checker.TypeCheckingPass(SymbolTable())
        visitor.exact_budget = ExactBudget(ExactPolicy(compilation_credits=cap))
        assert visitor._instantiated_value_fits(value, I32, I32, F32, {}) is accepted
        assert (value.kind, value.literal_value, value.exact_constant) == before
        if accepted:
            assert not visitor.errors
        else:
            assert len(visitor.errors) == 1
            assert 'cache reference exceeds compilation credits 0' in str(visitor.errors[0])


@pytest.mark.parametrize('width', [32, 64])
@pytest.mark.parametrize('account', ['initializer_credits', 'compilation_credits'])
def test_unused_generic_encoding_obeys_shared_budget(monkeypatch, tmp_path, width, account):
    # At the named IEEE conversion boundary, exhaust the existing account.
    # The real converter must reject before its first charged operation.
    from dataclasses import replace
    budget = ExactBudget()
    monkeypatch.setattr(checker, 'ExactBudget', lambda: budget)
    original = checker.ieee_bits
    observed = []
    def constrained(exact, target, active=None):
        assert active is budget
        observed.append(target)
        if target == width:
            used = budget.total if account == 'compilation_credits' else budget.initializers.get(budget.current, 0)
            budget.policy = replace(budget.policy, **{account: used})
        return original(exact, target, active)
    monkeypatch.setattr(checker, 'ieee_bits', constrained)
    result = expect_exit('pick :: fn(x: $T) i32 { ret match x { case 1.0: 1; else: 0 } }\nmain :: fn() {}',
                         tmp_path, 6, account.replace('_', ' '))
    assert observed == ([32] if width == 32 else [32, 64])
    assert len(result.failure.details) == 1
    assert result.failure.details[0]['span']['start_line'] == 1
    assert result.failure.details[0]['file'] == str(tmp_path / 'main.a7')
    assert not (tmp_path / 'main-debug.zig').exists()


def test_unused_generic_encodings_keep_expected_bits_and_overflow_marker(tmp_path):
    source = 'pick :: fn(x: $T) i32 { ret match x { case 1.0: 1; case 1e100: 2; else: 0 } }\nmain :: fn() {}'
    result = expect_ok(source, tmp_path)
    from pathlib import Path
    zig = Path(result.output_path).read_text()
    assert '@as(f32, @bitCast(@as(u32, 1065353216)))' in zig
    assert '@as(f64, @bitCast(@as(u64, 4607182418800017408)))' in zig
    assert '@compileError("match pattern does not fit target float")' in zig
    assert '@as(f64, @bitCast(@as(u64, 6103021453049119613)))' in zig


@pytest.mark.parametrize('refuse_copy', [False, True])
def test_generic_pattern_copies_release_only_transient_owners(monkeypatch, tmp_path, refuse_copy):
    from dataclasses import replace
    budget = ExactBudget()
    monkeypatch.setattr(checker, 'ExactBudget', lambda: budget)
    original = checker.materialize
    copies = []
    owners = []
    def observed(node, exact, integer=False, width=None, budget=None):
        if getattr(node, 'generic_pattern_exact', None) is not None:
            copies.append(node)  # Keep alive: GC cannot satisfy the release assertion.
            owners.append(budget.current)
            if refuse_copy:
                budget.policy = replace(budget.policy, initializer_credits=budget.initializers.get(budget.current, 0))
        return original(node, exact, integer=integer, width=width, budget=budget)
    monkeypatch.setattr(checker, 'materialize', observed)
    source = 'K :: 1.0\npick :: fn(x: $T) i32 { ret match x { case K: 1; else: 0 } }\nmain :: fn() { a: f32 = 0; b: f64 = 0; x := pick(a); y := pick(b) }'
    if refuse_copy:
        result = expect_exit(source, tmp_path, 6, 'initializer credits')
        assert result.failure.details[0]['span']['start_line'] == 2
        assert len(result.failure.details) == 1
    else:
        expect_ok(source, tmp_path)
        assert len(copies) == 2
        assert owners[0] == owners[1]
    assert copies
    for node, owner in zip(copies, owners):
        assert id(node) != owner
        assert id(node) not in budget.owners
        assert ('ast', id(node)) not in budget.retained
        assert ('ast', id(node)) not in budget.watched
        assert owner in budget.initializers
    assert sum(size for key, size in budget.retained.items() if key[0] == 'binding') == 66


def test_generic_template_comparisons_charge_only_executed_pairs(monkeypatch, tmp_path):
    original = checker.compare
    observed = []
    def compare(operator, left, right, budget=None):
        before = budget.total
        result = original(operator, left, right, budget)
        observed.append((left[0], right[0], budget.total - before))
        return result
    monkeypatch.setattr(checker, 'compare', compare)
    expect_ok('pick :: fn(x: $T) i32 { ret match x { case 1.0: 1; case 2.0: 2; else: 0 } }\nmain :: fn() {}', tmp_path)
    # Each pair has one-limb numerators and denominators: two product credits.
    # The failed 2 <= 1 comparison short-circuits the reverse overlap test.
    assert observed == [(Fraction(1), Fraction(1), 2),
                        (Fraction(2), Fraction(2), 2),
                        (Fraction(2), Fraction(1), 2)]


def test_equal_generic_values_keep_distinct_initializer_accounts(monkeypatch, tmp_path):
    budget = ExactBudget()
    monkeypatch.setattr(checker, 'ExactBudget', lambda: budget)
    original = checker.ieee_bits
    observed = []
    def ieee(exact, width, active=None):
        assert active is budget
        observed.append((active.current, width))
        return original(exact, width, active)
    monkeypatch.setattr(checker, 'ieee_bits', ieee)
    expect_ok('a :: fn(x: $T) i32 { ret match x { case 1.0: 1; else: 0 } }\nb :: fn(x: $U) i32 { ret match x { case 1.0: 1; else: 0 } }\nmain :: fn() {}', tmp_path)
    assert len(observed) == 4
    assert observed[0][0] == observed[1][0]
    assert observed[2][0] == observed[3][0]
    assert observed[0][0] != observed[2][0]
    assert [width for owner, width in observed] == [32, 64, 32, 64]
    assert budget.initializers[observed[0][0]] == budget.initializers[observed[2][0]]


def test_same_compiler_recovers_after_unused_encoding_budget_failure(monkeypatch, tmp_path):
    from dataclasses import replace
    from pathlib import Path
    from a7.compile import A7Compiler
    budgets = []
    def fresh():
        budget = ExactBudget()
        budgets.append(budget)
        return budget
    monkeypatch.setattr(checker, 'ExactBudget', fresh)
    original = checker.ieee_bits
    def ieee(exact, width, budget=None):
        if budget is budgets[0] and width == 64:
            budget.policy = replace(budget.policy, compilation_credits=budget.total)
        return original(exact, width, budget)
    monkeypatch.setattr(checker, 'ieee_bits', ieee)
    compiler = A7Compiler()
    source = tmp_path / 'main.a7'
    source.write_text('pick :: fn(x: $T) i32 { ret match x { case 1.0: 1; else: 0 } }\nmain :: fn() {}')
    bad = compiler.compile_file_detailed(str(source), str(tmp_path / 'bad.zig'))
    assert int(bad.exit_code) == 6
    assert 'compilation credits' in bad.failure.details[0]['message']
    assert not (tmp_path / 'bad.zig').exists()
    source.write_text('main :: fn() { x: i32 = 1 }')
    good = compiler.compile_file_detailed(str(source), str(tmp_path / 'good.zig'))
    assert good.ok
    assert 'const x: i32 = 1;' in Path(good.output_path).read_text()
    assert len(budgets) == 2 and budgets[0] is not budgets[1]
    assert budgets[1].total < budgets[0].total
