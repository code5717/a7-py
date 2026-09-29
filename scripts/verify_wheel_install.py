#!/usr/bin/env python3
"""Build and smoke-test the wheel in a clean virtual environment."""

from __future__ import annotations

import argparse
import glob
from email.parser import Parser
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
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
    zig = shutil.which("zig")
    if zig is None:
        raise RuntimeError("zig is required for installed-package native verification")
    with zipfile.ZipFile(wheel) as archive:
        metadata_paths = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_paths) != 1:
            raise RuntimeError("wheel must contain exactly one distribution metadata file")
        metadata = Parser().parsestr(archive.read(metadata_paths[0]).decode("utf-8"))
    expected_version = metadata.get("Version")
    if metadata.get("Name") != "a7-py" or not expected_version:
        raise RuntimeError("wheel has missing or unexpected package identity")
    with tempfile.TemporaryDirectory(prefix="a7-wheel-smoke-") as tmp_name:
        tmp = Path(tmp_name)
        venv_dir = tmp / "venv"
        work = tmp / "project with spaces"
        work.mkdir()
        program = work / "hello.a7"
        zig_output = work / "hello.zig"
        env = clean_python_env()

        venv.EnvBuilder(with_pip=True).create(venv_dir)
        python = venv_bin(venv_dir, "python")
        a7_cli = venv_bin(venv_dir, "a7")

        install = run_cmd([str(python), "-m", "pip", "install", str(wheel)], cwd=work, timeout=120, env=env)
        if install.returncode != 0:
            raise RuntimeError(f"wheel install failed:\n{first_error_text(install)}")

        origin = run_cmd(
            [str(python), "-I", "-c", "import a7; print(a7.__file__)"], cwd=work, env=env,
        )
        if origin.returncode != 0 or not Path(origin.stdout.strip()).resolve().is_relative_to(venv_dir.resolve()):
            raise RuntimeError(f"installed package did not resolve inside the clean venv: {origin.stdout!r}")

        identity = run_cmd(
            [str(python), "-I", "-c", "import a7, importlib.metadata, json; "
             "print(json.dumps([importlib.metadata.version('a7-py'), a7.__version__]))"],
            cwd=work, env=env,
        )
        if identity.returncode != 0 or json.loads(identity.stdout) != [expected_version, expected_version]:
            raise RuntimeError(f"installed package version disagrees with wheel metadata: {identity.stdout!r}")
        version = run_cmd([str(a7_cli), "--version"], cwd=work, env=env)
        if version.returncode != 0 or version.stdout != f"a7 {expected_version}\n":
            raise RuntimeError(f"installed CLI version disagrees with wheel metadata: {version.stdout!r}")
        doctor = run_cmd([str(a7_cli), "doctor"], cwd=work, env=env)
        qualified = sys.version_info[:2] == (3, 13) and sys.platform == "linux" and platform.machine() == "x86_64"
        if doctor.returncode != (0 if qualified else 2) or "Zig 0.16.0:" not in doctor.stdout:
            raise RuntimeError(f"installed CLI doctor failed: {doctor.stdout}\n{doctor.stderr}")
        if not qualified and "outside the V1 qualification target" not in doctor.stderr:
            raise RuntimeError("installed CLI doctor omitted the unsupported-environment diagnostic")

        (work / "helper.a7").write_text(
            "pub answer :: fn() i32 {\n    ret 42\n}\n", encoding="utf-8"
        )
        program.write_text(
            """io :: import "std/io"
helper :: import "helper"

main :: fn() {
    io.println("wheel smoke {}", helper.answer())
}
""",
            encoding="utf-8",
        )

        tokens = run_cmd(
            [str(a7_cli), "--format", "json", "--mode", "tokens", str(program)],
            cwd=work,
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

        before_check = set(work.rglob("*"))
        checked = run_cmd([str(a7_cli), "check", str(program), "--format", "json"], cwd=work, env=env)
        checked_payload = json.loads(checked.stdout)
        if (checked.returncode != 0 or checked_payload.get("status") != "ok"
                or checked_payload.get("artifacts") != {} or set(work.rglob("*")) != before_check):
            raise RuntimeError(f"installed CLI check failed or wrote artifacts: {checked.stdout}")

        zig_compile = run_cmd([str(a7_cli), str(program), "-o", str(zig_output)], cwd=work, timeout=30, env=env)
        if zig_compile.returncode != 0:
            raise RuntimeError(f"installed CLI Zig compile failed:\n{first_error_text(zig_compile)}")

        binary = work / ("hello-debug.exe" if sys.platform == "win32" else "hello-debug")
        build = run_cmd(
            [str(a7_cli), "build", str(program), "--profile", "debug", "-o", str(binary)],
            cwd=work, timeout=120, env=env,
        )
        if build.returncode != 0:
            raise RuntimeError(f"installed CLI debug build failed:\n{first_error_text(build)}")
        native = run_cmd([str(binary)], cwd=work, timeout=10, env=env)
        release = run_cmd(
            [str(a7_cli), "run", str(program), "--profile", "release"], cwd=work, timeout=120, env=env,
        )
        for profile, process in (("debug", native), ("release", release)):
            if process.returncode != 0 or process.stdout != "wheel smoke 42\n" or process.stderr:
                raise RuntimeError(
                    f"installed CLI {profile} native output mismatch: "
                    f"exit={process.returncode}, stdout={process.stdout!r}, stderr={process.stderr!r}"
                )

        invalid = work / "invalid.a7"
        invalid_output = work / "invalid.zig"
        invalid.write_text("main :: fn() {\n    missing_function()\n}\n", encoding="utf-8")
        rejected = run_cmd(
            [str(a7_cli), "--format", "json", str(invalid), "-o", str(invalid_output)],
            cwd=work, timeout=30, env=env,
        )
        if rejected.returncode != 6 or invalid_output.exists():
            raise RuntimeError(f"installed CLI failed to reject invalid source without an artifact: {rejected}")
        failure = json.loads(rejected.stdout)
        if failure.get("status") != "error" or "missing_function" not in rejected.stdout:
            raise RuntimeError(f"installed CLI omitted the invalid-source diagnostic: {failure!r}")

        before_invalid_check = set(work.rglob("*"))
        invalid_check = run_cmd(
            [str(a7_cli), "check", str(invalid), "--format", "json"], cwd=work, env=env,
        )
        invalid_payload = json.loads(invalid_check.stdout)
        if (invalid_check.returncode != 6 or invalid_payload.get("status") != "error"
                or invalid_payload.get("artifacts") != {} or "missing_function" not in invalid_check.stdout
                or set(work.rglob("*")) != before_invalid_check):
            raise RuntimeError(f"installed CLI check omitted rejection or wrote artifacts: {invalid_check.stdout}")


def verify_sdist(dist_dir: Path) -> str:
    archives = sorted(dist_dir.glob("a7_py-*.tar.gz"))
    if len(archives) != 1:
        raise RuntimeError(f"expected exactly one a7_py sdist in {dist_dir}, found {len(archives)}")
    with tempfile.TemporaryDirectory(prefix="a7-sdist-smoke-") as tmp_name:
        tmp = Path(tmp_name)
        source = tmp / "source"
        source.mkdir()
        with tarfile.open(archives[0]) as archive:
            archive.extractall(source, filter="data")
        projects = list(source.glob("*/pyproject.toml"))
        if len(projects) != 1:
            raise RuntimeError("sdist must contain exactly one top-level project")
        wheels = tmp / "wheels"
        uv = shutil.which("uv")
        if uv is None:
            raise RuntimeError("uv is required to verify the sdist")
        build = run_cmd(
            [uv, "build", "--wheel", "--out-dir", str(wheels)],
            cwd=projects[0].parent, timeout=120, env=clean_python_env(),
        )
        if build.returncode != 0:
            raise RuntimeError(f"sdist wheel build failed:\n{first_error_text(build)}")
        verify_wheel(find_single_wheel(wheels))
    return archives[0].name


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the built A7 wheel in a clean venv")
    parser.add_argument("--dist-dir", default="dist", help="Directory containing a7_py-*.whl")
    parser.add_argument("--skip-build", action="store_true", help="Use the existing wheel instead of running uv build")
    parser.add_argument("--verify-sdist", action="store_true", help="Also build, install and run the source distribution")
    args = parser.parse_args()

    if shutil.which("zig") is None:
        print("zig is required for installed-package native verification", file=sys.stderr)
        return 2

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
        if args.verify_sdist:
            sdist = verify_sdist(dist_dir)
            print(f"Source distribution install verified: {sdist}")
    except Exception as exc:
        print(f"wheel install verification failed: {exc}", file=sys.stderr)
        return 1

    print(f"Wheel install verified: {wheel.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
