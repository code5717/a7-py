"""Value-producing matches must cover every input before Zig lowering."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def compile_source(tmp_path, source):
    source_path = tmp_path / "match.a7"
    source_path.write_text(source)
    output = tmp_path / "match.zig"
    result = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(source_path), "--format", "json", "-o", str(output)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert "Traceback" not in result.stderr, result.stderr
    return result.returncode, json.loads(result.stdout), output


@pytest.mark.parametrize("type_name, pattern", [("i32", "1"), ("string", '"a"'), ("bool", "true")])
def test_incomplete_match_expression_is_a_semantic_error(tmp_path, type_name, pattern):
    code, payload, output = compile_source(tmp_path, f"pick :: fn(x: {type_name}) i32 {{\n    ret match x {{ case {pattern}: 10 }}\n}}\nmain :: fn() {{}}\n")
    assert code == 6, payload
    errors = payload["error"]["details"]
    coverage = next(error for error in errors if "Non-exhaustive match" in error["message"])
    assert coverage["span"]["start_line"] == 2
    if type_name == "bool":
        assert "Missing bool case(s): false" in coverage["message"]
    else:
        assert "match expression must cover every value" in coverage["message"]
    assert not output.exists()


def test_native_complete_matches_and_partial_statement_match(tmp_path):
    code, payload, output = compile_source(tmp_path, '''io :: import "std/io"
Color :: enum { Red, Blue }
by_else :: fn(x: i32) i32 { ret match x { case 1: 10; else: 20 } }
by_wildcard :: fn(x: i32) i32 { ret match x { case 1: 10; case _: 30 } }
by_bool :: fn(x: bool) i32 { ret match x { case true: 40; case false: 50 } }
by_enum :: fn(x: Color) i32 { ret match x { case Color.Red: 60; case Color.Blue: 70 } }
by_capture :: fn(x: i32) i32 { ret match x { case 1: 10; case value: value } }
main :: fn() {
    io.println("{} {} {} {} {}", by_else(2), by_wildcard(2), by_bool(false), by_enum(Color.Blue), by_capture(80))
    x := 9
    match x { case 1: { io.println("unmatched") } }
    io.println("done")
}
''')
    assert code == 0, payload.get("error")
    binary = tmp_path / "match"
    build = subprocess.run(["zig", "build-exe", str(output), f"-femit-bin={binary}"], capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(binary)], capture_output=True, text=True)
    assert (run.returncode, run.stdout, run.stderr) == (0, "20 30 50 70 80\ndone\n", "")
