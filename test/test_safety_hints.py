"""Safety-proof errors print a hint naming a guard the compiler accepts.

Each case checks two things: the rejected program prints the hint, and the
same program with the hinted guard applied compiles. The second half keeps
the hint honest: a hint that names a shape the prover rejects fails here.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from a7.compile import ExitCode

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HEADER = 'io :: import "std/io"\n'
MAIN = 'main :: fn() {\n    io.println("{}", 1)\n}\n'

CASES = [
    pytest.param(
        "avg :: fn(sum: i32, n: i32) i32 {\n    ret sum / n\n}\n",
        "Divisor not proven non-zero",
        "hint: Guard the divisor: 'if n != 0 { ... }' around the division, "
        "or an early 'if n == 0 { ret ... }' before it",
        "avg :: fn(sum: i32, n: i32) i32 {\n    if n != 0 {\n        ret sum / n\n    }\n    ret 0\n}\n",
        id="divisor-guard",
    ),
    pytest.param(
        "avg :: fn(sum: i32, n: i32) i32 {\n    ret sum % n\n}\n",
        "Divisor not proven non-zero",
        "an early 'if n == 0 { ret ... }' before it",
        "avg :: fn(sum: i32, n: i32) i32 {\n    if n == 0 {\n        ret 0\n    }\n    ret sum % n\n}\n",
        id="divisor-early-return",
    ),
    pytest.param(
        "S :: struct { d: i32 }\nhalf :: fn(s: S) i32 {\n    ret 10 / s.d\n}\n",
        "Divisor not proven non-zero",
        "hint: Copy the value to a local 'd' first; proofs track local variables only. "
        "Guard the divisor: 'if d != 0 { ... }'",
        "S :: struct { d: i32 }\nhalf :: fn(s: S) i32 {\n    d := s.d\n    if d != 0 {\n        ret 10 / d\n    }\n    ret 0\n}\n",
        id="divisor-field-copied-to-local",
    ),
    pytest.param(
        "pick :: fn(xs: [5]i32, i: usize) i32 {\n    ret xs[i]\n}\n",
        "Index not proven in bounds",
        "hint: Guard the index: 'if i < 5 { ... }' around the access",
        "pick :: fn(xs: [5]i32, i: usize) i32 {\n    if i < 5 {\n        ret xs[i]\n    }\n    ret 0\n}\n",
        id="array-index",
    ),
    pytest.param(
        "pick :: fn(xs: []i32, i: usize) i32 {\n    ret xs[i]\n}\n",
        "Index not proven in bounds",
        "hint: Guard the index: 'if i < xs.len { ... }' around the access",
        "pick :: fn(xs: []i32, i: usize) i32 {\n    if i < xs.len {\n        ret xs[i]\n    }\n    ret 0\n}\n",
        id="slice-index",
    ),
    pytest.param(
        "second :: fn(xs: []i32) i32 {\n    ret xs[1]\n}\n",
        "Index not proven in bounds",
        "hint: Copy the value to a local 'i' first; proofs track local variables only. "
        "Guard the index: 'if i < xs.len { ... }' around the access",
        "second :: fn(xs: []i32) i32 {\n    i: usize = 1\n    if i < xs.len {\n        ret xs[i]\n    }\n    ret 0\n}\n",
        id="slice-literal-index-copied-to-local",
    ),
    pytest.param(
        "take :: fn(xs: [5]i32, b: usize) usize {\n    s := xs[0..b]\n    ret s.len\n}\n",
        "Slice bounds not proven",
        "'if b <= 5 { ... xs[0..b] ... }'",
        "take :: fn(xs: [5]i32, b: usize) usize {\n    if b <= 5 {\n        s := xs[0..b]\n        ret s.len\n    }\n    ret 0\n}\n",
        id="slice-end",
    ),
    pytest.param(
        "N :: struct { v: i32 }\nmake :: fn() {\n    n := new N\n    n.v = 3\n    del n\n}\n",
        "Reference not proven non-nil",
        "hint: Check the reference first: 'if n != nil { ... }' around the use, "
        "or an early 'if n == nil { ret ... }' before it",
        "N :: struct { v: i32 }\nmake :: fn() {\n    n := new N\n    if n != nil {\n        n.v = 3\n    }\n    del n\n}\n",
        id="reference",
    ),
]


def run_pipeline(tmp_path, body):
    source = tmp_path / "main.a7"
    source.write_text(HEADER + body + MAIN, encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT), "NO_COLOR": "1", "COLUMNS": "200"}
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "check", str(source)],
        cwd=PROJECT_ROOT, capture_output=True, text=True, env=env,
    )


@pytest.mark.parametrize(("rejected", "headline", "hint", "guarded"), CASES)
def test_proof_error_prints_an_accepted_guard(tmp_path, rejected, headline, hint, guarded):
    failed = run_pipeline(tmp_path, rejected)

    assert failed.returncode == ExitCode.SEMANTIC, failed.stdout + failed.stderr
    assert headline in failed.stderr
    assert hint in failed.stderr

    accepted = run_pipeline(tmp_path, guarded)
    assert accepted.returncode == ExitCode.SUCCESS, accepted.stdout + accepted.stderr


def test_constant_zero_divisor_is_named_as_such(tmp_path):
    failed = run_pipeline(tmp_path, "bad :: fn(a: i32) i32 {\n    ret a / 0\n}\n")

    assert failed.returncode == ExitCode.SEMANTIC
    assert "hint: The divisor is the constant 0; divide by a non-zero value" in failed.stderr


def test_constant_index_past_the_end_names_the_valid_range(tmp_path):
    failed = run_pipeline(tmp_path, "bad :: fn(xs: [3]i32) i32 {\n    ret xs[5]\n}\n")

    assert failed.returncode == ExitCode.SEMANTIC
    assert "hint: This array has 3 elements; valid indexes are 0 to 2" in failed.stderr
