"""JSON output must preserve match expression and statement fallback shapes."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_json(path, *args):
    result = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(path), "--format", "json", *args],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert "Traceback" not in result.stderr, result.stderr
    return result.returncode, json.loads(result.stdout)


def nodes(value):
    work = [value]
    while work:
        current = work.pop()
        if isinstance(current, dict):
            if "kind" in current:
                yield current
            work.extend(current.values())
        elif isinstance(current, list):
            work.extend(current)


@pytest.mark.parametrize("example", ["025_linked_list.a7", "026_binary_tree.a7"])
def test_example_match_expression_ast_is_serializable(example):
    code, payload = run_json(ROOT / "examples" / example, "--mode", "ast")
    assert code == 0, payload.get("error")
    matches = [node for node in nodes(payload["stages"]["parse"]["ast"]) if node["kind"] == "MATCH_EXPR"]
    assert matches
    assert all(isinstance(node["else_case"], dict) and "kind" in node["else_case"] for node in matches)


@pytest.mark.parametrize("final_statement, expected_code", [("ret", 0), ("unknown()", 6)])
def test_match_json_survives_compile_success_and_semantic_failure(tmp_path, final_statement, expected_code):
    source = tmp_path / "match.a7"
    source.write_text('''main :: fn() {
    x := match 1 {
        case 1: 7
        else: 9
    }
    match x {
        case 7: { y := 3 }
        else: { y := 4 }
    }
    ''' + final_statement + "\n}\n")
    output = tmp_path / "match.zig"
    code, payload = run_json(source, "-o", str(output))
    assert code == expected_code, payload.get("error")
    ast_nodes = list(nodes(payload["stages"]["parse"]["ast"]))
    expression = next(node for node in ast_nodes if node["kind"] == "MATCH_EXPR")
    statement = next(node for node in ast_nodes if node["kind"] == "MATCH")
    assert expression["else_case"]["literal_value"] == 9
    assert isinstance(statement["else_case"], list)
    assert any(node.get("literal_value") == 4 for node in nodes(statement["else_case"]))
    if expected_code:
        assert payload["error"]["category"] == "semantic"
        assert "unknown" in json.dumps(payload["error"])
        assert not output.exists()
    else:
        assert output.exists()
