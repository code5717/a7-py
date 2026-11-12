"""Declared fixed-array elements use each concrete generic destination.

These are compiler-only contracts. They do not qualify native execution or
expand callable-origin eligibility.
"""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = [('generic_i8',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1, 2]; ret values }\n'
  'main :: fn() { seed: i8 = 0; value := make(seed) }\n',
  0),
 ('overflow_i8',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1, 128]; ret values }\n'
  'main :: fn() { seed: i8 = 0; value := make(seed) }\n',
  6),
 ('overflow_i16_control',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1, 128]; ret values }\n'
  'main :: fn() { seed: i16 = 0; value := make(seed) }\n',
  0),
 ('typed_runtime_i32_to_i8',
  'make :: fn(seed: $T, item: i32) [2]$T { values: [2]$T = [item, item]; ret values }\n'
  'main :: fn() { seed: i8 = 0; value := make(seed, 1) }\n',
  6),
 ('typed_runtime_i32_control',
  'make :: fn(seed: $T, item: i32) [2]$T { values: [2]$T = [item, item]; ret values }\n'
  'main :: fn() { seed: i32 = 0; value := make(seed, 1) }\n',
  0),
 ('bool_integer_reject',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1, 2]; ret values }\n'
  'main :: fn() { seed: bool = true; value := make(seed) }\n',
  6),
 ('string_integer_reject',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1, 2]; ret values }\n'
  'main :: fn() { seed: string = "seed"; value := make(seed) }\n',
  6),
 ('struct_integer_reject',
  'Box :: struct { value: i32 }\n'
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1, 2]; ret values }\n'
  'main :: fn() { seed := Box{value: 0}; value := make(seed) }\n',
  6),
 ('bool_matching',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [true, false]; ret values }\n'
  'main :: fn() { seed: bool = true; value := make(seed) }\n',
  0),
 ('string_matching',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = ["a", "b"]; ret values }\n'
  'main :: fn() { seed: string = "seed"; value := make(seed) }\n',
  0),
 ('struct_matching',
  'Box :: struct { value: i32 }\n'
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [Box{value: 1}, Box{value: 2}]; ret values }\n'
  'main :: fn() { seed := Box{value: 0}; value := make(seed) }\n',
  0),
 ('wrong_length_called',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1]; ret values }\n'
  'main :: fn() { seed: i8 = 0; value := make(seed) }\n',
  6),
 ('wrong_length_unused',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1]; ret values }\nmain :: fn() {}\n',
  6),
 ('unused_generic',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1, 2]; ret values }\nmain :: fn() {}\n',
  0),
 ('unused_generic_128',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1, 128]; ret values }\nmain :: fn() {}\n',
  0),
 ('immutable_alias_fit',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1, 2]; ret values }\n'
  'main :: fn() { seed: i8 = 0; alias := make; copy := alias; value := copy(seed) }\n',
  0),
 ('immutable_alias_overflow',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1, 128]; ret values }\n'
  'main :: fn() { seed: i8 = 0; alias := make; copy := alias; value := copy(seed) }\n',
  6),
 ('wrapper_fit',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1, 2]; ret values }\n'
  'forward :: fn(seed: $U) [2]$U { ret make(seed) }\n'
  'main :: fn() { seed: i8 = 0; value := forward(seed) }\n',
  0),
 ('wrapper_overflow',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1, 128]; ret values }\n'
  'forward :: fn(seed: $U) [2]$U { ret make(seed) }\n'
  'main :: fn() { seed: i8 = 0; value := forward(seed) }\n',
  6),
 ('concrete_array_control',
  'make :: fn(seed: $T) [2]i8 { values: [2]i8 = [1, 2]; ret values }\n'
  'main :: fn() { seed: i8 = 0; value := make(seed) }\n',
  0),
 ('whole_T_control',
  'make :: fn(seed: $T) $T { values: $T = [1, 2]; ret values }\n'
  'main :: fn() { seed: [2]i8 = [0, 0]; value := make(seed) }\n',
  0),
 ('whole_T_wrapper_control',
  'make :: fn(seed: $T) $T { values: $T = [1, 2]; ret values }\n'
  'forward :: fn(seed: $U) $U { ret make(seed) }\n'
  'main :: fn() { seed: [2]i8 = [0, 0]; value := forward(seed) }\n',
  0),
 ('whole_T_wrapper_overflow',
  'make :: fn(seed: $T) $T { values: $T = [1, 128]; ret values }\n'
  'forward :: fn(seed: $U) $U { ret make(seed) }\n'
  'main :: fn() { seed: [2]i8 = [0, 0]; value := forward(seed) }\n',
  6),
 ('two_instantiations',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1, 128]; ret values }\n'
  'main :: fn() { narrow: i8 = 0; wide: i16 = 0; a := make(wide); b := make(narrow) }\n',
  6),
 ('unused_whole_T',
  'make :: fn(seed: $T) $T { values: $T = [1, 128]; ret values }\nmain :: fn() {}\n',
  0),
 ('whole_T_bool',
  'make :: fn(seed: $T) $T { values: $T = [true, false]; ret values }\n'
  'main :: fn() { seed: [2]bool = [true, true]; value := make(seed) }\n',
  0),
 ('whole_T_string',
  'make :: fn(seed: $T) $T { values: $T = ["a", "b"]; ret values }\n'
  'main :: fn() { seed: [2]string = ["x", "y"]; value := make(seed) }\n',
  0),
 ('whole_T_struct',
  'Box :: struct { value: i32 }\n'
  'make :: fn(seed: $T) $T { values: $T = [Box{value: 1}, Box{value: 2}]; ret values }\n'
  'main :: fn() { seed: [2]Box = [Box{value: 0}, Box{value: 0}]; value := make(seed) }\n',
  0),
 ('generic_integral_float',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1.0, 2.0]; ret values }\n'
  'main :: fn() { seed: i8 = 0; value := make(seed) }\n',
  0),
 ('concrete_integral_float',
  'make :: fn(seed: $T) [2]i8 { values: [2]i8 = [1.0, 2.0]; ret values }\n'
  'main :: fn() { seed: i8 = 0; value := make(seed) }\n',
  0),
 ('generic_fractional_float',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1.0, 2.5]; ret values }\n'
  'main :: fn() { seed: i8 = 0; value := make(seed) }\n',
  6),
 ('concrete_fractional_float',
  'make :: fn(seed: $T) [2]i8 { values: [2]i8 = [1.0, 2.5]; ret values }\n'
  'main :: fn() { seed: i8 = 0; value := make(seed) }\n',
  6),
 ('nested_fit',
  'make :: fn(seed: $T) [2][2]$T { values: [2][2]$T = [[1, 2], [3, 4]]; ret values }\n'
  'main :: fn() { seed: i8 = 0; value := make(seed) }\n',
  0),
 ('nested_overflow',
  'make :: fn(seed: $T) [2][2]$T { values: [2][2]$T = [[1, 2], [3, 128]]; ret values }\n'
  'main :: fn() { seed: i8 = 0; value := make(seed) }\n',
  6),
 ('nested_wrong_length_unused',
  'make :: fn(seed: $T) [2][2]$T { values: [2][2]$T = [[1], [2, 3]]; ret values }\n'
  'main :: fn() {}\n',
  6),
 ('mixed_elements_unused',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1, true]; ret values }\nmain :: fn() {}\n',
  6),
 ('multiple_small_first',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1, 2]; ret values }\n'
  'main :: fn() { small: i8 = 0; wide: i64 = 0; a: [2]i8 = make(small); b: [2]i64 = make(wide) }\n',
  0),
 ('multiple_wide_first',
  'make :: fn(seed: $T) [2]$T { values: [2]$T = [1, 2]; ret values }\n'
  'main :: fn() { small: i8 = 0; wide: i64 = 0; b: [2]i64 = make(wide); a: [2]i8 = make(small) }\n',
  0)]

