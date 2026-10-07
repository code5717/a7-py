"""Type-checker helper results remain defined beyond Python's call depth."""

import sys
from contextlib import contextmanager

import pytest

from a7.ast_nodes import ASTNode, BinaryOp, LiteralKind, NodeKind
from a7.passes.type_checker import TypeCheckingPass
from a7.symbol_table import Symbol, SymbolKind, SymbolTable
from a7.types import ArrayType, FunctionType, GenericInstanceType, GenericParamType, I32, I64, STRING, StructType
from conftest import expect_ok, low_recursion_limit


@contextmanager
def limited_stack():
    previous = sys.getrecursionlimit()
    sys.setrecursionlimit(low_recursion_limit())
    try:
        yield
    finally:
        sys.setrecursionlimit(previous)


@pytest.mark.parametrize("leaf, returns", [(NodeKind.RETURN, True), (NodeKind.BREAK, False)])
def test_deep_final_statement_return_classification(leaf, returns):
    node = ASTNode(kind=leaf)
    for _ in range(300):
        node = ASTNode(kind=NodeKind.BLOCK, statements=[node])
    checker = TypeCheckingPass(SymbolTable())
    with limited_stack():
        actual = checker._statement_always_returns(node)
    assert actual is returns


def test_deep_range_diagnostic_keeps_start_end_order():
    node = ASTNode(kind=NodeKind.LITERAL, literal_kind=LiteralKind.INTEGER, literal_value=42)
    for _ in range(300):
        node = ASTNode(kind=NodeKind.PATTERN_RANGE, start=node,
                       end=ASTNode(kind=NodeKind.PATTERN_WILDCARD))
    checker = TypeCheckingPass(SymbolTable())
    with limited_stack():
        actual = checker._format_match_pattern(node)
    assert actual == "42" + ".._" * 300


@pytest.mark.parametrize("right_leaf, accepted", [(I64, True), (STRING, False)])
def test_deep_array_common_type_preserves_shape(right_leaf, accepted):
    left, right = I32, right_leaf
    for _ in range(300):
        left, right = ArrayType(left, 2), ArrayType(right, 2)
    checker = TypeCheckingPass(SymbolTable())
    with limited_stack():
        actual = checker._common_array_literal_element_type(left, right)
    if not accepted:
        assert actual is None
        return
    for _ in range(300):
        assert isinstance(actual, ArrayType)
        assert actual.size == 2
        actual = actual.element_type
    assert actual is I64


def test_deep_function_generic_substitution_keeps_mapped_record_identity():
    parameter = GenericParamType("T")
    node = parameter
    for _ in range(300):
        node = FunctionType((I32,), GenericInstanceType("Box", (node,)))
    record = StructType("Record", ())
    checker = TypeCheckingPass(SymbolTable())
    with limited_stack():
        actual = checker._substitute_generic(node, {"T": record})
    for _ in range(300):
        assert isinstance(actual, FunctionType)
        assert actual.param_types[0] is I32
        assert isinstance(actual.return_type, GenericInstanceType)
        assert actual.return_type.base_name == "Box"
        actual = actual.return_type.type_args[0]
    assert actual is record


def test_nested_array_inference_and_generic_call_compile(tmp_path):
    expect_ok('''
io :: import "std/io"
identity :: fn(value: $T) $T { ret value }
main :: fn() {
    small: i8 = 1
    wide: i64 = 2
    rows := [[small], [wide]]
    result := identity(rows)
    io.println("{} {}", result[0][0], result[1][0])
}
''', tmp_path)


def test_deep_constant_aliases_resolve_range_endpoints():
    symbols = SymbolTable()
    value = ASTNode(kind=NodeKind.LITERAL, literal_kind=LiteralKind.INTEGER, literal_value=17)
    for index in range(300):
        name = f"limit{index}"
        declaration = ASTNode(kind=NodeKind.CONST, name=name, value=value)
        symbols.define(Symbol(name, SymbolKind.CONSTANT, I32, declaration))
        value = ASTNode(kind=NodeKind.IDENTIFIER, name=name)
    checker = TypeCheckingPass(symbols)
    resolving = {"unrelated"}
    with limited_stack():
        actual = checker._range_pattern_value(
            ASTNode(kind=NodeKind.PATTERN_IDENTIFIER, name="limit299"), resolving)
    assert actual == ("number", 17)
    assert resolving == {"unrelated"}


@pytest.mark.parametrize("name", ["a", "missing", "variable"])
def test_range_alias_cycles_unknowns_and_variables_are_not_constants(name):
    symbols = SymbolTable()
    for source, target in (("a", "b"), ("b", "a")):
        declaration = ASTNode(kind=NodeKind.CONST, name=source,
                              value=ASTNode(kind=NodeKind.IDENTIFIER, name=target))
        symbols.define(Symbol(source, SymbolKind.CONSTANT, I32, declaration))
    symbols.define(Symbol("variable", SymbolKind.VARIABLE, I32,
                          ASTNode(kind=NodeKind.VAR, name="variable")))
    checker = TypeCheckingPass(symbols)
    assert checker._range_pattern_value(ASTNode(kind=NodeKind.PATTERN_IDENTIFIER, name=name), set()) is None


def test_literal_patterns_and_exact_expression_range_values_are_preserved():
    checker = TypeCheckingPass(SymbolTable())
    char = ASTNode(kind=NodeKind.PATTERN_LITERAL,
                   literal=ASTNode(kind=NodeKind.LITERAL, literal_kind=LiteralKind.CHAR, literal_value="a"))
    expression = ASTNode(kind=NodeKind.BINARY, operator=BinaryOp.ADD,
                         left=ASTNode(kind=NodeKind.LITERAL, literal_kind=LiteralKind.INTEGER, literal_value=2),
                         right=ASTNode(kind=NodeKind.LITERAL, literal_kind=LiteralKind.INTEGER, literal_value=3))
    assert checker._range_pattern_value(char, set()) == ("char", 97)
    assert checker._range_pattern_value(expression, set()) == ("number", 5)


def test_source_match_range_with_many_constant_aliases_compiles(tmp_path):
    aliases = ["C0 :: 1"] + [f"C{index} :: C{index - 1}" for index in range(1, 300)]
    source = 'io :: import "std/io"\n' + "\n".join(aliases) + '''
main :: fn() {
    value := 2
    match value {
        case C299..3: { io.println("hit") }
        else: { io.println("miss") }
    }
}
'''
    with limited_stack():
        expect_ok(source, tmp_path)
