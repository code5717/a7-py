"""A type name is not a value and a value is not a type name (P2-36).

Each of these passed the checker and failed in the backend or in Zig.
"""

from __future__ import annotations

import pytest

from conftest import expect_exit

DECLARATIONS = """\
io :: import "std/io"
Scale :: enum { Small, Large }
P :: struct { x: i32 }
"""


@pytest.mark.parametrize(
    ("body", "fragment"),
    [
        pytest.param(
            "s := Scale.Large\n    t := s.Small",
            "a value of enum 'Scale' has no fields; name a variant as 'Scale.Small'",
            id="variant-through-enum-value",
        ),
        pytest.param("y := P.x", "'P' is a struct type; '.x' needs a value of type 'P'", id="field-through-struct-name"),
        pytest.param("s := Scale{a: 1}", "'Scale' is an enum; name a variant as 'Scale.Variant'", id="struct-literal-of-enum"),
        pytest.param("p: Nope(i32)", "Undefined type (Type 'Nope')", id="undefined-generic-base"),
        pytest.param("d := io", "'io' is a module alias", id="module-alias-as-value"),
        pytest.param("x := P", "'P' is a type", id="struct-name-as-value"),
        pytest.param("q := Missing{x: 1}", "Undefined type (Type 'Missing')", id="struct-literal-of-undefined-type"),
    ],
)
def test_type_and_value_mixups_are_rejected(tmp_path, body, fragment):
    source = f"{DECLARATIONS}\nmain :: fn() {{\n    {body}\n}}\n"
    result = expect_exit(source, tmp_path, 6, fragment)
    assert len(result.failure.details) == 1, result.failure.details


@pytest.mark.parametrize(
    ("variants", "fragment"),
    [
        pytest.param("A = 1, B = 1", "'B' and 'A' of enum 'E' both have the value 1", id="two-explicit"),
        pytest.param("A, B = 0", "'B' and 'A' of enum 'E' both have the value 0", id="explicit-meets-implicit"),
        pytest.param("A = 2, B, C = 3", "'C' and 'B' of enum 'E' both have the value 3", id="implicit-after-explicit"),
    ],
)
def test_two_enum_variants_with_one_value_are_rejected(tmp_path, variants, fragment):
    source = f"E :: enum {{ {variants} }}\n\nmain :: fn() {{\n}}\n"
    expect_exit(source, tmp_path, 6, fragment)