@pytest.mark.parametrize("name,source,expected", CASES, ids=[row[0] for row in CASES])
def test_generic_array_element_destination(tmp_path, name, source, expected):
    path = tmp_path / (name + ".a7")
    output = tmp_path / (name + ".zig")
    path.write_text(source)
    result = subprocess.run([sys.executable, str(ROOT / "main.py"), "--mode", "compile", "--format", "json", "-o", str(output), str(path)], capture_output=True, text=True)
    assert result.returncode == expected, result.stdout + result.stderr
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    if expected:
        assert payload["error"]["category"] == "semantic"
        if "wrong_length" in name:
            assert "array size mismatch" in str(payload["error"])
        elif name not in {"concrete_fractional_float", "mixed_elements_unused"}:
            assert "Initializer of 'values'" in str(payload["error"]), payload["error"]
        assert not output.exists()
    else:
        assert payload["status"] == "ok"
        assert output.is_file()
        assert "pub fn main" in output.read_text()


# These escapes are deliberately outside existing initializer-obligation origins.
@pytest.mark.parametrize("body", [
    "f := make; f = make; seed: i8 = 0; value := f(seed)",
    "f := make; f = make",
    "f := make; nested :: fn() { seed: i8 = 0; value := f(seed) }; nested()",
    "f := make; nested :: fn() { g := f }",
    "seed: i16 = 0; valid := make(seed); f := make; f = make",
    "f := make; g := f; g = make",
    "items := [make, make]",
    "flag := true; f := if flag { make } else { make }",
])
def test_unsupported_array_initializer_origin_retains_declaration_error(tmp_path, body):
    from conftest import compile_program, failure_text
    result = compile_program("make :: fn(seed: $T) [2]$T { values: [2]$T = [1, 128]; ret values }\n"
                             "main :: fn() {" + body + "}", tmp_path)
    assert int(result.exit_code) == 6
    assert "Variable 'values'" in failure_text(result)


