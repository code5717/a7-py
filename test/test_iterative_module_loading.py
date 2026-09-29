"""Dependency depth, diagnostics and retry behavior through real module files."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from a7.errors import SemanticError
from a7.module_resolver import ModuleResolver

ROOT = Path(__file__).resolve().parents[1]


def compile_low_limit(source, output):
    # Import the CLI before reducing the limit so this checks the compiler,
    # rather than Python's module-import machinery.
    return subprocess.run(
        [sys.executable, '-c',
         'import sys; from a7.cli import main; sys.setrecursionlimit(100); main()',
         str(source), '--format', 'json', '--output', str(output)],
        cwd=ROOT, capture_output=True, text=True,
    )


def test_1100_module_chain_compiles_at_recursion_limit_100(tmp_path):
    for index in range(1100):
        dependency = f'dep{index} :: import "m{index + 1}"\n' if index < 1099 else ''
        (tmp_path / f'm{index}.a7').write_text(dependency + f'value{index} :: {index}\n')
    source = tmp_path / 'main.a7'
    source.write_text('root :: import "m0"\nmain :: fn() {}\n')
    output = tmp_path / 'main.zig'
    result = compile_low_limit(source, output)
    payload = json.loads(result.stdout)
    assert result.returncode == 0, payload
    assert payload['status'] == 'ok'
    emitted = output.read_text()
    assert 'value0' in emitted
    # A failure at the far end proves the loader visited the entire chain.
    # Current combined-file emission includes only direct module declarations.
    leaf = tmp_path / 'm1099.a7'
    leaf.write_text('last :: import "absent"\n')
    failure_output = tmp_path / 'failed.zig'
    failure = compile_low_limit(source, failure_output)
    diagnostic = json.loads(failure.stdout)
    assert failure.returncode == 6, diagnostic
    assert "Module 'absent' not found" in str(diagnostic['error'])
    assert str(leaf) in str(diagnostic['error'])
    assert not failure_output.exists()


@pytest.mark.parametrize('failure', ['missing', 'cycle'])
def test_dependency_failure_has_import_origin_and_no_output(tmp_path, failure):
    source = tmp_path / 'main.a7'
    source.write_text('root :: import "a"\nmain :: fn() {}\n')
    (tmp_path / 'a.a7').write_text('next :: import "b"\n')
    target = 'missing' if failure == 'missing' else 'a'
    (tmp_path / 'b.a7').write_text(f'next :: import "{target}"\n')
    output = tmp_path / 'main.zig'
    result = compile_low_limit(source, output)
    payload = json.loads(result.stdout)
    assert result.returncode == 6, payload
    diagnostic = str(payload['error'])
    expected = "Module 'missing' not found" if failure == 'missing' else 'a -> b -> a'
    assert expected in diagnostic
    assert str(tmp_path / 'b.a7') in diagnostic
    assert not output.exists()


def test_failed_load_does_not_poison_cache_and_retry_preserves_completed_modules(tmp_path):
    (tmp_path / 'root.a7').write_text('ok :: import "good"\nnext :: import "missing"\n')
    (tmp_path / 'good.a7').write_text('value :: 7\n')
    resolver = ModuleResolver([str(tmp_path)])
    for _ in range(2):
        with pytest.raises(SemanticError, match="Module 'missing' not found"):
            resolver.load_module('root')
        assert 'root' not in resolver.loaded_modules
        assert resolver.module_table.get_module('root') is None
        assert resolver.loading_stack == []
    good = resolver.get_module('good')
    (tmp_path / 'missing.a7').write_text('value :: 8\n')
    loaded = resolver.load_module('root')
    assert loaded.dependencies == ['good', 'missing']
    assert resolver.get_module('good') is good
    assert resolver.load_module('root') is loaded


def test_diamond_keeps_source_order_cache_identity_and_symbol_origins(tmp_path):
    sources = {
        'root': 'left :: import "left"\nright :: import "right"\n',
        'left': 'shared :: import "shared"\n',
        'right': 'shared :: import "shared"\n',
        'shared': 'value :: 7\n',
    }
    for name, source in sources.items():
        (tmp_path / f'{name}.a7').write_text(source)
    resolver = ModuleResolver([str(tmp_path)])
    root = resolver.load_module('root')
    assert list(resolver.loaded_modules) == ['root', 'left', 'shared', 'right']
    shared = resolver.load_module('shared')
    assert shared is resolver.get_module('shared')
    assert shared.ast.declarations[0].span.origin_file == str(tmp_path / 'shared.a7')
    assert resolver.load_module('root') is root
    assert resolver.loading_stack == []
