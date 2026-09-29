"""Native regressions for the language audit, in both supported build profiles."""
import pytest
from test_zig_backend_runtime import zig, zig_cache, compile_with_cli, build, run_piped

CASES = {
    'match-without-else': ('''io :: import "std/io"
show :: fn(x: i32) { match x { case 1: io.println("one") } }
main :: fn() { show(7); show(1); io.println("done") }
''', 'one\ndone\n'),
    'compound': ('''io :: import "std/io"
main :: fn() {
    x: i32 = -7
    y: i32 = 2
    x /= y
    z: f64 = -7.5
    z %= 2.0
    a: [1]i32 = [9]
    a[0] /= 2
    io.println("{} {} {}", x, z, a[0])
}
''', '-3 -1.5 4\n'),
    'braces': ('''io :: import "std/io"
main :: fn() { io.println("{{}} {{{}}} {{left}} }}", 7) }
''', '{} {7} {left} }\n'),
    'abs': ('''io :: import "std/io"
math :: import "std/math"
main :: fn() { x: i32 = -5; y := math.abs(x) - 10; io.println("{}", y) }
''', '-5\n'),
    'keyword-and-shadow': ('''io :: import "std/io"
test :: fn(x: i32) { io.println("{}", x) }
caller :: fn(test: fn(i32)) { h := test; h(5) }
main :: fn() { caller(test) }
''', '5\n'),
    'strings': ('''io :: import "std/io"
main :: fn() { a: [2]string; io.println("[{}][{}]", a[0], a[1]) }
''', '[][]\n'),
    'generic-fields': ('''io :: import "std/io"
Box($T) :: struct { items: []$T; slots: [2]$T }
main :: fn() { b: Box(i32); io.println("ok") }
''', 'ok\n'),
    'for-shadow': ('''io :: import "std/io"
main :: fn() {
    i: usize = 255
    for i := cast(u8, 0); i < 1; i += 1 { }
    a: [256]i32
    io.println("{} {}", i, a[i])
}
''', '255 0\n'),
    'wrap': ('''io :: import "std/io"
main :: fn() {
    x: u8 = 255
    x += 1
    y: i8 = -128
    y -= 1
    z: u8 = 128
    z *= 2
    a: u8 = 255
    b: u8 = 1
    io.println("{} {} {} {} {}", x, y, z, a + b, 2147483647 + 1)
}
''', '0 127 0 0 -2147483648\n'),
}

@pytest.mark.parametrize('profile', ['Debug', 'ReleaseFast'])
@pytest.mark.parametrize('source,expected', CASES.values(), ids=CASES.keys())
def test_audit_native_repairs(zig, zig_cache, tmp_path, profile, source, expected):
    output = compile_with_cli(tmp_path, source)
    executable = build(zig, zig_cache, tmp_path, output, profile)
    assert run_piped(executable) == (expected, '')


def test_for_shadow_does_not_narrow_outer_index(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    src, out = tmp_path / "unsafe.a7", tmp_path / "unsafe.zig"
    src.write_text(CASES["for-shadow"][0].replace("= 255", "= 300"))
    result = subprocess.run([sys.executable, str(root / "main.py"), str(src), "--format", "json", "-o", str(out)], cwd=root, capture_output=True, text=True)
    assert result.returncode == 6, result.stdout + result.stderr
    assert "Index not proven in bounds" in str(json.loads(result.stdout)["error"])
    assert not out.exists()
