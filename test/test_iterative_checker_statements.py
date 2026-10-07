"""Statement continuations retain diagnostics and lexical state at depth."""

import sys

import pytest

from a7.ast_nodes import ASTNode, LiteralKind, NodeKind
from a7.errors import SemanticErrorType, SourceSpan, TypeErrorType
from a7.parser import Parser
from a7.passes.name_resolution import NameResolutionPass
from a7.passes.type_checker import TypeCheckingPass
from a7.tokens import Tokenizer
from conftest import expect_exit, expect_ok, low_recursion_limit


def check_program(program):
    resolver = NameResolutionPass()
    symbols = resolver.analyze(program)
    assert not resolver.errors
    checker = TypeCheckingPass(symbols)
    checker.analyze(program)
    return checker


def check_source(source):
    return check_program(Parser(Tokenizer(source).tokenize()).parse())


def literal(kind, value):
    return ASTNode(kind=NodeKind.LITERAL, literal_kind=kind, literal_value=value)


@pytest.mark.parametrize('invalid', [False, True])
@pytest.mark.parametrize('shape', ['mixed', 'match_for_in'])
def test_deep_statements_reach_typed_leaf_and_restore_context(shape, invalid):
    span = SourceSpan(17, 2, 17, 8)
    leaf = ASTNode(kind=NodeKind.VAR, name='result', span=span,
                   explicit_type=ASTNode(kind=NodeKind.TYPE_PRIMITIVE, type_name='i32'),
                   value=literal(LiteralKind.STRING, 'bad') if invalid
                   else literal(LiteralKind.INTEGER, 7))
    statement = leaf
    for depth in range(1601):
        if shape == 'mixed':
            kind = (NodeKind.BLOCK, NodeKind.IF_STMT, NodeKind.WHILE,
                    NodeKind.FOR, NodeKind.DEFER)[depth % 5]
            if kind == NodeKind.BLOCK:
                statement = ASTNode(kind=kind, statements=[statement])
            elif kind == NodeKind.IF_STMT:
                statement = ASTNode(kind=kind, condition=literal(LiteralKind.BOOLEAN, True),
                                    then_stmt=statement)
            elif kind == NodeKind.DEFER:
                statement = ASTNode(kind=kind, statement=statement)
            else:
                statement = ASTNode(kind=kind, condition=literal(LiteralKind.BOOLEAN, False),
                                    body=statement)
        elif depth % 2:
            statement = ASTNode(kind=NodeKind.FOR_IN_INDEXED, iterator=f'value{depth}',
                                index_var=f'index{depth}', iterable=literal(LiteralKind.STRING, 'a'),
                                body=statement)
        else:
            case = ASTNode(kind=NodeKind.CASE_BRANCH,
                           patterns=[ASTNode(kind=NodeKind.PATTERN_WILDCARD)],
                           statement=statement)
            statement = ASTNode(kind=NodeKind.MATCH, expression=literal(LiteralKind.BOOLEAN, True),
                                cases=[case])
    program = ASTNode(kind=NodeKind.PROGRAM, declarations=[
        ASTNode(kind=NodeKind.FUNCTION, name='main', parameters=[], body=statement)])
    previous = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(low_recursion_limit())
        checker = check_program(program)
    finally:
        sys.setrecursionlimit(previous)
    assert len(checker.errors) == int(invalid)
    if invalid:
        assert checker.errors[0].error_type == TypeErrorType.TYPE_MISMATCH
        assert checker.errors[0].span is span
    else:
        assert str(checker.node_types[id(leaf)]) == 'i32'
    assert len(checker.symbols.scope_stack) == 1
    assert not checker.context.loop_stack
    assert checker.context.current_function is None
    assert not checker._nonnegative_vars
    assert not checker._nested_functions


def test_for_diagnostics_keep_condition_update_body_order():
    checker = check_source('''main :: fn() {
for i := 0; 3; i = "update" {
x: i32 = "body"
}
}''')
    assert [(e.error_type, e.span.start_line, e.span.start_column) for e in checker.errors] == [
        (TypeErrorType.CONDITION_NOT_BOOL, 2, 13),
        (TypeErrorType.ASSIGNMENT_TYPE_MISMATCH, 2, 16),
        (TypeErrorType.TYPE_MISMATCH, 3, 1),
    ]


def test_match_diagnostics_interleave_bodies_patterns_and_exhaustiveness():
    checker = check_source('''main :: fn() {
match true {
case true: { x: i32 = "first" }
case true: { y: bool = 3 }
}
}''')
    assert [(e.error_type, e.span.start_line) for e in checker.errors] == [
        (TypeErrorType.TYPE_MISMATCH, 3),
        (SemanticErrorType.UNREACHABLE_CODE, 4),
        (TypeErrorType.TYPE_MISMATCH, 4),
        (SemanticErrorType.NON_EXHAUSTIVE_MATCH, 2),
    ]


