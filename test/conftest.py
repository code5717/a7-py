"""Shared test helpers. Import is cheap; heavy imports stay lazy inside helpers."""

from __future__ import annotations

import os
import shutil

import pytest


def has_zig() -> bool:
    override = os.environ.get("A7_TEST_ZIG")
    if override:
        return True
    return shutil.which("zig") is not None


def zig_binary() -> str:
    override = os.environ.get("A7_TEST_ZIG")
    if override:
        return override
    found = shutil.which("zig")
    assert found is not None, "zig not found on PATH (set A7_TEST_ZIG to override)"
    return found


def zig_version(binary: str) -> str:
    import subprocess

    result = subprocess.run(
        [binary, "version"], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return result.stdout.strip()


@pytest.fixture(scope="session")
def zig() -> str:
    binary = zig_binary()
    assert zig_version(binary) == "0.16.0", f"expected zig 0.16.0, got {zig_version(binary)}"
    return binary


@pytest.fixture(scope="session")
def zig_cache(tmp_path_factory):
    return tmp_path_factory.mktemp("zig-cache")


def parse_program(source: str):
    from a7.parser import Parser
    from a7.tokens import Tokenizer

    tokenizer = Tokenizer(source)
    tokens = tokenizer.tokenize()
    return Parser(tokens).parse()


def run_semantic_analysis(source: str, filename: str = "test.a7"):
    from a7.passes.name_resolution import NameResolutionPass
    from a7.passes.semantic_validator import SemanticValidationPass
    from a7.passes.type_checker import TypeCheckingPass

    program = parse_program(source)
    resolver = NameResolutionPass()
    symbols = resolver.analyze(program, filename)
    checker = TypeCheckingPass(symbols)
    checker.analyze(program, filename)
    validator = SemanticValidationPass(symbols, checker.node_types)
    validator.analyze(program, filename)
    return {
        "program": program,
        "symbols": symbols,
        "resolver_errors": list(resolver.errors),
        "checker_errors": list(checker.errors),
        "validator_errors": list(validator.errors),
    }
