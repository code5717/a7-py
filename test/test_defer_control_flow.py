"""`defer` control flow (audit P2-61).

A deferred statement runs at scope exit, so `ret`, `break`, `continue` and
`fall` cannot leave it. The validator rejects them at exit 6; before, the
direct forms failed in codegen (exit 7) and the block forms reached Zig.
"""

import pytest

from conftest import expect_exit, run_both_profiles


LEAVES = "Control flow cannot leave a deferred block"

REJECTED = {
    "defer_ret": ("""
io :: import "std/io"
f :: fn() i32 {
    defer ret 1
    ret 2
}
main :: fn() { io.println("{}", f()) }
""", "'ret' inside defer"),
    "defer_break": ("""
io :: import "std/io"
main :: fn() {
    i := 0
    while i < 3 {
        defer break
        i += 1
    }
    io.println("{}", i)
}
""", "'break' inside defer"),
    "defer_continue": ("""
io :: import "std/io"
main :: fn() {
    i := 0
    while i < 3 {
        i += 1
        defer continue
    }
    io.println("{}", i)
}
""", "'continue' inside defer"),
    "defer_fall": ("""
io :: import "std/io"
main :: fn() {
    x := 1
    match x {
        case 1: {
            defer fall
        }
        else: { io.println("other") }
    }
}
""", "'fall' inside defer"),
    "ret_in_block": ("""
io :: import "std/io"
f :: fn(x: i32) i32 {
    defer {
        if x > 0 { ret 1 }
    }
    ret 2
}
main :: fn() { io.println("{}", f(1)) }
""", "'ret' inside defer"),
    "break_in_block_targets_outer_loop": ("""
io :: import "std/io"
main :: fn() {
    i := 0
    while i < 3 {
        defer {
            if i > 1 { break }
        }
        i += 1
    }
    io.println("{}", i)
}
""", "'break' inside defer"),
    "continue_in_inner_loop_targets_outer_label": ("""
io :: import "std/io"
main :: fn() {
    @outer for i := 0; i < 3; i += 1 {
        defer {
            for j := 0; j < 2; j += 1 {
                continue outer
            }
        }
    }
    io.println("done")
}
""", "'continue' inside defer"),
}


@pytest.mark.parametrize("shape", sorted(REJECTED))
def test_control_flow_leaving_a_defer_is_rejected(tmp_path, shape):
    source, statement = REJECTED[shape]
    result = expect_exit(source, tmp_path, 6, LEAVES)
    assert statement in "\n".join(str(d.get("message", "")) for d in result.failure.details)


def test_loop_control_inside_a_deferred_loop_runs(tmp_path, zig):
    out = run_both_profiles("""
io :: import "std/io"
main :: fn() {
    defer {
        for i := 0; i < 5; i += 1 {
            if i == 1 { continue }
            if i == 3 { break }
            io.println("deferred {}", i)
        }
    }
    io.println("body")
}
""", tmp_path, zig)
    assert out == "body\ndeferred 0\ndeferred 2\n"
