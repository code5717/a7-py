"""Float constant expressions must fold in IEEE f64, including inf and NaN.

A7 float literals are f64 (`type_checker.visit_literal` returns F64), and
ledger L16 (`docs/plan/decisions.md`) makes infinity and NaN ordinary values.
Leaving an overflowing float expression for Zig does not preserve that: bare
Zig float literals are `comptime_float`, which is f128, where 1e309 is an
ordinary finite value. So the compiler folds float constant expressions in f64
and emits a non-finite result as a typed Zig expression.

Every expected output below is the IEEE f64 answer derived by hand from the A7
source, not from running the compiler. Programs are compiled with the real CLI
and built with the real Zig 0.16.0 toolchain in Debug and ReleaseFast. Float
overflow is defined IEEE behavior, so these programs are safe to run: none of
them allocates, divides by a possible zero, indexes, or overflows an integer.

NaN is never asserted through its printed text. The sign bit of a NaN is not
specified by IEEE 754 and Zig prints `nan` or `-nan` depending on where the
value came from, so NaN is observed through predicates (`n != n`) instead.
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


def cli_compile(tmp_path, source):
    src = tmp_path / "main.a7"
    out = tmp_path / "main.zig"
    src.write_text(source, encoding="utf-8")
    process = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(src), "--output", str(out)],
        cwd=ROOT, capture_output=True, text=True,
    )
    return process, out


def emit(tmp_path, source):
    process, out = cli_compile(tmp_path, source)
    assert process.returncode == 0, process.stdout + process.stderr
    return out


def zig_cache_args(tmp_path):
    return ["--cache-dir", str(tmp_path / "cache"),
            "--global-cache-dir", str(tmp_path / "global-cache")]


def run_all_profiles(zig, tmp_path, output):
    observed = {}
    for profile in PROFILES:
        binary = tmp_path / ("program-" + profile)
        build = subprocess.run(
            [zig, "build-exe", str(output), "-O", profile,
             *zig_cache_args(tmp_path), "-femit-bin=" + str(binary)],
            capture_output=True, text=True,
        )
        assert build.returncode == 0, build.stdout + build.stderr
        process = subprocess.run([str(binary)], capture_output=True, text=True)
        observed[profile] = (process.returncode, process.stdout, process.stderr)
    return observed


def expect_everywhere(stdout):
    return {profile: (0, stdout, "") for profile in PROFILES}


def program(body):
    return 'io :: import "std/io"\n\nmain :: fn() {\n' + body + '}\n'


# ---------------------------------------------------------------------------
# A comparison over an overflowing float subexpression.
#
# In f64, 1e308 * 10.0 and 1e308 * 5.0 are both +inf, so:
#   inf > inf  is false
#   inf == inf is true
#   inf - inf  is NaN, and NaN == 0.0 is false
#   NaN == NaN is false and NaN != NaN is true
# In f128 (Zig comptime_float) 1e309 and 5e308 are finite and every one of
# those answers flips.
#
# d and e fold entirely inside A7: both operands are NaN literals by the time
# the comparison is folded, so the compiler itself must get NaN equality
# right. The emitted Zig is `const d = false;` / `const e = true;`.
# ---------------------------------------------------------------------------

def test_comparison_over_overflowing_floats_gives_the_f64_answer(tmp_path, zig):
    output = emit(tmp_path, program(
        '    a := 1e308 * 10.0 > 1e308 * 5.0\n'
        '    b := 1e308 * 10.0 == 1e308 * 5.0\n'
        '    c := (1e308 * 10.0 - 1e308 * 10.0) == 0.0\n'
        '    d := (1e308 * 10.0 - 1e308 * 10.0) == (1e308 * 10.0 - 1e308 * 10.0)\n'
        '    e := (1e308 * 10.0 - 1e308 * 10.0) != (1e308 * 10.0 - 1e308 * 10.0)\n'
        '    io.println("{} {} {} {} {}", a, b, c, d, e)\n'
    ))
    emitted = output.read_text(encoding="utf-8")
    assert "const d: bool = false;" in emitted, emitted
    assert "const e: bool = true;" in emitted, emitted
    assert run_all_profiles(zig, tmp_path, output) == expect_everywhere(
        "false true false false true\n")


def test_if_over_overflowing_floats_takes_the_f64_branch(tmp_path, zig):
    output = emit(tmp_path, program(
        '    if 1e308 * 10.0 > 1e308 * 5.0 {\n'
        '        io.println("greater")\n'
        '    } else {\n'
        '        io.println("not greater")\n'
        '    }\n'
    ))
    assert run_all_profiles(zig, tmp_path, output) == expect_everywhere(
        "not greater\n")


# ---------------------------------------------------------------------------
# A non-finite fold reaches the emitted Zig as a value of the right type.
# HEAD emitted `inf.0` / `nan.0` here, which Zig rejects.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("statement, stdout", [
    ("x: f64 = 1.0e308 * 10.0", "inf\n"),
    ("x: f64 = -1.0e308 * 10.0", "-inf\n"),
    # inf / 100.0 is inf; the f128 answer would be 1e307.
    ("x: f64 = 1.0e308 * 10.0 / 100.0", "inf\n"),
], ids=["inf", "negative-inf", "compound-overflow"])
def test_overflowing_float_declaration_prints_the_f64_value(
        tmp_path, zig, statement, stdout):
    output = emit(tmp_path, program(
        '    ' + statement + '\n'
        '    io.println("{}", x)\n'
    ))
    assert run_all_profiles(zig, tmp_path, output) == expect_everywhere(stdout)


@pytest.mark.parametrize("statement", [
    # inf - inf is NaN.
    "n: f64 = 1.0e308 * 10.0 - 1.0e308 * 10.0",
    # inf * 0.0 is NaN; the f128 answer would be 0.0.
    "n: f64 = 1.0e308 * 10.0 * 0.0",
], ids=["inf-minus-inf", "inf-times-zero"])
def test_nan_fold_behaves_as_nan(tmp_path, zig, statement):
    # n == n is false and n != n is true for every NaN, and a NaN is not
    # equal to 0.0. All three flip if the value is a finite f128 result.
    output = emit(tmp_path, program(
        '    ' + statement + '\n'
        '    io.println("{} {} {}", n == n, n != n, n == 0.0)\n'
    ))
    assert run_all_profiles(zig, tmp_path, output) == expect_everywhere(
        "false true false\n")


# ---------------------------------------------------------------------------
# The Zig expression used for a non-finite literal needs `std`, which the
# preamble only imports when the program asks for it. A program with no io
# call and no allocation would otherwise emit `std.math.inf` with no import.
# Compile only: the program prints nothing.
# ---------------------------------------------------------------------------

def test_nonfinite_fold_without_io_still_compiles(tmp_path, zig):
    output = emit(tmp_path, (
        'big_value :: fn() f64 {\n'
        '    ret 1.0e308 * 10.0\n'
        '}\n'
        '\n'
        'main :: fn() {\n'
        '    x: f64 = big_value()\n'
        '    if x > 0.0 {\n'
        '        ret\n'
        '    }\n'
        '}\n'
    ))
    build = subprocess.run(
        [zig, "build-obj", str(output), "-fno-emit-bin", *zig_cache_args(tmp_path)],
        capture_output=True, text=True,
    )
    assert build.returncode == 0, build.stdout + build.stderr


def test_float_remainder_constants_match_native_values(tmp_path, zig):
    # Truncated quotients leave the dividend's sign: -5.5 - (-2)*2 = -1.5.
    # The runtime expressions use typed locals; expected values are independent
    # of either implementation. Positive, negative, and exact division differ.
    output = emit(tmp_path, program(
        '    x: f64 = -5.5\n'
        '    p: f64 = 5.5\n'
        '    exact: f64 = -4.0\n'
        '    y: f64 = 2.0\n'
        '    io.println("{} {} {} {} {} {}", -5.5 % 2.0, x % y, 5.5 % 2.0, p % y, -4.0 % 2.0, exact % y)\n'
    ))
    assert run_all_profiles(zig, tmp_path, output) == expect_everywhere(
        "-1.5 -1.5 1.5 1.5 -0 -0\n")


def test_float_remainder_sign_and_nonfinite_boundaries():
    # These pure evaluator checks cover signed zero and nonfinite results that
    # printed equality cannot distinguish. Native integration is checked above.
    import math
    from a7.ast_nodes import BinaryOp
    from a7.const_eval import fold_binary
    from a7.types import F64

    assert fold_binary(BinaryOp.MOD, 5.5, -2.0, F64) == 1.5
    assert fold_binary(BinaryOp.MOD, -5.5, -2.0, F64) == -1.5
    zero = fold_binary(BinaryOp.MOD, -4.0, 2.0, F64)
    assert zero == 0.0 and math.copysign(1.0, zero) == -1.0
    assert math.isnan(fold_binary(BinaryOp.MOD, math.inf, 2.0, F64))
    assert math.isnan(fold_binary(BinaryOp.MOD, math.nan, 2.0, F64))
    assert fold_binary(BinaryOp.MOD, -5.5, math.inf, F64) == -5.5
    assert fold_binary(BinaryOp.MOD, 5.5, 0.0, F64) is None
