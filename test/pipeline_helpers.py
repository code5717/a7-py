"""Snippet helpers for the semantic test files.

Each helper runs the snippet through the whole compiler (tokenize, parse,
every semantic pass, the safety pass, codegen) with the conftest helpers.
A snippet with no `main :: fn` is compiled as a library, so it still reaches
the safety pass and codegen.

Import `pipeline_tmp` next to the helpers: pytest then applies it to every
test in the importing module, and the helpers write under that test's
`tmp_path`.
"""

from __future__ import annotations

import re

import pytest

from conftest import expect_exit, expect_ok

PARSE_EXIT = 5
SEMANTIC_EXIT = 6

_MAIN = re.compile(r"^\s*main\s*::\s*fn\b", re.MULTILINE)
_current: dict = {}


@pytest.fixture(autouse=True)
def pipeline_tmp(tmp_path):
    _current["tmp_path"] = tmp_path
    yield
    _current.clear()


def _tmp_path():
    assert "tmp_path" in _current, "import pipeline_tmp into the test module"
    return _current["tmp_path"]


def is_library(source: str) -> bool:
    return _MAIN.search(source) is None


def expect_success(source: str) -> bool:
    """The compiler must accept `source` and emit Zig (exit 0)."""
    expect_ok(source, _tmp_path(), is_library=is_library(source))
    return True


def expect_error(source: str, fragment: str) -> bool:
    """The compiler must exit 6 (semantic) and name `fragment`."""
    expect_exit(source, _tmp_path(), SEMANTIC_EXIT, fragment,
                is_library=is_library(source))
    return True


def expect_parse_error(source: str, fragment: str) -> bool:
    """The compiler must exit 5 (parse) and name `fragment`."""
    expect_exit(source, _tmp_path(), PARSE_EXIT, fragment,
                is_library=is_library(source))
    return True


def compile_to_zig(source: str, profile: str = "debug") -> str:
    """Zig text for `source`; fails on any compiler error at any stage.

    Uses the test's `tmp_path` when the importing module also imports
    `pipeline_tmp`; otherwise a temporary directory removed on return.
    """
    import tempfile
    from pathlib import Path

    def compile_in(directory) -> str:
        result = expect_ok(source, directory, profile=profile,
                           is_library=is_library(source))
        return Path(result.output_path).read_text(encoding="utf-8")

    if "tmp_path" in _current:
        return compile_in(_current["tmp_path"])
    with tempfile.TemporaryDirectory(prefix="a7-test-") as directory:
        return compile_in(Path(directory))
