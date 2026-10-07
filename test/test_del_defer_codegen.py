"""`del` and `defer` lowering, built and run.

`del` has one emitter, used for a plain `del` and for `defer del`. A deferred
statement goes through the same statement emitter as an undeferred one.
"""

from __future__ import annotations

import pytest

from conftest import expect_exit, run_both_profiles

IO_IMPORT = 'io :: import "std/io"\n'

DEL_LOCAL_NAMED_P = IO_IMPORT + """
Box :: struct { value: i32 }
main :: fn() {
    p := new Box
    if p == nil { ret }
    p.value = 3
    io.println("{}", p.value)
    del p
}
"""

DEFER_DEL_LOCAL_NAMED_P = IO_IMPORT + """
Node :: struct { value: i32, next: ref Node }
main :: fn() {
    p := new Node
    if p == nil { ret }
    p.value = 1
    defer del p
    n := p
    n.value = 2
    io.println("{}", p.value)
}
"""

TWO_DELS_IN_ONE_SCOPE = IO_IMPORT + """
Box :: struct { value: i32 }
main :: fn() {
    a := new Box
    b := new Box
    if a == nil { ret }
    if b == nil { ret }
    a.value = 1
    b.value = 2
    io.println("{}", a.value + b.value)
    defer del a
    del b
}
"""


@pytest.mark.parametrize("source, expected", [
    (DEL_LOCAL_NAMED_P, "3\n"),
    (DEFER_DEL_LOCAL_NAMED_P, "2\n"),
    (TWO_DELS_IN_ONE_SCOPE, "3\n"),
], ids=["del-p", "defer-del-p", "two-dels"])
def test_del_capture_does_not_collide_with_user_names(tmp_path, zig, source, expected):
    """The emitted `if (x) |capture|` once used the fixed name `p`, which Zig
    rejects beside a local named `p`."""
    assert run_both_profiles(source, tmp_path, zig) == expected


def test_deferred_statement_kinds_run_in_reverse_order(tmp_path, zig):
    """`defer if`, `defer while`, `defer for`, `defer match`, a deferred
    assignment, a deferred call and a deferred block. A deferred `if` once
    lowered to `defer void;`, which Zig rejects."""
    out = run_both_profiles(IO_IMPORT + """
    main :: fn() {
        x := 1
        defer if x == 3 { io.println("if {}", x) } else { io.println("else") }
        defer while x < 3 { x += 1 }
        defer for i := 0; i < 2; i += 1 { io.println("for {}", i) }
        defer match x {
            case 1: { io.println("one") }
            else: { io.println("other") }
        }
        defer x = 1
        defer io.println("call {}", x)
        defer { io.println("block {}", x) }
        x = 9
        io.println("body")
    }
    """, tmp_path, zig)
    assert out.splitlines() == ["body", "block 9", "call 9", "one", "for 0", "for 1", "if 3"]


@pytest.mark.parametrize("statement", ["ret", "break"])
def test_deferred_control_flow_is_rejected_before_codegen(tmp_path, statement):
    """Zig cannot leave a `defer`; the validator rejects it at exit 6."""
    expect_exit(IO_IMPORT + f"""
    main :: fn() {{
        for i := 0; i < 2; i += 1 {{
            defer {statement}
            io.println("body")
        }}
    }}
    """, tmp_path, 6, "Control flow cannot leave a deferred block")
