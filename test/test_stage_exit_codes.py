"""Stage-to-exit-code mapping and the no-recursion invariant for examples.

Exit codes are the compiler's own vocabulary (a7/compile.py ExitCode):
parse failure is 5, semantic and safety failures share 6.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXIT_PARSE = 5
EXIT_SEMANTIC = 6


def compile_result(source: Path, output: Path):
    return subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(source), "--output", str(output),
         "--format", "json"],
        cwd=ROOT, capture_output=True, text=True,
    )


def test_parse_failure_exits_5(tmp_path):
    source = tmp_path / "bad_parse.a7"
    source.write_text("main :: fn( {\n", encoding="utf-8")
    result = compile_result(source, tmp_path / "main.zig")
    assert result.returncode == EXIT_PARSE, result.stdout + result.stderr


def test_semantic_failure_exits_6(tmp_path):
    source = tmp_path / "bad_type.a7"
    source.write_text('main :: fn() {\n    x: i32 = "hello"\n}\n', encoding="utf-8")
    result = compile_result(source, tmp_path / "main.zig")
    assert result.returncode == EXIT_SEMANTIC, result.stdout + result.stderr


def test_safety_failure_exits_6(tmp_path):
    source = ROOT / "examples" / "rejected" / "divisor_not_proven.a7"
    result = compile_result(source, tmp_path / "main.zig")
    assert result.returncode == EXIT_SEMANTIC, result.stdout + result.stderr


def test_parse_and_semantic_exit_codes_are_disjoint():
    from a7.compile import ExitCode

    assert ExitCode.PARSE == EXIT_PARSE
    assert ExitCode.SEMANTIC == EXIT_SEMANTIC
    assert ExitCode.PARSE != ExitCode.SEMANTIC


def test_examples_hold_no_recursive_functions():
    """Source recursion is banned; no working example may rely on it."""
    from a7.passes.name_resolution import NameResolutionPass
    from a7.passes.semantic_validator import SemanticValidationPass
    from a7.passes.type_checker import TypeCheckingPass
    from a7.parser import Parser
    from a7.tokens import Tokenizer

    offenders = []
    for path in sorted((ROOT / "examples").glob("*.a7")):
        program = Parser(Tokenizer(path.read_text(encoding="utf-8")).tokenize()).parse()
        resolver = NameResolutionPass()
        symbols = resolver.analyze(program, str(path))
        checker = TypeCheckingPass(symbols)
        checker.analyze(program, str(path))
        validator = SemanticValidationPass(symbols, checker.node_types)
        validator.analyze(program, str(path))
        errors = list(resolver.errors) + list(checker.errors) + list(validator.errors)
        if any("recursi" in str(error).lower() for error in errors):
            offenders.append(path.name)
    assert not offenders, f"examples rely on banned recursion: {offenders}"
