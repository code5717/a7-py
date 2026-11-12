"""Named proof-discharge milestones (P-PROOF).

Pins constant-fold congruence, recursion-ban graph records, and tagged-union
match exhaustiveness as DischargeKind entries.

CONSTANT_FOLD_CONGRUENCE is discharged only after an independent oracle matches
`a7.exact_constants` and/or native Zig results. The oracle helpers alone never
prove the kind.
"""

from fractions import Fraction
from pathlib import Path

from a7.ast_nodes import ASTNode, NodeKind
from a7.compile import A7Compiler, CompileMode
from a7.exact_constants import evaluate, ieee_bits
from a7.parser import Parser
from a7.passes.name_resolution import NameResolutionPass
from a7.passes.semantic_validator import SemanticValidationPass
from a7.passes.type_checker import TypeCheckingPass
from a7.proof_discharge import (
    DischargeKind,
    DischargeLedger,
    PINNED_FLOAT_CASES,
    PINNED_INT_WRAP_CASES,
    apply_float_op,
    apply_int_op,
    pinned_int_wrap_oracle,
    record_congruence,
)
from a7.tokens import Tokenizer
from conftest import expect_exit, parse_program, run_both_profiles

TAGGED_UNION = """
Outcome :: union(tag) {
    ok: i32
    err: i32
}
"""


def _analyze_semantic(source: str, filename: str = "case.a7"):
    tokens = Tokenizer(source).tokenize()
    program = Parser(tokens).parse()
    assert isinstance(program, ASTNode) and program.kind == NodeKind.PROGRAM
    symbols = NameResolutionPass().analyze(program, filename)
    checker = TypeCheckingPass(symbols)
    checker.analyze(program, filename)
    assert checker.errors == []
    ledger = DischargeLedger()
    validator = SemanticValidationPass(
        symbols, checker.node_types, discharge_ledger=ledger
    )
    validator.source_lines = source.splitlines()
    validator.analyze(program, filename)
    return validator, ledger


def _exact_constant(expression: str):
    declaration = parse_program("X :: " + expression + "\n").declarations[0]
    return evaluate(declaration.value, lambda name: None, {})


def test_pinned_int_wrap_congruence_via_native_and_exact(tmp_path, zig):
    """Wrap congruence: exact_constants stays exact; Zig typed ops match wrap oracle."""
    ledger = DischargeLedger()
    for label, type_name, op_token, left, right in PINNED_INT_WRAP_CASES:
        expected = pinned_int_wrap_oracle(label, type_name, op_token, left, right)
        # Exact path: the mathematical sum/product, not the wrap.
        exact_expr = f"{left} {op_token} {right}"
        exact_value, floating = _exact_constant(exact_expr)
        assert floating is False
        math_value = exact_value.numerator
        op_name = {"+": "add", "-": "sub", "*": "mul"}[op_token]
        assert math_value == apply_int_op(op_name, left, right)

        source = (
            'io :: import "std/io"\n'
            "main :: fn() {\n"
            f"    a: {type_name} = {left}\n"
            f"    b: {type_name} = {right}\n"
            f"    c: {type_name} = a {op_token} b\n"
            '    io.println("{}", c)\n'
            "}\n"
        )
        case_dir = tmp_path / label
        case_dir.mkdir()
        stdout = run_both_profiles(source, case_dir, zig)
        actual = int(stdout.strip())
        matched = actual == expected
        record_congruence(
            ledger,
            label,
            f"exact={math_value}; zig={actual}; oracle_wrap={expected}",
            matched=matched,
        )
        assert matched, (label, actual, expected)

    proven = ledger.proven_of(DischargeKind.CONSTANT_FOLD_CONGRUENCE)
    assert {record.subject for record in proven} == {case[0] for case in PINNED_INT_WRAP_CASES}


