"""SAF-4 must retain facts after executing the continuing branch."""
import json
from pathlib import Path
import subprocess
import sys

import pytest
from test_zig_backend_runtime import build, compile_with_cli, run_piped, zig, zig_cache

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = '// probe: compile-only\nio :: import "std/io"\n\nf :: fn(x: i32) i32 {\n    v := x\n    if v == 0 {\n        ret 0\n    } else {\n        v = 0\n    }\n    ret 10 / v\n}\n\nmain :: fn() {\n    io.println("{}", f(3))\n}\n'

@pytest.mark.parametrize("mutation", ["v = 0", "zero(v)", "defer { v = 0 }"])
def test_continuing_else_mutation_invalidates_guard(tmp_path, mutation):
    source = ORIGINAL.replace("        v = 0", "        " + mutation)
    if mutation == "zero(v)":
        source = "zero :: fn(value: ref i32) { value = 0 }\n" + source
    src, out = tmp_path / "unsafe.a7", tmp_path / "unsafe.zig"
    src.write_text(source)
    result = subprocess.run([sys.executable, str(ROOT / "main.py"), str(src),
                             "--format", "json", "-o", str(out)],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 6, result.stdout + result.stderr
    error = json.loads(result.stdout)["error"]
    assert error["category"] == "semantic"
    assert "Divisor not proven non-zero" in str(error["details"])
    assert not out.exists()

SAFE = '''io :: import "std/io"
plain :: fn(v: i32) i32 {
    if v == 0 { ret 0 }
    ret 10 / v
}
unchanged :: fn(v: i32) i32 {
    if v == 0 { ret 0 } else { io.print("") }
    ret 10 / v
}
assigned :: fn(x: i32) i32 {
    v := x
    if v == 0 { ret 0 } else { v = 2 }
    ret 10 / v
}
reguarded :: fn(x: i32) i32 {
    v := x
    if v == 0 { ret 0 } else { v = 0 }
    if v == 0 { ret 0 }
    ret 10 / v
}
main :: fn() {
    io.println("{} {} {} {} {}", plain(2), unchanged(2), assigned(3), reguarded(3), plain(0))
}
'''

@pytest.mark.parametrize("profile", ["Debug", "ReleaseFast"])
def test_guarded_continuations_keep_their_actual_facts(tmp_path, zig, zig_cache, profile):
    out = compile_with_cli(tmp_path, SAFE)
    binary = build(zig, zig_cache, tmp_path, out, profile)
    assert run_piped(binary) == ("5 5 5 0 0\n", "")
