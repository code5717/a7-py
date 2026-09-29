"""Native results for bounded V1 backend repairs, through the complete CLI."""

import pytest

from test_zig_backend_runtime import build, compile_with_cli, run_piped, zig, zig_cache


CASES = {
    "array-snapshot-and-order": ('''io :: import "std/io"
mark :: fn(value: i32) i32 {
    io.println("read {}", value)
    ret value
}
main :: fn() {
    a: [2]i32 = [1, 2]
    a = [mark(a[1]), mark(a[0])]
    io.println("swap {} {}", a[0], a[1])
    a = [7, 8]
    io.println("plain {} {}", a[0], a[1])
    rows: [2][2]i32 = [[1, 2], [3, 4]]
    rows[0] = [rows[0][1], rows[0][0]]
    io.println("row {} {} {} {}", rows[0][0], rows[0][1], rows[1][0], rows[1][1])
}
''', 'read 2\nread 1\nswap 2 1\nplain 7 8\nrow 2 1 3 4\n'),
    "ascii-control-characters": (r'''io :: import "std/io"
main :: fn() {
    io.print("{}{}{}{}{}{}{}{}{}", '\x01', '\x08', '\x1f', '\x7f', '\0', '\t', '\n', '\\', 'A')
}
''', '\x01\x08\x1f\x7f\x00\t\n\\A'),
    "deferred-result-and-void": ('''io :: import "std/io"
value :: fn() i32 { io.println("value"); ret 7 }
empty :: fn() { io.println("void") }
early :: fn() {
    defer value()
    defer empty()
    io.println("body")
    ret
}
main :: fn() {
    early()
    io.println("after")
}
''', 'body\nvoid\nvalue\nafter\n'),
    "unused-constant-keeps-effects": ('''io :: import "std/io"
produce :: fn() i32 { io.println("evaluated"); ret 9 }
main :: fn() {
    unused :: 42
    result :: produce()
    used :: 5
    N :: 3
    Alias :: N
    buffer: [Alias]i32
    io.println("buffer {}", buffer[2])
    io.println("used {}", used)
}
''', 'evaluated\nbuffer 0\nused 5\n'),
}


@pytest.mark.parametrize("profile", ["Debug", "ReleaseFast"])
@pytest.mark.parametrize("source,expected", CASES.values(), ids=CASES.keys())
def test_native_backend_regressions(tmp_path, zig, zig_cache, profile, source, expected):
    output = compile_with_cli(tmp_path, source)
    binary = build(zig, zig_cache, tmp_path, output, profile)
    assert run_piped(binary) == (expected, "")
