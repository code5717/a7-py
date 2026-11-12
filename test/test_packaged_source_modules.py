"""Public package sources use ordinary file scopes and source call typing.

The resource fixtures replace only package resource discovery. ASCII is a test
fixture, not a shipped module. The imported callable alias is checked natively;
installed-package checks are separate.
"""
from pathlib import Path

import pytest
from a7.module_resolver import ModuleResolver
from a7.errors import ImportError as A7ImportError, SemanticError
from conftest import build_and_run, expect_ok, expect_exit


def put(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    return target


@pytest.fixture
def package_root(tmp_path, monkeypatch):
    root = tmp_path / 'package'
    root.mkdir()
    monkeypatch.setattr('a7.module_resolver.files', lambda package: root)
    project = tmp_path / 'project'
    project.mkdir()
    return root / 'sources/std', project


@pytest.fixture
def ascii_resource(monkeypatch):
    root = Path(__file__).parent / 'fixtures/packaged_source'
    monkeypatch.setattr('a7.module_resolver.files', lambda package: root)


def test_loader_prerequisite_does_not_publish_ascii(tmp_path):
    expect_exit('a::import "std/ascii"\nmain::fn(){}', tmp_path, 3,
                "Module 'std/ascii' not found")


def test_fixture_ascii_uses_source_signatures_and_ordinary_emission(tmp_path, ascii_resource):
    expect_ok('a::import "std/ascii"\nmain::fn(){'
              'd:bool=a.is_digit(\'4\');l:bool=a.is_alpha(\'a\');'
              's:bool=a.is_space(\' \' );u:bool=a.is_upper(\'A\');'
              'hi:char=a.to_upper(\'b\');lo:char=a.to_lower(\'B\');'
              'n:i32=a.digit_value(\'8\')}', tmp_path)
    emitted = (tmp_path / 'main-debug.zig').read_text()
    for name, typ in [('is_digit','bool'), ('is_alpha','bool'), ('is_space','bool'),
                      ('is_upper','bool'), ('to_upper','u8'), ('to_lower','u8'), ('digit_value','i32')]:
        assert f'fn module__stdlib_source_ascii__{name}(c: u8) {typ}' in emitted
    expect_exit('a::import "std/ascii"\nmain::fn(){x:=a.is_digit("4")}', tmp_path, 6, 'mismatch')
    expect_exit('a::import "std/ascii"\nmain::fn(){x:char=a.is_digit(\'4\')}', tmp_path, 6, 'mismatch')


def test_bare_ascii_is_local_and_public_identity_is_distinct(tmp_path, ascii_resource):
    local_path = put(tmp_path, 'ascii.a7', 'is_digit::fn(c:char)i32{ret 42}')
    resolver = ModuleResolver([str(tmp_path)])
    local = resolver.load_module('ascii')
    public = resolver.load_module('std/ascii')
    assert local.file_path == str(local_path)
    assert public.ast is not None
    assert public.path == '/stdlib-source/ascii'
    assert local is not public
    expect_ok('local::import "ascii"\na::import "std/ascii"\n'
              'main::fn(){x:i32=local.is_digit(\'0\');y:bool=a.is_digit(\'0\')}', tmp_path)


def test_source_dependencies_keep_local_types_and_registered_hooks(package_root):
    package, project = package_root
    put(package, 'part/types.a7', 'Point::struct{x:i32}\nvalue::fn()Point{ret Point{x:7}}')
    put(package, 'shared.a7', 'Point::struct{x:string}\nvalue::fn()Point{ret Point{x:"s"}}')
    put(package, 'part/wrapper.a7', 'types::import "types"\ns::import "std/shared"\n'
        'io::import "std/io"\nm::import "std/math"\n'
        'value::fn()types.Point{ret types.value()}\n'
        'other::fn()s.Point{ret s.value()}\n'
        'show::fn(){io.println("ok");r:f64=m.sqrt(4.0)}')
    put(project, 'local.a7', 'a::import "std/part/wrapper"\nvalue::fn()i32{ret a.value().x}')
    expect_ok('a::import "std/part/wrapper"\nt::import "std/part/types"\n'
              'local::import "local"\nPoint::string\n'
              'main::fn(){x:t.Point=a.value();y:string=a.other().x;z:i32=local.value();a.show()}', project)
    emitted = (project / 'main-debug.zig').read_text()
    assert 'module__stdlib_source_part_types__Point' in emitted
    assert 'module__stdlib_source_shared__Point' in emitted
    assert '@sqrt(4.0)' in emitted
    expect_exit('a::import "std/part/wrapper"\nmain::fn(){x:=a.types.value()}', project, 6, 'is local to module')


def test_private_declarations_remain_private(package_root):
    package, project = package_root
    put(package, 'hidden.a7', '_value::fn()i32{ret 7}\nvalue::fn()i32{ret _value()}')
    expect_ok('a::import "std/hidden"\nmain::fn(){x:=a.value()}', project)
    expect_exit('a::import "std/hidden"\nmain::fn(){x:=a._value()}', project, 6, 'Private declaration')


def test_duplicate_relative_and_reserved_paths_have_one_identity(package_root):
    package, project = package_root
    put(package, 'shared.a7', 'value::7')
    put(package, 'part/mod.a7', 'a::import "../shared"\nb::import "std/shared"')
    resolver = ModuleResolver([str(project)])
    with pytest.raises(SemanticError, match='Duplicate import'):
        resolver.load_module('std/part')
    put(package, 'part/mod.a7', 'a::import "../shared"')
    first = resolver.load_module('std/part')
    shared = resolver.get_module('../shared', first.file_path)
    assert shared is resolver.load_module('std/shared')
    assert resolver.load_module('std/part/mod') is first
    assert len(resolver.loaded_modules) == 2


@pytest.mark.parametrize('path', ['std/prelude', 'std/missing', 'std/../prelude', 'std/./ascii'])
def test_private_and_missing_sources_do_not_fall_back(package_root, path):
    package, project = package_root
    put(package.parent, 'prelude.a7', 'private_value::7')
    put(package, 'ascii.a7', 'value::7')
    with pytest.raises(A7ImportError):
        ModuleResolver([str(project)]).load_module(path)


def test_project_shadow_error_and_virtual_identity_preserved(tmp_path):
    resolver = ModuleResolver([str(tmp_path)])
    io = resolver.load_module('io')
    assert resolver.load_module('std/io') is io
    assert io.ast is None
    assert '/stdlib/io' in resolver.loaded_modules
    put(tmp_path, 'std/ascii.a7', 'value::7')
    with pytest.raises(A7ImportError, match='remove the project shadow'):
        resolver.load_module('std/ascii')


def test_source_failure_reports_package_origin_and_cleans_cache(package_root):
    package, project = package_root
    origin = put(package, 'broken.a7', 'missing::import "missing"')
    resolver = ModuleResolver([str(project)])
    with pytest.raises(A7ImportError, match="Module 'missing' not found") as caught:
        resolver.load_module('std/broken')
    assert caught.value.filename == str(origin)
    assert not resolver.loaded_modules
    assert not resolver.loading_stack


def test_package_relative_dependencies_cannot_escape_or_fall_back(package_root):
    package, project = package_root
    put(project, 'helper.a7', 'value::7')
    put(package, 'part/mod.a7', 'h::import "helper"')
    resolver = ModuleResolver([str(project)])
    with pytest.raises(A7ImportError, match="Module 'helper' not found"):
        resolver.load_module('std/part')
    put(package, 'part/mod.a7', 'h::import "../../../project/helper"')
    with pytest.raises(A7ImportError, match='not found'):
        resolver.load_module('std/part')


def test_source_function_value_alias_preserves_type_and_emission(tmp_path, ascii_resource):
    expect_ok('a::import "std/ascii"\nmain::fn(){f:=a.digit_value;x:i32=f(\'7\')}', tmp_path)
    emitted = (tmp_path / 'main-debug.zig').read_text()
    assert 'const f: *const fn (u8) i32 = module__stdlib_source_ascii__digit_value;' in emitted
    expect_exit('a::import "std/ascii"\nmain::fn(){f:=a.digit_value;x:=f("7")}', tmp_path, 6, 'mismatch')


@pytest.mark.parametrize('profile', ['debug', 'release', 'fast'])
def test_source_function_value_alias_native(tmp_path, ascii_resource, zig, profile):
    source = '''a::import "std/ascii"
io::import "std/io"
main::fn(){f:=a.digit_value;io.println("{}",f('7'))}
'''
    result = build_and_run(source, tmp_path, zig, profile=profile)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "7\n"
    assert result.stderr == ""


def test_source_cycle_uses_canonical_identity_and_package_origin(package_root):
    package, project = package_root
    put(package, 'a.a7', 'b::import "b"')
    second = put(package, 'b.a7', 'a::import "std/a"')
    resolver = ModuleResolver([str(project)])
    with pytest.raises(SemanticError, match='/stdlib-source/a -> /stdlib-source/b -> /stdlib-source/a') as caught:
        resolver.load_module('std/a')
    assert caught.value.filename == str(second)
    assert not resolver.loaded_modules


def test_source_semantic_failure_is_located_in_source_module(package_root):
    package, project = package_root
    origin = put(package, 'bad.a7', 'value::fn()i32{ret "bad"}')
    result = expect_exit('b::import "std/bad"\nmain::fn(){}', project, 6, 'mismatch')
    assert any(detail.get('file') == str(origin) for detail in result.failure.details)
