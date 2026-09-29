"""Console output contracts independent of parser recursion and terminal state."""

from io import StringIO
import sys

from rich.console import Console
from rich.tree import Tree

from a7.ast_nodes import ASTNode, LiteralKind, NodeKind
from a7.formatters.console_formatter import ConsoleFormatter
from a7.tokens import Token, TokenType


def formatter():
    result = ConsoleFormatter(mode="ast")
    output = StringIO()
    result.console = Console(file=output, width=80, color_system=None)
    return result, output


def test_shallow_ast_render_matches_baseline():
    body = ASTNode(kind=NodeKind.BLOCK, statements=[
        ASTNode(kind=NodeKind.DEFER, statement=ASTNode(kind=NodeKind.RETURN)),
        ASTNode(kind=NodeKind.BLOCK, statements=[ASTNode(kind=NodeKind.BREAK)]),
    ])
    root = ASTNode(kind=NodeKind.PROGRAM, declarations=[
        ASTNode(kind=NodeKind.FUNCTION, name="main", body=body),
    ])
    view, output = formatter()
    view._display_ast(root)
    # Captured from the formatter before this conversion at the same width.
    assert output.getvalue() == (
        "\nPARSING RESULTS\nSuccessfully parsed into AST\n"
        "AST Root: PROGRAM with 1 top-level declarations\nProgram\n"
        "└── FUNCTION main () → void\n"
        "    ├── DEFER → RETURN (void)\n"
        "    └── BLOCK (1 stmts)\n"
        "        └── BREAK\n\n"
        "Stopping before semantic analysis and code generation\n"
    )


def test_nested_type_order_and_missing_children():
    leaf = ASTNode(kind=NodeKind.TYPE_PRIMITIVE, type_name="i32")
    pair = ASTNode(kind=NodeKind.TYPE_GENERIC, name="Pair", type_args=[
        ASTNode(kind=NodeKind.TYPE_SLICE, element_type=leaf),
        ASTNode(kind=NodeKind.TYPE_ARRAY,
                size=ASTNode(kind=NodeKind.LITERAL, literal_value=3),
                element_type=ASTNode(kind=NodeKind.TYPE_POINTER, target_type=leaf)),
    ])
    function = ASTNode(kind=NodeKind.TYPE_FUNCTION, parameter_types=[pair, leaf],
                       return_type=ASTNode(kind=NodeKind.TYPE_GENERIC, name="Result", type_args=[leaf]))
    view, _ = formatter()
    assert view.format_type(function) == "fn(Pair([]i32, [3]ref i32), i32) Result(i32)"
    assert view.format_type(ASTNode(kind=NodeKind.TYPE_POINTER)) == "ref ?"
    assert view.format_type(ASTNode(kind=NodeKind.TYPE_FUNCTION)) == "fn()"


def test_deep_types_defer_labels_and_tree_render_at_low_recursion_limit():
    depth = 400
    type_node = ASTNode(kind=NodeKind.TYPE_PRIMITIVE, type_name="i32")
    statement = ASTNode(kind=NodeKind.RETURN)
    block = ASTNode(kind=NodeKind.BREAK)
    for _ in range(depth):
        type_node = ASTNode(kind=NodeKind.TYPE_GENERIC, name="Box", type_args=[
            ASTNode(kind=NodeKind.TYPE_FUNCTION, parameter_types=[type_node]),
        ])
        statement = ASTNode(kind=NodeKind.DEFER, statement=statement)
        block = ASTNode(kind=NodeKind.BLOCK, statements=[block])
    view, output = formatter()
    previous = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(100)
        assert view.format_type(type_node) == "Box(fn(" * depth + "i32" + "))" * depth
        label = view.format_statement_label(statement)
        assert label == "[blue]DEFER[/blue] → " * depth + "[blue]RETURN[/blue] [dim](void)[/dim]"
        tree = Tree("Program")
        view._add_statements_to_tree(tree, [block, statement])
        branch = tree.children[0]
        for _ in range(depth):
            assert branch.label == "[blue]BLOCK[/blue] [dim](1 stmts)[/dim]"
            assert len(branch.children) == 1
            branch = branch.children[0]
        assert branch.label == "[blue]BREAK[/blue]"
        view.console.print(tree)
    finally:
        sys.setrecursionlimit(previous)
    text = output.getvalue()
    # Rich clips labels once indentation consumes the terminal width.
    assert 0 < text.count("BLOCK") < depth
    assert text.count("DEFER") == depth
    assert "RETURN" in text
    assert all(len(line) <= 80 for line in text.splitlines())


def test_source_markup_is_literal_and_detail_remains_bounded():
    view, output = formatter()
    view._display_source_panel('main :: fn() {}', '[/oops].a7')
    view._display_tokens([Token(TokenType.STRING, '[/oops]', 1, 1)])
    detail = view.format_expression_detail(ASTNode(
        kind=NodeKind.LITERAL, literal_kind=LiteralKind.STRING,
        literal_value='[/oops]' + 'x' * 30,
    ))
    view.console.print(detail)
    text = output.getvalue()
    assert 'Parsing: [/oops].a7' in text
    assert "'[/oops]'" in text
    assert '[/oops]' + 'x' * 13 + '...' in text
    assert 'x' * 14 not in text
