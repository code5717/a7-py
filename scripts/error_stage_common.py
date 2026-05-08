#!/usr/bin/env python3
"""Shared CLI error-stage audit helpers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = ROOT / "main.py"

ALL_MODES = ["compile", "tokens", "ast", "semantic", "pipeline", "doc"]
PARSE_MODES = ["compile", "ast", "semantic", "pipeline", "doc"]
SEMANTIC_MODES = ["compile", "semantic", "pipeline", "doc"]
CODEGEN_MODES = ["compile", "pipeline", "doc"]
FORMATS = ["human", "json"]


@dataclass
class AuditResult:
    scenario: str
    mode: str
    output_format: str
    passed: bool
    detail: str = ""


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{ROOT}:{existing_pythonpath}" if existing_pythonpath else str(ROOT)
    return subprocess.run(
        [sys.executable, str(MAIN_PY), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


def parse_json(stdout: str) -> tuple[bool, dict, str]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return False, {}, f"invalid JSON output: {exc}"
    return True, payload, ""


def ensure(cond: bool, msg: str) -> tuple[bool, str]:
    if cond:
        return True, ""
    return False, msg


def verify_error_common(
    proc: subprocess.CompletedProcess[str],
    *,
    expected_exit: int,
    output_format: str,
    expected_category: Optional[str] = None,
    must_contain: Optional[list[str]] = None,
    must_not_have_output_artifact: bool = False,
) -> tuple[bool, str]:
    if proc.returncode != expected_exit:
        return False, f"expected exit {expected_exit}, got {proc.returncode}"

    if output_format == "human":
        combined = (proc.stdout + proc.stderr).lower()
        for needle in (must_contain or []):
            if needle.lower() not in combined:
                return False, f"missing human text: '{needle}'"
        return True, ""

    ok, payload, err = parse_json(proc.stdout)
    if not ok:
        return False, err

    checks = [
        ensure(payload.get("schema_version") == "2.0", "schema_version != 2.0"),
        ensure(payload.get("status") == "error", "status != error"),
    ]
    for passed, message in checks:
        if not passed:
            return False, message

    if expected_category is not None:
        got_category = payload.get("error", {}).get("category")
        if got_category != expected_category:
            return False, f"expected category {expected_category}, got {got_category}"

    if must_not_have_output_artifact:
        artifacts = payload.get("artifacts", {})
        if "output_path" in artifacts:
            return False, "unexpected artifacts.output_path for failing compilation"

    details = payload.get("error", {}).get("details", [])
    if not details:
        return False, "missing error.details"
    first_detail = details[0]
    if "type" not in first_detail or "message" not in first_detail or "file" not in first_detail:
        return False, "error.details[0] missing type/message/file"

    return True, ""


def verify_success_common(
    proc: subprocess.CompletedProcess[str],
    *,
    output_format: str,
) -> tuple[bool, str]:
    if proc.returncode != 0:
        return False, f"expected success exit 0, got {proc.returncode}"

    if output_format == "json":
        ok, payload, err = parse_json(proc.stdout)
        if not ok:
            return False, err
        if payload.get("status") != "ok":
            return False, "status != ok"

    return True, ""


def build_stage_sources(tmp_dir: Path) -> dict[str, Path]:
    tokenize_error = tmp_dir / "tokenize_error.a7"
    tokenize_error.write_text(
        'io :: import "std/io"\nmain :: fn() {\n    io.println("Hello, World!)\n}\n',
        encoding="utf-8",
    )

    parse_error = tmp_dir / "parse_error.a7"
    parse_error.write_text(
        "main :: fn() {\n    x := (\n}\n",
        encoding="utf-8",
    )

    semantic_error = tmp_dir / "semantic_error.a7"
    semantic_error.write_text(
        'main :: fn() {\n    x: i32 = "hello"\n}\n',
        encoding="utf-8",
    )

    deferred_semantic_error = tmp_dir / "deferred_semantic_error.a7"
    deferred_semantic_error.write_text(
        "main :: fn() {\n    x: i32 = 1\n    defer del x\n}\n",
        encoding="utf-8",
    )

    ok_program = tmp_dir / "ok.a7"
    ok_program.write_text("main :: fn() {}\n", encoding="utf-8")

    return {
        "tokenize": tokenize_error,
        "parse": parse_error,
        "semantic": semantic_error,
        "deferred_semantic": deferred_semantic_error,
        "ok": ok_program,
    }


def run_audit_with_sources(
    *,
    sources: dict[str, Path],
    tmp_dir: Path,
    selected_modes: list[str],
    selected_formats: list[str],
) -> list[AuditResult]:
    results: list[AuditResult] = []

    for output_format in selected_formats:
        fmt_args = ["--format", "json"] if output_format == "json" else []

        for mode in selected_modes:
            proc = run_cli(["--mode", mode, *fmt_args, str(sources["tokenize"])])
            passed, detail = verify_error_common(
                proc,
                expected_exit=4,
                output_format=output_format,
                expected_category="tokenize" if output_format == "json" else None,
                must_contain=["string is not closed", "hint"] if output_format == "human" else None,
                must_not_have_output_artifact=(mode == "compile" and output_format == "json"),
            )
            results.append(AuditResult("tokenize_error", mode, output_format, passed, detail))

        for mode in selected_modes:
            if mode not in PARSE_MODES:
                continue
            proc = run_cli(["--mode", mode, *fmt_args, str(sources["parse"])])
            passed, detail = verify_error_common(
                proc,
                expected_exit=5,
                output_format=output_format,
                expected_category="parse" if output_format == "json" else None,
                must_contain=["expected expression"] if output_format == "human" else None,
                must_not_have_output_artifact=(mode == "compile" and output_format == "json"),
            )
            results.append(AuditResult("parse_error", mode, output_format, passed, detail))

        if "tokens" in selected_modes:
            proc = run_cli(["--mode", "tokens", *fmt_args, str(sources["parse"])])
            passed, detail = verify_success_common(proc, output_format=output_format)
            results.append(AuditResult("tokens_mode_skips_parse", "tokens", output_format, passed, detail))

        for mode in selected_modes:
            if mode not in SEMANTIC_MODES:
                continue
            proc = run_cli(["--mode", mode, *fmt_args, str(sources["semantic"])])
            passed, detail = verify_error_common(
                proc,
                expected_exit=6,
                output_format=output_format,
                expected_category="semantic" if output_format == "json" else None,
                must_contain=["type mismatch", "hint"] if output_format == "human" else None,
                must_not_have_output_artifact=(mode == "compile" and output_format == "json"),
            )
            results.append(AuditResult("semantic_error", mode, output_format, passed, detail))

        for mode in selected_modes:
            if mode not in SEMANTIC_MODES:
                continue
            proc = run_cli(["--mode", mode, *fmt_args, str(sources["deferred_semantic"])])
            passed, detail = verify_error_common(
                proc,
                expected_exit=6,
                output_format=output_format,
                expected_category="semantic" if output_format == "json" else None,
                must_contain=["reference"] if output_format == "human" else None,
                must_not_have_output_artifact=(mode == "compile" and output_format == "json"),
            )
            results.append(AuditResult("deferred_semantic_error", mode, output_format, passed, detail))

        if "ast" in selected_modes:
            proc = run_cli(["--mode", "ast", *fmt_args, str(sources["semantic"])])
            passed, detail = verify_success_common(proc, output_format=output_format)
            results.append(AuditResult("ast_mode_skips_semantic", "ast", output_format, passed, detail))

        for mode in selected_modes:
            if mode not in CODEGEN_MODES:
                continue
            proc = run_cli(["--mode", mode, "--backend", "nope", *fmt_args, str(sources["ok"])])
            passed, detail = verify_error_common(
                proc,
                expected_exit=7,
                output_format=output_format,
                expected_category="codegen" if output_format == "json" else None,
                must_contain=["unknown backend"] if output_format == "human" else None,
                must_not_have_output_artifact=(mode == "compile" and output_format == "json"),
            )
            if passed and output_format == "human":
                combined = (proc.stdout + proc.stderr).lower()
                if combined.count("unknown backend") != 1:
                    passed = False
                    detail = "expected single codegen error line in human output"
            results.append(AuditResult("codegen_error", mode, output_format, passed, detail))

        missing = tmp_dir / "missing_file.a7"
        for mode in selected_modes:
            proc = run_cli(["--mode", mode, *fmt_args, str(missing)])
            passed, detail = verify_error_common(
                proc,
                expected_exit=3,
                output_format=output_format,
                expected_category="io" if output_format == "json" else None,
                must_contain=["input file not found"] if output_format == "human" else None,
            )
            results.append(AuditResult("io_error", mode, output_format, passed, detail))

    usage_proc = run_cli(["--mode", "tokens", "--output", str(tmp_dir / "out.zig"), str(sources["ok"])])
    passed = usage_proc.returncode == 2 and "--output is only valid" in usage_proc.stderr
    detail = "" if passed else "usage contract failed for --output with non-compile mode"
    results.append(AuditResult("usage_error", "n/a", "human", passed, detail))

    return results


def audit_payload(results: list[AuditResult]) -> dict[str, object]:
    return {
        "ok": all(r.passed for r in results),
        "passed": sum(1 for r in results if r.passed),
        "total": len(results),
        "results": [asdict(r) for r in results],
    }
