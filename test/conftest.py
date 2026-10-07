"""Shared test helpers. Import is cheap; heavy imports stay lazy inside helpers."""

from __future__ import annotations

import os
import shutil

import pytest


# A test body sits 31 frames deep under serial pytest, so the historical
# "recursion limit 100" left 69 frames for the compiler. Under pytest-xdist the
# body sits deeper; a fixed 100 would then measure the runner, not the compiler.
LOW_RECURSION_HEADROOM = 69


def low_recursion_limit() -> int:
    """Recursion limit that leaves LOW_RECURSION_HEADROOM frames below the caller."""
    import sys

    depth = 0
    frame = sys._getframe(1)
    while frame is not None:
        depth += 1
        frame = frame.f_back
    return depth + LOW_RECURSION_HEADROOM


def has_zig() -> bool:
    override = os.environ.get("A7_TEST_ZIG")
    if override:
        return True
    return shutil.which("zig") is not None


def zig_binary() -> str:
    override = os.environ.get("A7_TEST_ZIG")
    if override:
        return override
    found = shutil.which("zig")
    assert found is not None, "zig not found on PATH (set A7_TEST_ZIG to override)"
    return found


def zig_version(binary: str) -> str:
    import subprocess

    result = subprocess.run(
        [binary, "version"], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return result.stdout.strip()


@pytest.fixture(scope="session")
def zig() -> str:
    binary = zig_binary()
    assert zig_version(binary) == "0.16.0", f"expected zig 0.16.0, got {zig_version(binary)}"
    return binary


_ZIG_CACHE_ENV = "A7_TEST_ZIG_CACHE"


def shared_zig_cache():
    """One Zig cache root for the whole run, shared by pytest-xdist workers.

    The first process to ask creates the directory and exports its path, so
    workers spawned afterwards inherit it. Zig locks its cache, so concurrent
    builds are safe. A fresh global cache per test rebuilt Zig's runtime
    libraries every time and filled /tmp with about 20 GB.
    """
    import atexit
    import tempfile
    from pathlib import Path

    root = os.environ.get(_ZIG_CACHE_ENV)
    if root is None:
        root = tempfile.mkdtemp(prefix="a7-test-zig-cache-")
        os.environ[_ZIG_CACHE_ENV] = root
        atexit.register(shutil.rmtree, root, ignore_errors=True)
    path = Path(root)
    (path / "local").mkdir(exist_ok=True)
    (path / "global").mkdir(exist_ok=True)
    return path


def pytest_configure(config):
    # Create the cache in the controller so every xdist worker inherits it.
    shared_zig_cache()


# Native tests that reach Zig through the CLI or a script, not the fixture.
_NATIVE_WITHOUT_FIXTURE = (
    "test_examples_e2e.py::",
    "test_cli_workflows.py::test_native_",
    "test_audit_safety_repairs.py::test_guarded_mutation_and_bounded_loop_run",
    "test_release_tooling.py::test_wheel_install_smoke_uses_built_artifact",
)
_SLOW = ("test_error_stage_matrix.py::test_shared_audit_matrix_matches_pytest_matrix",)


def pytest_collection_modifyitems(items):
    # Fast loop: `pytest -m "not zig and not slow"`.
    for item in items:
        if "zig" in getattr(item, "fixturenames", ()) or any(
            part in item.nodeid for part in _NATIVE_WITHOUT_FIXTURE
        ):
            item.add_marker(pytest.mark.zig)
        if any(part in item.nodeid for part in _SLOW):
            item.add_marker(pytest.mark.slow)


@pytest.fixture(scope="session")
def zig_cache():
    return shared_zig_cache()


def parse_program(source: str):
    from a7.parser import Parser
    from a7.tokens import Tokenizer

    tokenizer = Tokenizer(source)
    tokens = tokenizer.tokenize()
    return Parser(tokens).parse()


def run_semantic_analysis(source: str, filename: str = "test.a7"):
    from a7.passes.name_resolution import NameResolutionPass
    from a7.passes.semantic_validator import SemanticValidationPass
    from a7.passes.type_checker import TypeCheckingPass

    program = parse_program(source)
    resolver = NameResolutionPass()
    symbols = resolver.analyze(program, filename)
    checker = TypeCheckingPass(symbols)
    checker.analyze(program, filename)
    validator = SemanticValidationPass(symbols, checker.node_types)
    validator.analyze(program, filename)
    return {
        "program": program,
        "symbols": symbols,
        "resolver_errors": list(resolver.errors),
        "checker_errors": list(checker.errors),
        "validator_errors": list(validator.errors),
    }


# ---------------------------------------------------------------------------
# Real-pipeline helpers
#
# These run the same entry point as the CLI (tokenize, parse, every semantic
# pass, the safety pass, codegen). Tests that call individual passes by hand
# skip the safety pass and codegen, so they pass on programs the compiler
# rejects.
# ---------------------------------------------------------------------------

# `release` keeps Zig's runtime checks; `fast` drops them (ledger L64).
ZIG_MODE = {"debug": "Debug", "release": "ReleaseSafe", "fast": "ReleaseFast"}


def compile_program(source: str, tmp_path, *, profile: str = "debug",
                    is_library: bool = False, name: str = "main"):
    """Compile `source` through the full pipeline. Returns CompilationResult."""
    from a7.compile import A7Compiler

    src = tmp_path / f"{name}.a7"
    src.write_text(source, encoding="utf-8")
    compiler = A7Compiler(build_profile=profile, is_library=is_library)
    return compiler.compile_file_detailed(str(src), str(tmp_path / f"{name}-{profile}.zig"))


def failure_text(result) -> str:
    """Every message of a failed compilation, joined for substring checks."""
    if result.failure is None:
        return ""
    parts = [result.failure.message]
    parts.extend(str(detail.get("message", "")) for detail in result.failure.details)
    return "\n".join(parts)


def expect_ok(source: str, tmp_path, **options):
    result = compile_program(source, tmp_path, **options)
    assert result.ok, f"exit {result.exit_code}: {failure_text(result)}"
    return result


def expect_exit(source: str, tmp_path, code: int, fragment: str, **options):
    """The compiler must exit `code` and name `fragment` in its diagnostics."""
    assert fragment, "expect_exit needs a message fragment; any error would pass"
    result = compile_program(source, tmp_path, **options)
    text = failure_text(result)
    assert result.exit_code == code, f"exit {result.exit_code}, wanted {code}: {text}"
    assert fragment.lower() in text.lower(), f"{fragment!r} not in: {text}"
    return result


def build_and_run(source: str, tmp_path, zig: str, *, profile: str = "debug",
                  stdin: str = "", timeout: int = 120):
    """Compile, build with Zig, run the binary. Returns the CompletedProcess.

    Take the `zig` fixture so the pinned toolchain is asserted and the test is
    marked native. `zig ast-check` is not a build check: it accepts programs
    that `zig build-exe` rejects.
    """
    import subprocess

    result = expect_ok(source, tmp_path, profile=profile)
    cache = shared_zig_cache()
    binary = tmp_path / f"program-{profile}"
    build = subprocess.run(
        [zig, "build-exe", result.output_path, "-O", ZIG_MODE[profile],
         "--cache-dir", str(cache / "local"),
         "--global-cache-dir", str(cache / "global"),
         "-femit-bin=" + str(binary)],
        capture_output=True, text=True, timeout=timeout,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    return subprocess.run([str(binary)], input=stdin, capture_output=True,
                          text=True, timeout=timeout)


def _run_profiles(profiles, source: str, tmp_path, zig: str, **options) -> str:
    outputs = {}
    for profile in profiles:
        process = build_and_run(source, tmp_path, zig, profile=profile, **options)
        assert process.returncode == 0, f"{profile}: {process.stderr}"
        outputs[profile] = process.stdout
    assert len(set(outputs.values())) == 1, outputs
    return outputs[profiles[0]]


def run_both_profiles(source: str, tmp_path, zig: str, **options) -> str:
    """Build and run checked (debug) and unchecked (fast); stdout must agree.

    These two differ most: a wrong proof or an undefined operation traps in
    debug and silently misbehaves in fast.
    """
    return _run_profiles(("debug", "fast"), source, tmp_path, zig, **options)


def run_all_profiles(source: str, tmp_path, zig: str, **options) -> str:
    """Build and run debug, release and fast; stdout must agree."""
    return _run_profiles(("debug", "release", "fast"), source, tmp_path, zig, **options)
