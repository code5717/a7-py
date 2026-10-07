"""Binding and labeled transfer outcomes through A7 CLI and Zig 0.16.0."""

import pytest

from test_zig_backend_runtime import build, compile_with_cli, run_piped, zig, zig_cache


CASES = {
    "unused-labels": ('''
main :: fn() {
    @unused while false {}
    @unused for i := 0; i < 2; i += 1 { io.println("c {}", i) }
    values: [2]i32 = [4, 5]
    @unused for value in values { io.println("v {}", value) }
    @unused for index, value in values { io.println("i {} {}", index, value) }
    @unused for { break }
}
''', "c 0\nc 1\nv 4\nv 5\ni 0 4\ni 1 5\n"),
    "label-identities-and-outer-update": ('''
step :: fn() i32 { io.println("step"); ret 1 }
main :: fn() {
    @same for i := 0; i < 2; i += 1 {
        @same for { io.println("inner {}", i); break same }
    }
    @same for { break same }
    i: i32 = 0
    @outer for i = 0; i < 4; step() {
        i += 1
        @inner for {
            if i < 3 { continue outer }
            break outer
        }
    }
    io.println("done {}", i)
}
''', "inner 0\ninner 1\nstep\nstep\ndone 3\n"),
    "label-suffix-collision-and-indexed-transfer": ('''
main :: fn() {
    @x for { break x }
    @x_1 for {
        @x for { break x }
        break x_1
    }
    values: [2]i32 = [4, 5]
    @items for value in values {
        @indices for index, inner in values {
            io.println("{} {} {}", value, index, inner)
            continue items
        }
    }
    io.println("done")
}
''', "4 0 4\n5 0 4\ndone\n"),
    "shadowed-binding-and-pattern-binding": ('''
main :: fn() {
    value :: 3
    if true { unused :: 1 }
    if false { unused :: 2 } else if true { unused :: 3 } else { unused :: 4 }
    { value :: 5; match 5 { case value: io.println("match"); else: io.println("wrong") } }
    match 3 { case value: io.println("outer") }
    io.println("{}", value)
}
''', "match\nouter\n3\n"),
    "sibling-and-initializer-bindings": ('''
main :: fn() {
    if true { y :: 2 }
    if true { y :: 3; io.println("{}", y) }
    y :: 7
    { y :: y + 1; io.println("{}", y) }
    { y := y + 2; io.println("{}", y) }
    { y: i32 = 12; { y :: y + 1; io.println("{}", y) }; io.println("{}", y) }
    io.println("{}", y)
}
''', "3\n8\n9\n13\n12\n7\n"),
    "type-only-and-array-bound": ('''
main :: fn() {
    N :: 2
    T :: i32
    { N :: 3; T :: i64; buffer: [N]T; for item in buffer { io.println("inner") } }
    buffer: [N]T
    for item in buffer { io.println("outer") }
}
''', "inner\ninner\ninner\nouter\nouter\n"),
    "unused-repeated-effects-and-return": ('''
produce :: fn(value: i32) i32 { io.println("read {}", value); ret value }
run :: fn() {
    for i := 0; i < 3; i += 1 {
        result :: produce(i)
        { result :: produce(i + 10) }
    }
    result :: produce(99)
    ret
}
main :: fn() { run() }
''', "read 0\nread 10\nread 1\nread 11\nread 2\nread 12\nread 99\n"),
    "loop-and-match-scopes": ('''
main :: fn() {
    value :: 40
    values: [2]i32 = [2, 3]
    for value in values { { value :: value + 1; io.println("{}", value) } }
    match 5 { case captured: { value :: captured; io.println("{}", value) } }
    result := match 6 { case captured: captured + 1 }
    io.println("{} {}", result, value)
    match 1 { case 1: { value :: 9; io.println("{}", value) }; else: { value :: 8 } }
    io.println("{}", value)
}
''', "3\n4\n5\n7 40\n9\n40\n"),
}


@pytest.mark.parametrize("profile", ["Debug", "ReleaseFast"])
@pytest.mark.parametrize("source,expected", CASES.values(), ids=CASES.keys())
def test_backend_binding_outcomes(tmp_path, zig, zig_cache, profile, source, expected):
    output = compile_with_cli(tmp_path, 'io :: import "std/io"\n' + source)
    binary = build(zig, zig_cache, tmp_path, output, profile)
    assert run_piped(binary) == (expected, "")
