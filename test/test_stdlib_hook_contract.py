"""Internal hook declarations drive real typing and Zig output.

The registry and package resource root are named test boundaries. Synthetic
hooks are not public APIs; these tests do not compile or execute Zig.
"""
from importlib.resources import files
from pathlib import Path
import re

import pytest

from a7.stdlib import StdlibFunction, StdlibModule, StdlibRegistry, ZigHook
from conftest import compile_program, expect_exit, expect_ok, failure_text


@pytest.fixture
def internal_hooks(tmp_path, monkeypatch):
    resource = tmp_path / 'package'
    (resource / 'sources').mkdir(parents=True)
    (resource / 'rt').mkdir()
    shipped = files('a7.stdlib')
    for name in ('prelude.a7', 'io.a7'):
        (resource / 'sources' / name).write_text(shipped.joinpath('sources', name).read_text())
    for source in shipped.joinpath('rt').iterdir():
        (resource / 'rt' / source.name).write_text(source.read_text())
    for owner in ('first', 'second'):
        (resource / 'sources' / (owner + '.a7')).write_text('Err :: enum { Bad }\n')
        (resource / 'rt' / (owner + '.zig')).write_text(
            f'fn __a7_{owner}_echo(value: anytype) @TypeOf(value) {{ return value; }}\n')
    (resource / 'rt' / 'twice.zig').write_text('fn __a7_contract_twice(value: i32) i32 { return value +% value; }\n')
    (resource / 'rt' / 'touch.zig').write_text('fn __a7_contract_touch(value: i32) void { _ = value; }\n')
    (resource / 'rt' / 'mapped.zig').write_text('fn mapped_twice(value: i32) i32 { return value +% value; }\n')
    original = StdlibRegistry._register_defaults

    def register(registry):
        original(registry)
        for owner in ('first', 'second'):
            module = StdlibModule(owner, public_paths=('std/' + owner,), type_source=owner + '.a7')
            module.functions['echo'] = StdlibFunction(owner, 'echo', 'std.' + owner + '.echo',
                'fn(Err) Err', backend_map={'zig': ZigHook('__a7_' + owner + '_echo', snippets=(owner + '.zig',))})
            registry.register_module(module)
        module = StdlibModule('contract', public_paths=('std/contract',))
        module.functions['twice'] = StdlibFunction('contract', 'twice', 'std.contract.twice',
            'fn(i32) i32', backend_map={'zig': ZigHook('__a7_contract_twice', snippets=('twice.zig',))})
        module.functions['touch'] = StdlibFunction('contract', 'touch', 'std.contract.touch',
            'fn(i32)', backend_map={'zig': ZigHook('__a7_contract_touch', snippets=('touch.zig',))})
        module.functions['unsupported'] = StdlibFunction('contract', 'unsupported', 'std.contract.unsupported', 'fn() i32')
        module.functions['mapped'] = StdlibFunction('contract', 'mapped', 'std.contract.mapped',
            'fn(i32) i32', backend_map={'zig': ZigHook('mapped_twice', snippets=('mapped.zig',))})
        registry.register_module(module)

    monkeypatch.setattr(StdlibRegistry, '_register_defaults', register)
    monkeypatch.setattr('a7.passes.name_resolution.files', lambda package: resource)
    monkeypatch.setattr('a7.backends.zig.files', lambda package: resource)


def test_fixed_hook_types_and_emits_its_resource_once(tmp_path, internal_hooks):
    result = expect_ok('c :: import "std/contract"\nmain :: fn() { a: i32 = c.twice(3); b: i32 = c.twice(4) }', tmp_path)
    emitted = Path(result.output_path).read_text()
    assert emitted.count('fn __a7_contract_twice(') == 1
    assert '__a7_contract_twice(3)' in emitted
    assert '__a7_contract_twice(4)' in emitted
    assert '__a7_contract_touch' not in emitted
    assert '__a7_first_echo' not in emitted


def test_import_without_call_emits_no_hook_resource(tmp_path, internal_hooks):
    result = expect_ok('c :: import "std/contract"\nmain :: fn() {}', tmp_path)
    assert '__a7_contract_' not in Path(result.output_path).read_text()
    assert 'mapped_twice' not in Path(result.output_path).read_text()


