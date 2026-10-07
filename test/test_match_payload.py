"""Pins for tagged-union match arms.

- Bare `case tag:` over a tagged union is an exit-6 error; it used to
  capture the whole union value (`const ok = __a7_match_N;`).
- A match over a tagged union with uncovered tags and no `else` is one
  exit-6 error at the match span listing every uncovered tag.
- Leading-dot patterns parse: `case .tag:` tests without binding,
  `case .tag(name):` binds the payload by value. There is no `.tag(_)`
  form.
- Unknown tags, shared-case bindings, `fall` in a tag arm, a tag named
  twice, and a binding whose payload type holds a `string` are exit-6
  errors. Test-only arms over such payloads stay allowed.
- A `ref` to a tagged union matches like the union.
- `else` and explicit `_` stay as opt-outs; untagged unions and non-union
  scrutinees are unaffected.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from a7.tokens import Tokenizer
from a7.parser import Parser
from a7.passes.name_resolution import NameResolutionPass
from a7.passes.type_checker import TypeCheckingPass
from a7.passes.semantic_validator import SemanticValidationPass
from a7.ast_nodes import NodeKind
from a7.errors import CompilerError
from conftest import compile_program, expect_exit, expect_ok, failure_text, run_both_profiles

ROOT = Path(__file__).resolve().parents[1]

RESULT_UNION = """
Outcome :: union(tag) {
    ok: i32
    err: i32
}
"""

STRING_UNION = """
Outcome :: union(tag) {
    ok: i32
    err: string
}
"""

GENERIC_UNION = """
Outcome :: union(tag) {
    ok: $T,
    err: $E,
}
"""

IO_IMPORT = 'io :: import "std/io"\n'


def parse_program(source: str):
    tokenizer = Tokenizer(source)
    tokens = tokenizer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


def run_semantic_analysis(source: str):
    program = parse_program(source)

    resolver = NameResolutionPass()
    symbols = resolver.analyze(program, "<test>")
    if resolver.errors:
        raise resolver.errors[0]

    type_checker = TypeCheckingPass(symbols)
    node_types = type_checker.analyze(program, "<test>")
    if type_checker.errors:
        raise type_checker.errors[0]

    validator = SemanticValidationPass(symbols, node_types)
    validator.analyze(program, "<test>")
    if validator.errors:
        raise validator.errors[0]

    return symbols, node_types


def validator_errors_with_real_types(source: str) -> list:
    """Run the real front end and return only the validator's errors.

    Name resolution must be clean. Type-checker errors are ignored, so a
    test using this helper checks the validator alone, not what the CLI
    reports.
    """
    program = parse_program(source)
    resolver = NameResolutionPass()
    symbols = resolver.analyze(program, "<test>")
    assert not resolver.errors
    type_checker = TypeCheckingPass(symbols)
    node_types = type_checker.analyze(program, "<test>")
    validator = SemanticValidationPass(symbols, node_types)
    validator.analyze(program, "<test>")
    return [str(e) for e in validator.errors]


def expect_success(source: str) -> bool:
    try:
        run_semantic_analysis(source)
        return True
    except CompilerError:
        return False


def expect_error(source: str, error_fragment: str | None = None) -> bool:
    try:
        run_semantic_analysis(source)
        return False
    except CompilerError as e:
        if error_fragment:
            return error_fragment.lower() in str(e).lower()
        return True


def run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run(
        [sys.executable, str(ROOT / "main.py"), *args],
        cwd=cwd, capture_output=True, text=True, env=env,
    )


def write_source(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return path


def cli_exit_and_output(tmp_path: Path, name: str, source: str) -> tuple[int, str]:
    src = write_source(tmp_path, name, source)
    proc = run_cli([str(src), "-o", str(tmp_path / (name + ".zig"))], ROOT)
    return proc.returncode, proc.stdout + proc.stderr


class TestBareCaseRejected:
    def test_bare_variant_name_rejected(self):
        source = RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case ok: {
                    x := 1
                }
            }
        }
        """
        assert expect_error(source, "never tests the tag")

    def test_bare_stray_name_rejected(self):
        source = RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case Blu: {
                    x := 1
                }
            }
        }
        """
        assert expect_error(source, "never tests the tag")

    def test_bare_case_exit_code_6(self, tmp_path: Path):
        code, out = cli_exit_and_output(tmp_path, "bare.a7", IO_IMPORT + RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case ok: {
                    io.println("ok")
                }
            }
        }
        """)
        assert code == 6, out
        assert "never tests the tag" in out

    def test_bare_case_in_match_expr_rejected(self, tmp_path: Path):
        code, out = cli_exit_and_output(tmp_path, "exprbare.a7", IO_IMPORT + RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            x := match r {
                case ok: 1
            }
            io.println("{}", x)
        }
        """)
        assert code == 6, out
        assert "never tests the tag" in out


class TestExhaustivenessListing:
    def test_empty_match_lists_all_tags(self, tmp_path: Path):
        code, out = cli_exit_and_output(tmp_path, "empty.a7", IO_IMPORT + RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
            }
        }
        """)
        assert code == 6, out
        flat = out.replace("\n", " ")
        assert "misses tag(s): ok, err" in flat

    def test_partial_coverage_lists_only_missing(self):
        source = RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case Outcome.ok: {
                    x := 1
                }
            }
        }
        """
        errors = validator_errors_with_real_types(source)
        assert len(errors) == 1, errors
        assert "misses tag(s): err" in errors[0]
        assert "ok" not in errors[0].split("misses tag(s):")[1].split(";")[0].replace("err", "")

    def test_dot_partial_coverage_lists_only_missing(self):
        source = RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case .ok: {
                    x := 1
                }
            }
        }
        """
        errors = validator_errors_with_real_types(source)
        assert len(errors) == 1, errors
        assert "misses tag(s): err" in errors[0]

    def test_dot_partial_coverage_exit_code_6(self, tmp_path: Path):
        code, out = cli_exit_and_output(tmp_path, "dotpartial.a7", IO_IMPORT + RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case .ok: {
                    io.println("ok")
                }
            }
        }
        """)
        assert code == 6, out

    def test_one_error_per_match(self):
        source = RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
            }
            match r {
            }
        }
        """
        errors = validator_errors_with_real_types(source)
        assert len(errors) == 2, errors


