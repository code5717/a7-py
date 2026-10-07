"""Assignment targets and `ref` arguments must be writable (P2-32, P2-33).

The mutability check used to look only at a bare identifier, so a field or
element of a constant or of a by-value parameter could be assigned, and Zig
rejected the generated code. The check now walks from the target to the
binding that stores it. A step through `ref` or a slice ends the walk.
"""

from __future__ import annotations

import pytest

from conftest import expect_exit, run_both_profiles

PRELUDE = """\
P :: struct { x: i32 }
bump :: fn(value: ref i32) { value += 1 }
grow :: fn(p: ref P) { p.x = p.x + 1 }
"""


@pytest.mark.parametrize(
    ("function", "fragment"),
    [
        pytest.param(
            "main :: fn() {\n    c :: P{x: 1}\n    c.x = 5\n}",
            "'c' is immutable: it is a constant",
            id="field-of-constant",
        ),
        pytest.param(
            "f :: fn(p: P) {\n    p.x = 5\n}\nmain :: fn() { }",
            "'p' is immutable: it is a parameter",
            id="field-of-value-parameter",
        ),
        pytest.param(
            "f :: fn(a: [2]i32) {\n    a[0] = 5\n}\nmain :: fn() { }",
            "'a' is immutable: it is a parameter",
            id="element-of-value-parameter",
        ),
        pytest.param(
            "f :: fn(a: [2]P) {\n    a[1].x = 5\n}\nmain :: fn() { }",
            "'a' is immutable: it is a parameter",
            id="field-of-element-of-value-parameter",
        ),
        pytest.param(
            'main :: fn() {\n    s: string = "abc"\n    s[0] = \'z\'\n}',
            "a string is immutable",
            id="string-character",
        ),
        pytest.param(
            "main :: fn() {\n    a: [3]i32 = [1, 2, 3]\n    s := a[0..2]\n    s.len = 1\n}",
            "'.len' of '[]i32' is read-only",
            id="slice-length",
        ),
        pytest.param(
            "f :: fn(v: i32) {\n    bump(v)\n}\nmain :: fn() { }",
            "'v' is immutable: it is a parameter",
            id="value-parameter-passed-by-ref",
        ),
        pytest.param(
            "f :: fn(p: P) {\n    grow(p)\n}\nmain :: fn() { }",
            "'p' is immutable: it is a parameter",
            id="struct-parameter-passed-by-ref",
        ),
        pytest.param(
            "main :: fn() {\n    c :: P{x: 1}\n    grow(c)\n}",
            "'c' is immutable: it is a constant",
            id="constant-passed-by-ref",
        ),
        pytest.param(
            "main :: fn() {\n    s: i8 = 4\n    bump(s)\n}",
            "a 'ref i32' parameter takes a variable of type 'i32'",
            id="narrower-variable-passed-by-ref",
        ),
    ],
)
def test_writing_to_immutable_storage_is_rejected(tmp_path, function, fragment):
    result = expect_exit(PRELUDE + function + "\n", tmp_path, 6, fragment)
    assert len(result.failure.details) == 1, result.failure.details


def test_writes_through_variables_references_and_slices_run(tmp_path, zig):
    source = """\
io :: import "std/io"

P :: struct { x: i32 }

bump :: fn(value: ref i32) { value += 1 }
grow :: fn(p: ref P) { p.x = p.x + 10 }
forward :: fn(p: ref P) { grow(p) }
fill :: fn(xs: []i32) {
    i: usize = 0
    if i < xs.len {
        xs[i] = 42
    }
}

main :: fn() {
    n: i32 = 1
    bump(n)
    p := P{x: 1}
    grow(p)
    forward(p)
    arr: [3]i32 = [1, 2, 3]
    bump(arr[1])
    fill(arr[0..2])
    io.println("{} {} {} {}", n, p.x, arr[0], arr[1])
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "2 21 42 3\n"
