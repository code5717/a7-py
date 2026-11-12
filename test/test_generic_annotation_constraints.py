"""Nominal annotations validate constraints in their defining owner scope."""

import json
import pytest
from test_generic_numeric_match_patterns import compile_source

CASES = [('annotation_bad', 'Box($T: Float) :: struct { value: $T }\nmain :: fn() { b: Box(i32) }\n', None, 6), ('annotation_good', 'Box($T: Float) :: struct { value: $T }\nmain :: fn() { b: Box(f32) }\n', None, 0), ('parameter_bad', 'Box($T: Float) :: struct { value: $T }\nread :: fn(b: ref Box(i32)) {}\nmain :: fn() {}\n', None, 6), ('return_bad', 'Box($T: Float) :: struct { value: $T }\nmake :: fn() ref Box(i32) { ret nil }\nmain :: fn() {}\n', None, 6), ('array_alias_bad', 'Alias :: [2]Box(i32)\nBox($T: Float) :: struct { value: $T }\nmain :: fn() { b: Alias }\n', None, 6), ('function_alias_bad', 'Callback :: fn(ref Box(i32))\nBox($T: Float) :: struct { value: $T }\nmain :: fn() {}\n', None, 6), ('forward_field_good', 'Outer($U: Float) :: struct { value: Box($U) }\nBox($T: Float) :: struct { value: $T }\nmain :: fn() { b: Outer(f32) }\n', None, 0), ('forward_field_bad', 'Outer($U: Integer) :: struct { value: Box($U) }\nBox($T: Float) :: struct { value: $T }\nmain :: fn() {}\n', None, 6), ('unconstrained_field_bad', 'Outer($U) :: struct { value: Box($U) }\nBox($T: Float) :: struct { value: $T }\nmain :: fn() {}\n', None, 6), ('forward_union_bad', 'Holder :: struct { value: Choice(i32) }\nChoice($T: Float) :: union(tag) { value: $T, empty: bool }\nmain :: fn() {}\n', None, 6), ('nested_alias_shadow', 'Box($T: Float) :: struct { value: $T }\nmain :: fn() { A :: [1]Box(f32); { A :: [1]Box(i32); b: A } }\n', None, 6), ('forward_constraint_member', 'Allowed :: @type_set(Word)\nBox($T: Allowed) :: struct { value: $T }\nWord :: i32\nmain :: fn() { b: Box(i32) }\n', None, 0), ('import_owner_bad', 'h :: import "helper"\nAllowed :: @type_set(i32)\nmain :: fn() { b: h.Box(i32) }\n', 'Allowed :: @type_set(f32, f64)\npub Box($T: Allowed) :: struct { value: $T }\n', 6), ('import_owner_good', 'h :: import "helper"\nAllowed :: @type_set(i32)\nmain :: fn() { b: h.Box(f32) }\n', 'Allowed :: @type_set(f32, f64)\npub Box($T: Allowed) :: struct { value: $T }\n', 0)]


@pytest.mark.parametrize('name,source,helper,expected', CASES, ids=[row[0] for row in CASES])
def test_annotation_contexts(tmp_path, name, source, helper, expected):
    if helper is not None:
        (tmp_path / 'helper.a7').write_text(helper)
    result = compile_source(tmp_path, source, expected, 'constraint_violation' if expected else None)
    if expected:
        details = json.loads(result)['error']['details']
        assert len(details) == 1, details
        error = details[0]
        assert error['code'] == 'constraint_violation'
        assert error['file'] == str(tmp_path / 'main.a7')
        written = 'h.Box(i32)' if name == 'import_owner_bad' else 'Choice(i32)' if name == 'forward_union_bad' else 'Box($U)' if name in {'forward_field_bad', 'unconstrained_field_bad'} else 'Box(i32)'
        offset = source.index(written)
        assert error['span']['start_line'] == source[:offset].count('\n') + 1
        assert error['span']['start_column'] == offset - source.rfind('\n', 0, offset)


def test_completed_unconstrained_owner_is_valid(tmp_path):
    compile_source(tmp_path, 'Box($T) :: struct { value: $T }\nmain :: fn() { a: Box(string); b: Box(i32) }')


def test_invalid_owner_keeps_primary_constraint_diagnostic(tmp_path):
    result = compile_source(tmp_path, 'Box($T: Missing) :: struct { value: $T }\nmain :: fn() { b: Box(f32) }', 6, 'not a type set')
    assert len(json.loads(result)['error']['details']) == 1


