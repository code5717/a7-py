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
from time import perf_counter
from typing import Any

from .backends import list_backends
from .backends.zig import ZIG_OPTIMIZE_MODE
from .compile import (
    A7Compiler,
    CompileMode,
    ExitCode,
    OutputFormat,
    _elapsed_ms,
    _safe_json_dumps,
    display_failure,
    error_console,
)

PROFILE_HELP = (
    "build profiles:\n"
    "  debug    Zig Debug: unoptimized, runtime checks on (default)\n"
    "  release  Zig ReleaseSafe: optimized, runtime checks on\n"
    "  fast     Zig ReleaseFast: optimized, runtime checks off"
)
MODES_HELP = (
    "modes (--mode):\n"
    "  compile   Full pipeline; write Zig (default)\n"
    "  tokens    Tokenize only\n"
    "  ast       Tokenize and parse\n"
    "  semantic  Parse and semantic passes\n"
    "  pipeline  Full pipeline; write nothing\n"
    "  doc       Full pipeline; write a markdown report"
)
EXIT_CODES_HELP = (
    "exit codes (stage-specific; JSON still prints diagnostics on failure):\n"
    "  0  success\n"
    "  2  usage or toolchain\n"
    "  3  I/O\n"
    "  4  tokenize\n"
    "  5  parse\n"
    "  6  semantic\n"
    "  7  codegen or native build\n"
    "  8  internal\n"
    "  `a7 run` returns the program exit status after a successful build"
)
ALIASES_HELP = (
    "short aliases (prefer long flags in scripts and agent commands):\n"
    "  -h  --help\n"
    "  -o  --output\n"
    "  -v  --verbose"
)
RUN_ARGS_HELP = (
    "Program arguments follow '--' and are passed through to the built\n"
    "program (e.g. `a7 run prog.a7 -- --help`). The program's exit code is\n"
    "returned as-is, so it can collide with compiler exit codes;\n"
    "distinguishing them needs a gate packet and is intentionally unchanged."
)

COMMANDS = {
    "check": "Check FILE through code generation; write nothing (--layout, --lib, --format json, --timings)",
    "build": "Build FILE to a native executable with Zig (--output, --profile, --timings)",
    "run": "Build FILE and run it; arguments after '--' go to the program",
    "doctor": "Report toolchain status; --format json lists capabilities for agents",
}
COMMANDS_HELP = "commands (see `a7 COMMAND --help`):\n" + "\n".join(
    f"  {name:<8} {summary}" for name, summary in COMMANDS.items()
)

ZIG_VERSION = "0.16.0"
DOCTOR_SCHEMA_VERSION = "1.0"
QUALIFICATION_TARGET = "Linux x86_64, Python 3.13, Zig 0.16.0"

EXIT_CODE_NAMES = {
    int(ExitCode.SUCCESS): "success",
    int(ExitCode.USAGE): "usage_or_toolchain",
    int(ExitCode.IO): "io",
    int(ExitCode.TOKENIZE): "tokenize",
    int(ExitCode.PARSE): "parse",
    int(ExitCode.SEMANTIC): "semantic",
    int(ExitCode.CODEGEN): "codegen_or_native_build",
    int(ExitCode.INTERNAL): "internal",
}


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


