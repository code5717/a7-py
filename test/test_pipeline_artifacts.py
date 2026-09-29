"""CLI artifact provenance and input preservation, using disposable real files.

These are required behavior tests. Known failures deliberately remain visible.
No compiler, filesystem, or subprocess boundary is mocked.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from a7.compile import ExitCode

ROOT = Path(__file__).resolve().parents[1]


def cli(source, *args):
    process = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(source), "--format", "json", *map(str, args)],
        cwd=ROOT, capture_output=True, text=True,
    )
    return process, json.loads(process.stdout)


@pytest.mark.parametrize("option", ["--output", "--doc-out"])
def test_cli_rejects_input_destination_without_changing_source(tmp_path, option):
    source = tmp_path / "main.a7"
    original = b"// Preserve this comment too.\nmain :: fn() {}\n"
    source.write_bytes(original)
    process, payload = cli(source, option, source)
    assert source.read_bytes() == original, f"{option} destroyed the A7 input"
    assert process.returncode != ExitCode.SUCCESS
    assert payload["status"] == "error"
    assert not payload["artifacts"]


def test_failed_compile_does_not_advertise_stale_output(tmp_path):
    source = tmp_path / "main.a7"
    source.write_text("main :: fn( {", encoding="utf-8")
    output = tmp_path / "main.zig"
    previous = b"// Previous successful build, not produced by this invocation.\n"
    output.write_bytes(previous)
    process, payload = cli(source, "--output", output)
    assert process.returncode == ExitCode.PARSE
    assert output.read_bytes() == previous
    assert "output_path" not in payload["artifacts"], payload["artifacts"]


def test_output_write_failure_does_not_advertise_directory_as_artifact(tmp_path):
    source = tmp_path / "main.a7"
    source.write_text("main :: fn() {}\n", encoding="utf-8")
    output = tmp_path / "destination.zig"
    output.mkdir()
    sentinel = output / "keep"
    sentinel.write_bytes(b"keep")
    process, payload = cli(source, "--output", output)
    assert process.returncode == ExitCode.IO
    assert sentinel.read_bytes() == b"keep"
    assert "output_path" not in payload["artifacts"], payload["artifacts"]


def test_success_reports_real_output_and_preserves_all_inputs(tmp_path):
    source = tmp_path / "main.a7"
    helper = tmp_path / "helper.a7"
    inputs = {
        source: b'helper :: import "helper"\nmain :: fn() { helper.work() }\n',
        helper: b'// Original module text.\npub work :: fn() {}\n',
    }
    for path, content in inputs.items():
        path.write_bytes(content)
    output = tmp_path / "build" / "main.zig"
    doc = tmp_path / "build" / "main.md"
    process, payload = cli(source, "--output", output, "--doc-out", doc)
    assert process.returncode == ExitCode.SUCCESS, process.stdout + process.stderr
    assert Path(payload["artifacts"]["output_path"]) == output
    assert Path(payload["artifacts"]["doc_path"]) == doc
    assert output.is_file() and output.stat().st_size > 0
    assert doc.is_file() and doc.stat().st_size > 0
    for path, content in inputs.items():
        assert path.read_bytes() == content


@pytest.mark.parametrize("alias_kind", ["symlink", "hardlink", "imported-module", "transitive-module"])
def test_output_cannot_overwrite_an_input_alias(tmp_path, alias_kind):
    source = tmp_path / "main.a7"
    helper = tmp_path / "helper.a7"
    source.write_text('helper :: import "helper"\nmain :: fn() { helper.work() }\n')
    helper.write_text('pub work :: fn() {}\n')
    output = tmp_path / "destination.zig"
    if alias_kind == "symlink":
        output.symlink_to(source)
    elif alias_kind == "hardlink":
        output.hardlink_to(source)
    elif alias_kind == "imported-module":
        output = helper
    else:
        output = tmp_path / "leaf.a7"
        output.write_text("pub leaf :: fn() {}\n")
        helper.write_text('leaf :: import "leaf"\npub work :: fn() {}\n')
    inputs = [source, helper] + ([output] if alias_kind == "transitive-module" else [])
    before = {path: path.read_bytes() for path in inputs}
    process, payload = cli(source, "--output", output)
    assert process.returncode == ExitCode.IO
    assert not payload["artifacts"]
    assert {path: path.read_bytes() for path in before} == before


def test_codegen_and_documentation_destinations_must_differ(tmp_path):
    source = tmp_path / "main.a7"
    source.write_text("main :: fn() {}\n")
    output = tmp_path / "combined.out"
    process, payload = cli(source, "--output", output, "--doc-out", output)
    assert process.returncode == ExitCode.IO
    assert not payload["artifacts"]
    assert not output.exists()
