"""`Name {` is a struct literal except at header depth of `if`/`while`/`for`/`match`.

In a header, up to the `{` that opens the body, `Name {` opens the body.
Inside parentheses, brackets or braces within the header, and everywhere
else, it is a struct literal.
"""

import pytest

from conftest import expect_exit, expect_ok

PARSE_EXIT = 5

PRELUDE = """
P :: struct {
    x: i32
}
take :: fn(p: P) i32 { ret p.x }
"""


def program(body: str) -> str:
    return PRELUDE + "main :: fn() {\n" + body + "\n}\n"


@pytest.mark.parametrize("body", [
    "    a := 1\n    b := 2\n    c := 3\n    d := 4\n    e := 5\n    f := 6\n    g := 21\n"
    "    if a + b + c + d + e + f == g {\n        a = 0\n    }",
    "    x := 1\n    y := 2\n    z := 3\n    w := true\n"
    "    if x == 1 and y == 2 and z == 3 and w {\n        x = 0\n    }",
    "    n := 0\n    limit := 3\n    while n + 1 + 1 + 1 + 1 + 1 + 1 < limit {\n        n += 1\n    }",
    "    step := 1\n    t := 0\n    for i := 0; i < 3; i = i + step {\n        t += i\n    }",
    "    key := 2\n    r := 0\n    match key {\n        case 2: r = 1\n        else: r = 2\n    }",
    "    items := [1, 2, 3]\n    t := 0\n    for v in items {\n        t += v\n    }",
], ids=["long-if-condition", "long-and-chain", "long-while-condition", "for-update-ends-in-name",
        "match-scrutinee-name", "for-in-iterable-name"])
def test_name_before_the_body_brace_is_not_a_struct_literal(tmp_path, body):
    expect_ok(program(body), tmp_path)


@pytest.mark.parametrize("body", [
    "    c := true\n    v := 0\n    if c { v = take(P{x: 1}) }",
    "    c := true\n    p := P{x: 0}\n    if c { p = P{x: 1} }",
    "    c := true\n    p := if c { P{x: 1} } else { P{x: 2} }",
    "    v := 0\n    if take(P{x: 1}) == 1 { v = 1 }",
    "    v := 0\n    while take(P{x: 1}) == 2 { v = 1 }",
    "    v := 0\n    if (P{x: 1}).x == 1 { v = 1 }",
    "    v := 0\n    if [P{x: 1}, P{x: 2}][0].x == 1 { v = 1 }",
    "    v := 0\n    match take(P{x: 1}) {\n        case 1: v = 1\n        else: v = 2\n    }",
], ids=["call-in-one-line-body", "assign-in-one-line-body", "if-expression-branches",
        "call-argument-in-if-header", "call-argument-in-while-header", "parenthesised-in-header",
        "array-literal-in-header", "call-argument-in-match-header"])
def test_struct_literal_inside_bodies_and_brackets_compiles(tmp_path, body):
    expect_ok(program(body), tmp_path)


def test_one_line_if_returning_a_struct_literal_compiles(tmp_path):
    expect_ok(PRELUDE + "make :: fn(c: bool) P {\n    if c { ret P{x: 1} }\n    ret P{x: 2}\n}\n"
              "main :: fn() { p := make(true) }\n", tmp_path)


def test_bare_struct_literal_at_header_depth_opens_the_body(tmp_path):
    """`if v == P{} {`: `P` ends the condition, `{}` is the body, the second `{` is left over."""
    result = expect_exit(program("    v := 1\n    if v == P{} {\n    }"), tmp_path, PARSE_EXIT,
                         "statement must end at a newline")
    assert "'{'" in result.failure.message
