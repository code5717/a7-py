"""Command-line interface for the A7 compiler."""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import platform
import subprocess
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .backends import list_backends
from .compile import A7Compiler, CompileMode, OutputFormat
from .toolchain import find_zig


def native_output_conflict(input_paths: list[str], destination: Path) -> bool:
    """Protect the sources already read by the compiler, including file aliases.

    compile inputs -> successful result -> native output check -> atomic write

    Reusing the input list avoids parsing and loading every module a second time.
    """
    return destination.is_dir() or any(
        destination.resolve() == path.resolve()
        or (destination.exists() and path.exists() and destination.samefile(path))
        for path in map(Path, input_paths)
    )


def package_version() -> str:
    try:
        return version("a7-py")
    except PackageNotFoundError:
        from . import __version__
        return __version__


def print_failure(result) -> None:
    print(result.failure.message, file=sys.stderr)
    for detail in result.failure.details:
        if detail.get("message"):
            print(detail["message"], file=sys.stderr)


def workflow(argv: list[str]) -> int:
    command = argv[0]
    parser = argparse.ArgumentParser(prog=f"a7 {command}")
    if command == "doctor":
        parser.parse_args(argv[1:])
        zig, message = find_zig()
        supported = sys.version_info[:2] == (3, 13) and sys.platform == "linux" and platform.machine() == "x86_64"
        print(f"A7 {package_version()}\nPython {platform.python_version()}: {sys.executable}\n"
              f"Platform {sys.platform}/{platform.machine()}\n{message}\n"
              "V1 qualification target: Linux x86_64, Python 3.13, Zig 0.16.0")
        if not supported:
            print("This Python/platform combination is outside the V1 qualification target", file=sys.stderr)
        return 0 if zig and supported else 2

    parser.add_argument("file", help="A7 source file")
    if command == "check":
        parser.add_argument("--format", choices=["human", "json"], default="human")
    else:
        parser.add_argument("--profile", choices=["debug", "release"], default="debug")
        if command == "build":
            parser.add_argument("-o", "--output", help="Native executable path, defaults to ./<source-stem>")
    options = argv[1:]
    program_args: list[str] = []
    if command == "run" and "--" in options:
        separator = options.index("--")
        program_args = options[separator + 1:]
        options = options[:separator]
    args = parser.parse_args(options)

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        result = A7Compiler(mode=CompileMode.PIPELINE, output_format=OutputFormat.JSON).compile_file_detailed(args.file)
    if command == "check":
        if args.format == "json":
            print(captured.getvalue(), end="")
        elif result.ok:
            print(f"Checked {args.file}")
        else:
            print_failure(result)
        return int(result.exit_code)
    if not result.ok:
        print_failure(result)
        return int(result.exit_code)

    zig, message = find_zig()
    if zig is None:
        print(message, file=sys.stderr)
        return 2
    destination = None
    if command == "build":
        destination = Path(args.output or (Path(args.file).stem + (".exe" if os.name == "nt" else ""))).absolute()
    try:
        if destination is not None:
            if destination.suffix == ".a7" or native_output_conflict(result.input_paths, destination):
                print("Native output conflicts with a source file or directory", file=sys.stderr)
                return 3
            destination.parent.mkdir(parents=True, exist_ok=True)
        # Same filesystem as the destination permits an atomic replacement.
        with tempfile.TemporaryDirectory(prefix="a7-native-", dir=destination.parent if destination else None) as folder:
            root = Path(folder)
            generated = root / "program.zig"
            generated.write_text(result.codegen_result["output_code"], encoding="utf-8")
            binary = root / ("program.exe" if os.name == "nt" else "program")
            build = subprocess.run(
                [zig, "build-exe", str(generated), "-O", "Debug" if args.profile == "debug" else "ReleaseFast",
                 f"-femit-bin={binary}"],
                capture_output=True, text=True,
            )
            if build.returncode != 0:
                print(build.stderr or build.stdout or "Zig build failed", file=sys.stderr, end="\n")
                return 7
            if destination is not None:
                os.replace(binary, destination)
                print(f"Built {destination}")
                return 0
            native = subprocess.run([str(binary), *program_args])
            return native.returncode if native.returncode >= 0 else 128 - native.returncode
    except OSError as exc:
        print(f"Native {command} failed: {exc}", file=sys.stderr)
        return 3


def main() -> None:
    if sys.argv[1:] == ["--version"]:
        print(f"a7 {package_version()}")
        return
    if sys.argv[1:2] and sys.argv[1] in {"check", "build", "run", "doctor"}:
        sys.exit(workflow(sys.argv[1:]))
    available_backends = ", ".join(list_backends())

    parser = argparse.ArgumentParser(
        description="A7 compiler. Commands: check, build, run, doctor. Use --version for the package version.",
        prog="a7",
    )

    parser.add_argument("file", help="A7 source file (.a7) to process")

    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in CompileMode],
        default=CompileMode.COMPILE.value,
        help="Execution mode (default: compile)",
    )

    parser.add_argument(
        "--format",
        dest="output_format",
        choices=[fmt.value for fmt in OutputFormat],
        default=OutputFormat.HUMAN.value,
        help="Output format (default: human)",
    )

    parser.add_argument(
        "-o",
        "--output",
        help="Output file path for --mode compile (default: auto-generated)",
    )

    parser.add_argument(
        "--doc-out",
        metavar="PATH",
        help=(
            "Write markdown documentation report. "
            "Allowed in modes: compile, pipeline, doc. "
            "Use 'auto' for <file>.md"
        ),
    )

    parser.add_argument(
        "--backend",
        default="zig",
        help=f"Target backend name (default: zig). Available: {available_backends}",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    mode = CompileMode(args.mode)
    output_format = OutputFormat(args.output_format)

    if mode != CompileMode.COMPILE and args.output:
        parser.error("--output is only valid when --mode compile")

    if args.doc_out and mode not in {
        CompileMode.COMPILE,
        CompileMode.PIPELINE,
        CompileMode.DOC,
    }:
        parser.error("--doc-out is only valid in modes: compile, pipeline, doc")

    input_path = Path(args.file)
    doc_path = None
    if args.doc_out:
        doc_path = str(input_path.with_suffix(".md")) if args.doc_out == "auto" else args.doc_out
    elif mode == CompileMode.DOC:
        doc_path = str(input_path.with_suffix(".md"))

    compiler = A7Compiler(
        backend=args.backend,
        verbose=args.verbose,
        mode=mode,
        output_format=output_format,
        doc_path=doc_path,
    )
    result = compiler.compile_file_detailed(str(input_path), args.output)
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