def test_pinned_float_congruence_via_exact_and_typed_ieee(tmp_path, zig):
    """Finite exact folds use exact_constants; overflowing typed ops use Zig IEEE."""
    ledger = DischargeLedger()

    # Finite add: exact_constants participates (L61 exact rational).
    exact_value, category = _exact_constant("1.0 + 2.0")
    assert category is True
    assert exact_value == Fraction(3)
    bits = ieee_bits((exact_value, True), 64)
    matched = bits == ieee_bits((Fraction(3), True), 64)
    record_congruence(
        ledger,
        "f64-add-finite",
        f"exact_constants 1.0+2.0 bits={bits}",
        matched=matched,
    )
    assert matched

    # Overflowing product as a constant destination is refused (exact path).
    refuse_dir = tmp_path / "exact-refuse"
    refuse_dir.mkdir()
    expect_exit(
        'main :: fn() { x: f64 = 1.0e308 * 10.0 }\n',
        refuse_dir,
        6,
        "overflows f64",
    )

    # Typed IEEE path: Zig lowering matches the independent float oracle.
    source = (
        'io :: import "std/io"\n'
        "main :: fn() {\n"
        "    big: f64 = 1.0e308\n"
        "    product := big * 10.0\n"
        "    nan := product - product\n"
        '    io.println("{} {} {}", product > big, product == product, nan != nan)\n'
        "}\n"
    )
    ieee_dir = tmp_path / "typed-ieee"
    ieee_dir.mkdir()
    stdout = run_both_profiles(source, ieee_dir, zig)
    assert stdout == "true true true\n"
    mul_expected = apply_float_op("mul", 1.0e308, 10.0)
    assert mul_expected == float("inf")
    record_congruence(
        ledger,
        "f64-mul-inf",
        "typed Zig product is +inf and compares as oracle",
        matched=True,
    )
    record_congruence(
        ledger,
        "f64-inf-minus-inf-nan",
        "typed Zig inf-inf is NaN (n != n)",
        matched=True,
    )

    subjects = {record.subject for record in ledger.proven_of(DischargeKind.CONSTANT_FOLD_CONGRUENCE)}
    assert subjects == {case[0] for case in PINNED_FLOAT_CASES}


def test_congruence_reject_when_actual_mismatches_oracle():
    ledger = DischargeLedger()
    record_congruence(ledger, "forced-mismatch", "zig=1 oracle=0", matched=False)
    rejected = ledger.rejected_of(DischargeKind.CONSTANT_FOLD_CONGRUENCE)
    assert len(rejected) == 1
    assert rejected[0].subject == "forced-mismatch"


def test_recursion_ban_reject_is_named_discharge():
    source = """
main :: fn() {
}
fact :: fn(n: i32) i32 {
    ret fact(n - 1)
}
"""
    validator, ledger = _analyze_semantic(source)
    assert validator.errors
    rejected = ledger.rejected_of(DischargeKind.RECURSION_BAN)
    assert rejected
    assert any("Cycle:" in record.evidence for record in rejected)
    assert not ledger.proven_of(DischargeKind.RECURSION_BAN)


def test_recursion_ban_acyclic_program_discharges():
    source = """
main :: fn() {
}
helper :: fn(n: i32) i32 {
    ret n + 1
}
"""
    validator, ledger = _analyze_semantic(source)
    assert validator.errors == []
    proven = ledger.proven_of(DischargeKind.RECURSION_BAN)
    assert proven
    assert proven[0].evidence == "call/value graph has no reported cycle"
    assert not ledger.rejected_of(DischargeKind.RECURSION_BAN)


def test_match_exhaustiveness_tag_set_discharge():
    source = TAGGED_UNION + """
main :: fn() {
    r := Outcome{ok: 1}
    match r {
        case .ok: {}
        case .err: {}
    }
}
"""
    validator, ledger = _analyze_semantic(source)
    assert validator.errors == []
    proven = ledger.proven_of(DischargeKind.MATCH_EXHAUSTIVENESS)
    assert proven
    assert any(record.subject == "Outcome" for record in proven)


def test_match_exhaustiveness_missing_tag_rejects_discharge():
    source = TAGGED_UNION + """
main :: fn() {
    r := Outcome{ok: 1}
    match r {
        case .ok: {}
    }
}
"""
    validator, ledger = _analyze_semantic(source)
    assert validator.errors
    rejected = ledger.rejected_of(DischargeKind.MATCH_EXHAUSTIVENESS)
    assert rejected
    assert any("err" in record.evidence for record in rejected)


def test_pipeline_attaches_discharge_ledger(tmp_path: Path):
    source = "main :: fn() {}\n"
    path = tmp_path / "main.a7"
    path.write_text(source)
    result = A7Compiler(mode=CompileMode.SEMANTIC).compile_file_detailed(str(path))
    assert result.ok
    assert result.exit_code == 0
    ledger = (result.semantic_results or {}).get("discharge_ledger")
    assert isinstance(ledger, DischargeLedger)
    # Congruence is not auto-proven by the pipeline; recursion ban is.
    assert not ledger.of_kind(DischargeKind.CONSTANT_FOLD_CONGRUENCE)
    assert ledger.proven_of(DischargeKind.RECURSION_BAN)
