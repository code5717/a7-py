"""Pins for minimal where-clauses on generic declarations.

Covers:
- Conjunctions of set memberships (`where T: Numeric`,
  `where T: Numeric, U: Float`) on generic fn/struct/union declarations;
  each bound is checked against the type set the name refers to, using the
  same resolution as declared `$T: Set` constraints (predefined sets,
  inline @type_set, local aliases).
- Misuse is exit 6: richer predicates (comparisons, arbitrary exprs),
  unknown names, duplicates, value-param bounds, non-set bounds, and
  enum where-clauses. Nothing richer is silently accepted.

Out of scope: full boolean predicates (rejected by design), overload
ranking, and Zig lowering of generic functions.
"""

import subprocess
import sys
from pathlib import Path

from a7.tokens import Tokenizer
from a7.parser import Parser
from a7.passes.name_resolution import NameResolutionPass
from a7.passes.type_checker import TypeCheckingPass
from a7.passes.semantic_validator import SemanticValidationPass
from a7.errors import CompilerError
from conftest import expect_exit

ROOT = Path(__file__).resolve().parents[1]


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


def expect_success(source: str) -> bool:
    try:
        run_semantic_analysis(source)
        return True
    except CompilerError:
        return False


def expect_error(source: str, error_fragment: str = None) -> bool:
    try:
        run_semantic_analysis(source)
        return False
    except CompilerError as e:
        if error_fragment:
            return error_fragment.lower() in str(e).lower()
        return True


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    import os

    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run(
        [sys.executable, str(ROOT / "main.py"), *args],
        cwd=ROOT, capture_output=True, text=True, env=env,
    )


def check_mode(path) -> list[str]:
    return ["--mode", "semantic", str(path)]


class TestWhereOnFunctions:
    """Single and multi-param bounds check calls like declared constraints."""

    def test_single_bound_accepts_member(self):
        source = """
        add :: fn(a: $T, b: $T) $T where T: Numeric {
            ret a + b
        }
        main :: fn() {
            x := add(1, 2)
        }
        """
        assert expect_success(source)

    def test_single_bound_rejects_non_member(self):
        source = """
        add :: fn(a: $T, b: $T) $T where T: Numeric {
            ret a + b
        }
        main :: fn() {
            x := add("a", "b")
        }
        """
        assert expect_error(source, "requires Numeric")

    def test_multi_bound_conjunction_enforced(self):
        source = """
        first :: fn(a: $T, b: $U) $T where T: Numeric, U: Numeric {
            ret a
        }
        main :: fn() {
            x := first(1, "hi")
        }
        """
        assert expect_error(source, "requires Numeric")

    def test_multi_bound_accepts_members(self):
        source = """
        first :: fn(a: $T, b: $U) $T where T: Numeric, U: Numeric {
            ret a
        }
        main :: fn() {
            x := first(1, 2)
        }
        """
        assert expect_success(source)

    def test_where_matches_declared_constraint(self):
        declared = """
        P($T: Numeric) :: struct {
            x: $T,
        }
        main :: fn() {
            p := P(string){x: "hi"}
        }
        """
        where_form = """
        P($T) :: struct {
            x: $T,
        } where T: Numeric
        main :: fn() {
            p := P(string){x: "hi"}
        }
        """
        assert expect_error(declared, "requires Numeric")
        assert expect_error(where_form, "requires Numeric")

    def test_inline_type_set_bound(self):
        source = """
        f :: fn(a: $T) $T where T: @type_set(i32, i64) {
            ret a
        }
        main :: fn() {
            x := f(1)
        }
        """
        assert expect_success(source)

    def test_inline_type_set_bound_rejects_outsider(self):
        source = """
        f :: fn(a: $T) $T where T: @type_set(i32, i64) {
            ret a
        }
        main :: fn() {
            x := f("s")
        }
        """
        assert expect_error(source)

    def test_local_alias_bound(self):
        source = """
        Num :: @type_set(i32, i64)
        f :: fn(a: $T) $T where T: Num {
            ret a
        }
        main :: fn() {
            x := f(1)
        }
        """
        assert expect_success(source)

    def test_dollar_name_rejected(self):
        source = """
        f :: fn(a: $T) $T where $T: Numeric {
            ret a
        }
        main :: fn() {}
        """
        assert expect_error(source, "Unsupported where-clause bound")

    def test_newline_before_body_accepted(self):
        source = """
        convert :: fn(value: $T) $T
        where
            T: Numeric
        {
            ret value
        }
        main :: fn() {}
        """
        assert expect_success(source)


