"""Char literal and `@` tokenizer errors name the real problem (exit 4)."""

import pytest

from conftest import expect_exit, expect_ok

TOKENIZE_EXIT = 4


def in_main(body: str) -> str:
    return "main :: fn() {\n" + body + "\n}\n"


@pytest.mark.parametrize(("literal", "fragment"), [
    ("''", "Empty char literal"),
    ("'ab'", "Too many characters in char literal"),
    ("'hello'", "use double quotes for a string"),
    ("'\\q'", "Invalid char escape sequence '\\q'"),
    ("'\\x4'", "'\\x' needs two hex digits"),
    ("'\u20ac'", "code point 8364; a char holds one byte"),
    ("'a", "The char is not closed"),
    ("'\n'", "The char is not closed"),
], ids=["empty", "two-characters", "word", "unknown-escape", "short-hex-escape",
        "above-one-byte", "no-closing-quote", "raw-newline"])
def test_bad_char_literal_reports_its_own_cause(tmp_path, literal, fragment):
    expect_exit(in_main(f"    c := {literal}"), tmp_path, TOKENIZE_EXIT, fragment)


def test_distinct_causes_do_not_share_the_not_closed_message(tmp_path):
    for literal in ("''", "'ab'", "'\\q'", "'\u20ac'"):
        result = expect_exit(in_main(f"    c := {literal}"), tmp_path, TOKENIZE_EXIT, "char")
        assert "not closed" not in result.failure.message


def test_valid_char_literals_compile(tmp_path):
    expect_ok(in_main("    a := 'a'\n    n := '\\n'\n    q := '\\''\n    b := '\\\\'\n    h := '\\x41'\n"
                      "    z := '\\0'\n    e := '\u00e9'"), tmp_path)


@pytest.mark.parametrize("body", ["    @ for { break }", "    x := @", "    x := @(1)"])
def test_bare_at_sign_is_a_tokenizer_error(tmp_path, body):
    expect_exit(in_main(body), tmp_path, TOKENIZE_EXIT, "Expected a name after '@'")


def test_loop_label_still_compiles(tmp_path):
    expect_ok(in_main("    @outer for i := 0; i < 2; i += 1 {\n        for {\n            break outer\n        }\n    }"),
              tmp_path)
