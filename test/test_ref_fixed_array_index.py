"""Fixed-array reference accesses preserve bounds, nil proofs and optional lowering."""
import pytest
from conftest import compile_program, expect_exit, failure_text

ARRAY = 'values: [4]i32 = [11, 22, 33, 44]; '


@pytest.mark.parametrize('body,call,emitted', [
    ('if a == nil { ret }; x := a[0]', ARRAY + 'access(values)', 'a.?[0]'),
    ('if a == nil { ret }; x := a[3]', ARRAY + 'access(values)', 'a.?[3]'),
    ('x := a[0]', ARRAY + 'access(values)', 'a.?[0]'),
    ('if a == nil { ret }; x := a[0]', 'access(nil)', 'a.?[0]'),
    ('a[0] = 9', ARRAY + 'access(values)', 'a.?[0] = 9'),
    ('if a == nil { ret }; a[0] = 9', 'access(nil)', 'a.?[0] = 9'),
    ('a[0] += 1', ARRAY + 'access(values)', 'a.?[0] +%= 1'),
])
def test_valid_access_emits_optional_unwrap(tmp_path, body, call, emitted):
    result = compile_program('access :: fn(a: ref [4]i32) { ' + body + ' }\nmain :: fn() { ' + call + ' }', tmp_path)
    assert int(result.exit_code) == 0, failure_text(result)
    zig = (tmp_path/'main-debug.zig').read_text()
    assert 'a: ?*[4]i32' in zig
    assert emitted in zig
    assert 'a[0]' not in zig


@pytest.mark.parametrize('body,call,fragment', [
    ('x := a[4]', ARRAY + 'access(values)', 'Index not proven in bounds'),
    ('a[4] = 1', ARRAY + 'access(values)', 'Index not proven in bounds'),
    ('x := a[0]', 'access(nil)', 'non-nil'),
    ('a[0] = 1', 'access(nil)', 'non-nil'),
    ('a[0] += 1', 'access(nil)', 'non-nil'),
])
def test_invalid_access_is_semantic_error(tmp_path, body, call, fragment):
    result = expect_exit('access :: fn(a: ref [4]i32) { ' + body + ' }\nmain :: fn() { ' + call + ' }', tmp_path, 6, fragment)
    assert not (tmp_path/'main-debug.zig').exists()
    assert all(detail['type'] == 'SafetyError' for detail in result.failure.details)
    assert all(detail['span']['start_line'] in (1, 2) for detail in result.failure.details)


@pytest.mark.parametrize('operation', ['x := a[0]', 'a[0] = 1', 'a[0] += 1'])
def test_nil_local_requires_dereference_proof(tmp_path, operation):
    expect_exit('main :: fn() { a: ref [4]i32 = nil; ' + operation + ' }', tmp_path, 6, 'Reference not proven non-nil')


def test_ref_slice_stays_rejected(tmp_path):
    expect_exit('access :: fn(a: ref [4]i32) { if a == nil { ret }; view := a[0..4] }\nmain :: fn() { ' + ARRAY + 'access(values) }', tmp_path, 6, 'Requires array or slice type')


@pytest.mark.parametrize('argument,exit_code', [('nil', 6), ('values', 0)])
def test_forwarded_access_retains_actual_nil_requirement(tmp_path, argument, exit_code):
    source = 'access :: fn(a: ref [4]i32) { x := a[0] }\nforward :: fn(a: ref [4]i32) { access(a) }\nmain :: fn() { ' + ARRAY + 'forward(' + argument + ') }'
    result = compile_program(source, tmp_path)
    assert int(result.exit_code) == exit_code, failure_text(result)
    if exit_code:
        assert 'non-nil' in failure_text(result)
        assert result.failure.details[0]['span']['start_line'] == 3


