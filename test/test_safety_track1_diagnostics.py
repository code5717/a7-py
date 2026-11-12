"""Track 1 release blockers: fn-ptr init, match capture, JSON spans, entry origin."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import expect_exit, expect_ok
from native_profiles import same_output_in_every_profile

ROOT = Path(__file__).resolve().parent.parent
IO = 'io :: import "std/io"\n'


def run_json(tmp_path: Path, source: str, *args: str):
    path = tmp_path / "main.a7"
    path.write_text(source, encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    result = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(path), "--format", "json", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)
    return result.returncode, payload


def test_uninitialized_function_pointer_call_exits_6(tmp_path):
    source = """
main :: fn() {
    f: fn(i32) i32
    x := f(3)
}
"""
    expect_exit(source, tmp_path, 6, "Function value")


def test_function_pointer_assigned_before_call_is_ok(tmp_path):
    source = IO + """
inc :: fn(x: i32) i32 { ret x + 1 }
main :: fn() {
    f: fn(i32) i32
    f = inc
    io.println("{}", f(3))
}
"""
    expect_ok(source, tmp_path)


def test_function_pointer_initialized_declaration_runs(tmp_path, zig):
    source = IO + """
inc :: fn(x: i32) i32 { ret x + 1 }
main :: fn() {
    f: fn(i32) i32 = inc
    io.println("{}", f(4))
}
"""
    assert same_output_in_every_profile(source, tmp_path, zig) == "5\n"


def test_function_pointer_both_branches_assign_before_call(tmp_path, zig):
    source = IO + """
inc :: fn(x: i32) i32 { ret x + 1 }
dec :: fn(x: i32) i32 { ret x - 1 }
run :: fn(flag: bool) {
    f: fn(i32) i32
    if flag { f = inc } else { f = dec }
    io.println("{}", f(3))
}
main :: fn() {
    run(true)
    run(false)
}
"""
    assert same_output_in_every_profile(source, tmp_path, zig) == "4\n2\n"


def test_for_in_over_function_array_keeps_initialized_binding(tmp_path):
    source = IO + """
inc :: fn(x: i32) i32 { ret x + 1 }
main :: fn() {
    fs: [1]fn(i32) i32 = [inc]
    for f in fs {
        io.println("{}", f(1))
    }
}
"""
    expect_ok(source, tmp_path)


def test_while_reassigned_function_local_stays_initialized(tmp_path):
    source = IO + """
inc :: fn(x: i32) i32 { ret x + 1 }
dec :: fn(x: i32) i32 { ret x - 1 }
main :: fn() {
    f: fn(i32) i32 = inc
    flag := false
    while flag {
        f = dec
    }
    io.println("{}", f(1))
}
"""
    expect_ok(source, tmp_path)


def test_bare_undefined_case_identifier_is_undefined_name(tmp_path):
    source = """
main :: fn() {
    x: i32 = 1
    match x {
        case Blu: {}
    }
}
"""
    expect_exit(source, tmp_path, 6, "Undefined identifier")


def test_bare_undefined_case_on_enum_is_undefined_name(tmp_path):
    source = """
Color :: enum { Red, Green }
main :: fn() {
    c := Color.Red
    match c {
        case Blu: {}
        case Color.Red: {}
        case Color.Green: {}
    }
}
"""
    expect_exit(source, tmp_path, 6, "Undefined identifier")


def test_wildcard_case_still_covers_remaining_values(tmp_path):
    source = """
main :: fn() {
    x: i32 = 1
    match x {
        case _: {}
    }
}
"""
    expect_ok(source, tmp_path)


def test_parse_stage_json_failure_has_message_and_span(tmp_path):
    code, payload = run_json(tmp_path, "main :: fn() {\n", "--mode", "pipeline")
    assert code == 5
    stage = payload["stages"]["parse"]
    assert stage["ok"] is False
    assert stage["message"]
    assert stage["span"]["start_line"] >= 1
    assert payload["error"]["span"] == stage["span"]
    assert stage["message"] in payload["error"]["message"] or payload["error"]["message"].endswith(
        stage["message"]
    )


def test_semantic_stage_json_failure_has_message_and_span(tmp_path):
    code, payload = run_json(
        tmp_path,
        "main :: fn() {\n    x := y\n}\n",
        "--mode",
        "pipeline",
    )
    assert code == 6
    stage = payload["stages"]["semantic"]
    assert stage["ok"] is False
    assert stage["errors"]
    detail = stage["errors"][0]
    assert detail["message"]
    assert detail["span"]["start_line"] == 2


def test_entry_callee_origin_includes_source_filename(tmp_path):
    header = """Box::struct{x:i32}
b::fn(n:bool,p:ref Box){v:=true;if n{v=false};if v{x:=p.x};if n{ret}}
f::fn(n:bool,p:ref Box){b(n,p)}
"""
    result = expect_exit(
        header + "main::fn(){flag:=false;f(flag,nil)}",
        tmp_path,
        6,
        "readonly executable entry field access",
    )
    message = result.failure.details[0]["message"]
    assert "callee use in main.a7 at line 2" in message
    assert "column 55" in message
