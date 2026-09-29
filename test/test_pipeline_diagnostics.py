"""Source diagnostics through the real CLI, without parser or pass substitutes.

Locations below come from the fixture text, not serialized compiler snapshots.
These compile-only cases do not qualify native execution or memory safety.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from a7.compile import ExitCode


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_json_compile(source: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), "--format", "json", str(source)],
        cwd=source.parent,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert "Traceback" not in result.stderr
    assert payload["status"] == "error"
    assert "codegen" not in payload["stages"]
    assert not source.with_suffix(".zig").exists()
    return result, payload


@pytest.mark.parametrize(
    ("statement", "exit_code", "category", "needle", "column"),
    [
        pytest.param("    x := `", ExitCode.TOKENIZE, "tokenize", "`", 10, id="token"),
        pytest.param("    x := )", ExitCode.PARSE, "parse", "expression", 10, id="parse"),
        pytest.param("    unknown()", ExitCode.SEMANTIC, "semantic", "unknown", 5, id="semantic"),
    ],
)
def test_cli_source_diagnostic_points_to_offending_token(
    tmp_path, statement, exit_code, category, needle, column
):
    source = tmp_path / "main.a7"
    original = f"// heading\nmain :: fn() {{\n{statement}\n}}\n"
    source.write_text(original, encoding="utf-8")

    result, payload = run_json_compile(source)

    assert source.read_text(encoding="utf-8") == original
    assert result.returncode == exit_code
    assert payload["error"]["category"] == category
    detail = next(item for item in payload["error"]["details"] if needle in item["message"])
    assert detail["file"] == str(source)
    assert detail["span"]["start_line"] == 3
    assert detail["span"]["start_column"] == column


def test_missing_import_diagnostic_locates_import_declaration(tmp_path):
    source = tmp_path / "main.a7"
    source.write_text(
        '// heading\nmissing :: import "missing/module"\nmain :: fn() {}\n',
        encoding="utf-8",
    )

    result, payload = run_json_compile(source)

    assert result.returncode == ExitCode.SEMANTIC
    detail = next(item for item in payload["error"]["details"] if "missing/module" in item["message"])
    assert detail["file"] == str(source)
    # The importing declaration is the editable source of a missing module.
    # Do not prescribe which token within that declaration the diagnostic uses.
    assert detail.get("span") is not None, "Missing import has no source location"
    assert detail["span"]["start_line"] == 2
    assert 1 <= detail["span"]["start_column"] <= len(source.read_text().splitlines()[1])


def test_imported_parse_error_is_a_source_failure_with_module_location(tmp_path):
    source = tmp_path / "main.a7"
    module = tmp_path / "helper.a7"
    source.write_text('helper :: import "helper"\nmain :: fn() {}\n', encoding="utf-8")
    module.write_text('// helper header\npub work :: fn() {\n    x := )\n}\n', encoding="utf-8")

    result, payload = run_json_compile(source)

    # An import wrapper may report semantic failure; a parser source error must
    # never become an internal compiler fault merely because it is in a module.
    assert result.returncode in {ExitCode.PARSE, ExitCode.SEMANTIC}
    assert payload["error"]["category"] in {"parse", "semantic"}
    details = payload["error"]["details"]
    assert any(
        item["file"] == str(module)
        and item.get("span", {}).get("start_line") == 3
        for item in details
    ), details


def test_imported_semantic_error_preserves_origin_file(tmp_path):
    source = tmp_path / "main.a7"
    module = tmp_path / "helper.a7"
    source.write_text('helper :: import "helper"\nmain :: fn() {}\n', encoding="utf-8")
    module.write_text('// helper header\npub work :: fn() {\n    unknown()\n}\n', encoding="utf-8")

    result, payload = run_json_compile(source)

    assert result.returncode == ExitCode.SEMANTIC
    detail = next(item for item in payload["error"]["details"] if "unknown" in item["message"])
    assert detail["file"] == str(module)
    assert detail["span"]["start_line"] == 3
    assert detail["span"]["start_column"] == 5


def test_nested_missing_import_points_to_immediate_importer(tmp_path):
    source = tmp_path / "main.a7"
    helper = tmp_path / "helper.a7"
    source.write_text('helper :: import "helper"\nmain :: fn() {}\n')
    helper.write_text('// helper header\nmissing :: import "absent"\n')
    result, payload = run_json_compile(source)
    assert result.returncode == ExitCode.SEMANTIC
    detail = next(item for item in payload["error"]["details"] if "absent" in item["message"])
    assert detail["file"] == str(helper)
    assert detail["span"]["start_line"] == 2
