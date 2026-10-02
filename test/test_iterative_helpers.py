"""Depth and behavior requirements for three compiler helpers.

These isolated tests do not qualify deep programs through the whole compiler.
Subprocesses set the recursion limit after imports to avoid pytest stack overhead.
"""
import subprocess
import sys
import textwrap
from pathlib import Path

import a7

ROOT = Path(a7.__file__).resolve().parent.parent


def run_at_low_limit(source):
    result = subprocess.run(
        [sys.executable, '-c', textwrap.dedent(source)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_integer_literal_negation_depth_and_nonliteral_boundary():
    run_at_low_limit(r'''
        import sys
        from a7.ast_nodes import ASTNode, NodeKind, LiteralKind, UnaryOp
        from a7.passes.safety import SafetyProofPass
        from a7.symbol_table import SymbolTable
        proof = SafetyProofPass(SymbolTable(), {})
        value = ASTNode(kind=NodeKind.LITERAL, literal_kind=LiteralKind.INTEGER, literal_value=17)
        for _ in range(5000):
            value = ASTNode(kind=NodeKind.UNARY, operator=UnaryOp.NEG, operand=value)
        sys.setrecursionlimit(100)
        assert proof._int_literal(value) == 17
        value = ASTNode(kind=NodeKind.UNARY, operator=UnaryOp.NEG, operand=value)
        assert proof._int_literal(value) == -17
        assert proof._int_literal(ASTNode(kind=NodeKind.IDENTIFIER, name='unknown')) is None
        assert proof._int_literal(ASTNode(kind=NodeKind.UNARY, operator=UnaryOp.NEG,
            operand=ASTNode(kind=NodeKind.LITERAL, literal_kind=LiteralKind.FLOAT, literal_value=2.5))) is None
        assert proof._int_literal(None) is None
    ''')


def test_mutation_base_depth_and_dereference_boundary():
    run_at_low_limit(r'''
        import sys
        from a7.ast_nodes import ASTNode, NodeKind
        from a7.backends.zig import ZigCodeGenerator
        direct = ASTNode(kind=NodeKind.IDENTIFIER, name='buffer')
        indirect = ASTNode(kind=NodeKind.DEREF,
            operand=ASTNode(kind=NodeKind.IDENTIFIER, name='pointer'))
        for i in range(5000):
            kind = NodeKind.FIELD_ACCESS if i % 2 else NodeKind.INDEX
            direct = ASTNode(kind=kind, object=direct)
            indirect = ASTNode(kind=kind, object=indirect)
        root = ASTNode(kind=NodeKind.BLOCK, statements=[
            ASTNode(kind=NodeKind.ASSIGNMENT, target=direct),
            ASTNode(kind=NodeKind.ASSIGNMENT, target=indirect),
        ])
        generator = ZigCodeGenerator()
        sys.setrecursionlimit(100)
        assert generator._collect_mutations(root) == {'buffer'}
    ''')


def test_scope_dump_preserves_order_indent_and_handles_deep_scopes():
    run_at_low_limit(r'''
        import sys
        from a7.symbol_table import SymbolTable, Scope, Symbol, SymbolKind
        from a7.types import I32
        table = SymbolTable()
        table.global_scope.define(Symbol('z', SymbolKind.VARIABLE, I32))
        table.global_scope.define(Symbol('a', SymbolKind.VARIABLE, I32, is_used=True))
        left = Scope('left', table.global_scope)
        leaf = Scope('leaf', left)
        right = Scope('right', table.global_scope)
        sys.setrecursionlimit(100)
        assert table.dump() == (
            'global:\n'
            '  [✓] Symbol(a: i32 [VARIABLE, const])\n'
            '  [✗] Symbol(z: i32 [VARIABLE, const])\n'
            '  left:\n'
            '    leaf:\n'
            '  right:'
        )
        assert table.dump(left, 2) == '    left:\n      leaf:'
        current = right
        for depth in range(1, 2001):
            current = Scope('deep' + str(depth), current)
        lines = table.dump(right).splitlines()
        assert len(lines) == 2001
        assert lines[0] == 'right:'
        assert lines[-1] == '  ' * 2000 + 'deep2000:'
        assert lines[1] == '  deep1:'
    ''')
