"""List items need a `,`; fields and variants may also use a newline (ledger L62)."""

import pytest

from conftest import expect_exit, expect_ok

PARSE_EXIT = 5

PAIR = "Pair($A, $B) :: struct {\n    first: $A\n    second: $B\n}\n"
POINT = "Point :: struct {\n    x: i32\n    y: i32\n}\n"


@pytest.mark.parametrize(("source", "fragment"), [
    (PAIR + "main :: fn() { p: Pair(i32 i64) }", "Expected ',' between items in type argument list, found 'i64'"),
    ("Box($T $U) :: struct { a: $T, b: $U }", "Expected ',' between items in generic parameter list, found '$U'"),
    ('import "v" { A B }', "Expected ',' between items in import list, found 'B'"),
    ("add :: fn(a: i32, b: i32) i32 { ret a + b }\nmain :: fn() { x := add(1 2) }",
     "Expected ',' between items in call arguments, found '2'"),
    ("main :: fn() { a := [1 2 3] }", "Expected ',' between items in array literal, found '2'"),
    ("add :: fn(a: i32 b: i32) i32 { ret a + b }", "Expected ',' between items in parameter list, found 'b'"),
    ("Cb :: fn(i32 i32) i32", "Expected ',' between items in function type parameter list, found 'i32'"),
    (POINT + "main :: fn() { p := Point{x: 1 y: 2} }", "Expected ',' between items in struct literal, found 'y'"),
    (POINT + "main :: fn() { p := Point{1 2} }", "Expected ',' between items in struct literal, found '2'"),
    ("Color :: enum { A B C }", "Expected ',' or a newline between items in enum variants, found 'B'"),
    ("S :: struct { a: i32 b: i32 }", "Expected ',' or a newline between items in struct fields, found 'b'"),
    ("U :: union { a: i32 b: f32 }", "Expected ',' or a newline between items in union fields, found 'b'"),
    ("N :: @type_set(i32 i64)", "Expected ',' between items in @type_set, found 'i64'"),
], ids=["type-arguments", "generic-parameters", "selected-imports", "call-arguments",
        "array-literal", "parameters", "function-type-parameters", "named-struct-literal",
        "positional-struct-literal", "enum-variants", "struct-fields", "union-fields", "type-set"])
def test_missing_comma_is_a_parse_error(tmp_path, source, fragment):
    expect_exit(source, tmp_path, PARSE_EXIT, fragment, is_library=True)


@pytest.mark.parametrize(("source", "fragment"), [
    ("Box(,,) :: struct { a: i32 }", "Expected a generic parameter such as $T, found ','"),
    ('import "v" {,,}', "Expected an imported name in import list, found ','"),
    ("main :: fn() { a := [1,,2] }", "Expected expression"),
    ("add :: fn(a: i32, b: i32) i32 { ret a + b }\nmain :: fn() { x := add(,1) }", "Expected expression"),
], ids=["generic-parameters", "selected-imports", "array-literal", "call-arguments"])
def test_comma_without_an_item_is_a_parse_error(tmp_path, source, fragment):
    expect_exit(source, tmp_path, PARSE_EXIT, fragment, is_library=True)


def test_newline_does_not_separate_call_arguments(tmp_path):
    source = "add :: fn(a: i32, b: i32) i32 { ret a + b }\nmain :: fn() {\n    x := add(1\n        2)\n}\n"
    expect_exit(source, tmp_path, PARSE_EXIT, "Expected ',' between items in call arguments, found '2'")


def test_newline_separated_fields_and_variants_compile(tmp_path):
    expect_ok("""
Color :: enum {
    Red
    Green = 5,
    Blue
}
Point :: struct {
    x: i32
    y: i32,
    z: i32
}
Shape :: union(tag) {
    side: i32
    radius: f64
}
main :: fn() {
    c := Color.Blue
    p := Point{x: 1, y: 2, z: 3}
    s := Shape{side: 2}
}
""", tmp_path)


def test_comma_separated_lists_with_trailing_commas_compile(tmp_path):
    expect_ok(PAIR + POINT + """
Color :: enum { Red, Green, Blue, }
Flat :: struct { a: i32, b: i32, }
add :: fn(
    a: i32,
    b: i32,
) i32 {
    ret a + b
}
main :: fn() {
    pair: Pair(i32, i64,) = Pair(i32, i64){first: 1, second: 2,}
    total := add(
        1,
        2,
    )
    values := [
        1,
        2,
        3,
    ]
    named := Point{
        x: 1,
        y: 2,
    }
    flat := Flat{a: 1, b: 2}
    c := Color.Green
}
""", tmp_path)


def test_positional_struct_literal_may_span_lines(tmp_path):
    expect_ok(POINT + "main :: fn() {\n    p := Point{\n        1,\n        2\n    }\n    q := Point{3, 4}\n}\n", tmp_path)
