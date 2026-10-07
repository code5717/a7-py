"""An enum's Zig tag type holds its explicit values (audit P2-47).

The backend wrote `enum(i32)` for every enum with an explicit value, so
`A = 3000000000` failed the Zig build. The tag is `i32` when every value
fits, else the first of `u32`, `i64`, `u64` that holds them all.
"""

import pytest

from a7.ast_nodes import ASTNode, LiteralKind, NodeKind
from a7.backends.zig import ZigCodeGenerator
from a7.errors import CodegenError
from conftest import expect_exit, run_both_profiles


def emitted_enum(values):
    """Emit one enum from a hand-built AST.

    The checker is not run and Zig does not build the output: this shows the
    tag type the backend picks, nothing about what the checker accepts.
    """
    variants = [
        ASTNode(
            kind=NodeKind.ENUM_VARIANT, name=f"V{index}",
            value=None if value is None else ASTNode(
                kind=NodeKind.LITERAL, literal_kind=LiteralKind.INTEGER, literal_value=value),
        )
        for index, value in enumerate(values)
    ]
    program = ASTNode(kind=NodeKind.PROGRAM, declarations=[
        ASTNode(kind=NodeKind.ENUM, name="E", variants=variants),
    ])
    return ZigCodeGenerator().generate(program)


@pytest.mark.parametrize("values, header", [
    ([None, None], "const E = enum {"),
    ([1, 2], "const E = enum(i32) {"),
    ([-1, 2147483647], "const E = enum(i32) {"),
    ([3000000000, 1], "const E = enum(u32) {"),
    ([-1, 3000000000], "const E = enum(i64) {"),
    ([4294967295, None], "const E = enum(i64) {"),
    ([18446744073709551615, 0], "const E = enum(u64) {"),
])
def test_tag_type_is_the_first_that_holds_every_value(values, header):
    assert header in emitted_enum(values)


def test_values_no_64_bit_tag_holds_are_rejected():
    with pytest.raises(CodegenError, match="do not fit one 64-bit tag type"):
        emitted_enum([-1, 18446744073709551615])


@pytest.mark.parametrize("variants, code, message", [
    ("A = 18446744073709551616", 6, "out of range for u64"),
    ("A = -1, B = 18446744073709551615", 7,
     "do not fit one 64-bit tag type"),
])
def test_unrepresentable_enum_values_fail_in_the_pipeline(tmp_path, variants, code, message):
    expect_exit(f"E :: enum {{ {variants} }}\nmain :: fn() {{}}\n",
                tmp_path, code, message)


def test_explicit_values_within_i32_build_and_compare(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
Level :: enum { Low = 5, Mid, High = -3 }
main :: fn() {
    e := Level.Mid
    if e == Level.Mid { io.println("mid") }
    if e != Level.High { io.println("not high") }
}
""", tmp_path, zig) == "mid\nnot high\n"


@pytest.mark.parametrize("variants, chosen", [
    ("A = 3000000000, B = 1", "A"),
    ("A = -1, B = 3000000000", "B"),
    ("A = 4294967295, B", "B"),
    ("A = 18446744073709551615, B = 0", "A"),
])
def test_wide_values_build_and_compare(tmp_path, zig, variants, chosen):
    source = """
io :: import "std/io"
Big :: enum { VARIANTS }
main :: fn() {
    e := Big.CHOSEN
    if e == Big.CHOSEN { io.println("A") }
}
""".replace("VARIANTS", variants).replace("CHOSEN", chosen)
    assert run_both_profiles(source, tmp_path, zig) == "A\n"
