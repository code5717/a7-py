"""Stack-independent flow queries, separate from parser and native execution."""

import sys

import pytest

from a7.ast_nodes import ASTNode, NodeKind, create_block, create_identifier
from a7.passes.semantic_validator import SemanticValidationPass
from a7.symbol_table import SymbolTable
from a7.types import BOOL
from conftest import low_recursion_limit


def validator():
    result = SemanticValidationPass(SymbolTable(), {})
    result.context.enter_function("example", None, ASTNode(NodeKind.FUNCTION))
    return result


def returning():
    return ASTNode(NodeKind.RETURN)


def branch(left, right):
    return ASTNode(NodeKind.IF_STMT, then_stmt=left, else_stmt=right)


def wildcard_match(checker, body):
    expression = create_identifier("condition")
    checker.node_types[id(expression)] = BOOL
    case = ASTNode(
        NodeKind.CASE_BRANCH, statement=body,
        patterns=[ASTNode(NodeKind.PATTERN_WILDCARD)],
    )
    return ASTNode(NodeKind.MATCH, expression=expression, cases=[case])


@pytest.mark.parametrize("query", ["_returns_on_all_paths", "_statement_exits_current_block"])
def test_deep_mixed_branches_preserve_complete_and_missing_paths(query):
    """A deep total branch tree returns; a single missing path makes it partial."""
    checker = validator()
    total = returning()
    partial = create_block()
    for _ in range(180):
        total = branch(create_block([wildcard_match(checker, total)]), returning())
        partial = branch(create_block([wildcard_match(checker, partial)]), returning())
    old_limit = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(low_recursion_limit())
        assert getattr(checker, query)(total) is True
        assert getattr(checker, query)(partial) is False
    finally:
        sys.setrecursionlimit(old_limit)


def test_block_exit_stops_before_unreachable_invalid_loop_control():
    checker = validator()
    body = create_block([returning(), ASTNode(NodeKind.BREAK)])
    assert checker._statement_exits_current_block(body) is True
    assert checker.context.errors == []
    # Return completeness keeps its existing last-statement rule. Reachability
    # diagnostics, rather than this query, reject the trailing statement.
    assert checker._returns_on_all_paths(body) is False


def test_partial_branch_does_not_validate_unneeded_else_control():
    checker = validator()
    assert checker._statement_exits_current_block(
        branch(create_block(), ASTNode(NodeKind.CONTINUE))
    ) is False
    assert checker.context.errors == []


def test_loop_control_requires_valid_context_and_is_not_a_return():
    checker = validator()
    breaker = ASTNode(NodeKind.BREAK, label="outer")
    continuer = ASTNode(NodeKind.CONTINUE, label="outer")
    assert checker._statement_exits_current_block(breaker) is False
    assert checker.context.errors == ["'break' statement outside of loop"]
    checker.context.clear_errors()
    checker.context.enter_loop("outer")
    assert checker._statement_exits_current_block(branch(breaker, continuer)) is True
    assert checker.context.errors == []
    assert checker._returns_on_all_paths(branch(breaker, continuer)) is False
    checker.context.exit_function()
    assert checker._statement_exits_current_block(returning()) is False


def test_match_requires_coverage_and_terminating_case_bodies():
    checker = validator()
    match = wildcard_match(checker, returning())
    assert checker._returns_on_all_paths(match) is True
    assert checker._statement_exits_current_block(match) is True
    match.cases[0].patterns = []
    assert checker._returns_on_all_paths(match) is False
    assert checker._statement_exits_current_block(match) is False
    match.else_case = [returning()]
    assert checker._returns_on_all_paths(match) is True
    assert checker._statement_exits_current_block(match) is True
    match.cases[0].statement = None
    match.cases[0].statements = [ASTNode(NodeKind.FALL)]
    assert checker._returns_on_all_paths(match) is False
    assert checker._statement_exits_current_block(match) is True
