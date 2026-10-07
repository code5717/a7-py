"""Name registration rules (P2-2, P2-5, P2-9).

A `case NAME:` pattern compares with the file-scope constant NAME wherever
that constant is declared. Before, a constant declared below the function
was unknown when the pattern was classified, so the pattern became a
capture and matched every value.
"""

from __future__ import annotations

import pytest

from conftest import expect_exit, run_both_profiles


def test_case_compares_with_a_constant_declared_below_the_function(tmp_path, zig):
    source = """\
io :: import "std/io"

classify :: fn(x: i32) i32 {
    match x {
        case LIMIT: { ret 1 }
        else: { ret 0 }
    }
}

LIMIT :: 5

main :: fn() {
    io.println("{} {}", classify(5), classify(7))
}
"""
    # A capture would match 7 as well and print "1 1".
    assert run_both_profiles(source, tmp_path, zig) == "1 0\n"


def test_a_nested_block_may_still_shadow_a_parameter(tmp_path, zig):
    source = """\
io :: import "std/io"

f :: fn(x: i32) i32 {
    if x > 0 {
        x := 2
        ret x
    }
    ret x
}

main :: fn() {
    io.println("{} {}", f(1), f(-1))
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "2 -1\n"


@pytest.mark.parametrize(
    ("source", "fragment"),
    [
        pytest.param(
            "Color :: enum { Red, Green, Red }\nmain :: fn() { }\n",
            "Duplicate enum variant: 'Red' in enum 'Color'",
            id="duplicate-variant",
        ),
        pytest.param(
            "f :: fn(x: i32) i32 {\n    x := 2\n    ret x\n}\nmain :: fn() { }\n",
            "Already defined: Variable 'x' (a parameter of 'f' has this name)",
            id="local-reuses-parameter-name",
        ),
        pytest.param(
            "f :: fn(x: i32) i32 {\n    x :: 2\n    ret x\n}\nmain :: fn() { }\n",
            "Already defined: Constant 'x' (a parameter of 'f' has this name)",
            id="local-constant-reuses-parameter-name",
        ),
        pytest.param(
            "main :: fn() {\n    L :: struct { v: i32 }\n    q := L{v: 3}\n}\n",
            "struct 'L' is declared inside a function; type declarations belong at file scope",
            id="struct-inside-function",
        ),
    ],
)
def test_name_registration_errors(tmp_path, source, fragment):
    result = expect_exit(source, tmp_path, 6, fragment)
    assert len(result.failure.details) == 1, result.failure.details