def doctor_capabilities() -> dict[str, Any]:
    """Stable discovery surface for agents (`a7 doctor --format json`)."""
    return {
        "commands": list(COMMANDS),
        "modes": [mode.value for mode in CompileMode],
        "formats": [fmt.value for fmt in OutputFormat],
        "backends": list(list_backends()),
        "profiles": list(ZIG_OPTIMIZE_MODE),
        "exit_codes": {
            str(code): name for code, name in sorted(EXIT_CODE_NAMES.items())
        },
        "flags": {
            "file_first": [
                "--mode",
                "--format",
                "--output",
                "--doc-out",
                "--backend",
                "--build-profile",
                "--no-nonwrap",
                "--lib",
                "--verbose",
                "--timings",
                "--version",
                "--help",
            ],
            "check": ["--format", "--layout", "--lib", "--timings"],
            "build": ["--output", "--profile", "--no-nonwrap", "--timings"],
            "run": ["--profile", "--no-nonwrap", "--timings"],
            "doctor": ["--format"],
            "short_aliases": {
                "-h": "--help",
                "-o": "--output",
                "-v": "--verbose",
            },
        },
        "json_schema_version": "3.0",
        "notes": [
            "Prefer long flags in scripts and agent commands.",
            "Compiler JSON payloads use schema_version 3.0 with exit_code and diagnostics.",
            "Nonzero compiler exits stay stage-specific; JSON still emits diagnostics on failure.",
            "a7 run returns the native process exit status after a successful build.",
        ],
    }


