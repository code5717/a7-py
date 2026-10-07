"""Local function fields keep their bindings beside file-module calls.

Native controls use nonclashing local names under L28. Separate rejection
fixtures cover bindings that reuse their own file's import alias.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from a7.ast_nodes import NodeKind
from a7.compile import A7Compiler
from a7.parser import parse_a7
from conftest import shared_zig_cache


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = PROJECT_ROOT / "main.py"

MODULE_SOURCE = """pub work :: fn() i32 {
    ret 1
}
pub takes :: fn(a: i32) i32 {
    ret a + 1
}
"""

HEADER = """io :: import "std/io"
h :: import "flat"
two :: fn() i32 {
    ret 2
}
Ops :: struct {
    work: fn() i32
}
"""


@pytest.fixture(scope="module")
def zig():
    executable = os.environ.get("A7_TEST_ZIG") or shutil.which("zig")
    assert executable, "Zig 0.16.0 required: set A7_TEST_ZIG or PATH"
    version = subprocess.run([executable, "version"], capture_output=True, text=True)
    assert version.returncode == 0 and version.stdout.strip() == "0.16.0", version
    return executable


def run_cli(args):
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{PROJECT_ROOT}:{existing}" if existing else str(PROJECT_ROOT)
    return subprocess.run(
        [sys.executable, str(MAIN_PY), *args],
        cwd=PROJECT_ROOT, capture_output=True, text=True, env=env,
    )


def write_program(tmp_path, main_source):
    (tmp_path / "flat.a7").write_text(MODULE_SOURCE, encoding="utf-8")
    src = tmp_path / "main.a7"
    src.write_text(main_source, encoding="utf-8")
    return src


def compile_build_run(zig, tmp_path, main_source):
    """Return {profile: stdout} after A7 compile, Zig build and run."""
    src = write_program(tmp_path, main_source)
    out = tmp_path / "main.zig"
    compiled = run_cli([str(src), "--output", str(out)])
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    outputs = {}
    for profile in ("Debug", "ReleaseFast"):
        binary = tmp_path / ("program-" + profile)
        built = subprocess.run(
            [zig, "build-exe", str(out), "-O", profile,
             "--cache-dir", str(tmp_path / "cache"),
             "--global-cache-dir", str(shared_zig_cache() / "global"),
             "-femit-bin=" + str(binary)],
            capture_output=True, text=True,
        )
        assert built.returncode == 0, profile + ": " + built.stdout + built.stderr
        ran = subprocess.run([str(binary)], capture_output=True, text=True)
        assert ran.returncode == 0, ran.stderr
        assert ran.stderr == ""
        outputs[profile] = ran.stdout
    return outputs


def expect_both(outputs, expected):
    assert outputs == {"Debug": expected, "ReleaseFast": expected}


def test_local_function_field_and_alias_call_keep_their_bindings(tmp_path, zig):
    # Both direct and copied function values call the local field.
    source = HEADER + """main :: fn() {
    k := Ops{work: two}
    g := k.work
    io.println("{} {}", k.work(), g())
}
"""
    expect_both(compile_build_run(zig, tmp_path, source), "2 2\n")


def test_module_call_beside_differently_named_locals_calls_module(tmp_path, zig):
    source = HEADER + """main :: fn() {
    k := Ops{work: two}
    io.println("{} {} {}", h.work(), k.work(), h.takes(4))
}
"""
    expect_both(compile_build_run(zig, tmp_path, source), "1 2 5\n")


def test_local_in_one_block_does_not_hide_module_elsewhere(tmp_path, zig):
    source = HEADER + """main :: fn() {
    if true {
        k := Ops{work: two}
        io.println("{}", k.work())
    }
    if true {
        io.println("{}", h.work())
    }
    io.println("{}", h.work())
}
"""
    expect_both(compile_build_run(zig, tmp_path, source), "2\n1\n1\n")


def test_loop_variable_field_and_module_call_are_distinct(tmp_path, zig):
    source = HEADER + """main :: fn() {
    arr: [1]Ops = [Ops{work: two}]
    for k in arr {
        io.println("{}", k.work())
    }
    io.println("{}", h.work())
}
"""
    expect_both(compile_build_run(zig, tmp_path, source), "2\n1\n")


def test_parameter_field_and_module_call_are_distinct(tmp_path, zig):
    source = HEADER + """use_param :: fn(k: Ops) i32 {
    ret k.work()
}
use_module :: fn(k: Ops) i32 {
    ret h.work() + k.work()
}
main :: fn() {
    io.println("{} {} {}", use_param(Ops{work: two}), use_module(Ops{work: two}), h.work())
}
"""
    expect_both(compile_build_run(zig, tmp_path, source), "2 3 1\n")


def _alias_calls(ast):
    """Return module and local field CALL nodes in source order (by line)."""
    found = []
    stack = [ast]
    while stack:
        value = stack.pop()
        if isinstance(value, list):
            stack.extend(value)
            continue
        if not hasattr(value, "kind"):
            continue
        if (
            value.kind == NodeKind.CALL
            and value.function is not None
            and value.function.kind == NodeKind.FIELD_ACCESS
            and value.function.object is not None
            and value.function.object.kind == NodeKind.IDENTIFIER
            and value.function.object.name in {"h", "k"}
        ):
            found.append(value)
        stack.extend(v for v in value.__dict__.values() if isinstance(v, list) or hasattr(v, "kind"))
    return sorted(found, key=lambda call: call.span.start_line)


def test_local_declared_after_call_in_same_block_does_not_capture_the_call(tmp_path, zig):
    # Module and local field calls retain their distinct targets.
    source = HEADER + """main :: fn() {
    io.println("{}", h.work())
    k := Ops{work: two}
    io.println("{}", k.work())
}
"""
    expect_both(compile_build_run(zig, tmp_path, source), "1\n2\n")

    ast = parse_a7(source, str(write_program(tmp_path, source)))
    A7Compiler()._annotate_file_module_calls(ast, {"h": "flat"})
    first, second = _alias_calls(ast)
    assert getattr(first, "file_module_call", None) == ("module_flat__", "work")
    assert getattr(second, "file_module_call", None) is None


def test_scope_walk_handles_60_nested_blocks_at_recursion_limit_100():
    depth = 60
    lines = [HEADER, "main :: fn() {"]
    for level in range(1, depth + 1):
        indent = "    " * level
        lines.append(indent + "if true {")
        if level == 10:
            lines.append(indent + '    io.println("{}", h.work())')
        if level == 30:
            lines.append(indent + "    k := Ops{work: two}")
    lines.append("    " * (depth + 1) + 'io.println("{}", k.work())')
    for level in range(depth, 0, -1):
        lines.append("    " * level + "}")
    lines.append("}")
    source = "\n".join(lines) + "\n"

    ast = parse_a7(source, "deep.a7")
    compiler = A7Compiler()
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(100)
    try:
        compiler._annotate_file_module_calls(ast, {"h": "flat"})
    finally:
        sys.setrecursionlimit(old_limit)

    outer, innermost = _alias_calls(ast)
    assert getattr(outer, "file_module_call", None) == ("module_flat__", "work")
    assert getattr(innermost, "file_module_call", None) is None
