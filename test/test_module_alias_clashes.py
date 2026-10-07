"""L28 binds aliases per importing file; compile-only checks never build Zig."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def compile_source(tmp_path, source, modules=None):
    for name, text in (modules or {"helper": "value :: fn() i32 { ret 1 }\n"}).items():
        (tmp_path / f"{name}.a7").write_text(text)
    path = tmp_path / "main.a7"
    path.write_text(source)
    result = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(path), "--mode", "compile",
         "--output", str(tmp_path / "main.zig")],
        cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT)), capture_output=True, text=True,
    )
    return result.returncode, result.stdout + result.stderr


@pytest.mark.parametrize("body", [
    "main :: fn() { h := 3 }",
    "main :: fn() { h :: 3 }",
    "other :: fn(h: i32) {}\nmain :: fn() {}",
    "main :: fn() { h :: fn() {} }",
    "main :: fn() { for h in [1, 2] {} }",
    "main :: fn() { for h, value in [1, 2] {} }",
    "main :: fn() { for value, h in [1, 2] {} }",
    "Outcome :: union(tag) { ok: i32 }\nmain :: fn() { x := Outcome{ok: 1}; match x { case .ok(h): {} } }",
])
def test_local_binding_cannot_reuse_own_import_alias(tmp_path, body):
    code, output = compile_source(tmp_path, 'h :: import "helper"\n' + body + '\n')
    assert code == 6, output
    assert "Local 'h' conflicts with this file's import alias" in output
    assert str(tmp_path / "main.a7") in output


def test_stdlib_alias_is_also_reserved_for_local_bindings(tmp_path):
    code, output = compile_source(tmp_path, 'io :: import "io"\nmain :: fn() { io := 3 }\n')
    assert code == 6, output
    assert "Local 'io' conflicts" in output


def test_imported_file_clash_reports_its_own_source(tmp_path):
    code, output = compile_source(tmp_path, 'part :: import "part"\nmain :: fn() {}\n', {
        "helper": 'value :: 1\n',
        "part": 'h :: import "helper"\nother :: fn() { h := 3 }\n',
    })
    assert code == 6, output
    assert "Local 'h' conflicts" in output
    assert str(tmp_path / "part.a7") in output


def test_other_file_alias_does_not_reserve_local_or_field_name(tmp_path):
    code, output = compile_source(tmp_path, 'h :: import "helper"\nmain :: fn() { x := h.value() }\n', {
        "helper": 'Fields :: struct { h: i32 }\nvalue :: fn() i32 { h := Fields{h: 7}; ret h.h }\n',
    })
    assert code == 0, output


def test_same_import_alias_in_distinct_files_remains_valid(tmp_path):
    code, output = compile_source(tmp_path, 'h :: import "helper"\nmain :: fn() { x := h.value() }\n', {
        "helper": 'h :: import "leaf"\nvalue :: fn() i32 { ret h.answer() }\n',
        "leaf": 'answer :: fn() i32 { ret 7 }\n',
    })
    assert code == 0, output


def test_imported_match_capture_reusing_own_alias_is_rejected(tmp_path):
    # The own-file alias is visible under L69. It is a reference, not a
    # capture; a namespace cannot serve as an integer value pattern.
    code, output = compile_source(tmp_path, 'part :: import "part"\nmain :: fn() {}\n', {
        "helper": 'answer :: 1\n',
        "part": 'h :: import "helper"\nother :: fn() { match 1 { case h: {} } }\n',
    })
    assert code == 6, output
    assert "module namespace" in output
    assert "conflicts with this file's import alias" not in output
    assert str(tmp_path / "part.a7") in output


def test_identifier_comparison_is_not_reported_as_alias_capture(tmp_path):
    # The entry import remains a symbol, so name resolution does not classify
    # this identifier as a capture. Any invalid-pattern error belongs to the
    # existing semantic checks, not the L28 binding diagnostic.
    code, output = compile_source(tmp_path, 'h :: import "helper"\nmain :: fn() { match 1 { case h: {} } }\n')
    assert code == 6, output
    assert "module namespace" in output
    assert "conflicts with this file's import alias" not in output


def test_non_alias_match_comparison_and_capture_remain_valid(tmp_path):
    code, output = compile_source(tmp_path, 'h :: import "helper"\nLIMIT :: 1\nmain :: fn() { match 1 { case LIMIT: {} case captured: {} } }\n')
    assert code == 0, output


@pytest.mark.parametrize('declaration', [
    'Box($h) :: struct { value: $h }',
    'Buffer($h: usize) :: struct { data: [$h]u8 }',
    'Outcome($h) :: union(tag) { value: $h }',
    'Outcome($h: usize) :: union(tag) { data: [$h]u8 }',
    'identity($h) :: fn(value: $h) $h { ret value }',
    'consume($h: usize) :: fn(value: [$h]u8) {}',
])
def test_explicit_generic_parameter_cannot_reuse_own_import_alias(tmp_path, declaration):
    code, output = compile_source(tmp_path, 'h :: import "helper"\n' + declaration + '\nmain :: fn() {}\n')
    assert code == 6, output
    assert "Local 'h' conflicts with this file's import alias" in output
    assert str(tmp_path / 'main.a7') in output


@pytest.mark.parametrize('declaration', [
    'Box($h) :: struct { value: $h }',
    'Outcome($h: usize) :: union(tag) { data: [$h]u8 }',
])
def test_imported_generic_parameter_clash_reports_declaration_owner(tmp_path, declaration):
    code, output = compile_source(tmp_path, 'part :: import "part"\nmain :: fn() {}\n', {
        'helper': 'value :: fn() i32 { ret 1 }\n',
        'part': 'h :: import "helper"\n' + declaration + '\n',
    })
    assert code == 6, output
    assert "Local 'h' conflicts with this file's import alias" in output
    assert str(tmp_path / 'part.a7') in output


def test_generic_parameters_and_fields_do_not_inherit_another_files_alias(tmp_path):
    code, output = compile_source(tmp_path, 'h :: import "helper"\nmain :: fn(){x:=h.value()}\n', {
        'helper': '''Box($h) :: struct { h: $h }
Outcome($h:usize) :: union(tag) { h: [$h]u8 }
value :: fn() i32 { ret 7 }
''',
    })
    assert code == 0, output


def test_nonclashing_generic_parameters_allow_field_named_like_alias(tmp_path):
    code, output = compile_source(tmp_path, '''h :: import "helper"
Box($T) :: struct { h: $T }
Outcome($N:usize) :: union(tag) { h: [$N]u8 }
main :: fn(){x:=h.value()}
''')
    assert code == 0, output


def test_inferred_generic_type_name_does_not_replace_module_binding(tmp_path):
    # Unlike explicit GENERIC_PARAM declarations, TYPE_GENERIC occurrences
    # currently create type variables without local name-resolution symbols.
    code, output = compile_source(tmp_path, '''h :: import "helper"
identity :: fn(value:$h) $h { local:=h.value();ret value }
main :: fn(){x:=identity(7)}
''')
    assert code == 0, output
