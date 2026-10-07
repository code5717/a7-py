"""Forms the parser accepted and a later stage or Zig rejected; now exit 5."""

import pytest

from conftest import expect_exit, expect_ok

PARSE_EXIT = 5


def in_main(body: str) -> str:
    return "main :: fn() {\n" + body + "\n}\n"


@pytest.mark.parametrize("statement", ["1 = 2", "g() = 2", "x + 1 = 2", "arr[0..1] = 2", "-x = 2", "g() += 1"])
def test_assignment_target_must_be_an_lvalue(tmp_path, statement):
    source = "g :: fn() i32 { ret 1 }\n" + in_main("    x := 1\n    arr := [1, 2]\n    " + statement)
    expect_exit(source, tmp_path, PARSE_EXIT, "Invalid assignment target")


def test_variable_field_and_index_targets_compile(tmp_path):
    expect_ok("""
P :: struct {
    x: i32
    cells: [2]i32
}
main :: fn() {
    v := 1
    v = 2
    v += 3
    p := P{x: 1, cells: [1, 2]}
    p.x = 4
    p.cells[1] = 5
    arr := [1, 2, 3]
    arr[0] = 6
    (v) = 7
}
""", tmp_path)


def test_parameter_without_a_type_is_a_parse_error(tmp_path):
    expect_exit("f :: fn(a:, b: i32) {}\nmain :: fn() {}", tmp_path, PARSE_EXIT,
                "Expected a type after ':' for parameter 'a'")
    expect_exit("f :: fn(a: i32, b:) {}\nmain :: fn() {}", tmp_path, PARSE_EXIT,
                "Expected a type after ':' for parameter 'b'")


@pytest.mark.parametrize(("arms", "fragment"), [
    ("        else: v = 1\n        else: v = 2", "A match has one 'else:' arm"),
    ("        else: v = 1\n        case 1: v = 2", "A 'case' arm cannot follow 'else:'"),
    ("        case 1: v = 1\n        else: v = 2\n        case 2: v = 3", "A 'case' arm cannot follow 'else:'"),
], ids=["second-else", "else-first", "case-after-else"])
def test_match_statement_else_is_single_and_last(tmp_path, arms, fragment):
    source = in_main("    v := 0\n    k := 1\n    match k {\n" + arms + "\n    }")
    expect_exit(source, tmp_path, PARSE_EXIT, fragment)


@pytest.mark.parametrize(("arms", "fragment"), [
    ("        else: 1\n        else: 2", "A match has one 'else:' arm"),
    ("        else: 1\n        case 1: 2", "A 'case' arm cannot follow 'else:'"),
], ids=["second-else", "case-after-else"])
def test_match_expression_else_is_single_and_last(tmp_path, arms, fragment):
    source = in_main("    k := 1\n    v := match k {\n" + arms + "\n    }")
    expect_exit(source, tmp_path, PARSE_EXIT, fragment)


def test_match_with_else_last_compiles(tmp_path):
    expect_ok(in_main("    k := 1\n    v := 0\n    match k {\n        case 1: v = 1\n        case 2, 3: v = 2\n"
                      "        else: v = 3\n    }\n    w := match k {\n        case 1: 10\n        else: 20\n    }"),
              tmp_path)


@pytest.mark.parametrize(("body", "fragment"), [
    ("    c := true\n    if c ret", "Expected '{' to open a block after the if condition, found 'ret'"),
    ("    c := true\n    v := 0\n    while c v += 1", "Expected '{' to open a block after the while condition, found 'v'"),
    ("    c := true\n    v := 0\n    if c { v = 1 } else v = 2", "Expected '{' to open a block after 'else', found 'v'"),
], ids=["if", "while", "else"])
def test_if_while_and_else_need_a_block(tmp_path, body, fragment):
    expect_exit(in_main(body), tmp_path, PARSE_EXIT, fragment)


def test_else_if_chain_compiles(tmp_path):
    expect_ok(in_main("    k := 2\n    v := 0\n    if k == 1 {\n        v = 1\n    } else if k == 2 {\n        v = 2\n"
                      "    } else {\n        v = 3\n    }\n    while v > 0 {\n        v -= 1\n    }"), tmp_path)


def test_if_expression_without_else_is_a_parse_error(tmp_path):
    expect_exit(in_main("    c := true\n    x := if c { 1 }"), tmp_path, PARSE_EXIT,
                "An if expression needs an 'else' branch")


def test_if_expression_with_else_compiles(tmp_path):
    expect_ok(in_main("    k := 2\n    x := if k == 1 { 10 } else if k == 2 { 20 } else { 30 }"), tmp_path)


def test_function_brace_on_the_next_line_compiles(tmp_path):
    expect_ok("one :: fn()\n{\n}\ntwo :: fn() i32\n{\n    ret 2\n}\nthree :: fn(a: i32) i32\n{\n    ret a\n}\n"
              "main :: fn()\n{\n    one()\n    x := two() + three(1)\n}\n", tmp_path)


def test_function_type_without_return_type_compiles(tmp_path):
    """`fn()` ends at `}`, `,`, `)`, a newline or end of file."""
    expect_ok("""
S :: struct { cb: fn() }
T :: struct { a: fn(), b: fn(i32) }
noop :: fn() {}
run :: fn(cb: fn()) { cb() }
main :: fn() {
    s := S{cb: noop}
    run(s.cb)
}
Cb :: fn()""", tmp_path)


def test_pub_import_is_a_parse_error(tmp_path):
    """SPEC 10.4 and 13.1 list no `pub` on the `import "path"` form."""
    expect_exit('pub import "std/io"\nmain :: fn() {}', tmp_path, PARSE_EXIT, "'pub' cannot be applied to an import")


def test_using_import_parses_and_records_the_flag():
    """SPEC 2.4/10.2/13.1: `using import "p"` is parsed and recorded as `is_using`."""
    from a7.ast_nodes import NodeKind
    from a7.parser import parse_a7

    program = parse_a7('using import "vector"\nimport "other"\n')
    first, second = program.declarations
    assert first.kind == NodeKind.IMPORT and first.module_path == "vector" and first.is_using is True
    assert second.kind == NodeKind.IMPORT and second.is_using is False


def test_using_stays_an_ordinary_identifier(tmp_path):
    expect_ok(in_main("    using := 1\n    x := using + 1"), tmp_path)