class TestOptOutsUnaffected:
    def test_else_opts_out(self, tmp_path: Path):
        code, out = cli_exit_and_output(tmp_path, "elseok.a7", IO_IMPORT + RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                else: {
                    io.println("other")
                }
            }
        }
        """)
        assert code == 0, out

    def test_explicit_wildcard_opts_out(self, tmp_path: Path):
        code, out = cli_exit_and_output(tmp_path, "wildok.a7", IO_IMPORT + RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case _: {
                    io.println("wild")
                }
            }
        }
        """)
        assert code == 0, out

    def test_untagged_union_unaffected(self, tmp_path: Path):
        code, out = cli_exit_and_output(tmp_path, "untagged.a7", IO_IMPORT + """
        Both :: union {
            a: i32
            b: i32
        }

        main :: fn() {
            r := Both{a: 1}
            match r {
                case a: {
                    io.println("a")
                }
            }
        }
        """)
        assert code == 0, out

    def test_non_union_scrutinee_unaffected(self, tmp_path: Path):
        code, out = cli_exit_and_output(tmp_path, "boolok.a7", IO_IMPORT + """
        main :: fn() {
            flag := true
            match flag {
                case other: {
                    io.println("v")
                }
            }
        }
        """)
        assert code == 0, out


class TestGenericUnionInterop:
    def test_specialized_union_listing_uses_base_tags(self):
        source = GENERIC_UNION + """
        main :: fn() {
            r := Outcome(i32, string){ok: 1}
            match r {
            }
        }
        """
        errors = validator_errors_with_real_types(source)
        assert len(errors) == 1, errors
        assert "misses tag(s): ok, err" in errors[0]

    def test_specialized_union_partial_lists_missing(self):
        source = GENERIC_UNION + """
        main :: fn() {
            r := Outcome(i32, string){ok: 1}
            match r {
                case .ok: {
                    x := 1
                }
            }
        }
        """
        errors = validator_errors_with_real_types(source)
        assert len(errors) == 1, errors
        assert "misses tag(s): err" in errors[0]

    def test_specialized_union_empty_match_exit_code_6(self, tmp_path: Path):
        code, out = cli_exit_and_output(tmp_path, "genempty.a7", IO_IMPORT + GENERIC_UNION + """
        main :: fn() {
            r := Outcome(i32, string){ok: 1}
            match r {
            }
        }
        """)
        assert code == 6, out
        assert "misses tag(s): ok, err" in out.replace("\n", " ")