@pytest.mark.parametrize('body, diagnostic', [
    ('c.twice()', 'contract.twice expects 1 arguments, got 0'),
    ('c.twice(true)', 'contract.twice argument'),
    ('x: bool = c.twice(1)', 'Type mismatch'),
    ('x := c.touch(1)', 'std.contract.touch returns no value'),
])
def test_fixed_hook_rejects_invalid_contract_use(tmp_path, internal_hooks, body, diagnostic):
    expect_exit('c :: import "std/contract"\nmain :: fn() {' + body + '}', tmp_path, 6, diagnostic)


def test_unmapped_backend_fails_without_emitting_output(tmp_path, internal_hooks):
    result = compile_program('c :: import "std/contract"\nmain :: fn() { x := c.unsupported() }', tmp_path)
    assert int(result.exit_code) == 7
    assert 'Zig backend: no lowering for std.contract.unsupported' in failure_text(result)
    assert not (tmp_path / 'main-debug.zig').exists()


def test_module_owned_signature_return_survives_wrapper(tmp_path, internal_hooks):
    (tmp_path / 'wrapper.a7').write_text('owner :: import "std/first"\nwrap :: fn(x: owner.Err) owner.Err { ret owner.echo(x) }')
    result = expect_ok('a :: import "std/first"\nb :: import "std/second"\nw :: import "wrapper"\nmain :: fn() { x: a.Err = w.wrap(a.Err.Bad); y: b.Err = b.echo(b.Err.Bad) }', tmp_path)
    emitted = Path(result.output_path).read_text()
    assert 'fn __a7_first_echo(' in emitted and 'fn __a7_second_echo(' in emitted
    declared_enums = re.findall(r'const (\w+) = enum', emitted)
    assert len(declared_enums) == 2 and len(set(declared_enums)) == 2


def test_same_spelled_owned_types_are_not_interchangeable(tmp_path, internal_hooks):
    result = compile_program('a :: import "std/first"\nb :: import "std/second"\nmain :: fn() { b.echo(a.Err.Bad) }', tmp_path)
    assert int(result.exit_code) == 6
    assert 'second.echo argument' in failure_text(result)
    assert '__a7_Err_' in failure_text(result) and '__a7_Err' in failure_text(result)


def test_fixed_void_statement_and_hook_name_local(tmp_path, internal_hooks):
    result = expect_ok('c :: import "std/contract"\nmain :: fn() { __a7_contract_twice := 7; x := c.twice(__a7_contract_twice); c.touch(x) }', tmp_path)
    emitted = Path(result.output_path).read_text()
    assert 'fn __a7_contract_twice(' in emitted
    assert 'fn __a7_contract_touch(' in emitted
    assert 'const __a7_contract_twice =' not in emitted
    assert '_ = __a7_contract_touch(' not in emitted
    assert '__a7_contract_touch(x);' in emitted


def test_signature_owner_is_not_importer_local_type(tmp_path, internal_hooks):
    result = compile_program('a :: import "std/first"\nErr :: enum { Bad }\nmain :: fn() { a.echo(Err.Bad) }', tmp_path)
    assert int(result.exit_code) == 6
    assert 'first.echo argument' in failure_text(result)


def test_mapped_target_keeps_global_and_local_calls_distinct(tmp_path, internal_hooks):
    result = expect_ok('''c :: import "std/contract"
mapped_twice :: fn(x: i32) i32 { ret x }
local :: fn() i32 {
    mapped_twice := 7
    ret c.mapped(mapped_twice)
}
main :: fn() { a := c.mapped(3); b := mapped_twice(5); d := local() }
''', tmp_path)
    emitted = Path(result.output_path).read_text()
    assert emitted.count('fn mapped_twice(') == 1
    user_function = re.search(r'fn (\w+)\(x: i32\) i32', emitted).group(1)
    assert user_function != 'mapped_twice'
    assert f'{user_function}(5)' in emitted
    assert 'mapped_twice(3)' in emitted
    local_name = re.search(r'const (\w+): i32 = 7;', emitted).group(1)
    assert local_name not in {'mapped_twice', user_function}
    assert f'return mapped_twice({local_name});' in emitted
