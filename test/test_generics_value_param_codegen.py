"""`$N` value parameters reach Zig as comptime values of their declared type.

The checker pins are in test_generics_value_params.py; these programs are
built and run.
"""

from __future__ import annotations

from pathlib import Path

from conftest import expect_ok, run_both_profiles

IO_IMPORT = 'io :: import "std/io"\n'

VALUE_PARAMS = IO_IMPORT + """
SIZE :: 4
SUM :: 1 + 1
YES :: true
Buf($N: usize) :: struct {
    data: [$N]u8,
}
Flag($B: bool) :: struct {
    x: i32,
}
Slot($N: u8) :: union(tag) {
    full: [$N]i32,
    empty: bool,
}
scale($N: usize) :: fn(x: i32) i32 {
    ret x
}
second :: fn(b: ref Buf(SIZE)) u8 {
    ret b.data[1]
}
main :: fn() {
    LOCAL :: 3
    b := Buf(SIZE){data: [1, 2, 3, 4]}
    c: Buf(SIZE) = Buf(SIZE){data: [5, 6, 7, 8]}
    d := Buf(LOCAL){data: [9, 9, 6]}
    f := Flag(YES){x: 7}
    s := Slot(SUM){full: [9, 8]}
    io.println("{} {} {} {} {}", b.data[3], c.data[0], d.data[2], f.x, second(b))
    match s {
        case .full(a): { io.println("{}", a[1]) }
        case .empty(e): { io.println("empty {}", e) }
    }
}
"""


def test_value_parameters_build_and_run(tmp_path, zig):
    """A struct and a union sized by `$N`, a `bool` parameter, a generic
    function declaring `$N`, and value arguments given as a top-level
    constant, a folded constant and a function-local constant, in a struct
    literal, a variable annotation and a `ref` parameter type."""
    result = expect_ok(VALUE_PARAMS, tmp_path)
    emitted = Path(result.output_path).read_text()
    assert "fn Buf(comptime N: usize) type" in emitted
    assert "fn Slot(comptime N: u8) type" in emitted
    # `$B` and the function's `$N` are never read; Zig rejects an unused name.
    assert "fn Flag(comptime _: bool) type" in emitted
    assert "fn scale(comptime _: usize, x: i32) i32" in emitted
    assert run_both_profiles(VALUE_PARAMS, tmp_path, zig) == "4 5 6 7 2\n8\n"
