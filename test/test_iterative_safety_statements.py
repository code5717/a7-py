"""Deep statements retain lifetime diagnostics without Python call-stack growth."""

import sys

import pytest

from a7.ast_nodes import ASTNode, LiteralKind, NodeKind
from a7.parser import Parser
from a7.passes.name_resolution import NameResolutionPass
from a7.passes.safety import SafetyProofPass
from a7.passes.type_checker import TypeCheckingPass
from a7.tokens import Tokenizer
from conftest import expect_exit, expect_ok, low_recursion_limit


def source_with_read(deleted):
    return ('Box::struct{value:i32}\nmain::fn(){b:=new Box;if b==nil{ret};'
            + ('del b;' if deleted else '') + 'v:=b.value}')


@pytest.mark.parametrize('deleted', [False, True])
@pytest.mark.parametrize('shape', ['blocks', 'branches'])
def test_deep_statement_leaf_keeps_lifetime_proof_and_restores_frames(deleted, shape):
    program = Parser(Tokenizer(source_with_read(deleted)).tokenize()).parse()
    body = program.declarations[-1].body
    statement = body.statements[-1]
    for depth in range(1601):
        if shape == 'branches' and depth % 2:
            statement = ASTNode(kind=NodeKind.IF_STMT,
                                condition=ASTNode(kind=NodeKind.LITERAL,
                                                  literal_kind=LiteralKind.BOOLEAN, literal_value=True),
                                then_stmt=statement)
        else:
            statement = ASTNode(kind=NodeKind.BLOCK, statements=[statement])
    body.statements[-1] = statement
    previous = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(low_recursion_limit())
        resolver = NameResolutionPass()
        symbols = resolver.analyze(program)
        assert not resolver.errors
        checker = TypeCheckingPass(symbols)
        checker.analyze(program)
        assert not checker.errors
        safety = SafetyProofPass(symbols, checker.node_types)
        safety.analyze(program)
    finally:
        sys.setrecursionlimit(previous)
    assert len(safety.errors) == int(deleted)
    if deleted:
        assert 'Use after move or delete' in str(safety.errors[0])
    assert safety.frames == []
    assert safety.defer_floor == 0


@pytest.mark.parametrize('deleted', [False, True])
def test_nested_source_reaches_safety_and_codegen_with_low_headroom(tmp_path, deleted):
    source = source_with_read(deleted).replace('v:=b.value', 'if true{' * 120 + 'v:=b.value' + '}' * 120)
    previous = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(low_recursion_limit())
        if deleted:
            expect_exit(source, tmp_path, 6, 'Use after move or delete')
        else:
            expect_ok(source, tmp_path)
    finally:
        sys.setrecursionlimit(previous)
