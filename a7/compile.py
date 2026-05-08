"""
A7 to Zig Compiler

Main compilation pipeline that orchestrates lexing, parsing, semantic analysis,
AST preprocessing, and code generation.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from pathlib import Path
from time import perf_counter
from typing import Any, Optional

from rich.console import Console

from .ast_nodes import ASTNode, NodeKind
from .ast_preprocessor import ASTPreprocessor
from .backends import get_backend
from .errors import CompilerError, ParseError, SemanticError, SemanticErrorType, display_error, display_errors
from .formatters import ConsoleFormatter, JSONFormatter, MarkdownFormatter
from .parser import Parser
from .passes import GenericLoweringPass, NameResolutionPass, SemanticValidationPass, TypeCheckingPass
from .stdlib import StdlibRegistry
from .tokens import Tokenizer

console = Console()


class CompileMode(StrEnum):
    COMPILE = "compile"
    TOKENS = "tokens"
    AST = "ast"
    SEMANTIC = "semantic"
    PIPELINE = "pipeline"
    DOC = "doc"


class OutputFormat(StrEnum):
    HUMAN = "human"
    JSON = "json"


class ExitCode(IntEnum):
    SUCCESS = 0
    USAGE = 2
    IO = 3
    TOKENIZE = 4
    PARSE = 5
    SEMANTIC = 6
    CODEGEN = 7
    INTERNAL = 8


@dataclass
class FailureInfo:
    category: str
    message: str
    details: list[dict[str, Any]] = field(default_factory=list)
    span: Optional[dict[str, Any]] = None
    exception_type: Optional[str] = None


@dataclass
class CompilationResult:
    ok: bool
    exit_code: int
    mode: CompileMode
    input_path: str
    backend: str
    timing_ms: int = 0
    source_code: str = ""
    tokens: Optional[list] = None
    ast: Any = None
    semantic_results: Optional[dict[str, Any]] = None
    codegen_result: Optional[dict[str, Any]] = None
    stages: dict[str, dict[str, Any]] = field(default_factory=dict)
    output_path: Optional[str] = None
    doc_path: Optional[str] = None
    failure: Optional[FailureInfo] = None


class A7Compiler:
    """Main compiler class that handles the A7 compilation pipeline."""

    def __init__(
        self,
        backend: str = "zig",
        verbose: bool = False,
        mode: CompileMode | str = CompileMode.COMPILE,
        output_format: OutputFormat | str = OutputFormat.HUMAN,
        doc_path: Optional[str] = None,
    ):
        self.backend = backend
        self.verbose = verbose
        self.mode = CompileMode(mode)
        self.output_format = OutputFormat(output_format)
        self.doc_path = doc_path

        self.json_formatter = JSONFormatter(backend=backend)
        self.console_formatter = ConsoleFormatter(mode=self.mode.value, backend=backend)

    # Public API compatibility: bool-returning compile method
    def compile_file(self, input_path: str, output_path: Optional[str] = None) -> bool:
        return self.compile_file_detailed(input_path, output_path).ok

    def compile_file_detailed(
        self, input_path: str, output_path: Optional[str] = None
    ) -> CompilationResult:
        """
        Compile a single A7 source file and return a detailed result object.
        """
        start = perf_counter()
        result = CompilationResult(
            ok=False,
            exit_code=ExitCode.INTERNAL,
            mode=self.mode,
            input_path=input_path,
            backend=self.backend,
        )

        try:
            input_file = Path(input_path)

            if not input_file.exists():
                return self._finish_with_failure(
                    result,
                    ExitCode.IO,
                    "io",
                    f"Input file not found: {input_path}",
                    start,
                    compiler_error=CompilerError(f"Input file not found: {input_path}"),
                )

            if input_file.suffix != ".a7":
                return self._finish_with_failure(
                    result,
                    ExitCode.IO,
                    "io",
                    f"Expected .a7 file, got: {input_path}",
                    start,
                    compiler_error=CompilerError(f"Expected .a7 file, got: {input_path}"),
                )

            if self.mode == CompileMode.COMPILE:
                result.output_path = output_path or self._generate_output_path(input_path)

            with open(input_path, "r", encoding="utf-8") as f:
                source_code = f.read()
            result.source_code = source_code

            # Stage 1: Tokenization
            try:
                tokenizer = Tokenizer(source_code, filename=str(input_path))
                tokens = tokenizer.tokenize()
                result.tokens = tokens
                result.stages["tokenize"] = {
                    "ok": True,
                    "token_count": len([t for t in tokens if t.type.name != "EOF"]),
                }
            except CompilerError as e:
                return self._finish_with_failure(
                    result,
                    ExitCode.TOKENIZE,
                    "tokenize",
                    str(e),
                    start,
                    compiler_error=e,
                )

            # Stage 2: Parse
            parse_error: Optional[Exception] = None
            ast = None
            needs_parse = self.mode != CompileMode.TOKENS
            if needs_parse:
                try:
                    source_lines = source_code.splitlines() if source_code else []
                    parser = Parser(
                        tokens, filename=str(input_path), source_lines=source_lines
                    )
                    ast = parser.parse()
                    result.ast = ast
                    result.stages["parse"] = {"ok": True}
                except ParseError as e:
                    parse_error = e
                except CompilerError as e:
                    parse_error = e
                except Exception as e:
                    parse_error = CompilerError(
                        str(e),
                        filename=str(input_path),
                        source_lines=source_code.splitlines() if source_code else [],
                    )

                if parse_error is not None:
                    result.stages["parse"] = {"ok": False}
                    return self._finish_with_failure(
                        result,
                        ExitCode.PARSE,
                        "parse",
                        str(parse_error),
                        start,
                        parse_error=parse_error,
                    )

            # Stage 3: Semantic analysis
            symbol_table = None
            type_map = None
            all_errors: list[Any] = []
            semantic_passes: list[dict[str, Any]] = []
            semantic_modes = {
                CompileMode.SEMANTIC,
                CompileMode.PIPELINE,
                CompileMode.COMPILE,
                CompileMode.DOC,
            }
            needs_semantic = self.mode in semantic_modes
            if needs_semantic and ast is not None:
                source_lines = source_code.splitlines() if source_code else []

                # Non-fatal import processing
                from .module_resolver import ModuleResolver

                file_dir = str(Path(input_path).parent)
                module_resolver = ModuleResolver(
                    search_paths=[
                        file_dir,
                        str(Path(file_dir) / "stdlib"),
                        str(Path(__file__).parent.parent / "stdlib"),
                    ]
                )
                import_errors: list[Any] = []
                try:
                    module_resolver.load_program_dependencies(ast, str(input_path))
                except SemanticError as e:
                    import_errors.append(e)
                backend_import_errors: list[Any] = []
                codegen_modes = {CompileMode.COMPILE, CompileMode.PIPELINE, CompileMode.DOC}
                if not import_errors and self.mode in codegen_modes:
                    backend_import_errors = self._backend_unsupported_import_errors(
                        ast=ast,
                        module_resolver=module_resolver,
                        filename=str(input_path),
                        source_lines=source_lines,
                    )
                backend_feature_errors: list[Any] = []
                if self.mode in codegen_modes:
                    backend_feature_errors = self._backend_unsupported_feature_errors(
                        ast=ast,
                        filename=str(input_path),
                        source_lines=source_lines,
                    )

                name_resolver = NameResolutionPass()
                name_resolver.source_lines = source_lines
                symbol_table = name_resolver.analyze(ast, str(input_path))
                nr_ok = len(name_resolver.errors) == 0
                import_ok = len(import_errors) == 0
                backend_import_ok = len(backend_import_errors) == 0
                backend_feature_ok = len(backend_feature_errors) == 0
                semantic_passes.append(
                    {
                        "name": "Import Resolution",
                        "ok": import_ok,
                        "errors": len(import_errors),
                    }
                )
                if import_errors:
                    all_errors.extend(import_errors)
                semantic_passes.append(
                    {
                        "name": "Backend Import Support",
                        "ok": backend_import_ok,
                        "errors": len(backend_import_errors),
                    }
                )
                if backend_import_errors:
                    all_errors.extend(backend_import_errors)
                semantic_passes.append(
                    {
                        "name": "Backend Feature Support",
                        "ok": backend_feature_ok,
                        "errors": len(backend_feature_errors),
                    }
                )
                if backend_feature_errors:
                    all_errors.extend(backend_feature_errors)
                semantic_passes.append(
                    {
                        "name": "Name Resolution",
                        "ok": nr_ok,
                        "errors": len(name_resolver.errors),
                    }
                )
                if name_resolver.errors:
                    all_errors.extend(name_resolver.errors)

                if import_ok and backend_import_ok and backend_feature_ok and nr_ok:
                    type_checker = TypeCheckingPass(symbol_table)
                    type_checker.source_lines = source_lines
                    type_checker.analyze(ast, str(input_path))
                    tc_ok = len(type_checker.errors) == 0
                    semantic_passes.append(
                        {
                            "name": "Type Checking",
                            "ok": tc_ok,
                            "errors": len(type_checker.errors),
                        }
                    )
                    if type_checker.errors:
                        all_errors.extend(type_checker.errors)
                    type_map = type_checker.node_types

                    if tc_ok:
                        validator = SemanticValidationPass(
                            symbol_table, type_checker.node_types
                        )
                        validator.source_lines = source_lines
                        validator.analyze(ast, str(input_path))
                        sv_ok = len(validator.errors) == 0
                        semantic_passes.append(
                            {
                                "name": "Semantic Validation",
                                "ok": sv_ok,
                                "errors": len(validator.errors),
                            }
                        )
                        if validator.errors:
                            all_errors.extend(validator.errors)

                semantic_ok = len(all_errors) == 0
                result.semantic_results = {
                    "passes": semantic_passes,
                    "errors": all_errors,
                    "symbol_table": symbol_table,
                    "type_map": type_map,
                }
                result.stages["semantic"] = {
                    "ok": semantic_ok,
                    "passes": semantic_passes,
                    "error_count": len(all_errors),
                }
                if not semantic_ok:
                    return self._finish_with_failure(
                        result,
                        ExitCode.SEMANTIC,
                        "semantic",
                        f"Semantic analysis failed with {len(all_errors)} error(s)",
                        start,
                        semantic_errors=all_errors,
                    )

            # Stage 4: Preprocess + codegen
            target_code = None
            codegen_modes = {CompileMode.COMPILE, CompileMode.PIPELINE, CompileMode.DOC}
            needs_codegen = self.mode in codegen_modes
            if needs_codegen and ast is not None:
                if self.backend == "c":
                    ast = GenericLoweringPass().process(ast)

                preprocessor = ASTPreprocessor(
                    symbol_table=symbol_table,
                    type_map=type_map,
                    stdlib=StdlibRegistry(),
                )
                ast = preprocessor.process(ast)
                result.ast = ast

                try:
                    codegen = get_backend(self.backend)
                    target_code = codegen.generate(
                        ast, type_map=type_map, symbol_table=symbol_table
                    )
                    language_name = codegen.language_name
                    syntax = self.backend
                except Exception as e:
                    if self.output_format == OutputFormat.HUMAN and self.verbose:
                        traceback.print_exc()
                    return self._finish_with_failure(
                        result,
                        ExitCode.CODEGEN,
                        "codegen",
                        str(e),
                        start,
                        exception=e,
                    )

                result.codegen_result = {
                    "output_code": target_code,
                    "output_path": result.output_path,
                    "bytes": len(target_code),
                    "changes": preprocessor.changes_made,
                    "backend": self.backend,
                    "language": language_name,
                    "syntax": syntax,
                }
                result.stages["codegen"] = {
                    "ok": True,
                    "bytes": len(target_code),
                    "changes": preprocessor.changes_made,
                }

                if self.mode == CompileMode.COMPILE:
                    try:
                        if result.output_path is None:
                            raise CompilerError("Missing output path for compile mode")
                        out_dir = os.path.dirname(result.output_path)
                        if out_dir:
                            os.makedirs(out_dir, exist_ok=True)
                        with open(result.output_path, "w", encoding="utf-8") as f:
                            f.write(target_code)
                    except Exception as e:
                        return self._finish_with_failure(
                            result,
                            ExitCode.IO,
                            "io",
                            f"Failed to write output file: {e}",
                            start,
                            exception=e,
                        )

            # Optional markdown documentation output (can be combined with compile mode)
            if self.doc_path and ast is not None:
                doc_output = self.doc_path
                if doc_output == "auto":
                    doc_output = input_path.replace(".a7", ".md")
                try:
                    md_formatter = MarkdownFormatter()
                    md_content = md_formatter.format_compilation_doc(
                        input_path,
                        source_code,
                        result.tokens or [],
                        ast,
                        result.semantic_results,
                        result.codegen_result,
                    )
                    doc_dir = os.path.dirname(doc_output)
                    if doc_dir:
                        os.makedirs(doc_dir, exist_ok=True)
                    with open(doc_output, "w", encoding="utf-8") as f:
                        f.write(md_content)
                    result.doc_path = doc_output
                except Exception as e:
                    return self._finish_with_failure(
                        result,
                        ExitCode.IO,
                        "io",
                        f"Failed to write documentation file: {e}",
                        start,
                        exception=e,
                    )

            # Render success output
            result.ok = True
            result.exit_code = ExitCode.SUCCESS
            result.timing_ms = int((perf_counter() - start) * 1000)
            self._emit_success(result)
            return result

        except Exception as e:
            if self.output_format == OutputFormat.HUMAN:
                print(f"Unexpected error: {e}", file=sys.stderr)
            result.failure = FailureInfo(
                category="internal",
                message=str(e),
                exception_type=type(e).__name__,
            )
            result.ok = False
            result.exit_code = ExitCode.INTERNAL
            result.timing_ms = int((perf_counter() - start) * 1000)
            if self.output_format == OutputFormat.JSON:
                print(json.dumps(self._to_json_payload(result), indent=2))
            return result

    def _emit_success(self, result: CompilationResult) -> None:
        if self.output_format == OutputFormat.JSON:
            print(json.dumps(self._to_json_payload(result), indent=2))
            return

        if self.mode in {CompileMode.TOKENS, CompileMode.AST}:
            self.console_formatter.display_compilation(
                result.tokens or [], result.ast, result.source_code, result.input_path
            )
        elif self.mode == CompileMode.SEMANTIC:
            self.console_formatter.display_through_semantic(
                result.input_path,
                result.source_code,
                result.tokens or [],
                result.ast,
                result.semantic_results or {},
            )
        elif self.mode in {CompileMode.PIPELINE, CompileMode.DOC, CompileMode.COMPILE}:
            self.console_formatter.display_full_pipeline(
                result.input_path,
                result.source_code,
                result.tokens or [],
                result.ast,
                result.semantic_results or {},
                result.codegen_result or {},
            )
        elif self.verbose:
            self.console_formatter.display_full_pipeline(
                result.input_path,
                result.source_code,
                result.tokens or [],
                result.ast,
                result.semantic_results,
                result.codegen_result,
            )

        if result.doc_path:
            console.print(f"[blue]📄[/blue] Documentation written to {result.doc_path}")

    def _backend_unsupported_import_errors(
        self,
        *,
        ast: ASTNode,
        module_resolver: Any,
        filename: str,
        source_lines: list[str],
    ) -> list[SemanticError]:
        """Reject file-backed modules until codegen can lower/link their symbols."""
        if ast.kind != NodeKind.PROGRAM:
            return []

        errors: list[SemanticError] = []
        for decl in ast.declarations or []:
            if decl.kind != NodeKind.IMPORT:
                continue
            module_path = decl.module_path or ""
            if module_resolver.is_virtual_module(module_path):
                continue
            errors.append(
                SemanticError.from_type(
                    SemanticErrorType.UNSUPPORTED_IMPORT,
                    span=decl.span,
                    filename=filename,
                    source_lines=source_lines,
                    custom_message=(
                        f"File-backed import '{module_path}' resolves, but {self.backend} "
                        "backend lowering/linking for local modules is not implemented yet"
                    ),
                )
            )
        return errors

    def _backend_unsupported_feature_errors(
        self,
        *,
        ast: ASTNode,
        filename: str,
        source_lines: list[str],
    ) -> list[SemanticError]:
        """Reject parsed syntax that currently has no backend ABI/lowering."""
        errors: list[SemanticError] = []
        stack: list[Any] = [ast]
        seen: set[int] = set()

        while stack:
            value = stack.pop()
            if isinstance(value, ASTNode):
                node_id = id(value)
                if node_id in seen:
                    continue
                seen.add(node_id)

                if getattr(value, "is_variadic", False):
                    errors.append(
                        SemanticError.from_type(
                            SemanticErrorType.UNSUPPORTED_FEATURE,
                            span=value.span,
                            filename=filename,
                            source_lines=source_lines,
                            custom_message=(
                                "Variadic parameters are parsed for future support, "
                                f"but {self.backend} backend ABI/lowering is not implemented yet"
                            ),
                        )
                    )

                stack.extend(value.__dict__.values())
            elif isinstance(value, (list, tuple)):
                stack.extend(value)

        return errors

    def _finish_with_failure(
        self,
        result: CompilationResult,
        exit_code: ExitCode,
        category: str,
        message: str,
        start_time: float,
        *,
        compiler_error: Optional[CompilerError] = None,
        parse_error: Optional[Exception] = None,
        semantic_errors: Optional[list[Any]] = None,
        exception: Optional[Exception] = None,
    ) -> CompilationResult:
        details: list[dict[str, Any]] = []
        span = None

        if semantic_errors:
            details = [self._error_to_detail(err, result.input_path) for err in semantic_errors]
        elif parse_error is not None:
            details = [self._error_to_detail(parse_error, result.input_path)]
        elif compiler_error is not None:
            details = [self._error_to_detail(compiler_error, result.input_path)]
        elif exception is not None:
            details = [
                {
                    "type": type(exception).__name__,
                    "message": str(exception),
                    "file": result.input_path,
                }
            ]

        if details:
            span = details[0].get("span")

        result.ok = False
        result.exit_code = exit_code
        result.failure = FailureInfo(
            category=category,
            message=message,
            details=details,
            span=span,
            exception_type=type(exception).__name__ if exception else None,
        )
        result.timing_ms = int((perf_counter() - start_time) * 1000)

        if self.output_format == OutputFormat.JSON:
            print(json.dumps(self._to_json_payload(result), indent=2))
        else:
            if semantic_errors:
                display_errors(semantic_errors, console)
            elif parse_error is not None:
                if isinstance(parse_error, CompilerError):
                    display_error(parse_error, console)
                else:
                    console.print(f"[red]✗[/red] {parse_error}")
            elif compiler_error is not None:
                display_error(compiler_error, console)
            else:
                console.print(f"[red]✗[/red] {message}")

        return result

    def _to_json_payload(self, result: CompilationResult) -> dict[str, Any]:
        formatted = self.json_formatter.format_compilation(
            result.tokens or [],
            result.ast,
            result.source_code,
            result.input_path,
        )

        payload: dict[str, Any] = {
            "schema_version": "2.0",
            "mode": result.mode.value,
            "status": "ok" if result.ok else "error",
            "input": result.input_path,
            "backend": result.backend,
            "timing_ms": result.timing_ms,
            "stages": {},
            "artifacts": {},
        }

        if "tokenize" in result.stages:
            payload["stages"]["tokenize"] = {
                **result.stages["tokenize"],
                "tokens": formatted["tokens"],
            }

        if "parse" in result.stages:
            payload["stages"]["parse"] = {
                **result.stages["parse"],
                "ast": formatted["ast"] if result.stages["parse"].get("ok") else None,
            }

        if result.semantic_results is not None:
            payload["stages"]["semantic"] = {
                "ok": result.stages.get("semantic", {}).get("ok", False),
                "passes": result.semantic_results.get("passes", []),
                "errors": [
                    self._error_to_detail(err, result.input_path)
                    for err in result.semantic_results.get("errors", [])
                ],
            }

        if result.codegen_result is not None:
            payload["stages"]["codegen"] = {
                "ok": True,
                "bytes": result.codegen_result.get("bytes", 0),
                "output_code": result.codegen_result.get("output_code", ""),
            }

        if result.output_path and Path(result.output_path).exists():
            payload["artifacts"]["output_path"] = result.output_path
        if result.doc_path and Path(result.doc_path).exists():
            payload["artifacts"]["doc_path"] = result.doc_path

        if not result.ok and result.failure is not None:
            payload["error"] = {
                "category": result.failure.category,
                "message": result.failure.message,
                "details": result.failure.details,
                "span": result.failure.span,
                "exception_type": result.failure.exception_type,
            }

        return payload

    def _error_to_detail(self, err: Any, file_path: str) -> dict[str, Any]:
        detail: dict[str, Any] = {
            "type": type(err).__name__,
            "message": str(err),
            "file": file_path,
        }
        span = getattr(err, "span", None)
        if span is not None:
            detail["span"] = {
                "start_line": getattr(span, "start_line", None),
                "start_column": getattr(span, "start_column", None),
                "end_line": getattr(span, "end_line", None),
                "end_column": getattr(span, "end_column", None),
                "length": getattr(span, "length", None),
            }
        return detail

    def compile_project(self, project_root: str, output_dir: str = "build") -> bool:
        """
        Compile all .a7 files in a project directory.
        """
        project_path = Path(project_root)
        if not project_path.exists():
            print(f"Project directory not found: {project_root}", file=sys.stderr)
            return False

        a7_files = list(project_path.rglob("*.a7"))
        if not a7_files:
            print(f"No .a7 files found in {project_root}", file=sys.stderr)
            return False

        if self.verbose:
            print(f"Found {len(a7_files)} source files")

        success_count = 0
        extension = self._get_backend_extension()
        for a7_file in a7_files:
            rel_path = a7_file.relative_to(project_path)
            output_path = Path(output_dir) / rel_path.with_suffix(extension)
            if self.compile_file(str(a7_file), str(output_path)):
                success_count += 1

        if success_count == len(a7_files):
            if self.verbose:
                print(f"Successfully compiled {success_count}/{len(a7_files)} files")
            return True

        print(
            f"Compilation failed: {success_count}/{len(a7_files)} files compiled",
            file=sys.stderr,
        )
        return False

    def _generate_output_path(self, input_path: str) -> str:
        extension = self._get_backend_extension()
        return input_path.replace(".a7", extension)

    def _get_backend_extension(self) -> str:
        try:
            return get_backend(self.backend).file_extension
        except Exception:
            # Keep compile-mode output-path generation resilient for invalid backends.
            return ".out"


def compile_a7_file(
    input_path: str,
    output_path: Optional[str] = None,
    *,
    backend: str = "zig",
    verbose: bool = False,
    mode: CompileMode | str = CompileMode.COMPILE,
    output_format: OutputFormat | str = OutputFormat.HUMAN,
    doc_path: Optional[str] = None,
) -> bool:
    """
    Convenience function to compile a single A7 file.
    """
    compiler = A7Compiler(
        backend=backend,
        verbose=verbose,
        mode=mode,
        output_format=output_format,
        doc_path=doc_path,
    )
    return compiler.compile_file(input_path, output_path)


def compile_a7_project(
    project_root: str,
    output_dir: str = "build",
    verbose: bool = False,
) -> bool:
    """
    Convenience function to compile an A7 project.
    """
    compiler = A7Compiler(verbose=verbose, mode=CompileMode.COMPILE)
    return compiler.compile_project(project_root, output_dir)
