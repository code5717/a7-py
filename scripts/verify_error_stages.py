#!/usr/bin/env python3
"""Verify compiler error handling across stages, modes, and output formats."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from error_stage_common import (
    ALL_MODES,
    AuditResult,
    audit_payload,
    build_stage_sources,
    run_audit_with_sources,
)


def run_audit(selected_modes: list[str], selected_formats: list[str]) -> list[AuditResult]:
    with tempfile.TemporaryDirectory(prefix="a7-stage-audit-") as tmp:
        tmp_dir = Path(tmp)
        sources = build_stage_sources(tmp_dir)
        return run_audit_with_sources(
            sources=sources,
            tmp_dir=tmp_dir,
            selected_modes=selected_modes,
            selected_formats=selected_formats,
        )


def print_summary(results: list[AuditResult]) -> None:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    print(f"Error-stage audit: {passed}/{total} checks passed")

    failures = [r for r in results if not r.passed]
    if failures:
        print("\nFailures:")
        for item in failures:
            label = f"{item.scenario} [{item.mode}/{item.output_format}]"
            print(f"- {label}: {item.detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify compiler error handling across stages")
    parser.add_argument(
        "--format",
        choices=["human", "json", "both"],
        default="both",
        help="Output format(s) to validate",
    )
    parser.add_argument(
        "--mode-set",
        choices=["all", "compile-only"],
        default="all",
        help="Modes to include in the audit",
    )
    parser.add_argument(
        "--json-report",
        default="",
        help="Optional path to write JSON report",
    )
    args = parser.parse_args()

    selected_formats = ["human", "json"] if args.format == "both" else [args.format]
    selected_modes = ALL_MODES if args.mode_set == "all" else ["compile"]

    results = run_audit(selected_modes=selected_modes, selected_formats=selected_formats)
    print_summary(results)

    if args.json_report:
        payload = audit_payload(results)
        report_path = Path(args.json_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
