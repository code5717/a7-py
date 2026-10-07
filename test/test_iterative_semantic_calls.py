"""Deep call summaries retain callback forwarding and lexical shadowing.

Nested FOR initializers exercise pass-level AST traversal. Source tests cover
parser-supported loops and defers through the whole compiler.
"""

import sys
from contextlib import contextmanager

from a7.ast_nodes import ASTNode, NodeKind
from a7.passes.semantic_validator import SemanticValidationPass
from a7.symbol_table import SymbolTable
from conftest import expect_ok, low_recursion_limit


@contextmanager
def limited_stack():
    previous = sys.getrecursionlimit()
    sys.setrecursionlimit(low_recursion_limit())
    try:
        yield
    finally:
        sys.setrecursionlimit(previous)


def call(name, argument=None):
    return ASTNode(kind=NodeKind.CALL,
                   function=ASTNode(kind=NodeKind.IDENTIFIER, name=name),
                   arguments=[] if argument is None else [
                       ASTNode(kind=NodeKind.IDENTIFIER, name=argument)])


def test_deep_loop_initializers_collect_named_calls():
    init = ASTNode(kind=NodeKind.EXPRESSION_STMT, expression=call("start"))
    for _ in range(300):
        init = ASTNode(kind=NodeKind.FOR, init=init, condition=call("condition"),
                       update=call("update"),
                       body=ASTNode(kind=NodeKind.EXPRESSION_STMT, expression=call("body")))
    function = ASTNode(kind=NodeKind.FUNCTION, name="owner", body=init)
    validator = SemanticValidationPass(SymbolTable(), {})
    with limited_stack():
        calls = validator._collect_function_calls(
            function, {"start", "condition", "update", "body"}, track_aliases=False)
    assert calls == {"start", "condition", "update", "body"}


def test_deep_loop_initializers_keep_callback_aliases_local():
    init = ASTNode(kind=NodeKind.VAR, name="first",
                   value=ASTNode(kind=NodeKind.IDENTIFIER, name="second"))
    for _ in range(300):
        init = ASTNode(kind=NodeKind.FOR, init=init,
                       condition=call("first", "second"))
    function = ASTNode(kind=NodeKind.FUNCTION, name="owner", body=init,
                       parameters=[ASTNode(kind=NodeKind.PARAMETER, name=name)
                                   for name in ("first", "second")])
    validator = SemanticValidationPass(SymbolTable(), {})
    with limited_stack():
        called, forwarding = validator._collect_called_parameter_usage(function)
    assert called == {0, 1}
    # Only the innermost loop sees the initializer's shadowing declaration.
    assert forwarding == [(1, [1])] + [(0, [1])] * 299


def test_deep_deferred_statements_reach_control_flow_validation():
    statement = ASTNode(kind=NodeKind.BREAK)
    for _ in range(300):
        statement = ASTNode(kind=NodeKind.DEFER, statement=statement)
    function = ASTNode(kind=NodeKind.FUNCTION, name="owner", body=statement)
    validator = SemanticValidationPass(SymbolTable(), {})
    with limited_stack():
        validator.visit_function_decl(function)
    assert len(validator.errors) == 1
    assert "Break statement outside loop" in str(validator.errors[0])
    assert not validator.context.in_function()


def test_source_loops_callbacks_and_nested_defers_compile(tmp_path):
    expect_ok('''
io :: import "std/io"
positive :: fn(x: i32) bool { ret x > 0 }
visit :: fn(check: fn(i32) bool) {
    for keep := check(1); keep; keep = false {
        defer { defer io.println("done") }
    }
}
main :: fn() { visit(positive) }
''', tmp_path)
