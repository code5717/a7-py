"""Stdlib calls are recognized only through a resolved stdlib module import.

A call lowers to stdlib code (stdout printing, a Zig math builtin) only when
its callee root resolves to a module symbol imported from `std/io`, `std/math`,
`io` or `math`. A user function, struct value or local named like a stdlib
name must run the user's code.

Each case compiles A7 source with the repository CLI, builds the emitted Zig in
Debug and ReleaseFast, runs the binary and compares its output with the value
derived by hand from the source (written in the case table before any run).
Nothing is mocked. The programs use no heap, references, indexing, integer
division or overflow-prone arithmetic.

Set A7_TEST_ZIG to a Zig 0.16.0 binary or put zig on PATH. A missing Zig fails
the tests.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ("Debug", "ReleaseFast")


@pytest.fixture(scope="module")
def zig():
    executable = os.environ.get("A7_TEST_ZIG") or shutil.which("zig")
    assert executable, "Zig 0.16.0 required: set A7_TEST_ZIG or PATH"
    version = subprocess.run([executable, "version"], capture_output=True, text=True)
    assert version.returncode == 0 and version.stdout.strip() == "0.16.0", version
    return executable


@pytest.fixture(scope="module")
def zig_cache(tmp_path_factory):
    return tmp_path_factory.mktemp("zig-cache")


def run_cli(src, out):
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(src), "--output", str(out)],
        cwd=ROOT, capture_output=True, text=True, env=env,
    )


def compile_source(tmp_path, source):
    src = tmp_path / "main.a7"
    out = tmp_path / "main.zig"
    src.write_text(source, encoding="utf-8")
    process = run_cli(src, out)
    assert process.returncode == 0, process.stdout + process.stderr
    return out


def build_and_run(zig, zig_cache, tmp_path, output, profile):
    binary = tmp_path / ("program-" + profile)
    build = subprocess.run(
        [zig, "build-exe", str(output), "-O", profile,
         "--cache-dir", str(zig_cache / "local"),
         "--global-cache-dir", str(zig_cache / "global"),
         "-femit-bin=" + str(binary)],
        capture_output=True, text=True,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    run = subprocess.run([str(binary)], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    return run.stdout, run.stderr


# name: (source, expected stdout, expected stderr)
USER_CODE_CASES = {
    # PIP-2 (audit probe s01): the user's sqrt_f64 adds 1.0, so 9.0 -> 10.
    "user-fn-named-sqrt_f64": ('''io :: import "std/io"
sqrt_f64 :: fn(x: f64) f64 {
    ret x + 1.0
}
main :: fn() {
    io.println("{}", sqrt_f64(9.0))
}
''', "10\n", ""),
    # SAF-9 (audit probe f07): the user's abs_f64 adds 100.0, so -1.0 -> 99.
    "user-fn-named-abs_f64": ('''io :: import "std/io"

abs_f64 :: fn(x: f64) f64 {
    ret x + 100.0
}

main :: fn() {
    io.println("{}", abs_f64(-1.0))
}
''', "99\n", ""),
    # Every other registered typed name is also a plain user function when
    # declared: each returns its argument plus a distinct offset.
    "user-fns-named-other-typed-builtins": ('''io :: import "std/io"
floor_f32 :: fn(x: f32) f32 {
    ret x + 1.0
}
ceil_f64 :: fn(x: f64) f64 {
    ret x + 2.0
}
min_f64 :: fn(a: f64, b: f64) f64 {
    ret a + b
}
max_f32 :: fn(a: f32, b: f32) f32 {
    ret a + b
}
sin_f64 :: fn(x: f64) f64 {
    ret x + 3.0
}
main :: fn() {
    h: f32 = 0.5
    one: f32 = 1.0
    two: f32 = 2.0
    io.println("{} {} {} {} {}", floor_f32(h), ceil_f64(0.5), min_f64(1.0, 2.0), max_f32(one, two), sin_f64(0.0))
}
''', "1.5 2.5 3 3 3\n", ""),
    # PIP-3 (audit probe s02b): no std/io import; `io` is a struct value whose
    # println field is `say`, which prints nothing.
    "struct-value-named-io-without-import": ('''say :: fn(s: string) {
}
Printer :: struct {
    println: fn(string)
}
main :: fn() {
    io := Printer{println: say}
    g := io.println
    g("quiet")
    io.println("hijacked")
}
''', "", ""),
    # ZIG-5 (audit probe p077b): std/io is imported as `console`; `io` is a
    # struct value whose println field is `show`, so both calls reach `show`.
    "struct-value-named-io-with-console-import": ('''console :: import "std/io"
Printer :: struct {
    println: fn(string)
}
show :: fn(s: string) {
    console.println("show called with {}", s)
}
main :: fn() {
    io := Printer{println: show}
    g := io.println
    io.println("direct")
    g("through g")
}
''', "show called with direct\nshow called with through g\n", ""),
    # B14 (probe b14a): `math` is a struct value whose sqrt field is halve.
    "struct-value-named-math": ('''io :: import "std/io"

Ops :: struct {
    sqrt: fn(f64) f64
}

halve :: fn(v: f64) f64 {
    ret v / 2.0
}

main :: fn() {
    math := Ops{sqrt: halve}
    io.println("{}", math.sqrt(9.0))
}
''', "4.5\n", ""),
    # B14 (probe b14d): the field call and the call through a copy agree.
    "struct-value-named-math-and-copy": ('''io :: import "std/io"

Ops :: struct {
    sqrt: fn(f64) f64
}

halve :: fn(v: f64) f64 {
    ret v / 2.0
}

main :: fn() {
    math := Ops{sqrt: halve}
    g := math.sqrt
    io.println("{} {}", math.sqrt(9.0), g(9.0))
}
''', "4.5 4.5\n", ""),
    # A block local `io` hides the file-scope std/io alias inside its block
    # only; `say` prints nothing, the calls outside the block print.
    "block-local-io-shadows-stdlib-alias": ('''io :: import "std/io"
Printer :: struct {
    println: fn(string)
}
say :: fn(s: string) {
}
main :: fn() {
    io.println("outer")
    {
        io := Printer{println: say}
        io.println("hidden")
    }
    io.println("after")
}
''', "outer\nafter\n", ""),
    # A parameter named `io` hides the std/io alias in its function body.
    "parameter-io-shadows-stdlib-alias": ('''io :: import "std/io"
Printer :: struct {
    println: fn(string)
}
say :: fn(s: string) {
}
use_it :: fn(io: Printer) {
    io.println("hidden")
}
main :: fn() {
    p := Printer{println: say}
    use_it(p)
    io.println("after")
}
''', "after\n", ""),
}

# name: (source, expected stdout, expected stderr)
STDLIB_CASES = {
    "io-println-print-eprintln": ('''io :: import "std/io"
main :: fn() {
    io.print("a")
    io.println("b{}", 1)
    io.eprintln("err {}", 2)
}
''', "ab1\n", "err 2\n"),
    "math-sqrt-default-alias": ('''io :: import "std/io"
math :: import "std/math"
main :: fn() {
    io.println("{}", math.sqrt(9.0))
}
''', "3\n", ""),
    "math-sqrt-other-alias": ('''io :: import "std/io"
m :: import "std/math"
main :: fn() {
    io.println("{}", m.sqrt(16.0))
}
''', "4\n", ""),
    "io-other-alias": ('''console :: import "std/io"
main :: fn() {
    console.println("x")
}
''', "x\n", ""),
    # Ledger L31: bare `io` and `math` import paths are the standard library.
    "bare-stdlib-import-paths": ('''io :: import "io"
math :: import "math"
main :: fn() {
    io.println("{}", math.abs(-2.5))
}
''', "2.5\n", ""),
}


def _check_runtime(zig, zig_cache, tmp_path, source, expected_out, expected_err):
    output = compile_source(tmp_path, source)
    for profile in PROFILES:
        assert build_and_run(zig, zig_cache, tmp_path, output, profile) == (expected_out, expected_err), profile
    return output


@pytest.mark.parametrize("name", sorted(USER_CODE_CASES))
def test_user_code_named_like_stdlib_runs_user_code(tmp_path, zig, zig_cache, name):
    source, expected_out, expected_err = USER_CODE_CASES[name]
    _check_runtime(zig, zig_cache, tmp_path, source, expected_out, expected_err)


@pytest.mark.parametrize("name", sorted(STDLIB_CASES))
def test_resolved_stdlib_calls_still_lower_to_stdlib(tmp_path, zig, zig_cache, name):
    source, expected_out, expected_err = STDLIB_CASES[name]
    _check_runtime(zig, zig_cache, tmp_path, source, expected_out, expected_err)


def test_math_call_through_alias_lowers_to_zig_builtin(tmp_path):
    output = compile_source(tmp_path, STDLIB_CASES["math-sqrt-other-alias"][0])
    assert "@sqrt(16.0)" in output.read_text(encoding="utf-8")


def test_undeclared_typed_builtin_name_stays_rejected(tmp_path):
    src = tmp_path / "main.a7"
    src.write_text('''io :: import "std/io"
main :: fn() {
    x: f64 = 9.0
    io.println("{}", sqrt_f64(x))
}
''', encoding="utf-8")
    process = run_cli(src, tmp_path / "main.zig")
    assert process.returncode == 6, process.stdout + process.stderr
    assert "sqrt_f64" in process.stdout + process.stderr


@pytest.mark.parametrize("example", ["018_modules", "030_calculator"])
def test_stdlib_examples_match_golden_output(tmp_path, zig, zig_cache, example):
    output = tmp_path / (example + ".zig")
    process = run_cli(ROOT / "examples" / (example + ".a7"), output)
    assert process.returncode == 0, process.stdout + process.stderr
    golden = (ROOT / "test" / "fixtures" / "golden_outputs" / (example + ".out")).read_text(encoding="utf-8")
    for profile in PROFILES:
        stdout, stderr = build_and_run(zig, zig_cache, tmp_path, output, profile)
        assert (stdout, stderr) == (golden, ""), profile
