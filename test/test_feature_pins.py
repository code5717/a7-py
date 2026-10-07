"""Phase 3 feature pins without another natural home.

Bench coverage: every bench/*.a7 program emits through the real CLI and
builds with real Zig in both Debug and ReleaseFast (binaries are built, not
run: bench runs are timing-sensitive). CLI rejection pins: an f64 value
assigned to an f32 local is a width mismatch, and `pub` on a local is a
parse error. Cross-module visibility and del-through-ref have no passing
test: both are accepted today (spec-drift findings, not pins).
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from a7.compile import ExitCode
from conftest import shared_zig_cache


ROOT = Path(__file__).resolve().parents[1]
BENCH_DIR = ROOT / "bench"
PROFILES = ("Debug", "ReleaseFast")

BENCHES = (
    "alloc_churn",
    "aos_walk",
    "arith_loop",
    "array_walk",
    "kv_append",
    "print_lines",
    "soa_walk",
    "sort_load",
    "stride_walk",
    "vector_ops",
)


def test_bench_corpus_shape_is_pinned():
    assert sorted(p.stem for p in BENCH_DIR.glob("*.a7")) == sorted(BENCHES)


@pytest.fixture(scope="module")
def zig():
    executable = os.environ.get("A7_TEST_ZIG") or shutil.which("zig")
    assert executable, "Zig 0.16.0 required: set A7_TEST_ZIG or PATH"
    version = subprocess.run([executable, "version"], capture_output=True, text=True)
    assert version.returncode == 0 and version.stdout.strip() == "0.16.0", version
    return executable


@pytest.fixture(scope="module")
def zig_cache():
    return shared_zig_cache()


def compile_bench(tmp_path, name):
    source = BENCH_DIR / f"{name}.a7"
    assert source.exists(), source
    output = tmp_path / f"{name}.zig"
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    process = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(source), "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True, env=env,
    )
    assert process.returncode == ExitCode.SUCCESS, process.stdout + process.stderr
    return output


@pytest.mark.parametrize("name", BENCHES)
def test_each_bench_builds_debug_and_release(tmp_path, zig, zig_cache, name):
    output = compile_bench(tmp_path, name)
    for profile in PROFILES:
        binary = tmp_path / f"{name}-{profile}"
        process = subprocess.run(
            [zig, "build-exe", str(output), "-O", profile,
             "--cache-dir", str(zig_cache / "local"),
             "--global-cache-dir", str(zig_cache / "global"),
             "-femit-bin=" + str(binary)],
            capture_output=True, text=True,
        )
        assert (profile, process.returncode) == (profile, 0), process.stdout + process.stderr


def run_cli_json(tmp_path, source, name="main"):
    src = tmp_path / f"{name}.a7"
    out = tmp_path / f"{name}.zig"
    src.write_text(source, encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    process = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(src),
         "--output", str(out), "--format", "json"],
        cwd=ROOT, capture_output=True, text=True, env=env,
    )
    return process.returncode, json.loads(process.stdout)


def test_float_width_mismatch_assignment_is_rejected(tmp_path):
    source = '''io :: import "std/io"
main :: fn() {
    x: f32 = 1.0
    y: f64 = 2.0
    x = y
    io.println("{}", x)
}
'''
    code, payload = run_cli_json(tmp_path, source)
    assert code == ExitCode.SEMANTIC, payload
    details = (payload.get("error") or {}).get("details") or []
    assert len(details) == 1, details
    assert "expected 'f32', got 'f64'" in details[0]["message"], details[0]
    assert details[0].get("span", {}).get("start_line") == 5, details[0]


def test_pub_on_local_is_rejected(tmp_path):
    source = '''io :: import "std/io"
main :: fn() {
    pub x := 1
    io.println("{}", x)
}
'''
    code, payload = run_cli_json(tmp_path, source)
    assert code == ExitCode.PARSE, payload