class TestDotPatternSyntax:
    def test_dot_payload_syntax_parses(self):
        source = """
        Shape :: union(tag) { circle: f32, none: bool }

        is_none :: fn(s: Shape) bool {
            ret match s {
                case .none: true
                else: false
            }
        }
        """
        program = parse_program(source)
        assert program is not None

    def test_dot_test_only_shape(self):
        program = parse_program("main :: fn() { match s { case .none: { x := 1 } } }")
        case = program.declarations[0].body.statements[0].cases[0]
        pattern = case.patterns[0]
        assert pattern.kind == NodeKind.PATTERN_ENUM
        assert pattern.enum_type == ""
        assert pattern.variant == "none"
        assert not (pattern.name or "")

    def test_dot_bind_shape(self):
        program = parse_program("main :: fn() { match s { case .circle(r): { x := 1 } } }")
        case = program.declarations[0].body.statements[0].cases[0]
        pattern = case.patterns[0]
        assert pattern.kind == NodeKind.PATTERN_ENUM
        assert pattern.enum_type == ""
        assert pattern.variant == "circle"
        assert pattern.name == "r"

    def test_dot_placeholder_rejected(self):
        try:
            parse_program("main :: fn() { match s { case .tag(_): { x := 1 } } }")
            assert False, "expected a parse error for .tag(_)"
        except CompilerError as e:
            assert ".tag(_)" in str(e)

    def test_dot_empty_binding_rejected(self):
        try:
            parse_program("main :: fn() { match s { case .tag(): { x := 1 } } }")
            assert False, "expected a parse error for .tag()"
        except CompilerError as e:
            assert "binding name" in str(e)


NAME_STRUCT = """
Name :: struct {
    s: string,
}
"""

HOLDS_STRING = "holds a string"


