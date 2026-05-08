#!/usr/bin/env python3
"""Verify selected A7 programs produce identical Zig and C backend output."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = ROOT / "main.py"


CASES: dict[str, str] = {
    "numeric_control_flow": r'''
io :: import "std/io"

main :: fn() {
    total := 0
    i := 1
    while i <= 5 {
        if i % 2 == 0 {
            total += i * 2
        } else {
            total += i
        }
        i += 1
    }
    io.println("score = {}", total)
}
''',
    "string_iteration": r'''
io :: import "std/io"

main :: fn() {
    io.print("chars = ")
    for ch in "A7" {
        io.print("{}", ch)
    }
    io.println("")
}
''',
    "labeled_loop_totals": r'''
io :: import "std/io"

main :: fn() {
    total := 0
    @outer for i := 0; i < 4; i += 1 {
        for j := 0; j < 4; j += 1 {
            if j == 2 {
                continue outer
            }
            total += i + j
        }
    }
    io.println("labeled = {}", total)
}
''',
    "function_pointer_dispatch": r'''
io :: import "std/io"

Op :: fn(i32, i32) i32

add :: fn(a: i32, b: i32) i32 {
    ret a + b
}

mul :: fn(a: i32, b: i32) i32 {
    ret a * b
}

apply :: fn(op: Op, a: i32, b: i32) i32 {
    ret op(a, b)
}

main :: fn() {
    op: Op = add
    io.println("add = {}", apply(op, 6, 7))
    op = mul
    io.println("mul = {}", apply(op, 6, 7))
}
''',
    "slice_index_fields": r'''
io :: import "std/io"

main :: fn() {
    arr: [4]i32 = [10, 20, 30, 40]
    tail := arr[1..4]
    ptr := tail.ptr
    total := tail[0]
    for x in tail {
        total += x
    }
    index_sum: usize = 0
    indexed_value_total := 0
    for i, x in tail {
        index_sum += i
        indexed_value_total += x
    }
    io.println("slice = {} {} {}", tail.len, ptr.val, total)
    io.println("indexed = {} {}", index_sum, indexed_value_total)
}
''',
    "array_literal_assignment": r'''
io :: import "std/io"

main :: fn() {
    widened: [3]i64 = [1, 2, 3]
    matrix: [2][2]i64 = [[1, 2], [3, 4]]
    total := widened[0] + widened[1] + widened[2]
    total += matrix[0][0] + matrix[0][1] + matrix[1][0] + matrix[1][1]
    io.println("array assignment = {}", total)
}
''',
    "match_statement_ranges": r'''
io :: import "std/io"

main :: fn() {
    value := 7
    match value {
        case 0: io.println("zero")
        case 1..5: io.println("small")
        case 6..10: io.println("medium")
        else: io.println("large")
    }
}
''',
    "match_fallthrough": r'''
io :: import "std/io"

main :: fn() {
    value := 1
    match value {
        case 1: {
            defer io.println("cleanup one")
            io.println("one")
            fall
        }
        case 2: {
            io.println("two")
        }
        else: {
            io.println("else")
        }
    }

    other := 3
    match other {
        case 1: {
            fall
        }
        case 2: {
            io.println("bad")
        }
        else: {
            defer io.println("cleanup else")
            io.println("else")
        }
    }
}
''',
    "nested_match_fallthrough": r'''
io :: import "std/io"

main :: fn() {
    outer := 1
    inner := 1
    match outer {
        case 1: {
            match inner {
                case 1: {
                    io.println("inner one")
                    fall
                }
                case 2: {
                    io.println("inner two")
                }
                else: {}
            }
        }
        else: {}
    }
}
''',
    "match_expression_side_effects": r'''
io :: import "std/io"

calls: i32 = 0

value :: fn() i32 {
    calls += 1
    ret 2
}

pick :: fn() i32 {
    ret match value() {
        case 2: 20
        else: 0
    }
}

identity :: fn(x: i32) i32 {
    ret x
}

main :: fn() {
    x: i32 = 0
    x = match value() {
        case 2: 7
        else: 1
    }
    y := identity(match value() {
        case 2: 5
        else: 0
    })
    z := pick()
    io.println("match = {} {} {} {}", x, y, z, calls)
}
''',
    "match_capture_patterns": r'''
io :: import "std/io"

calls: i32 = 0

next :: fn() i32 {
    calls += 1
    ret 7
}

score :: fn(n: i32) i32 {
    ret match n {
        case value: value + 1
    }
}

main :: fn() {
    n := next()
    match n {
        case value: {
            io.println("capture stmt = {}", value)
        }
    }
    io.println("capture expr = {} calls {}", score(next()), calls)
}
''',
    "string_slice_iteration": r'''
io :: import "std/io"

main :: fn() {
    text: string = "abcdef"
    io.print("text = ")
    for ch in text[1..4] {
        io.print("{}", ch)
    }
    for ch in text[4..] {
        io.print("{}", ch)
    }
    io.println("")
}
''',
    "defer_unwind_order": r'''
io :: import "std/io"

normal :: fn() {
    defer io.println("normal cleanup 1")
    defer io.println("normal cleanup 2")
    io.println("normal body")
}

early :: fn() i32 {
    defer io.println("early cleanup 1")
    defer io.println("early cleanup 2")
    ret 7
}

main :: fn() {
    normal()
    value := early()
    io.println("early value = {}", value)
}
''',
    "union_field_access": r'''
io :: import "std/io"

Value :: union {
    int_val: i32
    flag_val: bool
}

main :: fn() {
    integer := Value{int_val: 42}
    flag := Value{flag_val: true}
    io.println("union = {} {}", integer.int_val, flag.flag_val)
}
''',
    "generic_function_specialization": r'''
io :: import "std/io"

identity($T) :: fn(value: $T) $T {
    ret value
}

main :: fn() {
    io.println("generic = {} {}", identity(7), identity("ok"))
}
''',
    "enum_match_expression": r'''
io :: import "std/io"

State :: enum {
    Ready
    Busy
    Done
}

score :: fn(state: State) i32 {
    ret match state {
        case State.Ready: 1
        case State.Busy: 2
        case State.Done: 3
    }
}

main :: fn() {
    io.println("enum ready = {}", score(State.Ready))
    io.println("enum busy = {}", score(State.Busy))
    io.println("enum done = {}", score(State.Done))
}
''',
    "heap_struct_roundtrip": r'''
io :: import "std/io"

Point :: struct {
    x: i32
    y: i32
}

main :: fn() {
    point := new Point
    defer del point
    point.val = Point{x: 6, y: 7}
    io.println("heap point = {} {}", point.val.x, point.val.y)
}
''',
    "nested_fixed_arrays": r'''
io :: import "std/io"

main :: fn() {
    matrix: [2][3]i32 = [[1, 2, 3], [4, 5, 6]]
    total := 0
    for row in matrix {
        for value in row {
            total += value
        }
    }
    io.println("matrix = {}", total)
}
''',
    "nested_3d_arrays": r'''
io :: import "std/io"

main :: fn() {
    cube: [2][2][2]i32 = [[[1, 2], [3, 4]], [[5, 6], [7, 8]]]
    total := 0
    for plane in cube {
        for row in plane {
            for value in row {
                total += value
            }
        }
    }
    io.println("cube = {}", total)
}
''',
}


@dataclass
class ParityResult:
    name: str
    zig_ok: bool = False
    c_ok: bool = False
    output_match: bool = False
    zig_output: str = ""
    c_output: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.zig_ok and self.c_ok and self.output_match


def result_to_json(result: ParityResult) -> dict[str, object]:
    data = asdict(result)
    data["ok"] = result.ok
    return data


def run_cmd(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: float = 10.0,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            cmd,
            124,
            stdout=_timeout_stream_text(exc.stdout),
            stderr=f"command timed out after {timeout:.1f}s",
        )


def _timeout_stream_text(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def normalize_output(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    if lines and lines[-1] == "":
        lines = lines[:-1]
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def first_error_text(proc: subprocess.CompletedProcess[str]) -> str:
    output = (proc.stderr or proc.stdout or "").strip()
    if not output:
        return "command failed without output"
    return "\n".join(output.splitlines()[:12])


def compile_build_run(
    case_name: str,
    source_path: Path,
    backend: str,
    build_dir: Path,
    timeout: float,
) -> tuple[bool, str]:
    source_ext = ".zig" if backend == "zig" else ".c"
    generated = build_dir / f"{case_name}.{backend}{source_ext}"
    binary = build_dir / f"{case_name}.{backend}.bin"

    compile_proc = run_cmd(
        [
            sys.executable,
            str(MAIN_PY),
            "--backend",
            backend,
            str(source_path),
            "-o",
            str(generated),
        ],
        cwd=ROOT,
        timeout=timeout,
    )
    if compile_proc.returncode != 0:
        return False, f"{backend} compile failed:\n{first_error_text(compile_proc)}"

    if backend == "zig":
        build_cmd = ["zig", "build-exe", str(generated), f"-femit-bin={binary}"]
    else:
        build_cmd = [
            "zig",
            "cc",
            "-std=c11",
            "-Werror=incompatible-pointer-types",
            str(generated),
            "-lm",
            "-o",
            str(binary),
        ]

    build_proc = run_cmd(build_cmd, cwd=ROOT, timeout=timeout)
    if build_proc.returncode != 0:
        return False, f"{backend} build failed:\n{first_error_text(build_proc)}"

    try:
        run_proc = subprocess.run(
            [str(binary)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"{backend} binary timed out after {timeout:.1f}s"

    if run_proc.returncode != 0:
        output = (run_proc.stdout or "").strip()
        detail = (
            "\n".join(output.splitlines()[:12])
            if output
            else f"exit code {run_proc.returncode}"
        )
        return False, f"{backend} binary exited non-zero:\n{detail}"

    return True, normalize_output(run_proc.stdout or "")


def verify_case(name: str, source: str, root_dir: Path, timeout: float) -> ParityResult:
    result = ParityResult(name=name)
    case_dir = root_dir / name
    case_dir.mkdir(parents=True, exist_ok=True)
    source_path = case_dir / f"{name}.a7"
    source_path.write_text(source.strip() + "\n", encoding="utf-8")

    zig_ok, zig_output = compile_build_run(name, source_path, "zig", case_dir, timeout)
    if not zig_ok:
        result.error = zig_output
        return result
    result.zig_ok = True
    result.zig_output = zig_output

    c_ok, c_output = compile_build_run(name, source_path, "c", case_dir, timeout)
    if not c_ok:
        result.error = c_output
        return result
    result.c_ok = True
    result.c_output = c_output

    if zig_output != c_output:
        result.error = "backend output mismatch"
        return result

    result.output_match = True
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify selected Zig/C backend output parity")
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Per compile/build/run command timeout in seconds",
    )
    parser.add_argument(
        "--json-report",
        default="",
        help="Optional path to write a JSON report",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="a7-backend-parity-") as tmp:
        results = [
            verify_case(name, source, Path(tmp), args.timeout)
            for name, source in CASES.items()
        ]

    passed = sum(1 for result in results if result.ok)
    total = len(results)
    print(f"Backend parity verified: {passed}/{total}")

    failed = [result for result in results if not result.ok]
    if failed:
        print("\nFailures:")
        for result in failed:
            print(f"- {result.name}: {result.error}")
            if result.zig_output or result.c_output:
                print("  zig output:")
                print(result.zig_output.rstrip())
                print("  c output:")
                print(result.c_output.rstrip())

    if args.json_report:
        report_path = Path(args.json_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "passed": passed,
                    "total": total,
                    "ok": passed == total,
                    "results": [result_to_json(result) for result in results],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
