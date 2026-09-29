"""Observe CLI and import defects using only disposable temporary inputs.

Run from the repository root with:
    uv run python docs/audits/2026-09-14/repros/language_contract.py

This records behavior without asserting that the defects must remain present.
"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))


def compile_file(source, *arguments):
    process = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(source), *arguments, "--format", "json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return process.returncode, json.loads(process.stdout)


observations = {}
with tempfile.TemporaryDirectory(prefix="a7-language-contract-") as directory:
    work = Path(directory)
    source = work / "demo.a7"
    original = "main :: fn() {}\n"
    source.write_text(original)
    code, payload = compile_file(source, "-o", str(source))
    observations["output_overwrites_source"] = {
        "exit_code": code,
        "source_changed": source.read_text() != original,
        "first_line": source.read_text().splitlines()[0],
    }

    source.write_text(original)
    code, payload = compile_file(source, "--doc-out", str(source))
    observations["documentation_overwrites_source"] = {
        "exit_code": code,
        "source_changed": source.read_text() != original,
        "is_markdown_report": source.read_text().startswith("# Compilation Report:"),
    }

    output = work / "demo.zig"
    output.write_text("old artifact")
    source.write_text("main :: fn( {")
    code, payload = compile_file(source, "-o", str(output))
    observations["failed_compile_reports_old_artifact"] = {
        "exit_code": code,
        "reports_output_artifact": "output_path" in payload["artifacts"],
        "old_file_unchanged": output.read_text() == "old artifact",
    }

    (work / "main.a7").write_text('a :: import "a"\nmain :: fn() { a.work() }\n')
    (work / "a.a7").write_text('b :: import "b"\npub work :: fn() {}\n')
    (work / "b.a7").write_text('a :: import "a"\npub other :: fn() {}\n')
    code, payload = compile_file(work / "main.a7")
    from a7.module_resolver import ModuleResolver

    resolver = ModuleResolver([str(work)])
    resolver.load_module("a")
    observations["cyclic_imports"] = {
        "cli_exit_code": code,
        "cli_error": payload.get("error"),
        "resolver_loaded_modules": sorted(resolver.loaded_modules),
    }
    try:
        resolver.topological_sort()
    except Exception as error:
        observations["cyclic_imports"]["topological_sort_error"] = str(error)

print(json.dumps(observations, indent=2, sort_keys=True))
