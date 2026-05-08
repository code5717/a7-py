#!/usr/bin/env python3
"""Build and smoke-test the wheel in a clean virtual environment."""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def run_cmd(
    cmd: list[str],
    *,
    cwd: Path = ROOT,
    timeout: float = 60.0,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
    )


def first_error_text(proc: subprocess.CompletedProcess[str]) -> str:
    output = (proc.stderr or proc.stdout or "").strip()
    if not output:
        return "command failed without output"
    return "\n".join(output.splitlines()[:20])


def find_single_wheel(dist_dir: Path) -> Path:
    wheels = sorted(Path(path) for path in glob.glob(str(dist_dir / "a7_py-*.whl")))
    if len(wheels) != 1:
        raise RuntimeError(f"expected exactly one a7_py wheel in {dist_dir}, found {len(wheels)}")
    return wheels[0]


def venv_bin(venv_dir: Path, name: str) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / f"{name}.exe"
    return venv_dir / "bin" / name


def clean_python_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
        env.pop(key, None)
    return env


def verify_wheel(wheel: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="a7-wheel-smoke-") as tmp_name:
        tmp = Path(tmp_name)
        venv_dir = tmp / "venv"
        program = tmp / "hello.a7"
        zig_output = tmp / "hello.zig"
        c_output = tmp / "hello.c"
        env = clean_python_env()

        venv.EnvBuilder(with_pip=True).create(venv_dir)
        python = venv_bin(venv_dir, "python")
        a7_cli = venv_bin(venv_dir, "a7")

        install = run_cmd([str(python), "-m", "pip", "install", str(wheel)], cwd=tmp, timeout=120, env=env)
        if install.returncode != 0:
            raise RuntimeError(f"wheel install failed:\n{first_error_text(install)}")

        program.write_text(
            """io :: import "std/io"

main :: fn() {
    io.println("wheel smoke")
}
""",
            encoding="utf-8",
        )

        tokens = run_cmd(
            [str(a7_cli), "--format", "json", "--mode", "tokens", str(program)],
            cwd=tmp,
            timeout=30,
            env=env,
        )
        if tokens.returncode != 0:
            raise RuntimeError(f"installed CLI token mode failed:\n{first_error_text(tokens)}")

        try:
            payload = json.loads(tokens.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"installed CLI token mode did not emit JSON: {exc}") from exc

        if payload.get("schema_version") != "2.0" or payload.get("status") != "ok":
            raise RuntimeError(f"installed CLI JSON payload is not an ok v2 response: {payload!r}")

        zig_compile = run_cmd([str(a7_cli), str(program), "-o", str(zig_output)], cwd=tmp, timeout=30, env=env)
        if zig_compile.returncode != 0:
            raise RuntimeError(f"installed CLI Zig compile failed:\n{first_error_text(zig_compile)}")

        generated_zig = zig_output.read_text(encoding="utf-8")
        if "wheel smoke" not in generated_zig:
            raise RuntimeError("installed CLI Zig output did not contain the expected program text")

        c_compile = run_cmd(
            [str(a7_cli), str(program), "--backend", "c", "-o", str(c_output)],
            cwd=tmp,
            timeout=30,
            env=env,
        )
        if c_compile.returncode != 0:
            raise RuntimeError(f"installed CLI C compile failed:\n{first_error_text(c_compile)}")

        generated_c = c_output.read_text(encoding="utf-8")
        if "wheel smoke" not in generated_c:
            raise RuntimeError("installed CLI C output did not contain the expected program text")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the built A7 wheel in a clean venv")
    parser.add_argument("--dist-dir", default="dist", help="Directory containing a7_py-*.whl")
    parser.add_argument("--skip-build", action="store_true", help="Use the existing wheel instead of running uv build")
    args = parser.parse_args()

    if shutil.which("uv") is None and not args.skip_build:
        print("uv is required to build the wheel", file=sys.stderr)
        return 2

    dist_dir = (ROOT / args.dist_dir).resolve()
    if not args.skip_build:
        dist_dir.mkdir(parents=True, exist_ok=True)
        for artifact in list(dist_dir.glob("a7_py-*.whl")) + list(dist_dir.glob("a7_py-*.tar.gz")):
            artifact.unlink()
        build = run_cmd(["uv", "build", "--out-dir", str(dist_dir)], timeout=120)
        if build.returncode != 0:
            print(f"uv build failed:\n{first_error_text(build)}", file=sys.stderr)
            return 1

    try:
        wheel = find_single_wheel(dist_dir)
        verify_wheel(wheel)
    except Exception as exc:
        print(f"wheel install verification failed: {exc}", file=sys.stderr)
        return 1

    print(f"Wheel install verified: {wheel.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
