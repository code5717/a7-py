#!/usr/bin/env python3
"""Build A7 examples as debug or release native binaries."""

from __future__ import annotations

import argparse
import difflib
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = ROOT / "main.py"

PROFILE_FLAGS = {
    "debug": {
        "zig": ["-ODebug"],
        "c": ["-O0", "-g"],
    },
    "release": {
        "zig": ["-OReleaseFast"],
        "c": ["-O3", "-DNDEBUG"],
    },
}


@dataclass
class BuildResult:
    example: str
    backend: str
    profile: str
    source_path: str
    binary_path: str
    compile_ok: bool = False
    syntax_ok: bool = False
    build_ok: bool = False
    run_ok: bool = False
    output_match: bool = False
    error: str = ""
    diff: str = ""

    @property
    def ok(self) -> bool:
        return (
            self.compile_ok
            and self.syntax_ok
            and self.build_ok
            and self.run_ok
            and self.output_match
        )


def run_cmd(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: Optional[float] = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def first_error_text(proc: subprocess.CompletedProcess[str]) -> str:
    output = (proc.stderr or proc.stdout or "").strip()
    if not output:
        return "command failed without output"
    return "\n".join(output.splitlines()[:10])


def normalize_output(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return "" if not lines else "\n".join(lines) + "\n"


def find_examples(examples_dir: Path) -> list[Path]:
    return sorted(path for path in examples_dir.glob("*.a7") if path.is_file())


def compile_source(example: Path, backend: str, source_path: Path) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(MAIN_PY), str(example), "--backend", backend, "-o", str(source_path)]
    return run_cmd(cmd, cwd=ROOT)


def build_zig(source_path: Path, binary_path: Path, profile: str) -> tuple[bool, str]:
    ast_check = run_cmd(["zig", "ast-check", str(source_path)], cwd=ROOT)
    if ast_check.returncode != 0:
        return False, f"zig ast-check failed:\n{first_error_text(ast_check)}"

    build = run_cmd(
        [
            "zig",
            "build-exe",
            str(source_path),
            *PROFILE_FLAGS[profile]["zig"],
            f"-femit-bin={binary_path}",
        ],
        cwd=ROOT,
    )
    if build.returncode != 0:
        return False, f"zig build-exe failed:\n{first_error_text(build)}"
    return True, ""


def build_c(source_path: Path, binary_path: Path, profile: str) -> tuple[bool, str]:
    object_path = binary_path.with_suffix(".o")
    syntax = run_cmd(
        ["zig", "cc", "-std=c11", "-c", str(source_path), "-o", str(object_path)],
        cwd=ROOT,
    )
    if syntax.returncode != 0:
        return False, f"zig cc syntax check failed:\n{first_error_text(syntax)}"

    build = run_cmd(
        [
            "zig",
            "cc",
            "-std=c11",
            str(source_path),
            "-lm",
            *PROFILE_FLAGS[profile]["c"],
            "-o",
            str(binary_path),
        ],
        cwd=ROOT,
    )
    if build.returncode != 0:
        return False, f"zig cc build failed:\n{first_error_text(build)}"
    return True, ""


def verify_runtime(
    binary_path: Path,
    fixture_path: Path,
    timeout: float,
) -> tuple[bool, str, str]:
    try:
        run = subprocess.run(
            [str(binary_path)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"binary timed out after {timeout:.1f}s", ""

    if run.returncode != 0:
        output = (run.stdout or "").strip()
        if output:
            output = "\n".join(output.splitlines()[:10])
        else:
            output = f"exit code {run.returncode}"
        return False, f"binary exited non-zero:\n{output}", ""

    actual = normalize_output(run.stdout or "")
    if not fixture_path.exists():
        return False, f"missing golden fixture: {fixture_path}", ""

    expected = fixture_path.read_text(encoding="utf-8")
    if actual == expected:
        return True, "", ""

    diff = "".join(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=f"expected/{fixture_path.name}",
            tofile=f"actual/{fixture_path.name}",
            n=3,
        )
    )
    return False, "runtime output mismatch", diff


def build_example(
    example: Path,
    backend: str,
    profile: str,
    out_dir: Path,
    fixtures_dir: Path,
    timeout: float,
) -> BuildResult:
    source_ext = ".zig" if backend == "zig" else ".c"
    source_path = out_dir / backend / "src" / f"{example.stem}{source_ext}"
    binary_path = out_dir / backend / "bin" / example.stem
    source_path.parent.mkdir(parents=True, exist_ok=True)
    binary_path.parent.mkdir(parents=True, exist_ok=True)

    result = BuildResult(
        example=example.stem,
        backend=backend,
        profile=profile,
        source_path=str(source_path),
        binary_path=str(binary_path),
    )

    compile_proc = compile_source(example, backend, source_path)
    if compile_proc.returncode != 0:
        result.error = f"compile failed:\n{first_error_text(compile_proc)}"
        return result
    result.compile_ok = True

    if backend == "zig":
        built, error = build_zig(source_path, binary_path, profile)
    elif backend == "c":
        built, error = build_c(source_path, binary_path, profile)
    else:
        result.error = f"unknown backend: {backend}"
        return result

    if not built:
        result.error = error
        return result

    result.syntax_ok = True
    result.build_ok = True

    ok, error, diff = verify_runtime(
        binary_path=binary_path,
        fixture_path=fixtures_dir / f"{example.stem}.out",
        timeout=timeout,
    )
    result.run_ok = ok
    result.output_match = ok
    result.error = error
    result.diff = diff
    return result


def summarize(results: list[BuildResult]) -> tuple[int, int]:
    passed = sum(1 for item in results if item.ok)
    total = len(results)
    print(f"Build artifacts verified: {passed}/{total}")

    failures = [item for item in results if not item.ok]
    if failures:
        print("\nFailures:")
        for item in failures:
            print(f"- {item.profile}/{item.backend}/{item.example}: {item.error}")
            if item.diff:
                print(item.diff)

    return passed, total


def main() -> int:
    parser = argparse.ArgumentParser(description="Build debug/release A7 example artifacts")
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILE_FLAGS.keys()),
        default="debug",
        help="Build profile (default: debug)",
    )
    parser.add_argument(
        "--backend",
        choices=["zig", "c", "both"],
        default="both",
        help="Backend to build (default: both)",
    )
    parser.add_argument(
        "--examples-dir",
        default=str(ROOT / "examples"),
        help="Directory containing .a7 examples",
    )
    parser.add_argument(
        "--fixtures-dir",
        default=str(ROOT / "test" / "fixtures" / "golden_outputs"),
        help="Directory containing expected runtime outputs",
    )
    parser.add_argument(
        "--out-dir",
        default="",
        help="Output directory (default: build/<profile>)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove the selected output directory before building",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Per-binary runtime timeout in seconds",
    )
    parser.add_argument(
        "--json-report",
        default="",
        help="Optional path to write a JSON report",
    )
    args = parser.parse_args()

    examples_dir = Path(args.examples_dir).resolve()
    fixtures_dir = Path(args.fixtures_dir).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else ROOT / "build" / args.profile
    backends = ["zig", "c"] if args.backend == "both" else [args.backend]

    if not shutil.which("zig"):
        print("zig is required for debug/release artifact builds", file=sys.stderr)
        return 2

    examples = find_examples(examples_dir)
    if not examples:
        print(f"No examples found in {examples_dir}", file=sys.stderr)
        return 2

    if args.clean and out_dir.exists():
        shutil.rmtree(out_dir)

    results = [
        build_example(
            example=example,
            backend=backend,
            profile=args.profile,
            out_dir=out_dir,
            fixtures_dir=fixtures_dir,
            timeout=args.timeout,
        )
        for backend in backends
        for example in examples
    ]

    passed, total = summarize(results)

    if args.json_report:
        report_path = Path(args.json_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "profile": args.profile,
            "backend": args.backend,
            "out_dir": str(out_dir),
            "passed": passed,
            "total": total,
            "ok": passed == total,
            "results": [asdict(item) for item in results],
        }
        report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
