"""Release checks must reject missing files and unknown registry shapes."""

import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_script(relative):
    name = Path(relative).stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("iterator,target", [
    ('("sqrt", "abs")', 'name'),
    ('["sqrt", "abs"]', 'name'),
    ('functions.items()', 'name, builtin'),
])
def test_coverage_reads_supported_registration_loops(tmp_path, monkeypatch, iterator, target):
    checker = load_script("site/scripts/check-coverage.py")
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    stdlib = tmp_path / "a7" / "stdlib"
    stdlib.mkdir(parents=True)
    (stdlib / "__init__.py").write_text(
        "def _register_defaults(self):\n"
        "    from .math import register_math_module\n"
        "    register_math_module(self)\n"
    )
    (stdlib / "math.py").write_text(
        "def register_math_module(registry):\n"
        "    module = StdlibModule(name='math')\n"
        "    functions = {'sqrt': '@sqrt', 'abs': '@abs'}\n"
        f"    for {target} in {iterator}:\n"
        "        module.functions[name] = StdlibFunction()\n"
    )
    assert checker.stdlib_operations() == ["std.math.sqrt", "std.math.abs"]


@pytest.mark.parametrize("iterator", ['get_names()', '("sqrt", dynamic_name)'])
def test_coverage_rejects_registration_names_it_cannot_extract(tmp_path, monkeypatch, iterator):
    checker = load_script("site/scripts/check-coverage.py")
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    stdlib = tmp_path / "a7" / "stdlib"
    stdlib.mkdir(parents=True)
    (stdlib / "__init__.py").write_text(
        "def _register_defaults(self):\n"
        "    from .math import register_math_module\n"
        "    register_math_module(self)\n"
    )
    (stdlib / "math.py").write_text(
        "def register_math_module(registry):\n"
        "    module = StdlibModule(name='math')\n"
        f"    for name in {iterator}:\n"
        "        module.functions[name] = StdlibFunction()\n"
    )
    with pytest.raises(ValueError, match="registration loop"):
        checker.stdlib_operations()


@pytest.mark.parametrize("kind", [tarfile.DIRTYPE, tarfile.SYMTYPE, tarfile.LNKTYPE])
def test_archive_file_requirements_reject_other_member_types(tmp_path, kind):
    path = tmp_path / "docs.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        target = tarfile.TarInfo("dist/target")
        target.size = 4
        archive.addfile(target, io.BytesIO(b"docs"))
        entry = tarfile.TarInfo("dist/llms.txt")
        entry.type = kind
        entry.linkname = "target"
        archive.addfile(entry)
    for requirement in (["--require", "dist/llms.txt"],
                        ["--require-glob-count", "dist/*.txt=1"]):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_archive_contents.py"),
             str(path), *requirement], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 1, result.stdout + result.stderr
        assert "archive content verification failed" in result.stderr


def test_archive_checks_unsafe_members_even_when_they_are_not_required(tmp_path):
    checker = load_script("scripts/verify_archive_contents.py")
    path = tmp_path / "unsafe.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        entry = tarfile.TarInfo("../escape")
        entry.type = tarfile.DIRTYPE
        archive.addfile(entry)
    with pytest.raises(ValueError, match="unsafe archive member"):
        checker.archive_members(path)


def test_mutation_check_requires_git_before_editing(tmp_path, monkeypatch, capsys):
    harness = load_script("scripts/mutation_harness.py")
    monkeypatch.setenv("PATH", str(tmp_path))
    assert harness.check_mutants(False) == 2
    assert "git is required" in capsys.readouterr().err


def test_mutation_check_rejects_failed_git_status(tmp_path, monkeypatch, capsys):
    harness = load_script("scripts/mutation_harness.py")
    monkeypatch.setattr(harness, "ROOT", tmp_path)
    assert harness.check_mutants(False) == 2
    assert "Cannot check the working tree" in capsys.readouterr().err


@pytest.fixture
def gate_uv_boundary(tmp_path, monkeypatch):
    """Capture the external uv command; real pytest and compiler checks are unverified."""
    calls = tmp_path / "uv-arguments"
    uv = tmp_path / "uv"
    uv.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$A7_TEST_UV_ARGUMENTS"\n')
    uv.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("A7_TEST_UV_ARGUMENTS", str(calls))
    monkeypatch.delenv("A7_PYTEST_WORKERS", raising=False)
    return calls


@pytest.mark.parametrize("workers", ["", "0", "9", "auto", "1.5", "-1"])
def test_gate_rejects_invalid_workers_before_checks(gate_uv_boundary, monkeypatch, workers):
    monkeypatch.setenv("A7_PYTEST_WORKERS", workers)
    result = subprocess.run(
        ["bash", str(ROOT / "run_all_tests.sh"), "--only", "pytest", "--timeout", "0"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "A7_PYTEST_WORKERS must be an integer from 1 to 8" in result.stderr
    assert not gate_uv_boundary.exists()
    assert "All Pytest Tests:" not in result.stdout


@pytest.mark.parametrize("workers,expected", [(None, "8"), ("2", "2"), ("1", "1")])
def test_gate_passes_worker_count_to_pytest(gate_uv_boundary, monkeypatch, workers, expected):
    if workers is not None:
        monkeypatch.setenv("A7_PYTEST_WORKERS", workers)
    result = subprocess.run(
        ["bash", str(ROOT / "run_all_tests.sh"), "--only", "pytest", "--timeout", "0"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert gate_uv_boundary.read_text().splitlines() == [
        "run", "pytest", "--tb=short", "-q", "-n", expected,
    ]
    assert "Summary: 1/1 checks passed" in result.stdout


def test_gate_only_filter_is_a_literal_substring(gate_uv_boundary):
    result = subprocess.run(
        ["bash", str(ROOT / "run_all_tests.sh"), "--only", "py?est", "--timeout", "0"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "error: no check ran; --only/--skip matched nothing to run" in result.stderr
    assert not gate_uv_boundary.exists()


def test_gate_skip_filter_does_not_expand_wildcards(gate_uv_boundary):
    result = subprocess.run(
        ["bash", str(ROOT / "run_all_tests.sh"), "--only", "PYTEST", "--skip", "*", "--timeout", "0"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Summary: 1/1 checks passed" in result.stdout
    assert gate_uv_boundary.read_text().splitlines()[:2] == ["run", "pytest"]
