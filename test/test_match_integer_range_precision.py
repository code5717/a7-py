"""Literal/range overlap preserves the subject's integer precision."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("endpoint,literal,expected", [
    ("9007199254740992", "9007199254740993", 0),
    ("9007199254740993", "9007199254740993", 6),
    ("-9007199254740992", "-9007199254740993", 0),
    ("-9007199254740993", "-9007199254740993", 6),
    ("9223372036854775807", "9223372036854775807", 6),
])
def test_integer_singleton_overlap_in_both_orders(tmp_path, reverse, endpoint, literal, expected):
    patterns = [f"{endpoint}..{endpoint}", literal]
    if reverse:
        patterns.reverse()
    _check(tmp_path, "i64", patterns, expected)


@pytest.mark.parametrize("type_name,patterns,expected", [
    ("i64", ["2..2", "3"], 0),
    ("i64", ["2..3", "3"], 6),
    ("i64", ["9007199254740992", "9007199254740993"], 0),
    ("i64", ["9007199254740992..9007199254740992", "9007199254740993..9007199254740993"], 0),
    ("f32", ["1.0", "1.00000001"], 6),
    ("f32", ["1.0", "1.00000011920928955078125"], 0),
    ("f64", ["1.0", "1.00000001"], 0),
    ("u64", ["18446744073709551614..18446744073709551614", "18446744073709551615"], 0),
    ("u64", ["18446744073709551615..18446744073709551615", "18446744073709551615"], 6),
    ("char", ["'a'..'a'", "'b'"], 0),
    ("char", ["'a'..'b'", "'b'"], 6),
])
def test_existing_numeric_and_character_controls(tmp_path, type_name, patterns, expected):
    _check(tmp_path, type_name, patterns, expected)


def _check(tmp_path, type_name, patterns, expected):
    source = tmp_path / "match.a7"
    source.write_text(
        f"pick :: fn(x: {type_name}) i32 {{\n"
        "    ret match x {\n"
        f"        case {patterns[0]}: 1\n"
        f"        case {patterns[1]}: 2\n"
        "        else: 0\n    }\n}\nmain :: fn() {}\n"
    )
    output = tmp_path / "match.zig"
    result = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(source), "--format", "json", "-o", str(output)],
        cwd=tmp_path, capture_output=True, text=True,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == expected, payload.get("error")
    assert not result.stderr
    if expected == 0:
        assert payload.get("error") is None
        assert output.is_file()
    else:
        assert payload["error"]["category"] == "semantic"
        details = payload["error"]["details"]
        assert len(details) == 1
        assert details[0]["code"] == "unreachable_code"
        assert "pattern" in details[0]["message"]
        assert details[0]["span"]["start_line"] == 4
        assert not output.exists()