@pytest.mark.parametrize('body', ['x := a[0][1]', 'a[0][1] = 9', 'a[0][1] += 1'])
@pytest.mark.parametrize('argument,exit_code', [('values', 0), ('nil', 6)])
def test_nested_array_access_keeps_root_requirement(tmp_path, body, argument, exit_code):
    source = 'access :: fn(a: ref [2][2]i32) { ' + body + ' }\nmain :: fn() { values: [2][2]i32 = [[1, 2], [3, 4]]; access(' + argument + ') }'
    result = compile_program(source, tmp_path)
    assert int(result.exit_code) == exit_code, failure_text(result)
    if exit_code:
        assert 'non-nil' in failure_text(result)
    else:
        assert 'a.?[0][1]' in (tmp_path/'main-debug.zig').read_text()


@pytest.mark.parametrize('body', ['x := a[i]', 'a[i] = 9', 'a[i] += 1'])
def test_guarded_usize_index_uses_existing_bound_proof(tmp_path, body):
    source = 'access :: fn(a: ref [4]i32, i: usize) { if i < 4 { ' + body + ' } }\nmain :: fn() { ' + ARRAY + 'access(values, 3) }'
    result = compile_program(source, tmp_path)
    assert int(result.exit_code) == 0, failure_text(result)
    assert 'a.?[i]' in (tmp_path/'main-debug.zig').read_text()


@pytest.mark.parametrize('body', ['x := a[0]', 'a[0] = 9'])
def test_guarded_forwarder_preserves_nil_call(tmp_path, body):
    source = 'access :: fn(a: ref [4]i32) { ' + body + ' }\nforward :: fn(a: ref [4]i32) { if a == nil { ret }; access(a) }\nmain :: fn() { forward(nil) }'
    result = compile_program(source, tmp_path)
    assert int(result.exit_code) == 0, failure_text(result)


def test_local_reference_alias_keeps_nil_requirement(tmp_path):
    source = 'access :: fn(a: ref [4]i32) { copy := a; x := copy[0] }\nmain :: fn() { access(nil) }'
    expect_exit(source, tmp_path, 6, 'non-nil')


@pytest.mark.parametrize('argument,exit_code', [('nil', 6), ('values', 0)])
def test_stable_local_callable_copy_keeps_nil_requirement(tmp_path, argument, exit_code):
    source = 'access :: fn(a: ref [4]i32) { x := a[0] }\nmain :: fn() { invoke := access; copy := invoke; ' + ARRAY + 'copy(' + argument + ') }'
    result = compile_program(source, tmp_path)
    assert int(result.exit_code) == exit_code, failure_text(result)
    if exit_code:
        assert 'non-nil' in failure_text(result)


@pytest.mark.parametrize('call', ['invoke := access; invoke = access; invoke(nil)', 'invoke := access; invoke = access; ' + ARRAY + 'invoke(values)'])
def test_mutable_callable_value_retains_prior_rejection(tmp_path, call):
    expect_exit('access :: fn(a: ref [4]i32) { x := a[0] }\nmain :: fn() { ' + call + ' }', tmp_path, 6, 'Index not proven in bounds')


def test_nested_function_and_shadowed_callable_alias(tmp_path):
    result = compile_program('''
read :: fn(a: ref [4]i32) { x := a[0] }
main :: fn() {
    nested :: fn(a: ref [4]i32) { read(a) }
    invoke := read
    if true { invoke := nested; values: [4]i32 = [1, 2, 3, 4]; invoke(values) }
    values: [4]i32 = [5, 6, 7, 8]
    invoke(values)
}
''', tmp_path)
    assert int(result.exit_code) == 0, failure_text(result)


@pytest.mark.parametrize('index,expected', [('0', 6), ('4', 0)])
def test_index_guard_also_controls_nil_call_requirement(tmp_path, index, expected):
    source = 'access :: fn(a: ref [4]i32, i: usize) { if i < 4 { a[i] = 7 } }\nmain :: fn() { access(nil, ' + index + ') }'
    result = compile_program(source, tmp_path)
    assert int(result.exit_code) == expected, failure_text(result)


def test_direct_nil_call_error_is_at_call_and_names_callee_use(tmp_path):
    result = expect_exit('''access :: fn(a: ref [4]i32) {
    a[0] = 1
}
main :: fn() {
    access(nil)
}
''', tmp_path, 6, 'indexed access must remain non-nil')
    assert len(result.failure.details) == 1
    error = result.failure.details[0]
    assert error['span']['start_line'] == 5
    assert 'callee use at line 2, column 5' in error['message']