class TestTagArmRules:
    """Tag-arm rules through the full pipeline (exit code and message)."""

    def test_unknown_dot_tag_rejected(self, tmp_path: Path):
        result = expect_exit(RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case .bogus: {
                }
                else: {
                }
            }
        }
        """, tmp_path, 6, "Union has no such tag (Union 'Outcome' has no tag 'bogus')")
        assert "Struct has no such field" not in failure_text(result)

    def test_unknown_qualified_tag_rejected(self, tmp_path: Path):
        result = expect_exit(RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case Outcome.nope: {
                }
                else: {
                }
            }
        }
        """, tmp_path, 6, "Union has no such tag (Union 'Outcome' has no tag 'nope')")
        assert "Struct has no such field" not in failure_text(result)

    def test_shared_case_binding_rejected(self, tmp_path: Path):
        expect_exit(RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case .ok(v), .err(e): {
                }
            }
        }
        """, tmp_path, 6, "must be the only pattern in its case")

    def test_string_payload_bind_rejected(self, tmp_path: Path):
        result = expect_exit(STRING_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case .ok(v): {
                }
                case .err(e): {
                }
            }
        }
        """, tmp_path, 6, "case '.err(e)' binds a payload of type 'string' by value")
        text = failure_text(result)
        assert "match '.err' without a binding" in text
        assert "'.ok(v)'" not in text

    def test_generic_string_payload_bind_rejected(self, tmp_path: Path):
        expect_exit(GENERIC_UNION + """
        main :: fn() {
            r := Outcome(i32, string){ok: 1}
            match r {
                case .ok(v): {
                }
                case .err(e): {
                }
            }
        }
        """, tmp_path, 6, "case '.err(e)' binds a payload of type 'string' by value")

    def test_struct_with_string_field_payload_bind_rejected(self, tmp_path: Path):
        expect_exit(NAME_STRUCT + """
        R :: union(tag) {
            ok: Name
            none: i32
        }
        main :: fn() {
            r := R{none: 1}
            match r {
                case .ok(v): {
                }
                case .none: {
                }
            }
        }
        """, tmp_path, 6, "case '.ok(v)' binds a payload of type 'Name' by value")

    def test_string_array_payload_bind_rejected(self, tmp_path: Path):
        expect_exit("""
        R :: union(tag) {
            arr: [2]string
            none: i32
        }
        main :: fn() {
            r := R{none: 1}
            match r {
                case .arr(a): {
                }
                case .none: {
                }
            }
        }
        """, tmp_path, 6, "case '.arr(a)' binds a payload of type '[2]string' by value")

    def test_generic_array_bound_to_string_payload_bind_rejected(self, tmp_path: Path):
        expect_exit("""
        Box :: union(tag) {
            items: [2]$T
            none: i32
        }
        main :: fn() {
            b := Box(string){items: ["a", "b"]}
            match b {
                case .items(xs): {
                }
                case .none: {
                }
            }
        }
        """, tmp_path, 6, "case '.items(xs)' binds a payload of type '[2]string' by value")

    def test_generic_struct_bound_to_string_payload_bind_rejected(self, tmp_path: Path):
        expect_exit("""
        Wrap($T) :: struct {
            v: $T,
        }
        R :: union(tag) {
            ok: Wrap(string)
            none: i32
        }
        main :: fn() {
            r := R{none: 1}
            match r {
                case .ok(w): {
                }
                case .none: {
                }
            }
        }
        """, tmp_path, 6, "case '.ok(w)' binds a payload of type 'Wrap(string)' by value")

    def test_payload_message_has_no_plan_ids(self, tmp_path: Path):
        result = compile_program(STRING_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case .err(e): {
                }
                else: {
                }
            }
        }
        """, tmp_path)
        text = failure_text(result)
        assert HOLDS_STRING in text
        for plan_id in ("G5a", "M33", "M49"):
            assert plan_id not in text

    def test_struct_without_string_payload_bind_allowed(self, tmp_path: Path):
        expect_ok("""
        Point :: struct {
            x: i32,
            y: i32,
        }
        R :: union(tag) {
            at: Point
            none: i32
        }
        main :: fn() {
            r := R{none: 1}
            match r {
                case .at(p): {
                }
                case .none: {
                }
            }
        }
        """, tmp_path)

    def test_test_only_over_string_payload_allowed(self, tmp_path: Path):
        expect_ok(STRING_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case .ok: {
                }
                case .err: {
                }
            }
        }
        """, tmp_path)


