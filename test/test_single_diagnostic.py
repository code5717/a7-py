"""One mistake, one diagnostic, with the right label (P2-39, G-1, G-7, G-8).

An expression that already produced an error has the checker's poison
type. Every check that meets it afterwards stays silent, so the enclosing
assignment, argument, return, condition or pattern adds nothing.
"""

from __future__ import annotations

import pytest

from conftest import compile_program

PRELUDE = """\
P :: struct { x: i32 }
take :: fn(v: u8) { }
"""

ONE_MISTAKE = [
    pytest.param("p := P{x: 1}\n    y := p.nope + 1", "has no field 'nope'", id="bad-field-in-arithmetic"),
    pytest.param("p := P{x: 1}\n    z: i32 = p.nope", "has no field 'nope'", id="bad-field-into-typed-variable"),
    pytest.param("p := P{x: 1}\n    if p.nope { }", "has no field 'nope'", id="bad-field-as-condition"),
    pytest.param("p := P{x: 1}\n    while p.nope < 3 { }", "has no field 'nope'", id="bad-field-in-comparison"),
    pytest.param("p := P{x: 1}\n    take(p.nope)", "has no field 'nope'", id="bad-field-as-argument"),
    pytest.param("p := P{x: 1}\n    p.x = p.nope", "has no field 'nope'", id="bad-field-assigned"),
    pytest.param("p := P{x: p_typo}", "Undefined identifier: 'p_typo'", id="undefined-name-as-field-value"),
    pytest.param("a := [1, totl, 3]", "Undefined identifier: 'totl'", id="undefined-name-as-element"),
    pytest.param("x := totl + 1\n", "Undefined identifier: 'totl'", id="undefined-name-in-arithmetic"),
    pytest.param("count = 0", "Undefined identifier: 'count'", id="assignment-to-undeclared-name"),
    pytest.param('io.println("hi")', "Undefined identifier: 'io'", id="module-never-imported"),
    pytest.param("y := missing(1, 2)", "Undefined identifier: 'missing'", id="call-of-undefined-name"),
    pytest.param("take(300)", "300 is out of range for u8", id="argument-out-of-range"),
    pytest.param("v: u8 = 300", "300 is out of range for u8", id="initializer-out-of-range"),
    pytest.param("v: u8 = 1\n    v = 300", "300 is out of range for u8", id="assignment-out-of-range"),
    pytest.param("p := P{x: 5000000000}", "5000000000 is out of range for i32", id="field-out-of-range"),
    pytest.param("a: [2]u8 = [1, 300]", "300 is out of range for u8", id="element-out-of-range"),
    pytest.param(
        "a: [2][2]i32 = [[1, 2], [3, 4.5]]", "9/2 is fractional and cannot fit i32",
        id="nested-element-does-not-fit",
    ),
    pytest.param(
        "v: u8 = 3\n    match v {\n        case 300: { }\n        else: { }\n    }",
        "300 is out of range for u8",
        id="pattern-out-of-range",
    ),
    # A constant beside an earlier error is not held to the i32 default.
    pytest.param("x: Nope = 5000000000", "Undefined type (Type 'Nope')", id="constant-into-undefined-type"),
    pytest.param("y := missing(5000000000)", "Undefined identifier: 'missing'", id="constant-into-undefined-call"),
    pytest.param("z := totl + 5000000000", "Undefined identifier: 'totl'", id="constant-beside-undefined-name"),
    pytest.param("p := P{x: 1, x: 2}", "Duplicate struct field initializer", id="field-given-twice"),
    pytest.param("p := P{x: 1, z: 2}", "has no field 'z'", id="unknown-field-in-literal"),
]


def messages(source: str, tmp_path) -> list[str]:
    result = compile_program(source, tmp_path)
    assert result.exit_code == 6, result.exit_code
    return [str(detail["message"]) for detail in result.failure.details]


@pytest.mark.parametrize(("body", "fragment"), ONE_MISTAKE)
def test_one_mistake_reports_one_error(tmp_path, body, fragment):
    found = messages(f"{PRELUDE}\nmain :: fn() {{\n    {body}\n}}\n", tmp_path)
    assert len(found) == 1, found
    assert fragment in found[0]
    # Compiler internals do not belong in a message.
    for leak in ("unknown type", "NodeKind.", "None"):
        assert leak not in found[0]


@pytest.mark.parametrize(
    ("function", "fragment", "sites"),
    [
        pytest.param("f :: fn(a: Nope) { }", "Undefined type (Type 'Nope')", 1, id="parameter-type"),
        pytest.param(
            "f :: fn(a: Nope) Nope {\n    ret a\n}", "Undefined type (Type 'Nope')", 2,
            id="parameter-and-return-type",
        ),
        pytest.param("f :: fn() i32 {\n    ret\n}", "Return type mismatch: expected 'i32' ('ret' has no value)", 1, id="bare-ret"),
        pytest.param("f :: fn() i32 {\n    ret nil\n}", "Nil only allowed for reference types", 1, id="nil-returned-as-integer"),
        pytest.param("f :: fn() u8 {\n    ret 300\n}", "300 is out of range for u8", 1, id="return-out-of-range"),
    ],
)
def test_a_signature_or_return_mistake_reports_once_per_site(tmp_path, function, fragment, sites):
    # A signature is resolved when it is registered and again when its body
    # is checked; each written type must still be reported once.
    found = messages(f"{function}\n\nmain :: fn() {{\n}}\n", tmp_path)
    assert len(found) == sites, found
    for message in found:
        assert fragment in message
        assert "None" not in message and "unknown type" not in message


def test_an_undefined_name_is_labelled_as_a_name_with_a_spelling_hint(tmp_path):
    result = compile_program("main :: fn() {\n    total := 1\n    x := totl + 1\n}\n", tmp_path)
    assert result.exit_code == 6
    (detail,) = result.failure.details
    assert detail["code"] == "undefined_identifier"
    assert detail["message"] == "Undefined identifier: 'totl'"
    assert detail["hint"] == "Fix the spelling or declare the name before this line"
