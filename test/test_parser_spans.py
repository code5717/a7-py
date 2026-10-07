"""Expression nodes span their first through their last token (columns are 1-based, end exclusive)."""

import pytest

from a7.ast_nodes import NodeKind
from a7.parser import parse_a7


def first_statement(line: str):
    program = parse_a7("main :: fn() {\n" + line + "\n}\n")
    return program.declarations[0].body.statements[0]


def columns(node):
    span = node.span
    return (span.start_line, span.start_column, span.end_line, span.end_column)


@pytest.mark.parametrize(("line", "kind", "text"), [
    ("x := add(1, 2)", NodeKind.CALL, "add(1, 2)"),
    ("x := items[i + 1]", NodeKind.INDEX, "items[i + 1]"),
    ("x := items[1..n]", NodeKind.SLICE, "items[1..n]"),
    ("x := point.inner.value", NodeKind.FIELD_ACCESS, "point.inner.value"),
    ("x := -value", NodeKind.UNARY, "-value"),
    ("x := not ready(1)", NodeKind.UNARY, "not ready(1)"),
    ("x := (a + b)", NodeKind.BINARY, "(a + b)"),
    ("x := cast(i64, value)", NodeKind.CAST, "cast(i64, value)"),
    ("x := grid.rows[2].cells(0)", NodeKind.CALL, "grid.rows[2].cells(0)"),
])
def test_expression_span_covers_first_through_last_token(line, kind, text):
    node = first_statement(line).value
    assert node.kind == kind
    start = line.index(text) + 1
    assert columns(node) == (2, start, 2, start + len(text))


def test_assignment_span_covers_target_through_value():
    line = "point.x += f(1)"
    node = first_statement(line)
    assert node.kind == NodeKind.ASSIGNMENT
    assert columns(node) == (2, 1, 2, len(line) + 1)


def test_binary_span_includes_parenthesised_operands():
    line = "x := (a + b) * (c - d)"
    node = first_statement(line).value
    assert node.kind == NodeKind.BINARY
    start = line.index("(") + 1
    assert columns(node) == (2, start, 2, len(line) + 1)


def test_call_spanning_lines_ends_at_its_closing_parenthesis():
    program = parse_a7("main :: fn() {\n    x := add(\n        1,\n        2,\n    )\n}\n")
    node = program.declarations[0].body.statements[0].value
    assert columns(node) == (2, 10, 5, 6)