def doctor_report(*, output_format: str) -> int:
    """Print toolchain status; JSON includes capabilities for discovery."""
    zig, message = find_zig()
    supported = (
        sys.version_info[:2] == (3, 13)
        and sys.platform == "linux"
        and platform.machine() == "x86_64"
    )
    exit_code = 0 if zig and supported else 2
    if output_format == "json":
        zig_version = None
        zig_path = None
        if zig is not None:
            zig_path = zig
            zig_version = ZIG_VERSION
        payload = {
            "schema_version": DOCTOR_SCHEMA_VERSION,
            "command": "doctor",
            "status": "ok" if exit_code == 0 else "error",
            "exit_code": exit_code,
            "version": package_version(),
            "python": {
                "version": platform.python_version(),
                "executable": sys.executable,
            },
            "platform": {
                "system": sys.platform,
                "machine": platform.machine(),
            },
            "zig": {
                "ok": zig is not None,
                "required_version": ZIG_VERSION,
                "version": zig_version,
                "path": zig_path,
                "message": message,
            },
            "qualification": {
                "target": QUALIFICATION_TARGET,
                "ok": supported,
            },
            "capabilities": doctor_capabilities(),
        }
        print(_safe_json_dumps(payload))
        return exit_code

    print(
        f"A7 {package_version()}\n"
        f"Python {platform.python_version()}: {sys.executable}\n"
        f"Platform {sys.platform}/{platform.machine()}\n"
        f"{message}\n"
        f"V1 qualification target: {QUALIFICATION_TARGET}"
    )
    if not supported:
        print(
            "This Python/platform combination is outside the V1 qualification target",
            file=sys.stderr,
        )
    return exit_code


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
    epilogs = {
        "build": PROFILE_HELP + "\n\n" + ALIASES_HELP,
        "run": PROFILE_HELP + "\n\n" + RUN_ARGS_HELP + "\n\n" + ALIASES_HELP,
        "check": ALIASES_HELP,
        "doctor": (
            "Use --format json for machine-readable discovery "
            "(modes, exit codes, backends, flags).\n\n" + ALIASES_HELP
        ),
    }
    parser = argparse.ArgumentParser(
        prog=f"a7 {command}",
        epilog=epilogs.get(command),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    if command == "doctor":
        parser.add_argument(
            "--format",
            choices=["human", "json"],
            default="human",
            help="Output format (default: human). json includes capabilities for agents",
        )
        args = parser.parse_args(argv[1:])
        return doctor_report(output_format=args.format)

    parser.add_argument("file", help="A7 source file")
    parser.add_argument(
        "--timings",
        action="store_true",
        help="Report per-stage wall times (frontend stages; Zig for build/run)",
    )
    if command == "check":
        parser.add_argument(
            "--format",
            choices=["human", "json"],
            default="human",
            help="Output format (default: human). json uses schema 3.0 with exit_code and diagnostics",
        )
        parser.add_argument(
            "--layout",
            action="store_true",
            help="Print struct memory layout (size, 64B line use, field offsets)",
        )
        parser.add_argument(
            "--lib",
            action="store_true",
            help="Check as a library: allow no 'main :: fn()' entry point",
        )
    else:
        parser.add_argument(
            "--profile",
            choices=list(ZIG_OPTIMIZE_MODE),
            default="debug",
            help="Build profile (default: debug); see 'build profiles' below",
        )
        parser.add_argument(
            "--no-nonwrap",
            action="store_true",
            help="Force wrapping arithmetic even in release and fast builds",
        )
        if command == "build":
            parser.add_argument(
                "--output",
                "-o",
                help="Native executable path (long form preferred); defaults to ./<source-stem>",
            )
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
        report_timings=args.timings,
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
            if args.timings:
                print(f"timings: {compiler._format_stage_timings(result)}")
        else:
            display_failure(result.failure, error_console)
        return int(result.exit_code)
    if not result.ok:
        display_failure(result.failure, error_console)
        return int(result.exit_code)

    # Reject source conflicts before the Zig lookup so exit 3 stays
    # stage-specific even when the toolchain is missing.
    destination = None
    if command == "build":
        destination = Path(
            args.output or (Path(args.file).stem + (".exe" if os.name == "nt" else ""))
        ).absolute()
        if destination.suffix == ".a7" or native_output_conflict(
            result.input_paths, destination
        ):
            print(
                f"Native output conflicts with a source file or directory: {destination}",
                file=sys.stderr,
            )
            return 3

    zig, message = find_zig()
    if zig is None:
        print(message, file=sys.stderr)
        return 2
    try:
        if destination is not None:
            destination.parent.mkdir(parents=True, exist_ok=True)
        # Same filesystem as the destination permits an atomic replacement.
        with tempfile.TemporaryDirectory(prefix="a7-native-", dir=destination.parent if destination else None) as folder:
            root = Path(folder)
            generated = root / "program.zig"
            generated.write_text(result.codegen_result["output_code"], encoding="utf-8")
            binary = root / ("program.exe" if os.name == "nt" else "program")
            zig_start = perf_counter()
            build = subprocess.run(
                [zig, "build-exe", str(generated), "-O", ZIG_OPTIMIZE_MODE[args.profile],
                 f"-femit-bin={binary}"],
                capture_output=True, text=True,
            )
            zig_ms = _elapsed_ms(zig_start)
            if build.returncode != 0:
                print(build.stderr or build.stdout or "Zig build failed", file=sys.stderr, end="\n")
                return 7
            if args.timings:
                print(f"timings: {compiler._format_stage_timings(result)} zig={zig_ms}ms")
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
        description=(
            "A7 compiler. `a7 FILE` writes Zig source; "
            "`a7 doctor --format json` lists modes, exit codes, backends and flags."
        ),
        prog="a7",
        usage="a7 [options] FILE\n       a7 {check,build,run,doctor} [options] [FILE]",
        epilog=(
            COMMANDS_HELP
            + "\n\n"
            + MODES_HELP
            + "\n\n"
            + PROFILE_HELP
            + "\n\n"
            + EXIT_CODES_HELP
            + "\n\n"
            + ALIASES_HELP
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the package version and exit",
    )
    parser.add_argument("file", help="A7 source file (.a7) to process")

    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in CompileMode],
        default=CompileMode.COMPILE.value,
        help="Execution mode (default: compile); see 'modes' below",
    )

    parser.add_argument(
        "--format",
        dest="output_format",
        choices=[fmt.value for fmt in OutputFormat],
        default=OutputFormat.HUMAN.value,
        help=(
            "Output format (default: human). "
            "json uses schema 3.0 with stages, exit_code and diagnostics"
        ),
    )

    parser.add_argument(
        "--output",
        "-o",
        help="Zig output path for --mode compile (long form preferred; default: auto-generated)",
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
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output in human format (long form preferred)",
    )

    parser.add_argument(
        "--timings",
        action="store_true",
        help="Report per-stage wall times (tokenize/parse/semantic/safety/codegen)",
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
        report_timings=args.timings,
    )
    result = compiler.compile_file_detailed(str(input_path), args.output)
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