class TestTagArmDiagnostics:
    def test_unknown_tag_in_literal_is_a_tag_error(self, tmp_path: Path):
        result = expect_exit(RESULT_UNION + """
        main :: fn() {
            r := Outcome{bogus: 1}
        }
        """, tmp_path, 6, "Union has no such tag (Union 'Outcome' has no tag 'bogus')")
        assert "Struct has no such field" not in failure_text(result)

    def test_unknown_tag_in_member_access_is_a_tag_error(self, tmp_path: Path):
        result = expect_exit(RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            x := r.nope
        }
        """, tmp_path, 6, "Union has no such tag (Union 'Outcome' has no tag 'nope')")
        assert "Struct has no such field" not in failure_text(result)

    def test_match_expression_missing_tag_reports_once(self, tmp_path: Path):
        result = expect_exit(RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            x := match r {
                case .ok(v): v
            }
        }
        """, tmp_path, 6, "match over tagged union 'Outcome' misses tag(s): err")
        assert len(result.failure.details) == 1, failure_text(result)

    def test_dot_then_qualified_same_tag_is_redundant(self, tmp_path: Path):
        expect_exit(RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case .ok: {
                }
                case Outcome.ok: {
                }
                case .err: {
                }
            }
        }
        """, tmp_path, 6, "redundant match pattern 'Outcome.ok'")

    def test_qualified_then_dot_same_tag_is_redundant(self, tmp_path: Path):
        expect_exit(RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case Outcome.err: {
                }
                case .err: {
                }
                case .ok: {
                }
            }
        }
        """, tmp_path, 6, "redundant match pattern '.err'")

    def test_fall_in_tag_arm_is_semantic_error(self, tmp_path: Path):
        expect_exit(IO_IMPORT + RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case .ok: {
                    io.println("ok")
                    fall
                }
                case .err: {
                    io.println("err")
                }
            }
        }
        """, tmp_path, 6, "fall cannot be used in a match over tagged union 'Outcome'")


REF_UNION_MATCH = IO_IMPORT + RESULT_UNION + """
show :: fn(r: ref Outcome) {
    match r {
        case .ok(v): {
            io.println("ok {}", v)
        }
        case .err(e): {
            io.println("err {}", e)
        }
    }
}

main :: fn() {
    a := Outcome{ok: 1}
    b := Outcome{err: 2}
    show(a)
    show(b)
}
"""


class TestRefTaggedUnionMatch:
    def test_ref_union_dot_arms_pass_semantic_analysis(self, tmp_path: Path):
        expect_ok(REF_UNION_MATCH, tmp_path)

    def test_ref_union_dot_arms_run(self, tmp_path: Path, zig):
        assert run_both_profiles(REF_UNION_MATCH, tmp_path, zig) == "ok 1\nerr 2\n"

    def test_ref_union_missing_tag_rejected(self, tmp_path: Path):
        expect_exit(RESULT_UNION + """
        show :: fn(r: ref Outcome) {
            match r {
                case .ok(v): {
                }
            }
        }
        main :: fn() {
            a := Outcome{ok: 1}
            show(a)
        }
        """, tmp_path, 6, "match over tagged union 'Outcome' misses tag(s): err")

    def test_ref_union_unknown_tag_rejected(self, tmp_path: Path):
        expect_exit(RESULT_UNION + """
        show :: fn(r: ref Outcome) {
            match r {
                case .bogus: {
                }
                else: {
                }
            }
        }
        main :: fn() {
            a := Outcome{ok: 1}
            show(a)
        }
        """, tmp_path, 6, "Union 'Outcome' has no tag 'bogus'")


def test_qualified_full_coverage_compiles_end_to_end(tmp_path: Path):
    code, out = cli_exit_and_output(tmp_path, "qualfull.a7", IO_IMPORT + RESULT_UNION + """
    main :: fn() {
        r := Outcome{ok: 1}
        match r {
            case Outcome.ok: {
                io.println("ok")
            }
            case Outcome.err: {
                io.println("err")
            }
        }
    }
    """)
    assert code == 0, out


def test_dot_full_coverage_compiles_end_to_end(tmp_path: Path):
    code, out = cli_exit_and_output(tmp_path, "dotfull.a7", IO_IMPORT + RESULT_UNION + """
    main :: fn() {
        r := Outcome{ok: 1}
        match r {
            case .ok(v): {
                io.println("ok")
            }
            case .err(e): {
                io.println("err")
            }
        }
    }
    """)
    assert code == 0, out


def test_bare_with_else_reports_tag_failure(tmp_path: Path):
    code, out = cli_exit_and_output(tmp_path, "bareelse.a7", IO_IMPORT + RESULT_UNION + """
    main :: fn() {
        r := Outcome{ok: 1}
        match r {
            case ok: {
                io.println("ok")
            }
            else: {
                io.println("other")
            }
        }
    }
    """)
    assert code == 6, out
    assert "never tests the tag" in out
