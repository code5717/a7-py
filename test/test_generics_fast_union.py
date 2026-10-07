"""Pins for generic `union(tag)` specialization and conflicting `$T` bindings.

- `union(tag)` declarations with `$T` fields monomorphize positionally
  like generic structs (`Outcome(i32, string){...}`).
- Conflicting `$T` bindings at one call site are a compile error.
- A wrong number of type arguments is an arity error naming both counts.
"""

from a7.tokens import Tokenizer
from a7.parser import Parser
from a7.passes.name_resolution import NameResolutionPass
from a7.passes.type_checker import TypeCheckingPass
from a7.passes.semantic_validator import SemanticValidationPass
from a7.errors import CompilerError
from conftest import expect_exit, failure_text


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


class TestGenericUnionSpecialization:
    """2a: positional union specialization monomorphizes like structs."""

    def test_union_specialization_initializes(self):
        source = """
        Outcome :: union(tag) {
            ok: $T,
            err: $E,
        }

        main :: fn() {
            r := Outcome(i32, string){ok: 1}
        }
        """
        assert expect_success(source)

    def test_union_specialization_checks_field_type(self):
        source = """
        Outcome :: union(tag) {
            ok: $T,
            err: $E,
        }

        main :: fn() {
            r := Outcome(i32, string){ok: "nope"}
        }
        """
        assert expect_error(source, "Union field 'ok'")

    def test_union_specialization_rejects_unknown_field(self):
        source = """
        Outcome :: union(tag) {
            ok: $T,
            err: $E,
        }

        main :: fn() {
            r := Outcome(i32, string){missing: 1}
        }
        """
        assert expect_error(source, "Union has no such tag (Union 'Outcome' has no tag 'missing')")

    def test_union_specialization_field_access(self):
        source = """
        Outcome :: union(tag) {
            ok: $T,
            err: $E,
        }

        main :: fn() {
            r := Outcome(i32, string){ok: 1}
            x := r.ok
        }
        """
        assert expect_success(source)

    def test_distinct_specializations_do_not_mix(self):
        source = """
        Outcome :: union(tag) {
            ok: $T,
            err: $E,
        }

        main :: fn() {
            r: Outcome(string, string) = Outcome(i32, string){ok: 1}
        }
        """
        assert expect_error(source, "Type mismatch")

    def test_single_param_union(self):
        source = """
        Maybe :: union(tag) {
            just: $T,
            nothing: bool,
        }

        main :: fn() {
            m := Maybe(i32){just: 7}
        }
        """
        assert expect_success(source)


class TestConflictingInferenceIsError:
    """Conflicting $T bindings at one site are a compile error."""

    def test_conflicting_bindings_error(self):
        source = """
        f :: fn(a: $T, b: $T) $T { ret a }

        main :: fn() {
            y := f(1, "hi")
        }
        """
        assert expect_error(source, "Conflicting types for $T")

    def test_conflict_names_both_types(self):
        source = """
        f :: fn(a: $T, b: $T) $T { ret a }

        main :: fn() {
            y := f(1, "hi")
        }
        """
        try:
            run_semantic_analysis(source)
            assert False, "expected a conflicting-binding error"
        except CompilerError as e:
            message = str(e).lower()
            assert "i32" in message
            assert "string" in message

    def test_matching_bindings_still_pass(self):
        source = """
        f :: fn(a: $T, b: $T) $T { ret a }

        main :: fn() {
            y := f(1, 2)
        }
        """
        assert expect_success(source)

    def test_conflict_headline_names_the_conflict(self, tmp_path):
        result = expect_exit("""
        f :: fn(a: $T, b: $T) $T { ret a }

        main :: fn() {
            x: i32 = 1
            y := f(x, "hi")
        }
        """, tmp_path, 6, "Conflicting generic parameter bindings: Conflicting types for $T")
        assert "Generic parameter count mismatch" not in failure_text(result)


GENERIC_RESULT = """
Outcome :: union(tag) {
    ok: $T,
    err: $E,
}
"""

GENERIC_PAIR = """
Pair($A, $B) :: struct {
    a: $A,
    b: $B,
}
"""


class TestTypeArgumentCount:
    """`Name(args){...}` with the wrong number of arguments is an arity error."""

    def test_union_too_few_arguments(self, tmp_path):
        result = expect_exit(GENERIC_RESULT + """
        main :: fn() {
            c := Outcome(i32){ok: 1}
        }
        """, tmp_path, 6,
            "Generic parameter count mismatch: Outcome takes 2 generic argument(s) ($T, $E), got 1")
        assert len(result.failure.details) == 1, failure_text(result)

    def test_union_too_many_arguments(self, tmp_path):
        result = expect_exit(GENERIC_RESULT + """
        main :: fn() {
            d := Outcome(i32, string, bool){ok: 1}
        }
        """, tmp_path, 6, "Outcome takes 2 generic argument(s) ($T, $E), got 3")
        assert "Union field 'ok'" not in failure_text(result)

    def test_struct_too_few_arguments(self, tmp_path):
        result = expect_exit(GENERIC_PAIR + """
        main :: fn() {
            p := Pair(i32){a: 1, b: 2}
        }
        """, tmp_path, 6, "Pair takes 2 generic argument(s) ($A, $B), got 1")
        assert len(result.failure.details) == 1, failure_text(result)

    def test_struct_too_many_arguments(self, tmp_path):
        expect_exit(GENERIC_PAIR + """
        main :: fn() {
            p := Pair(i32, i32, i32){a: 1, b: 2}
        }
        """, tmp_path, 6, "Pair takes 2 generic argument(s) ($A, $B), got 3")

    def test_matching_count_still_passes(self):
        assert expect_success(GENERIC_PAIR + """
        main :: fn() {
            p := Pair(i32, bool){a: 1, b: true}
        }
        """)

    def test_annotation_too_few_arguments(self, tmp_path):
        result = expect_exit(GENERIC_PAIR + """
        main :: fn() {
            x: Pair(i32)
        }
        """, tmp_path, 6, "Pair takes 2 generic argument(s) ($A, $B), got 1")
        assert len(result.failure.details) == 1, failure_text(result)

    def test_annotation_too_many_arguments(self, tmp_path):
        expect_exit(GENERIC_RESULT + """
        main :: fn() {
            z: Outcome(i32, i32, i32)
        }
        """, tmp_path, 6, "Outcome takes 2 generic argument(s) ($T, $E), got 3")

    def test_parameter_annotation_arity_reported_once(self, tmp_path):
        result = expect_exit(GENERIC_PAIR + """
        take :: fn(p: ref Pair(i32)) {}
        main :: fn() {}
        """, tmp_path, 6, "Pair takes 2 generic argument(s) ($A, $B), got 1")
        assert len(result.failure.details) == 1, failure_text(result)
