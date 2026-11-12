"""Named proof-discharge milestones (P-PROOF).

Pins constant-fold congruence, recursion-ban graph records, and tagged-union
match exhaustiveness as DischargeKind entries. Behavior stays with the
existing semantic/exact-constant paths; this file checks the ledger API.
"""

from pathlib import Path

from a7.ast_nodes import ASTNode, NodeKind
from a7.compile import A7Compiler, CompileMode
from a7.parser import Parser
from a7.passes.name_resolution import NameResolutionPass
from a7.passes.semantic_validator import SemanticValidationPass
from a7.passes.type_checker import TypeCheckingPass
from a7.proof_discharge import (
    DischargeKind,
    DischargeLedger,
    check_pinned_constant_fold_congruence,
)
from a7.tokens import Tokenizer

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


def test_pinned_constant_fold_congruence_discharges():
    ledger = check_pinned_constant_fold_congruence()
    records = ledger.of_kind(DischargeKind.CONSTANT_FOLD_CONGRUENCE)
    assert records
    assert all(record.proven for record in records)
    subjects = {record.subject for record in records}
    assert "i32-add-overflow" in subjects
    assert "f64-mul-inf" in subjects
    assert "f64-inf-minus-inf-nan" in subjects


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
    assert ledger.proven_of(DischargeKind.CONSTANT_FOLD_CONGRUENCE)
    assert ledger.proven_of(DischargeKind.RECURSION_BAN)
