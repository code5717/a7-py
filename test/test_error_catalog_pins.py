"""Pins for the Phase 1B error review: JSON hardening, token-count
definition, and imported-file stage coverage.

Imported-file cases pin current behavior with worker C attribution
(import-decl spans in the entry file) present. All tests pass.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run(
        [sys.executable, str(ROOT / "main.py"), *args],
        cwd=cwd, capture_output=True, text=True, env=env,
    )


def run_json(args: list[str], cwd: Path) -> tuple[int, dict]:
    proc = run_cli([*args, "--format", "json"], cwd)
    assert "Traceback" not in proc.stderr, proc.stderr
    return proc.returncode, json.loads(proc.stdout)


def test_safe_json_value_degrades_non_serializable_to_str() -> None:
    from a7.formatters.json_formatter import _safe_json_value

    assert _safe_json_value(Fraction(1, 3)) == "1/3"
    assert _safe_json_value(object()) != ""
    assert _safe_json_value(9) == 9
    assert _safe_json_value("s") == "s"
    assert _safe_json_value(None) is None
    assert _safe_json_value([Fraction(1, 2), 1]) == ["1/2", 1]


def test_literal_value_fraction_survives_json_dump() -> None:
    from a7.formatters.json_formatter import JSONFormatter

    node = SimpleNamespace(
        kind=SimpleNamespace(name="LITERAL"),
        span=None,
        literal_kind=SimpleNamespace(name="INT"),
        literal_value=Fraction(7, 1),
        raw_text="7",
    )
    payload = JSONFormatter()._ast_node_shallow_dict(node)
    assert payload["literal_value"] == "7"
    json.dumps(payload)  # must not raise


def test_safe_json_dumps_never_throws_on_stray_values() -> None:
    from a7.compile import _safe_json_dumps

    text = _safe_json_dumps({"detail": {"value": object()}, "span": None})
    assert json.loads(text)["detail"]["value"]


def test_token_count_excludes_eof_everywhere(tmp_path: Path) -> None:
    source = tmp_path / "tiny.a7"
    source.write_text("main :: fn() {\n    x := 1\n}\n", encoding="utf-8")
    code, payload = run_json(["--mode", "tokens", str(source)], ROOT)
    assert code == 0, payload.get("error")
    tokens = payload["stages"]["tokenize"]["tokens"]
    assert payload["stages"]["tokenize"]["token_count"] == len(tokens)
    assert all(token["type"] != "EOF" for token in tokens)


def test_missing_imported_module_is_io_with_import_span(tmp_path: Path) -> None:
    (tmp_path / "main.a7").write_text(
        'h :: import "nosuchmod"\nio :: import "std/io"\n\n'
        'main :: fn() {\n    io.println("{}", h.value())\n}\n',
        encoding="utf-8",
    )
    code, payload = run_json(["--mode", "semantic", str(tmp_path / "main.a7")], ROOT)
    assert code == 3, payload.get("error")
    assert payload["error"]["category"] == "io"
    detail = payload["error"]["details"][0]
    assert detail["span"]["start_line"] == 1
    assert "nosuchmod" in detail["message"]


def test_missing_transitive_module_names_importing_file(tmp_path: Path) -> None:
    (tmp_path / "helper.a7").write_text(
        'x :: import "nosuchdeep"\n\npub value :: fn() i32 {\n    ret 1\n}\n',
        encoding="utf-8",
    )
    (tmp_path / "main.a7").write_text(
        'h :: import "helper"\nio :: import "std/io"\n\n'
        'main :: fn() {\n    io.println("{}", h.value())\n}\n',
        encoding="utf-8",
    )
    code, payload = run_json(["--mode", "semantic", str(tmp_path / "main.a7")], ROOT)
    assert code == 3, payload.get("error")
    assert payload["error"]["category"] == "io"
    detail = payload["error"]["details"][0]
    assert detail["file"].endswith("helper.a7")
    assert detail["span"]["start_line"] == 1


def test_parse_error_in_imported_module_stays_parse(tmp_path: Path) -> None:
    (tmp_path / "helper.a7").write_text("pub value :: fn( {\n", encoding="utf-8")
    (tmp_path / "main.a7").write_text(
        'h :: import "helper"\nio :: import "std/io"\n\n'
        'main :: fn() {\n    io.println("{}", h.value())\n}\n',
        encoding="utf-8",
    )
    code, payload = run_json(["--mode", "semantic", str(tmp_path / "main.a7")], ROOT)
    assert code == 5, payload.get("error")
    assert payload["error"]["category"] == "parse"


def test_circular_import_is_semantic_with_import_span(tmp_path: Path) -> None:
    (tmp_path / "mod_a.a7").write_text(
        'b :: import "mod_b"\n\npub avalue :: fn() i32 {\n    ret 1\n}\n',
        encoding="utf-8",
    )
    (tmp_path / "mod_b.a7").write_text(
        'a :: import "mod_a"\n\npub bvalue :: fn() i32 {\n    ret 2\n}\n',
        encoding="utf-8",
    )
    (tmp_path / "main.a7").write_text(
        'a :: import "mod_a"\nio :: import "std/io"\n\n'
        'main :: fn() {\n    io.println("{}", a.avalue())\n}\n',
        encoding="utf-8",
    )
    code, payload = run_json(["--mode", "semantic", str(tmp_path / "main.a7")], ROOT)
    assert code == 6, payload.get("error")
    assert payload["error"]["category"] == "semantic"
    assert "ircular" in payload["error"]["details"][0]["message"]
    assert payload["error"]["details"][0]["span"]["start_line"] == 1


def test_type_error_through_import_is_semantic(tmp_path: Path) -> None:
    (tmp_path / "helper.a7").write_text(
        'pub value :: fn() i32 {\n    ret "nope"\n}\n', encoding="utf-8"
    )
    (tmp_path / "main.a7").write_text(
        'h :: import "helper"\nio :: import "std/io"\n\n'
        'main :: fn() {\n    io.println("{}", h.value())\n}\n',
        encoding="utf-8",
    )
    code, payload = run_json(["--mode", "semantic", str(tmp_path / "main.a7")], ROOT)
    assert code == 6, payload.get("error")
    assert payload["error"]["category"] == "semantic"
    assert payload["error"]["details"]
