#!/usr/bin/env python3
"""Shared end-to-end verifier for A7 example programs."""

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional


ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = ROOT / "main.py"


@dataclass(frozen=True)
class BackendConfig:
    name: str
    generated_suffix: str
    temp_prefix: str
    validation_field: str
    validation_error_label: str
    summary_label: str
    compile_args: Callable[[Path, Path], list[str]]
    validation_args: Callable[[Path, Path, Path], list[str]]
    build_args: Callable[[Path, Path, Path], list[str]]


@dataclass
class ExampleResult:
    name: str
    compile_ok: bool = False
    ast_ok: bool = False
    syntax_ok: bool = False
    build_ok: bool = False
    run_ok: bool = False
    output_match: bool = False
    output_path: Optional[str] = None
    error: str = ""
    diff: str = ""

    def ok(self, validation_field: str) -> bool:
        return (
            self.compile_ok
            and bool(getattr(self, validation_field))
            and self.build_ok
            and self.run_ok
            and self.output_match
        )


def run_cmd(cmd: list[str], *, cwd: Path, timeout: Optional[float] = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def normalize_output(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    if lines and lines[-1] == "":
        lines = lines[:-1]
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def first_error_text(proc: subprocess.CompletedProcess[str]) -> str:
    output = (proc.stderr or proc.stdout or "").strip()
    if not output:
        return "command failed without output"
    lines = output.splitlines()
    return "\n".join(lines[:10])


def verify_example(
    example: Path,
    fixtures_dir: Path,
    build_dir: Path,
    timeout: float,
    update_golden: bool,
    backend: BackendConfig,
) -> ExampleResult:
    result = ExampleResult(name=example.stem)

    generated_out = build_dir / f"{example.stem}{backend.generated_suffix}"
    intermediate_out = build_dir / f"{example.stem}.o"
    bin_out = build_dir / example.stem

    compile_proc = run_cmd(backend.compile_args(example, generated_out), cwd=ROOT)
    if compile_proc.returncode != 0:
        result.error = f"compile failed:\n{first_error_text(compile_proc)}"
        return result
    result.compile_ok = True

    validation_proc = run_cmd(
        backend.validation_args(generated_out, intermediate_out, bin_out),
        cwd=ROOT,
    )
    if validation_proc.returncode != 0:
        result.error = f"{backend.validation_error_label} failed:\n{first_error_text(validation_proc)}"
        return result
    setattr(result, backend.validation_field, True)

    build_proc = run_cmd(
        backend.build_args(generated_out, intermediate_out, bin_out),
        cwd=ROOT,
    )
    if build_proc.returncode != 0:
        result.error = f"{backend.name} build failed:\n{first_error_text(build_proc)}"
        return result
    result.build_ok = True

    try:
        run_proc = subprocess.run(
            [str(bin_out)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        result.error = f"binary timed out after {timeout:.1f}s"
        return result

    if run_proc.returncode != 0:
        captured = (run_proc.stdout or "").strip()
        if captured:
            captured = "\n".join(captured.splitlines()[:10])
        else:
            captured = f"exit code {run_proc.returncode}"
        result.error = f"binary exited non-zero:\n{captured}"
        return result

    result.run_ok = True

    actual = normalize_output(run_proc.stdout or "")
    fixture_path = fixtures_dir / f"{example.stem}.out"
    result.output_path = str(fixture_path)

    if update_golden or not fixture_path.exists():
        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        fixture_path.write_text(actual, encoding="utf-8")
        result.output_match = True
        return result

    expected = fixture_path.read_text(encoding="utf-8")
    if actual == expected:
        result.output_match = True
        return result

    result.error = "runtime output mismatch"
    result.diff = "".join(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=f"expected/{fixture_path.name}",
            tofile=f"actual/{fixture_path.name}",
            n=3,
        )
    )
    return result


def find_examples(examples_dir: Path) -> list[Path]:
    return sorted(path for path in examples_dir.glob("*.a7") if path.is_file())


def summarize(results: list[ExampleResult], backend: BackendConfig) -> tuple[int, int]:
    total = len(results)
    passed = sum(1 for r in results if r.ok(backend.validation_field))
    print(f"{backend.summary_label}: {passed}/{total}")

    failed = [r for r in results if not r.ok(backend.validation_field)]
    if failed:
        print("\nFailures:")
        for item in failed:
            print(f"- {item.name}: {item.error}")
            if item.diff:
                print(item.diff)

    return passed, total


def report_payload(results: list[ExampleResult], backend: BackendConfig, passed: int, total: int) -> dict[str, object]:
    result_items = []
    unused_validation_field = "syntax_ok" if backend.validation_field == "ast_ok" else "ast_ok"
    for result in results:
        item = asdict(result)
        item.pop(unused_validation_field, None)
        result_items.append(item)

    return {
        "passed": passed,
        "total": total,
        "ok": passed == total,
        "results": result_items,
    }


def main_for_backend(backend: BackendConfig) -> int:
    parser = argparse.ArgumentParser(description=f"Verify examples end-to-end ({backend.name})")
    parser.add_argument(
        "--examples-dir",
        default=str(ROOT / "examples"),
        help="Directory containing .a7 examples",
    )
    parser.add_argument(
        "--fixtures-dir",
        default=str(ROOT / "test" / "fixtures" / "golden_outputs"),
        help="Directory containing expected outputs",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Per-binary runtime timeout in seconds",
    )
    parser.add_argument(
        "--update-golden",
        action="store_true",
        help="Write current outputs into golden fixtures",
    )
    parser.add_argument(
        "--json-report",
        default="",
        help="Optional path to write a JSON report",
    )

    args = parser.parse_args()

    examples_dir = Path(args.examples_dir).resolve()
    fixtures_dir = Path(args.fixtures_dir).resolve()

    examples = find_examples(examples_dir)
    if not examples:
        print(f"No examples found in {examples_dir}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix=backend.temp_prefix) as tmp:
        build_dir = Path(tmp)
        results = [
            verify_example(
                example=example,
                fixtures_dir=fixtures_dir,
                build_dir=build_dir,
                timeout=args.timeout,
                update_golden=args.update_golden,
                backend=backend,
            )
            for example in examples
        ]

    passed, total = summarize(results, backend)

    if args.json_report:
        payload = report_payload(results, backend, passed, total)
        report_path = Path(args.json_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return 0 if passed == total else 1
