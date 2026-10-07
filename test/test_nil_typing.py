"""`nil` has its own type: it fits `ref T` and nothing else (findings P2-31).

SPEC 2.6: nil is the null value of reference types. It used to carry the
checker's "unknown" type, which is assignable to everything, so `x == nil`
on an integer and `id(nil)` passed and `p = nil` on a reference failed.
"""

from __future__ import annotations

import pytest

from conftest import expect_exit, run_both_profiles


def test_nil_assigns_to_and_compares_with_references(tmp_path, zig):
    source = """\
io :: import "std/io"

Node :: struct { v: i32, next: ref Node }

main :: fn() {
    p: ref i32 = new i32
    if p == nil { ret }
    p = 7
    seen := 0
    if p != nil {
        seen = 1
    }
    del p
    p = nil
    if p == nil {
        seen += 10
    }
    pair: [2]ref Node = [nil, nil]
    if pair[0] == nil and pair[1] == nil {
        seen += 100
    }
    io.println("{}", seen)
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "111\n"


@pytest.mark.parametrize(
    ("body", "fragment"),
    [
        pytest.param(
            "x: i32 = 1\n    if x == nil { }",
            "only a 'ref' value can be nil, and 'i32' is not a reference",
            id="integer-compared-with-nil",
        ),
        pytest.param("a := id(nil)", "nil has no type to bind '$T'", id="nil-binds-no-generic"),
        pytest.param("a := [nil, nil]", "nil has no type of its own", id="array-of-nil"),
        pytest.param("x := []", "an empty array literal has no element type", id="empty-array"),
        pytest.param("x: i32 = nil", "Nil only allowed for reference types", id="nil-into-integer"),
        pytest.param("p := new i32\n    if p < nil { }", "nil has no order", id="nil-ordering"),
    ],
)
def test_nil_where_no_reference_type_is_known_is_rejected(tmp_path, body, fragment):
    source = f"id($T) :: fn(x: $T) $T {{ ret x }}\n\nmain :: fn() {{\n    {body}\n}}\n"
    result = expect_exit(source, tmp_path, 6, fragment)
    assert len(result.failure.details) == 1, result.failure.details
