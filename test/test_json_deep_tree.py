"""`--format json` on an AST nested far past Python's recursion limit.

`a.b.b.b...` parses in a loop, so the tree depth equals the chain length
and no parser nesting cap applies.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from a7.compile import ExitCode

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_chain(tmp_path, links, mode):
    source = tmp_path / "deep.a7"
    source.write_text("main :: fn() {\n    x := a" + ".b" * links + "\n}\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "--mode", mode, "--format", "json", str(source)],
        cwd=PROJECT_ROOT, capture_output=True, text=True, env=env,
    )


def load_deep(text):
    # json.loads recurses per level; the payload is about three levels per link.
    previous = sys.getrecursionlimit()
    sys.setrecursionlimit(50_000)
    try:
        return json.loads(text)
    finally:
        sys.setrecursionlimit(previous)


def test_ast_mode_emits_the_whole_deep_tree(tmp_path):
    links = 2_000
    result = run_chain(tmp_path, links, "ast")

    assert result.returncode == ExitCode.SUCCESS, result.stderr[-500:]
    payload = load_deep(result.stdout)
    assert payload["status"] == "ok"
    node = payload["stages"]["parse"]["ast"]["declarations"][0]["body"]["statements"][0]["value"]
    depth = 0
    while node["kind"] == "FIELD_ACCESS":
        node = node["object"]
        depth += 1
    assert depth == links
    assert node == {**node, "kind": "IDENTIFIER", "name": "a"}


@pytest.mark.parametrize("mode", ["semantic", "pipeline", "doc"])
def test_deep_tree_failure_is_reported_as_json(tmp_path, mode):
    # `a` is undefined, so the program must fail. Today the type checker
    # recurses per link and the failure is internal (exit 8); once it walks
    # iteratively the failure is semantic (exit 6). Either way the report
    # is valid JSON on stdout whose category matches the exit code.
    result = run_chain(tmp_path, 2_000, mode)

    assert "Traceback" not in result.stderr
    categories = {ExitCode.SEMANTIC: "semantic", ExitCode.INTERNAL: "internal"}
    assert result.returncode in categories, result.stderr[-500:]
    payload = load_deep(result.stdout)
    assert payload["status"] == "error"
    assert payload["error"]["category"] == categories[result.returncode]


def test_ten_thousand_links_exit_cleanly(tmp_path):
    result = run_chain(tmp_path, 10_000, "ast")

    assert result.returncode == ExitCode.SUCCESS, result.stderr[-500:]
    assert result.stderr == ""
    assert result.stdout.startswith('{\n  "schema_version"')
    assert result.stdout.endswith("}\n")


def test_ordinary_payload_keeps_the_two_space_json_layout():
    # The iterative writer must print what json.dumps(indent=2) printed.
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "--mode", "pipeline", "--format", "json",
         "examples/026_binary_tree.a7"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, env=env,
    )

    assert result.returncode == ExitCode.SUCCESS, result.stderr
    assert result.stdout == json.dumps(json.loads(result.stdout), indent=2) + "\n"
