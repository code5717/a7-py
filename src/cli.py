"""Command-line interface for the A7 compiler."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .backends import list_backends
from .compile import A7Compiler, CompileMode, OutputFormat


def main() -> None:
    available_backends = ", ".join(list_backends())

    parser = argparse.ArgumentParser(
        description="A7 Programming Language Compiler/Interpreter",
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