def test_sibling_function_scopes_and_forward_calls_compile(tmp_path):
    expect_ok('''main :: fn() {
    { x: i32 = local(2); local :: fn(x: i32) i32 { ret x } }
    { x: string = local("ok"); local :: fn(x: string) string { ret x } }
}''', tmp_path)
    expect_exit('''main :: fn() {
    { x: i32 = 1 }
    { y: i32 = x }
}''', tmp_path, 6, 'Undefined identifier')


def test_for_in_binding_types_and_scope_compile(tmp_path):
    expect_ok('''main :: fn() {
    for i, value in [1, 2] { index: usize = i; number: i32 = value }
    for value in "ab" { letter: char = value }
}''', tmp_path)
    expect_exit('''main :: fn() {
    for i, value in [1, 2] { text: string = value }
}''', tmp_path, 6, 'Type mismatch')


def test_fact_regions_preserve_branch_and_early_return_boundaries():
    # Observe statement entry while retaining the real declaration/type checker.
    # Numeric conversion safety itself belongs to the safety-pass tests.
    class ObservedChecker(TypeCheckingPass):
        def visit_var_decl(self, node):
            observed[node.name] = set(self._nonnegative_vars)
            super().visit_var_decl(node)

    source = '''probe :: fn(x: i32) {
if x >= 0 { positive: i32 = x } else { negative: i32 = x }
outside: i32 = x
{ if x < 0 { ret }; guarded: i32 = x }
after_block: i32 = x
}'''
    program = Parser(Tokenizer(source).tokenize()).parse()
    resolver = NameResolutionPass()
    symbols = resolver.analyze(program)
    assert not resolver.errors
    observed = {}
    checker = ObservedChecker(symbols)
    checker.analyze(program)
    assert not checker.errors
    assert observed == {'positive': {'x'}, 'negative': set(), 'outside': set(),
                        'guarded': {'x'}, 'after_block': set()}


def test_leaf_exception_unwinds_protected_scopes_loops_and_facts(monkeypatch):
    # The injected leaf failure isolates traversal cleanup. Other tests check
    # actual leaf typing. No queued later statement may run after this failure.
    source = '''probe :: fn(x: i32) {
for i := 0; true; i = 1 {
if x >= 0 { match true { case _: { failure: i32 = x } } }
}
after: i32 = 0
}'''
    program = Parser(Tokenizer(source).tokenize()).parse()
    resolver = NameResolutionPass()
    symbols = resolver.analyze(program)
    assert not resolver.errors
    checker = TypeCheckingPass(symbols)
    original = checker.visit_var_decl
    seen = []

    class LeafFailure(Exception):
        pass

    def fail_at_leaf(node):
        seen.append(node.name)
        if node.name == 'failure':
            assert checker._nonnegative_vars == {'x'}
            assert len(checker.context.loop_stack) == 1
            raise LeafFailure('leaf')
        original(node)

    monkeypatch.setattr(checker, 'visit_var_decl', fail_at_leaf)
    # Enter the real function scope explicitly: this test qualifies statement
    # finally regions, not the separate function visitor's exception policy.
    checker._enter_matching_scope('function_probe')
    starting_scopes = tuple(symbols.scope_stack)
    with pytest.raises(LeafFailure, match='leaf'):
        checker.visit_statement(program.declarations[0].body)
    assert seen == ['i', 'failure']
    assert tuple(symbols.scope_stack) == starting_scopes
    assert not checker.context.loop_stack
    assert not checker._nonnegative_vars


@pytest.mark.parametrize('legacy_list', [False, True])
def test_match_body_list_does_not_gain_block_fact_learning(legacy_list):
    class ObservedChecker(TypeCheckingPass):
        def visit_var_decl(self, node):
            observed[node.name] = set(self._nonnegative_vars)
            super().visit_var_decl(node)

    program = Parser(Tokenizer('''probe :: fn(x: i32) {
match true { case _: { if x < 0 { ret }; value: i32 = x } }
}''').tokenize()).parse()
    case = program.declarations[0].body.statements[0].cases[0]
    if legacy_list:
        case.statements = case.statement.statements
        case.statement = None
    resolver = NameResolutionPass()
    symbols = resolver.analyze(program)
    assert not resolver.errors
    observed = {}
    checker = ObservedChecker(symbols)
    checker.analyze(program)
    assert not checker.errors
    assert observed == {'value': set() if legacy_list else {'x'}}
    assert len(symbols.scope_stack) == 1
