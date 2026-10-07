"""`--profile` has three values: debug, release (ReleaseSafe), fast (ReleaseFast) (L64)."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import compile_program, expect_ok, failure_text

ROOT = Path(__file__).resolve().parent.parent
ZIG_MODE = {"debug": "Debug", "release": "ReleaseSafe", "fast": "ReleaseFast"}

HELLO = 'io :: import "std/io"\nmain :: fn() {\n    io.println("hi")\n}\n'


def recording_zig(tmp_path, zig: str) -> tuple[dict, Path]:
    """Put a `zig` on PATH that logs its arguments and then runs the real Zig.

    The real toolchain still builds the program, so the only thing the shim
    leaves unverified is that Zig honors the `-O` value it is given.
    """
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    log = tmp_path / "zig-args.log"
    shim = shim_dir / "zig"
    shim.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        f"with open({str(log)!r}, 'a') as handle:\n"
        "    handle.write(' '.join(sys.argv[1:]) + '\\n')\n"
        f"os.execv({zig!r}, [{zig!r}, *sys.argv[1:]])\n"
    )
    shim.chmod(0o755)
    env = {**os.environ, "PATH": f"{shim_dir}{os.pathsep}{os.environ['PATH']}"}
    return env, log


def optimize_flags(log: Path) -> list[str]:
    flags = []
    for line in log.read_text().splitlines():
        words = line.split()
        if words[0] != "build-exe":
            continue
        for index, word in enumerate(words):
            if word == "-O":
                flags.append(words[index + 1])
            elif word.startswith("-O"):
                flags.append(word[2:])
    return flags


@pytest.mark.parametrize("profile", list(ZIG_MODE))
def test_cli_build_selects_the_zig_mode_for_each_profile(tmp_path, zig, profile):
    source = tmp_path / "hello.a7"
    source.write_text(HELLO)
    env, log = recording_zig(tmp_path, zig)
    output = tmp_path / "hello"
    built = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "build", str(source), "-o", str(output), "--profile", profile],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120,
    )
    assert built.returncode == 0, built.stderr + built.stdout
    assert optimize_flags(log) == [ZIG_MODE[profile]]
    native = subprocess.run([str(output)], capture_output=True, text=True, timeout=30)
    assert (native.returncode, native.stdout) == (0, "hi\n")


@pytest.mark.parametrize("profile", list(ZIG_MODE))
def test_example_build_script_selects_the_zig_mode_for_each_profile(tmp_path, zig, profile):
    examples_dir = tmp_path / "examples"
    examples_dir.mkdir()
    shutil.copy(ROOT / "examples" / "001_hello.a7", examples_dir / "001_hello.a7")
    env, log = recording_zig(tmp_path, zig)
    result = subprocess.run(
        [sys.executable, "scripts/build_examples.py", "--profile", profile, "--backend", "zig",
         "--examples-dir", str(examples_dir), "--out-dir", str(tmp_path / "build"), "--clean"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert optimize_flags(log) == [ZIG_MODE[profile]]


def test_unknown_profile_is_rejected_not_built_as_debug(tmp_path):
    result = compile_program(HELLO, tmp_path, profile="turbo")
    assert result.exit_code == 7, failure_text(result)
    assert "unknown build profile 'turbo'" in failure_text(result)
    cli = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "build", "hello.a7", "--profile", "turbo"],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    assert cli.returncode == 2
    assert "invalid choice: 'turbo'" in cli.stderr


PROVEN_LOOP = """
io :: import "std/io"
Node :: struct { value: i32 }
main :: fn() {
    total := 0
    for i := 0; i < 10; i += 1 {
        total = i
    }
    node := new Node
    if node == nil { ret }
    io.println("{} {}", total, node.value)
    del node
}
"""


def emitted(tmp_path, profile: str) -> str:
    result = expect_ok(PROVEN_LOOP, tmp_path, profile=profile)
    return Path(result.output_path).read_text()


def test_release_and_fast_share_the_nonwrap_lowering_and_allocator(tmp_path):
    # L49: a proven `i += 1` lowers to the plain operator outside debug.
    debug = emitted(tmp_path, "debug")
    assert "i +%= 1" in debug and "std.heap.page_allocator" in debug
    release = emitted(tmp_path, "release")
    assert "i += 1" in release and "i +%= 1" not in release
    assert "std.heap.smp_allocator" in release
    assert emitted(tmp_path, "fast") == release


@pytest.mark.parametrize("command", [("--help",), ("build", "--help"), ("run", "--help")])
def test_help_describes_each_profile_on_one_line(tmp_path, command):
    result = subprocess.run([sys.executable, str(ROOT / "main.py"), *command],
                            cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0
    lines = [line.strip() for line in result.stdout.splitlines()]
    for profile, mode in ZIG_MODE.items():
        described = [line for line in lines if line.startswith(f"{profile} ") and f"Zig {mode}" in line]
        assert len(described) == 1, result.stdout
