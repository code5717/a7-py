"""The console, markdown and JSON AST views show the same statements.

The program puts one assignment with a distinct literal in every nested
position: loop bodies, both `if` branches of an else-if chain, match cases,
the match `else`, and a deferred block. Each view must show every literal.
"""

import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from a7.ast_nodes import ASTNode
from a7.compile import ExitCode
from a7.formatters.ast_walk import CHILD_FIELDS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Literal -> where it sits in the source.
MARKERS = {
    "1101": "for body",
    "1102": "while body",
    "1103": "for-in body",
    "1104": "if branch",
    "1105": "else-if branch",
    "1106": "final else branch",
    "1107": "match case block",
    "1108": "match case single statement",
    "1109": "match else",
    "1110": "deferred block",
}
SOURCE = """io :: import "std/io"

Color :: enum { Red, Green }

main :: fn() {
    total := 0
    for i := 0; i < 3; i += 1 {
        total += 1101
    }
    while total > 100000 {
        total -= 1102
    }
    xs: [3]i32 = [1, 2, 3]
    for x in xs {
        total += 1103
    }
    if total == 1 {
        total = 1104
    } else if total == 2 {
        total = 1105
    } else {
        total = 1106
    }
    c := Color.Red
    match c {
        case Color.Red: {
            total = 1107
        }
        case Color.Green: total = 1108
    }
    match total {
        case 1: total = 7
        else: {
            total = 1109
        }
    }
    defer {
        total = 1110
    }
    io.println("{}", total)
}
"""


def run_cli(args, cwd):
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT), "NO_COLOR": "1", "COLUMNS": "200"}
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), *map(str, args)],
        cwd=cwd, capture_output=True, text=True, env=env,
    )


@pytest.fixture(scope="module")
def views(tmp_path_factory):
    folder = tmp_path_factory.mktemp("views")
    (folder / "views.a7").write_text(SOURCE, encoding="utf-8")
    console = run_cli(["--mode", "ast", "views.a7"], folder)
    as_json = run_cli(["--mode", "ast", "--format", "json", "views.a7"], folder)
    doc = run_cli(["--mode", "doc", "views.a7"], folder)
    for result in (console, as_json, doc):
        assert result.returncode == ExitCode.SUCCESS, result.stdout + result.stderr
    report = (folder / "views.md").read_text(encoding="utf-8")
    tree = report.split("### AST Structure", 1)[1].split("## 4. Stage 3", 1)[0]
    return {
        "console": console.stdout.split("PARSING RESULTS", 1)[1],
        "markdown": tree,
        "json": json.dumps(json.loads(as_json.stdout)["stages"]["parse"]["ast"]),
    }


@pytest.mark.parametrize("view", ["console", "markdown", "json"])
def test_view_shows_every_nested_statement(views, view):
    missing = [place for literal, place in MARKERS.items() if literal not in views[view]]
    assert missing == []


def test_console_tree_nests_branches_under_their_statement(views):
    lines = views["console"].splitlines()
    chain = [text for text in lines if "IF_STMT" in text or "ELSE → BLOCK" in text][:3]

    def depth(text):
        return len(text) - len(text.lstrip("│├└─ "))

    # The else-if hangs under the first `if`, the final else under the else-if.
    assert [text.lstrip("│├└─ ") for text in chain] == [
        "IF_STMT binary_op eq",
        "ELSE → IF_STMT binary_op eq",
        "ELSE → BLOCK (1 stmts)",
    ]
    assert depth(chain[0]) < depth(chain[1]) < depth(chain[2])
    assert any(text.endswith("CASE_BRANCH Color.Red") for text in lines)
    assert any(text.endswith("CASE_BRANCH Color.Green") for text in lines)


def test_markdown_tree_names_the_field_of_each_branch(views):
    assert "else_stmt: IF_STMT" in views["markdown"]
    assert "cases: CASE_BRANCH" in views["markdown"]
    assert "else_case: BLOCK" in views["markdown"]


def test_every_node_valued_ast_field_is_a_shared_child_field():
    # A child field left out of CHILD_FIELDS disappears from all three views.
    # Two node-annotated fields are not source children: the parser stores
    # `struct_type` as a type name string, and `resolved_type` is an inferred
    # annotation the AST preprocessor adds after parsing.
    not_children = {"struct_type", "resolved_type"}
    node_fields = {
        field.name for field in dataclasses.fields(ASTNode)
        if "ASTNode" in str(field.type)
    }
    assert node_fields - set(CHILD_FIELDS) == not_children


def test_markdown_report_survives_a_code_fence_in_the_source(tmp_path):
    source = 'io :: import "std/io"\n// ```\n// ````\nmain :: fn() {\n    io.println("é")\n}\n'
    (tmp_path / "fence.a7").write_text(source, encoding="utf-8")

    result = run_cli(["--mode", "doc", "fence.a7"], tmp_path)

    assert result.returncode == ExitCode.SUCCESS, result.stdout + result.stderr
    report = (tmp_path / "fence.md").read_text(encoding="utf-8")
    section = report.split("## 1. Source Code", 1)[1].split("## 2. Stage 1", 1)[0]
    # The fence is longer than the four backticks in the source, so the
    # whole source sits inside one block.
    assert "`````\n" + source.rstrip() + "\n`````" in section
    # `é` is two bytes in UTF-8: the size is bytes, not characters.
    assert f"**Size:** {len(source.encode('utf-8'))} bytes" in section
    assert len(source.encode("utf-8")) == len(source) + 1
