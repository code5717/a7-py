"""Command-line interface for the A7 compiler."""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .backends import list_backends
from .backends.zig import ZIG_OPTIMIZE_MODE
from .compile import A7Compiler, CompileMode, OutputFormat, _safe_json_dumps, display_failure, error_console

PROFILE_HELP = (
    "build profiles:\n"
    "  debug    Zig Debug: unoptimized, runtime checks on (default)\n"
    "  release  Zig ReleaseSafe: optimized, runtime checks on\n"
    "  fast     Zig ReleaseFast: optimized, runtime checks off"
)
RUN_ARGS_HELP = (
    "Program arguments follow '--' and are passed through to the built\n"
    "program (e.g. `a7 run prog.a7 -- --help`). The program's exit code is\n"
    "returned as-is, so it can collide with compiler exit codes;\n"
    "distinguishing them needs a gate packet and is intentionally unchanged."
)

COMMANDS = {
    "check": "Check FILE through code generation; write nothing (--layout, --lib, --format json)",
    "build": "Build FILE to a native executable with Zig (-o, --profile)",
    "run": "Build FILE and run it; arguments after '--' go to the program",
    "doctor": "Report the Python, platform and Zig toolchain status",
}
COMMANDS_HELP = "commands (see `a7 COMMAND -h`):\n" + "\n".join(
    f"  {name:<8} {summary}" for name, summary in COMMANDS.items()
)

ZIG_VERSION = "0.16.0"


def find_zig() -> tuple[str | None, str]:
    executable = shutil.which("zig")
    if executable is None:
        return None, f"Zig {ZIG_VERSION} required: zig was not found on PATH"
    try:
        result = subprocess.run([executable, "version"], text=True, capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"Cannot run Zig: {exc}"
    version = result.stdout.strip()
    if result.returncode != 0 or version != ZIG_VERSION:
        return None, f"Zig {ZIG_VERSION} required; found {version or result.stderr.strip() or 'unknown version'}"
    return executable, f"Zig {version}: {executable}"


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


def _struct_layouts(result) -> list:
    """Struct layouts, with field touch counts, from a successful pipeline result."""
    from .layout import apply_touches, compute_struct_layouts, count_field_touches

    semantic = result.semantic_results or {}
    layouts = compute_struct_layouts(semantic.get("symbol_table"))
    touches = count_field_touches(result.ast, semantic.get("type_map"))
    apply_touches(layouts, touches)
    return layouts


def workflow(argv: list[str]) -> int:
    command = argv[0]
    epilogs = {"build": PROFILE_HELP, "run": PROFILE_HELP + "\n\n" + RUN_ARGS_HELP}
    parser = argparse.ArgumentParser(
        prog=f"a7 {command}",
        epilog=epilogs.get(command),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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
        parser.add_argument("--layout", action="store_true",
                            help="Print struct memory layout (size, 64B line use, field offsets)")
        parser.add_argument("--lib", action="store_true",
                            help="Check as a library: allow no 'main :: fn()' entry point")
    else:
        parser.add_argument("--profile", choices=list(ZIG_OPTIMIZE_MODE), default="debug",
                            help="Build profile (default: debug); see 'build profiles' below")
        parser.add_argument("--no-nonwrap", action="store_true")
        if command == "build":
            parser.add_argument("-o", "--output", help="Native executable path, defaults to ./<source-stem>")
    options = argv[1:]
    program_args: list[str] = []
    if command == "run" and "--" in options:
        separator = options.index("--")
        program_args = options[separator + 1:]
        options = options[:separator]
    args = parser.parse_args(options)

    compiler = A7Compiler(
        mode=CompileMode.PIPELINE,
        output_format=OutputFormat.JSON,
        build_profile=getattr(args, "profile", "debug"),
        no_nonwrap=getattr(args, "no_nonwrap", False),
        is_library=getattr(args, "lib", False),
    )
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        result = compiler.compile_file_detailed(args.file)
    if command == "check":
        from .layout import format_report, layouts_to_json

        want_layout = result.ok and args.layout
        if args.format == "json" and want_layout:
            payload = compiler.to_json_payload(result)
            payload["layout"] = layouts_to_json(_struct_layouts(result))
            print(_safe_json_dumps(payload))
        elif args.format == "json":
            print(captured.getvalue(), end="")
        elif result.ok:
            print(f"Checked {args.file}")
            if want_layout:
                print(format_report(_struct_layouts(result)))
        else:
            display_failure(result.failure, error_console)
        return int(result.exit_code)
    if not result.ok:
        display_failure(result.failure, error_console)
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
                print(f"Native output conflicts with a source file or directory: {destination}", file=sys.stderr)
                return 3
            destination.parent.mkdir(parents=True, exist_ok=True)
        # Same filesystem as the destination permits an atomic replacement.
        with tempfile.TemporaryDirectory(prefix="a7-native-", dir=destination.parent if destination else None) as folder:
            root = Path(folder)
            generated = root / "program.zig"
            generated.write_text(result.codegen_result["output_code"], encoding="utf-8")
            binary = root / ("program.exe" if os.name == "nt" else "program")
            build = subprocess.run(
                [zig, "build-exe", str(generated), "-O", ZIG_OPTIMIZE_MODE[args.profile],
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
    # Arguments after `--` belong to the program started by `a7 run`.
    own_args = sys.argv[1:]
    if "--" in own_args:
        own_args = own_args[:own_args.index("--")]
    if "--version" in own_args:
        print(f"a7 {package_version()}")
        return
    if sys.argv[1:2] and sys.argv[1] in COMMANDS:
        sys.exit(workflow(sys.argv[1:]))
    available_backends = ", ".join(list_backends())

    parser = argparse.ArgumentParser(
        description="A7 compiler. `a7 FILE` writes Zig source; the commands below build on it.",
        prog="a7",
        usage="a7 [options] FILE\n       a7 {check,build,run,doctor} [options] [FILE]",
        epilog=COMMANDS_HELP + "\n\n" + PROFILE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--version", action="store_true", help="Print the package version and exit")
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
        "--build-profile",
        choices=list(ZIG_OPTIMIZE_MODE),
        default="debug",
        help="Build profile passed to codegen (default: debug); see 'build profiles' below",
    )

    parser.add_argument(
        "--no-nonwrap",
        action="store_true",
        help="Force wrapping arithmetic even in release and fast builds",
    )

    parser.add_argument(
        "--lib",
        action="store_true",
        help="Compile as a library: allow no 'main :: fn()' entry point",
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
        build_profile=args.build_profile,
        no_nonwrap=args.no_nonwrap,
        is_library=args.lib,
    )
    result = compiler.compile_file_detailed(str(input_path), args.output)
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
