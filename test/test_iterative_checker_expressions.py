"""Expression depth must not consume the checker's Python call stack."""

from pathlib import Path
import subprocess
import sys

import pytest

from a7.ast_nodes import ASTNode, LiteralKind, NodeKind
from a7.passes.type_checker import TypeCheckingPass
from a7.symbol_table import SymbolTable


def test_real_unary_sources_and_parser_limited_calls_at_python_limit_100(tmp_path):
    code = r'''
import pathlib, sys
from a7.compile import A7Compiler
from a7.parser import Parser
from a7.tokens import Tokenizer
from a7.passes.name_resolution import NameResolutionPass
from a7.passes.type_checker import TypeCheckingPass
folder = pathlib.Path(sys.argv[1])
for depth in (30, 60):
    for bad in (False, True):
        source = 'f :: fn(b:' + ('i32' if bad else 'bool') + ')bool {ret ' + 'not '*depth + 'b}\nmain :: fn(){}'
        sys.setrecursionlimit(100)
        tree = Parser(Tokenizer(source).tokenize()).parse()
        resolver = NameResolutionPass(); symbols = resolver.analyze(tree, 'unary.a7')
        assert not resolver.errors
        checker = TypeCheckingPass(symbols); checker.analyze(tree, 'unary.a7')
        assert len(checker.errors) == int(bad), checker.errors
        if bad:
            assert 'bool' in str(checker.errors[0])
        assert len(symbols.scope_stack) == 1
        # Thirty unary operators also fit the independent backend boundary.
        if depth == 30:
            path = folder / ('bad.a7' if bad else 'good.a7'); path.write_text(source)
            result = A7Compiler().compile_file_detailed(str(path), str(path.with_suffix('.zig')))
            assert int(result.exit_code) == (6 if bad else 0), result.failure
for bad in (False, True):
    source = 'f :: fn(x:i32)i32 {ret x}\nmain :: fn(){v:' + ('bool=false' if bad else 'i32=1') + ';x:=' + 'f('*60 + 'v' + ')'*60 + '}'
    # The parser's expression recursion is a separate, still-open boundary.
    sys.setrecursionlimit(1000)
    tree = Parser(Tokenizer(source).tokenize()).parse()
    resolver = NameResolutionPass(); symbols = resolver.analyze(tree, 'calls.a7')
    assert not resolver.errors
    sys.setrecursionlimit(100)
    checker = TypeCheckingPass(symbols); checker.analyze(tree, 'calls.a7')
    assert len(checker.errors) == int(bad), checker.errors
    if bad:
        assert 'Argument 1' in str(checker.errors[0])
assert sys.getrecursionlimit() == 100
'''
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path)],
                            cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_deep_compound_arms_and_array_fitting_at_python_limit_100():
    code = r'''
import sys
from a7.ast_nodes import ASTNode, NodeKind, LiteralKind, BinaryOp
from a7.errors import SourceSpan
from a7.parser import Parser
from a7.tokens import Tokenizer
from a7.passes.name_resolution import NameResolutionPass
from a7.passes.type_checker import TypeCheckingPass
from a7.types import ArrayType, I8, I32

def literal(value):
    return ASTNode(NodeKind.LITERAL, literal_kind=LiteralKind.INTEGER, literal_value=value)
for shape in ('right_binary', 'if', 'match', 'array'):
    for bad in (False, True):
        tree = Parser(Tokenizer('f :: fn(x:i32, flag:bool)i32 {ret x}\nmain :: fn(){}').tokenize()).parse()
        resolver = NameResolutionPass(); symbols = resolver.analyze(tree)
        checker = TypeCheckingPass(symbols); checker.analyze(tree)
        span = SourceSpan(9, 3, 9, 8)
        leaf = ASTNode(NodeKind.IDENTIFIER, name='missing' if bad else 'value', span=span)
        # Use a checked variable so constant folding cannot erase the depth.
        from a7.symbol_table import Symbol, SymbolKind
        symbols.define(Symbol('value', SymbolKind.VARIABLE, I32))
        node = leaf
        expected = I8
        if shape == 'array':
            node = literal(300 if bad else 7)
        for _ in range(180):
            if shape == 'right_binary':
                node = ASTNode(NodeKind.BINARY, operator=BinaryOp.ADD, left=literal(1), right=node)
            elif shape == 'if':
                node = ASTNode(NodeKind.IF_EXPR, condition=ASTNode(NodeKind.LITERAL, literal_kind=LiteralKind.BOOLEAN, literal_value=True), then_expr=node, else_expr=literal(2))
            elif shape == 'match':
                case = ASTNode(NodeKind.CASE_BRANCH, patterns=[ASTNode(NodeKind.PATTERN_WILDCARD)], expression=node)
                node = ASTNode(NodeKind.MATCH_EXPR, expression=literal(1), cases=[case])
            else:
                node = ASTNode(NodeKind.ARRAY_INIT, elements=[node])
                expected = ArrayType(expected, 1)
        sys.setrecursionlimit(100)
        actual = checker.visit_expression(node)
        if shape == 'array':
            accepted = checker._is_initializer_assignable_to(node, actual, expected, span)
            assert accepted is not bad, (shape, checker.errors)
        elif not bad:
            assert actual.equals(I32), (shape, actual)
        assert len(checker.errors) == int(bad), (shape, checker.errors)
        if bad and shape != 'array':
            assert checker.errors[0].span is span
            assert 'missing' in str(checker.errors[0])
        assert len(symbols.scope_stack) == 1
        sys.setrecursionlimit(1000)
'''
    result = subprocess.run([sys.executable, '-c', code],
                            cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_match_arm_exception_restores_nested_scopes(monkeypatch):
    checker = TypeCheckingPass(SymbolTable())
    node = ASTNode(NodeKind.IDENTIFIER, name='fault')
    for _ in range(8):
        arm = ASTNode(NodeKind.CASE_BRANCH,
                      patterns=[ASTNode(NodeKind.PATTERN_WILDCARD)], expression=node)
        node = ASTNode(NodeKind.MATCH_EXPR,
                       expression=ASTNode(NodeKind.LITERAL, literal_kind=LiteralKind.INTEGER,
                                          literal_value=1), cases=[arm])
    original_scope = checker.symbols.current_scope

    def fail_at_identifier(_node):
        # Inject a leaf failure while arm scopes are active. This checks unwind,
        # not the behavior of a particular internal expression action.
        assert len(checker.symbols.scope_stack) == 9
        raise ValueError('leaf failure')

    monkeypatch.setattr(checker, 'visit_identifier', fail_at_identifier)
    with pytest.raises(ValueError, match='leaf failure'):
        checker.visit_expression(node)
    assert checker.symbols.current_scope is original_scope
    assert len(checker.symbols.scope_stack) == 1
    assert not checker.errors