def test_argument_kind_error_precedes_membership(tmp_path):
    result = compile_source(tmp_path, 'Box($N: usize, $T: Float) :: struct { value: $T }\nmain :: fn() { b: Box(f32, i32) }', 6, 'requires a comptime usize')
    assert len(json.loads(result)['error']['details']) == 1


def test_argument_count_error_precedes_membership(tmp_path):
    result = compile_source(tmp_path, 'Box($T: Float) :: struct { value: $T }\nmain :: fn() { b: Box(i32, f32) }', 6, 'takes 1 generic argument')
    assert len(json.loads(result)['error']['details']) == 1


def test_unresolved_argument_keeps_primary_type_error(tmp_path):
    result = compile_source(tmp_path, 'Box($T: Float) :: struct { value: $T }\nmain :: fn() { b: Box(Missing) }', 6, 'Undefined type')
    assert len(json.loads(result)['error']['details']) == 1


def test_global_alias_does_not_borrow_record_parameter_constraint(tmp_path):
    compile_source(tmp_path, 'Outer($U: Float) :: struct { value: Alias }\nAlias :: [1]Box($U)\nBox($T: Float) :: struct { value: $T }\nmain :: fn() {}', 6, 'requires Float, got $U')


def test_local_alias_keeps_its_function_parameter_constraint(tmp_path):
    compile_source(tmp_path, 'Box($T: Float) :: struct { value: $T }\nwrap($U: Float) :: fn(x: $U) { Alias :: [1]Box($U); b: Alias }\nmain :: fn() { x: f32 = 1; wrap(x) }')


def test_nested_function_annotation_checked_once(tmp_path):
    result = compile_source(tmp_path, 'Box($T: Float) :: struct { value: $T }\nmain :: fn() { inner :: fn(b: ref Box(i32)) {} }', 6, 'constraint_violation')
    assert len(json.loads(result)['error']['details']) == 1


def test_signature_before_owner_declaration(tmp_path):
    result = compile_source(tmp_path, 'take :: fn(b: ref Box(i32)) {}\nBox($T: Float) :: struct { value: $T }\nmain :: fn() {}', 6, 'constraint_violation')
    assert len(json.loads(result)['error']['details']) == 1


def test_imported_invalid_alias_reports_definition_file(tmp_path):
    (tmp_path / 'helper.a7').write_text('pub Alias :: [1]Box(i32)\nBox($T: Float) :: struct { value: $T }\n')
    result = compile_source(tmp_path, 'h :: import "helper"\nmain :: fn() { b: h.Alias }', 6, 'constraint_violation')
    details = json.loads(result)['error']['details']
    assert len(details) == 1
    assert details[0]['file'] == str(tmp_path / 'helper.a7')
    assert details[0]['span']['start_line'] == 1
    assert details[0]['span']['start_column'] == 17


@pytest.mark.parametrize('before', [False, True])
@pytest.mark.parametrize('construct', [False, True])
@pytest.mark.parametrize('actual,expected', [('f32', 0), ('i32', 6)])
def test_forward_set_member_matches_resolved_membership(tmp_path, before, construct, actual, expected):
    alias = 'Word :: f32\n'
    owner = 'Allowed :: @type_set(Word)\nBox($T: Allowed) :: struct { value: $T }\n'
    source = (alias + owner) if before else (owner + alias)
    use = f'b := Box({actual}){{value: 1}}' if construct else f'b: Box({actual})'
    result = compile_source(tmp_path, source + f'main :: fn() {{ {use} }}', expected,
                            'constraint_violation' if expected else None)
    if expected:
        errors = json.loads(result)['error']['details']
        assert len(errors) == 1
        assert 'f32' in errors[0]['message']
        assert errors[0]['span']['start_line'] == 4


def test_imported_forward_member_uses_owner_alias(tmp_path):
    (tmp_path / 'helper.a7').write_text('Allowed :: @type_set(Word)\npub Box($T: Allowed) :: struct { value: $T }\nWord :: f32\n')
    source = 'h :: import "helper"\nWord :: i32\nAllowed :: @type_set(i32)\nmain :: fn() { b: h.Box(f32); c := h.Box(f32){value: 1} }'
    compile_source(tmp_path, source)


def test_alias_cycle_retains_primary_error(tmp_path):
    result = compile_source(tmp_path, 'A :: [1]B\nB :: [1]A\nBox($T: Float) :: struct { value: $T }\nmain :: fn() { b: Box(A) }', 6, 'cycle')
    assert all(error['code'] != 'constraint_violation' for error in json.loads(result)['error']['details'])
