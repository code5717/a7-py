"""Filesystem lookup failures retain their import location and IO stage.

Real long-path cases exercise the CLI. Injected stat failures cover permission
and IO errors at the filesystem boundary, not host permission enforcement.
"""
import errno
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_import(tmp_path, path, *, transitive=False):
    main = tmp_path / "main.a7"
    source = '\n\nm :: import "' + path + '"\n'
    if transitive:
        owner = tmp_path / "helper.a7"
        owner.write_text(source + 'value :: 1\n')
        main.write_text('h :: import "helper"\nmain :: fn() {}\n')
    else:
        owner = main
        main.write_text(source + 'main :: fn() {}\n')
    output = tmp_path / "result.zig"
    result = subprocess.run(
        [sys.executable, str(ROOT / 'main.py'), '--mode', 'compile', '--format', 'json',
         '-o', str(output), str(main)], capture_output=True, text=True,
        env=dict(os.environ, PYTHONPATH=str(ROOT)),
    )
    assert result.stderr == ''
    return result, json.loads(result.stdout), owner, output


@pytest.mark.parametrize('path', ['a' * 300, 'a/' * 2500 + 'leaf'])
@pytest.mark.parametrize('transitive', [False, True])
@pytest.mark.parametrize('reserved', [False, True])
def test_long_import_path_is_located_io_error(tmp_path, path, transitive, reserved):
    if reserved:
        (tmp_path / 'std').mkdir()
        path = 'std/' + path
    result, payload, owner, output = run_import(tmp_path, path, transitive=transitive)
    assert result.returncode == 3, result.stdout
    assert payload['error']['category'] == 'io'
    [detail] = payload['error']['details']
    assert detail['type'] == 'ImportError'
    assert 'File name too long' in detail['message']
    assert path in detail['message']
    assert detail['file'] == str(owner)
    assert detail['span']['start_line'] == 3
    assert detail['span']['start_column'] == 1
    assert not output.exists()


@pytest.mark.parametrize('path', ['missing', 'std/missing'])
@pytest.mark.parametrize('transitive', [False, True])
def test_absent_import_stays_missing_with_its_owner(tmp_path, path, transitive):
    result, payload, owner, output = run_import(tmp_path, path, transitive=transitive)
    assert result.returncode == 3
    [detail] = payload['error']['details']
    assert detail['type'] == 'ImportError'
    assert detail['message'] == f"Module '{path}' not found"
    assert detail['file'] == str(owner)
    assert detail['span']['start_line'] == 3
    assert not output.exists()


def test_reserved_shadow_remains_a_reserved_path_error(tmp_path):
    (tmp_path / 'std').mkdir()
    (tmp_path / 'std/math.a7').write_text('value :: 1\n')
    result, payload, owner, output = run_import(tmp_path, 'std/math')
    assert result.returncode == 3
    [detail] = payload['error']['details']
    assert 'reserved for the standard library' in detail['message']
    assert detail['file'] == str(owner)
    assert detail['span']['start_line'] == 3
    assert not output.exists()


@pytest.mark.parametrize('path', ['helper', 'std/math'])
def test_valid_import_still_emits(tmp_path, path):
    (tmp_path / 'helper.a7').write_text('answer :: fn() i32 { ret 42 }\n')
    result, payload, owner, output = run_import(tmp_path, path)
    assert result.returncode == 0, result.stdout
    assert payload['status'] == 'ok'
    assert output.is_file()


@pytest.mark.parametrize('error_number', [errno.EACCES, errno.EIO])
@pytest.mark.parametrize('path', ['blocked', 'std/math'])
def test_stat_error_is_not_reclassified_as_missing(tmp_path, monkeypatch, error_number, path):
    from conftest import compile_program
    target = tmp_path / (path + '.a7')
    original = Path.stat

    def fail_target(self, *args, **kwargs):
        if self == target:
            raise OSError(error_number, os.strerror(error_number), str(self))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'stat', fail_target)
    result = compile_program('\n\nm :: import "' + path + '"\nmain :: fn() {}', tmp_path)
    assert int(result.exit_code) == 3
    assert result.failure.category == 'io'
    [detail] = result.failure.details
    assert detail['type'] == 'ImportError'
    assert os.strerror(error_number) in detail['message']
    assert 'not found' not in detail['message']
    assert detail['file'] == str(tmp_path / 'main.a7')
    assert detail['span']['start_line'] == 3


def test_resolver_lookup_keeps_original_os_error_as_cause(tmp_path):
    from a7.errors import ImportError as A7ImportError
    from a7.module_resolver import ModuleResolver
    resolver = ModuleResolver([str(tmp_path)])
    with pytest.raises(A7ImportError) as raised:
        resolver.resolve_module_path('a' * 300)
    assert isinstance(raised.value.__cause__, OSError)
    assert raised.value.__cause__.errno == errno.ENAMETOOLONG


def test_later_dependency_lookup_keeps_transitive_import_location(tmp_path, monkeypatch):
    # A dependency can become inaccessible after it was loaded. Trigger that
    # filesystem boundary after load_module returns, without timing a real race.
    from a7.module_resolver import ModuleResolver
    from conftest import compile_program
    (tmp_path / 'helper.a7').write_text('\n\nleaf :: import "leaf"\nvalue :: 1\n')
    (tmp_path / 'leaf.a7').write_text('value :: 2\n')
    loaded = False
    original_load = ModuleResolver.load_module
    original_stat = Path.stat

    def finish_load(self, path, importing_file=None):
        nonlocal loaded
        result = original_load(self, path, importing_file)
        loaded = True
        return result

    def fail_later(self, *args, **kwargs):
        if loaded and self == tmp_path / 'leaf.a7':
            raise OSError(errno.EIO, 'Input/output error', str(self))
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(ModuleResolver, 'load_module', finish_load)
    monkeypatch.setattr(Path, 'stat', fail_later)
    result = compile_program('h :: import "helper"\nmain :: fn() {}', tmp_path)
    assert int(result.exit_code) == 3
    [detail] = result.failure.details
    assert detail['type'] == 'ImportError'
    assert 'Input/output error' in detail['message']
    assert detail['file'] == str(tmp_path / 'helper.a7')
    assert detail['span']['start_line'] == 3
