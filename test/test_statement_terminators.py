"""A statement or declaration ends at a newline, `;`, `}` or end of file (ledger L62)."""

import pytest

from conftest import expect_exit, expect_ok

TOKENIZE_EXIT = 4
PARSE_EXIT = 5
STATEMENT_END = "statement must end at a newline"


def in_main(body: str) -> str:
    return "main :: fn() {\n" + body + "\n}\n"


@pytest.mark.parametrize(("source", "unexpected"), [
    (in_main("    x := 1 2"), "'2'"),
    (in_main("    p := 1\n    q := p.5"), "'.5'"),
    (in_main("    a :: 1 b :: 2"), "'b'"),
    ("a :: 1 b :: 2\nmain :: fn() {}\n", "'b'"),
    (in_main("    x := 1\n    x = 2 x = 3"), "'x'"),
    ("f :: fn() {} main :: fn() {}\n", "'main'"),
    (in_main("    x := 1\n    if x == 1 { } x = 2"), "'x'"),
], ids=["literal-after-value", "dot-float-after-name", "two-constants-local",
        "two-constants-top-level", "two-assignments", "two-functions", "statement-after-block"])
def test_second_statement_on_a_line_is_a_parse_error(tmp_path, source, unexpected):
    result = expect_exit(source, tmp_path, PARSE_EXIT, STATEMENT_END)
    assert unexpected in result.failure.message


@pytest.mark.parametrize("source", [
    in_main("    x := 1; y := 2\n    x = y; y = x"),
    in_main("    x := 1\n    if x == 1 { x = 2 }"),
    in_main("    x := 1\n    if x == 1 { x = 2 } else { x = 3 }"),
    in_main("    t := 0\n    for i := 0; i < 3; i += 1 { t += i }"),
    in_main("    x := 1\n    match x { case 1: x = 2; else: x = 3 }"),
    in_main("    x := 1\n    match x { case 1: { x = 2 } case 2: { x = 3 } else: { } }"),
    "one :: fn() i32 { ret 1 }\nmain :: fn() { x := one() }",
], ids=["semicolons", "one-line-if", "one-line-if-else", "c-style-for-header",
        "one-line-match-semicolon", "one-line-match-arms", "end-of-file-after-brace"])
def test_statements_that_end_properly_still_compile(tmp_path, source):
    expect_ok(source, tmp_path)


@pytest.mark.parametrize(("literal", "fragment"), [
    ("123abc", "'a' cannot follow the number '123'"),
    ("5.foo", "'f' cannot follow the number '5.'"),
    ("1.5.3", "a second '.3' cannot follow the number '1.5'"),
    ("0x1.5", "a second '.5' cannot follow the number '0x1'"),
    ("0b102", "'2' cannot follow the number '0b10'"),
    ("0x1G", "'G' cannot follow the number '0x1'"),
])
def test_number_glued_to_more_text_is_a_tokenizer_error(tmp_path, literal, fragment):
    expect_exit(in_main(f"    x := {literal}"), tmp_path, TOKENIZE_EXIT, fragment)


def test_number_forms_from_spec_2_6_still_compile(tmp_path):
    """`1.`, `.5`, exponents, separators and a `1..5`-style range are SPEC 2.6 forms."""
    expect_ok(in_main(
        "    a := 1.\n    b := .5\n    c := 2.5e3\n    d := 1.e2\n    e := 1_000\n"
        "    arr := [10, 20, 30, 40]\n    s := arr[1..3]\n    f := 0x2A + 0o52 + 0b101010"
    ), tmp_path)


def test_uppercase_prefix_splits_as_spec_2_6_says_then_fails_the_statement_rule(tmp_path):
    """SPEC 2.6: `0X2A` lexes as `0` then `X2A`; the statement rule rejects the pair."""
    result = expect_exit(in_main("    x := 0X2A"), tmp_path, PARSE_EXIT, STATEMENT_END)
    assert "'X2A'" in result.failure.message
