"""Language audit regressions through the public CLI and native output.

Malformed programs must produce diagnostics without replacing output artifacts.
The native control proves multiline array elements survive the complete pipeline.
"""

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from a7.ast_nodes import NodeKind
from a7.parser import parse_a7


ROOT = Path(__file__).resolve().parents[1]


def compile_source(tmp_path, source, mode="compile"):
    path = tmp_path / "case.a7"
    path.write_text(source)
    output = tmp_path / "case.zig"
    result = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(path), "--format", "json",
         "--mode", mode] + (["-o", str(output)] if mode == "compile" else []),
        capture_output=True, text=True, cwd=ROOT,
    )
    assert "Traceback" not in result.stderr
    return result.returncode, json.loads(result.stdout), output


@pytest.mark.parametrize("prefix", ["", 'io :: import "std/io"\n', "first :: 1\nsecond :: 2\n"])
def test_malformed_function_never_drops_main_or_promotes_local(tmp_path, prefix):
    sentinel = tmp_path / "case.zig"
    sentinel.write_text("existing output\n")
    code, payload, output = compile_source(
        tmp_path, prefix + "main :: fn() {\n    x, y := 10, 20\n}\n"
    )
    assert code == 5
    assert payload["error"]["category"] == "parse"
    assert payload["error"]["span"]["start_line"] == prefix.count("\n") + 2
    assert payload["error"]["span"]["start_column"] == 6
    assert payload["stages"]["parse"]["ast"] is None
    assert output.read_text() == "existing output\n"


@pytest.mark.parametrize("literal", ["1_", "1__2", "1_.0", "1.0_", "1e2_", "0xFF_", "0b1__0", "0o7_"])
def test_malformed_numeric_separators_are_tokenizer_diagnostics(tmp_path, literal):
    code, payload, output = compile_source(tmp_path, f"main :: fn() {{\n    value := {literal}\n}}\n")
    assert code == 4
    assert payload["error"]["category"] == "tokenize"
    assert "Invalid numeric literal" in payload["error"]["message"]
    assert payload["error"]["span"]["start_line"] == 2
    assert payload["error"]["span"]["start_column"] == 14
    assert not output.exists()


def test_valid_numeric_separators_keep_literal_values():
    ast = parse_a7("a :: 1_000\nb :: 0xF_F\nc :: 0b1_0\nd :: 0o1_0\ne :: 1.2_5e1_0")
    assert [node.value.literal_value for node in ast.declarations] == [1000, 255, 2, 8, 1.25e10]


def test_ellipsis_has_its_own_located_diagnostic(tmp_path):
    code, payload, output = compile_source(tmp_path, "main :: fn() {\n    a := [1, 2, 3]\n    b := a[0...2]\n}\n")
    assert code == 4
    assert "'...' operator is unsupported" in payload["error"]["message"]
    assert payload["error"]["span"]["start_line"] == 3
    assert payload["error"]["span"]["length"] == 3
    assert not output.exists()


def test_multiline_array_preserves_elements_through_native_execution(tmp_path):
    code, payload, output = compile_source(tmp_path, '''io :: import "std/io"
main :: fn() {
    values := [
        10,
        20,
        30,
    ]
    io.println("{} {} {}", values[0], values[1], values[2])
}
''')
    assert code == 0, payload.get("error")
    zig = shutil.which("zig")
    assert zig is not None, "Native verification requires Zig"
    binary = tmp_path / "array"
    built = subprocess.run([zig, "build-exe", str(output), f"-femit-bin={binary}"], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    run = subprocess.run([str(binary)], capture_output=True, text=True)
    assert (run.returncode, run.stdout, run.stderr) == (0, "10 20 30\n", "")


def test_unused_nested_recursion_is_rejected(tmp_path):
    code, payload, output = compile_source(tmp_path, "main :: fn() {\n    inner :: fn() { inner() }\n}\n")
    assert code == 6
    assert "Recursion is not allowed: Cycle: inner -> inner" in json.dumps(payload["error"])
    assert not output.exists()


def test_nonrecursive_nested_function_with_outer_name_is_not_a_cycle(tmp_path):
    code, payload, _ = compile_source(tmp_path, "outer :: fn() {}\nmain :: fn() {\n    outer :: fn() {}\n}\n", mode="semantic")
    assert code == 0, payload.get("error")


def test_large_program_has_all_declarations_without_stdout_warning(capsys):
    ast = parse_a7("\n".join(f"value_{index} :: {index}" for index in range(1001)))
    assert len(ast.declarations) == 1001
    assert ast.declarations[-1].name == "value_1000"
    assert all(node.kind == NodeKind.CONST for node in ast.declarations)
    assert capsys.readouterr().out == ""