class TestWhereOnStructsAndUnions:
    """Where bounds on nominal generics check each instantiation."""

    def test_struct_bound_accepts_member(self):
        source = """
        P($T) :: struct {
            x: $T,
        } where T: Numeric
        main :: fn() {
            p := P(i32){x: 1}
        }
        """
        assert expect_success(source)

    def test_struct_bound_rejects_non_member(self):
        source = """
        P($T) :: struct {
            x: $T,
        } where T: Numeric
        main :: fn() {
            p := P(string){x: "hi"}
        }
        """
        assert expect_error(source, "requires Numeric")

    def test_union_multi_bound(self):
        source = """
        R($T, $E) :: union(tag) {
            ok: $T,
            err: $E,
        } where T: Numeric, E: Numeric
        main :: fn() {
            r := R(i32, i32){ok: 1}
        }
        """
        assert expect_success(source)

    def test_union_bound_rejects_non_member(self):
        source = """
        R($T, $E) :: union(tag) {
            ok: $T,
            err: $E,
        } where T: Numeric, E: Numeric
        main :: fn() {
            r := R(string, i32){ok: "hi"}
        }
        """
        assert expect_error(source, "requires Numeric")


class TestWhereRejected:
    """Richer predicates and malformed bounds fail at the checker (exit 6)."""

    def test_comparison_bound_rejected(self):
        source = """
        add :: fn(a: $T, b: $T) $T where T == i32 {
            ret a
        }
        main :: fn() {}
        """
        assert expect_error(source, "Unsupported where-clause bound")

    def test_bare_predicate_rejected(self):
        source = """
        add :: fn(a: $T, b: $T) $T where true {
            ret a
        }
        main :: fn() {}
        """
        assert expect_error(source, "Unsupported where-clause bound")

    def test_unknown_name_rejected(self):
        source = """
        add :: fn(a: $T, b: $T) $T where Z: Numeric {
            ret a
        }
        main :: fn() {}
        """
        assert expect_error(source, "unknown generic parameter")

    def test_duplicate_of_declared_constraint_rejected(self):
        source = """
        P($T: Numeric) :: struct {
            x: $T,
        } where T: Numeric
        main :: fn() {}
        """
        assert expect_error(source, "Duplicate constraint")

    def test_value_param_bound_rejected(self):
        source = """
        Buf($N: usize) :: struct {
            data: [$N]u8,
        } where N: Numeric
        main :: fn() {}
        """
        assert expect_error(source, "cannot constrain value parameter")

    def test_non_set_bound_rejected(self):
        source = """
        add :: fn(a: $T, b: $T) $T where T: i32 {
            ret a
        }
        main :: fn() {}
        """
        assert expect_error(source, "must be a type set")

    def test_enum_where_rejected_at_parse(self):
        source = """
        E :: enum {
            A,
            B,
        } where T: Numeric
        main :: fn() {}
        """
        assert expect_error(source)

    def test_empty_where_rejected_at_parse(self):
        source = """
        add :: fn(a: $T, b: $T) $T where {
            ret a
        }
        main :: fn() {}
        """
        assert expect_error(source, "at least one constraint")


class TestWhereExitCodes:
    """Stage pins: valid parses clean, violations and predicates exit 6."""

    def test_valid_where_parses_and_checks(self, tmp_path):
        main = tmp_path / "main.a7"
        main.write_text(
            "add :: fn(a: $T, b: $T) $T where T: Numeric {\n"
            "    ret a + b\n"
            "}\n"
            "main :: fn() {}\n",
            encoding="utf-8",
        )
        result = run_cli(check_mode(main))
        assert result.returncode == 0, result.stdout + result.stderr

    def test_violation_exits_semantic(self, tmp_path):
        main = tmp_path / "main.a7"
        main.write_text(
            "add :: fn(a: $T, b: $T) $T where T: Numeric {\n"
            "    ret a + b\n"
            "}\n"
            "main :: fn() {\n"
            "    x := add(\"a\", \"b\")\n"
            "}\n",
            encoding="utf-8",
        )
        result = run_cli(check_mode(main))
        assert result.returncode == 6, result.stdout + result.stderr

    def test_richer_predicate_exits_semantic(self, tmp_path):
        main = tmp_path / "main.a7"
        main.write_text(
            "add :: fn(a: $T, b: $T) $T where T == i32 {\n"
            "    ret a\n"
            "}\n"
            "main :: fn() {}\n",
            encoding="utf-8",
        )
        result = run_cli(check_mode(main))
        assert result.returncode == 6, result.stdout + result.stderr

    def test_struct_violation_exits_semantic(self, tmp_path):
        main = tmp_path / "main.a7"
        main.write_text(
            "P($T) :: struct {\n"
            "    x: $T,\n"
            "} where T: Numeric\n"
            "main :: fn() {\n"
            "    p := P(string){x: \"hi\"}\n"
            "}\n",
            encoding="utf-8",
        )
        result = run_cli(check_mode(main))
        assert result.returncode == 6, result.stdout + result.stderr


class TestTrailingComma:
    def test_trailing_comma_before_function_body_is_parse_error(self, tmp_path):
        expect_exit("""
add :: fn(a: $T, b: $T) $T where T: Numeric, {
    ret a + b
}
main :: fn() {}
""", tmp_path, 5, "Expected a constraint after ',' in where clause")

    def test_comma_then_newline_continues_the_clause(self):
        assert expect_error("""
        pick :: fn(a: $T, b: $U) $T where T: Numeric,
            U: Integer {
            ret a
        }
        main :: fn() {
            x := pick(1, 2.5)
        }
        """, "requires Integer")