@pytest.mark.parametrize("suffix", [
    "saved :: make; main :: fn() {}",
    "saved :: make; main :: fn() { seed: i8 = 0; value := saved(seed) }",
    "take :: fn(f: fn($T) [2]$T) {}; main :: fn() { take(make) }",
    "set :: fn(f: ref fn($T) [2]$T) { f = make }; main :: fn() { f := make; set(f) }",
])
def test_stored_or_parameter_array_initializer_origin_is_not_inferred(tmp_path, suffix):
    from conftest import compile_program, failure_text
    result = compile_program("make :: fn(seed: $T) [2]$T { values: [2]$T = [1, 128]; ret values }\n" + suffix, tmp_path)
    assert int(result.exit_code) == 6
    assert "Variable 'values'" in failure_text(result)


@pytest.mark.parametrize("depth", [1, 2])
@pytest.mark.parametrize("body", [
    "f := TARGET; f = TARGET; seed: i8 = 0; value := f(seed)",
    "seed: i16 = 0; valid := TARGET(seed); f := TARGET; f = TARGET",
    "f := TARGET; nested :: fn() { seed: i8 = 0; value := f(seed) }; nested()",
])
def test_wrapper_obligations_cannot_escape_through_unknown_origins(tmp_path, depth, body):
    from conftest import compile_program, failure_text
    source = "make :: fn(seed: $T) [2]$T { values: [2]$T = [1, 128]; ret values }\n"
    source += "wrap :: fn(seed: $U) [2]$U { ret make(seed) }\n"
    if depth == 2:
        source += "wrap2 :: fn(seed: $V) [2]$V { ret wrap(seed) }\n"
    source += "main :: fn() {" + body.replace("TARGET", "wrap" if depth == 1 else "wrap2") + "}"
    result = compile_program(source, tmp_path)
    assert int(result.exit_code) == 6
    assert "Variable 'values'" in failure_text(result)


def test_already_typed_generic_elements_keep_existing_origin_behavior(tmp_path):
    from conftest import compile_program
    result = compile_program('make :: fn(seed: $T) [2]$T { values: [2]$T = [seed, seed]; ret values }\n'
                             'main :: fn() { f := make; f = make; seed: i8 = 0; value := f(seed) }', tmp_path)
    assert int(result.exit_code) == 0


@pytest.mark.parametrize("value,expected", [(2, 0), (128, 6)])
@pytest.mark.parametrize("use", [
    "a := fixed(seed)",
    "f := fixed; a := f(seed)",
    "f := fixed; f = fixed; a := f(seed)",
    "a := invoke(fixed, seed)",
])
def test_concrete_wrapper_discharges_array_obligation(tmp_path, value, expected, use):
    from conftest import compile_program, failure_text
    source = f"make :: fn(seed: $T) [2]$T {{ values: [2]$T = [1, {value}]; ret values }}\n"
    source += "fixed :: fn(seed: i8) [2]i8 { ret make(seed) }\n"
    source += "invoke :: fn(f: fn(i8) [2]i8, seed: i8) [2]i8 { ret f(seed) }\n"
    source += "main :: fn() { seed: i8 = 0;" + use + "}"
    result = compile_program(source, tmp_path)
    assert int(result.exit_code) == expected, failure_text(result)
    if expected:
        assert "Initializer of 'values'" in failure_text(result)


@pytest.mark.parametrize("value,expected", [(2, 0), (128, 6)])
def test_unrelated_generic_parameter_does_not_reopen_concrete_obligation(tmp_path, value, expected):
    from conftest import compile_program, failure_text
    source = f"make :: fn(seed: $T) [2]$T {{ values: [2]$T = [1, {value}]; ret values }}\n"
    source += "fixed :: fn(other: $U) [2]i8 { seed: i8 = 0; ret make(seed) }\n"
    source += "main :: fn() { f := fixed; f = fixed; a := f(true) }"
    result = compile_program(source, tmp_path)
    assert int(result.exit_code) == expected, failure_text(result)
    if expected:
        assert "Initializer of 'values'" in failure_text(result)


def test_unrelated_already_assignable_initializer_does_not_escape(tmp_path):
    from conftest import compile_program, failure_text
    source = "make :: fn(seed: $T, other: $U) [2]$T { values: [2]$T = [1, 2]; typed: [2]$U = [other, other]; ret values }\n"
    source += "fixed :: fn(other: $V) [2]i8 { seed: i8 = 0; ret make(seed, other) }\n"
    source += "main :: fn() { f := fixed; f = fixed; a := f(true) }"
    result = compile_program(source, tmp_path)
    assert int(result.exit_code) == 0, failure_text(result)


def test_concrete_destination_with_unresolved_source_retains_obligation(tmp_path):
    from conftest import compile_program, failure_text
    source = "make :: fn(seed: $T, other: $U) [2]$T { values: [2]$T = [other, other]; ret values }\n"
    source += "fixed :: fn(other: $V) [2]i8 { seed: i8 = 0; ret make(seed, other) }\n"
    source += "main :: fn() { f := fixed; f = fixed; item: i32 = 1; a := f(item) }"
    result = compile_program(source, tmp_path)
    assert int(result.exit_code) == 6
    assert "Variable 'values'" in failure_text(result)
