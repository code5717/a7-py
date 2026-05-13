#!/usr/bin/env python3
"""Single source for small project status facts used by docs and release checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def project_status() -> dict[str, object]:
    examples = sorted((ROOT / "examples").glob("*.a7"))
    goldens = sorted((ROOT / "test" / "fixtures" / "golden_outputs").glob("*.out"))
    return {
        "example_count": len(examples),
        "golden_output_count": len(goldens),
        "backend": "zig",
        "zig_version": "0.16.0",
        "release_archive_prefix": "a7-example-artifacts-linux-x86_64-zig0.16.0",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Print A7 project status facts")
    parser.add_argument("--field", choices=sorted(project_status().keys()))
    args = parser.parse_args()

    status = project_status()
    if args.field:
        print(status[args.field])
    else:
        print(json.dumps(status, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