@pytest.mark.parametrize('guard,argument,expected', [('', 'values', 0), ('', 'nil', 6), ('if a == nil { ret }; ', 'nil', 0)])
def test_print_arguments_keep_index_nil_requirement(tmp_path, guard, argument, expected):
    source = 'io :: import "std/io"\nread :: fn(a: ref [4]i32) { ' + guard + 'io.println("{} {}", a[0], a[3]) }\nmain :: fn() { ' + ARRAY + 'read(' + argument + ') }'
    result = compile_program(source, tmp_path)
    assert int(result.exit_code) == expected, failure_text(result)
    if expected:
        assert 'indexed access must remain non-nil' in failure_text(result)
    else:
        assert 'a.?[0]' in (tmp_path/'main-debug.zig').read_text()


def test_same_index_has_separate_bounds_and_deref_approvals(tmp_path):
    result = compile_program('read :: fn(a: ref [4]i32) { a[0] += 1 }\nmain :: fn() { ' + ARRAY + 'read(values) }', tmp_path)
    assert int(result.exit_code) == 0, failure_text(result)
    approvals = result.semantic_results['backend_plan'].approved
    indexes = [(identity, proof) for (identity, operation), proof in approvals.items() if operation == 'index']
    assert len(indexes) == 1
    identity, bounds = indexes[0]
    assert bounds.proven and bounds.obligation.kind.name == 'INDEX_IN_BOUNDS'
    deref = approvals[(identity, 'deref')]
    assert deref.proven and deref.obligation.kind.name == 'REF_NON_NIL'


@pytest.mark.parametrize('is_library', [False, True])
@pytest.mark.parametrize('forwarded', [False, True])
@pytest.mark.parametrize('predicate,argument,expected', [
    ('flag()', 'nil', 6),
    ('false_flag()', 'nil', 0),
    ('true', 'nil', 6),
    ('false', 'nil', 0),
    ('flag()', 'values', 0),
    ('false_flag()', 'values', 0),
])
def test_unknown_entry_predicate_does_not_discharge_index_requirement(tmp_path, is_library, forwarded, predicate, argument, expected):
    source = ('flag::fn()bool{ret true}\nfalse_flag::fn()bool{ret false}\n'
              'access::fn(a:ref[4]i32,b:bool){if b{x:=a[0]}}\n'
              'forward::fn(a:ref[4]i32,b:bool){access(a,b)}\n'
              'main::fn(){' + ARRAY + ('forward' if forwarded else 'access')
              + '(' + argument + ',' + predicate + ')}')
    result = compile_program(source, tmp_path, is_library=is_library)
    assert int(result.exit_code) == expected, failure_text(result)
    if expected:
        assert 'non-nil' in failure_text(result) or 'nil proof' in failure_text(result)
        assert not (tmp_path/'main-debug.zig').exists()
    else:
        assert 'a.?[0]' in (tmp_path/'main-debug.zig').read_text()


@pytest.mark.parametrize('is_library', [False, True])
def test_uncalled_nil_index_with_true_predicate_stays_rejected(tmp_path, is_library):
    source = ('flag::fn()bool{ret true}\naccess::fn(a:ref[4]i32,b:bool){if b{x:=a[0]}}\n'
              'bad::fn(){access(nil,flag())}\nmain::fn(){}')
    expect_exit(source, tmp_path, 6, 'reachable readonly callee read receives nil', is_library=is_library)


@pytest.mark.parametrize('is_library', [False, True])
def test_symbolic_nil_wrapper_remains_incomplete(tmp_path, is_library):
    source = ('access::fn(a:ref[4]i32,b:bool){if b{x:=a[0]}}\n'
              'wrap::fn(b:bool){access(nil,b)}\nmain::fn(){wrap(false)}')
    expect_exit(source, tmp_path, 6, 'reference-array caller requirement is unresolved', is_library=is_library)
