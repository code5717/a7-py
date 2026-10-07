"""Build and run one A7 program under each of the three build profiles.

`conftest.build_and_run` knows two profiles today. These helpers call Zig
directly so a test can cover `debug`, `release` and `fast`.
"""

from __future__ import annotations

import resource
import subprocess
from pathlib import Path

from conftest import expect_ok, shared_zig_cache

ZIG_MODE = {"debug": "Debug", "release": "ReleaseSafe", "fast": "ReleaseFast"}
PROFILES = tuple(ZIG_MODE)

# A panicking binary aborts; without this each abort stores a core dump.
def no_core_dump() -> None:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def build_binary(source: str, tmp_path, zig: str, profile: str, timeout: int = 120) -> Path:
    result = expect_ok(source, tmp_path, profile=profile)
    cache = shared_zig_cache()
    binary = Path(tmp_path) / f"program-{profile}"
    build = subprocess.run(
        [zig, "build-exe", result.output_path, "-O", ZIG_MODE[profile],
         "--cache-dir", str(cache / "local"),
         "--global-cache-dir", str(cache / "global"),
         "-femit-bin=" + str(binary)],
        capture_output=True, text=True, timeout=timeout,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    return binary


def run_profile(source: str, tmp_path, zig: str, profile: str, timeout: int = 120):
    binary = build_binary(source, tmp_path, zig, profile, timeout)
    return subprocess.run([str(binary)], capture_output=True, text=True,
                          timeout=timeout, preexec_fn=no_core_dump)


def same_output_in_every_profile(source: str, tmp_path, zig: str) -> str:
    """Every profile must exit 0 and print the same text."""
    outputs = {}
    for profile in PROFILES:
        process = run_profile(source, tmp_path, zig, profile)
        assert process.returncode == 0, f"{profile}: {process.stderr}"
        outputs[profile] = process.stdout
    assert outputs["debug"] == outputs["release"] == outputs["fast"], outputs
    return outputs["debug"]
