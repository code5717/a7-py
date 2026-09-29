"""AST-only CLI display and defensive handling of malformed cyclic ASTs."""
from pathlib import Path
import subprocess
import sys

from a7.ast_nodes import ASTNode, NodeKind
from a7.formatters.console_formatter import ConsoleFormatter

ROOT = Path(__file__).resolve().parents[1]


def test_cli_ast_displays_type_set_without_internal_error(tmp_path):
    source = tmp_path / 'typeset.a7'
    source.write_text('main :: fn() { x: @type_set(i32, i64) = 5 }\n')
    result = subprocess.run([sys.executable, str(ROOT / 'main.py'), str(source),
                             '--mode', 'ast'], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '@type_set(i32, i64)' in result.stdout
    assert 'Stopping before semantic analysis' in result.stdout
    assert 'Unexpected error' not in result.stdout
    assert not source.with_suffix('.zig').exists()


def test_type_cycles_terminate_without_suppressing_shared_children():
    view = ConsoleFormatter()
    result = subprocess.run([sys.executable, '-c', '''
from a7.ast_nodes import ASTNode, NodeKind
from a7.formatters.console_formatter import ConsoleFormatter
view = ConsoleFormatter()
wrapper = ASTNode(kind=NodeKind.TYPE_SLICE)
wrapper.element_type = wrapper
print(view.format_type(wrapper))
generic = ASTNode(kind=NodeKind.TYPE_GENERIC, name='Box')
generic.type_args = [generic]
print(view.format_type(generic))
'''], cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout == '[]<cycle>\nBox(<cycle>)\n'
    leaf = ASTNode(kind=NodeKind.TYPE_PRIMITIVE, type_name='i32')
    shared = ASTNode(kind=NodeKind.TYPE_FUNCTION, parameter_types=[leaf], return_type=leaf)
    pair = ASTNode(kind=NodeKind.TYPE_GENERIC, name='Pair', type_args=[shared, shared])
    assert view.format_type(pair) == 'Pair(fn(i32) i32, fn(i32) i32)'
    assert view.format_type(ASTNode(kind=NodeKind.TYPE_PRIMITIVE)) == 'primitive'
    assert view.format_type(ASTNode(kind=NodeKind.TYPE_IDENTIFIER)) == 'identifier'
    assert view.format_type(ASTNode(kind=NodeKind.TYPE_SET)) == '@type_set()'
    assert view.format_type('__inline__') == '__inline__'


def test_defer_cycle_terminates_and_shared_tail_is_repeatable():
    view = ConsoleFormatter()
    result = subprocess.run([sys.executable, '-c', '''
from a7.ast_nodes import ASTNode, NodeKind
from a7.formatters.console_formatter import ConsoleFormatter
first = ASTNode(kind=NodeKind.DEFER)
second = ASTNode(kind=NodeKind.DEFER, statement=first)
first.statement = second
print(ConsoleFormatter().format_statement_label(first))
'''], cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        '[blue]DEFER[/blue] → [blue]DEFER[/blue] → [dim]<cycle>[/dim]\n')
    tail = ASTNode(kind=NodeKind.RETURN)
    branches = [ASTNode(kind=NodeKind.DEFER, statement=tail) for _ in range(2)]
    for branch in branches:
        assert view.format_statement_label(branch) == (
            '[blue]DEFER[/blue] → [blue]RETURN[/blue] [dim](void)[/dim]')
