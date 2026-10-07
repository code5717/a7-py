"""Pins for $N value parameters on generic structs and unions (checker side).

Covers:
- Declared value params ($N: usize, fixed-width ints, bool) size arrays; the
  declaration and named-constant instantiation (Buf(SIZE), SIZE :: 4)
  type-check, and distinct values are distinct types.
- A constant argument folds through the exact evaluator: `NEG :: -1` and
  `SUM :: 2 + 2` are valid value arguments.
- Misuse is exit 6 at struct/union literals and at type annotations: bare
  $N as a type, a value for a type parameter, a type for a value parameter,
  bool/int confusion, out-of-range values, bool-sized arrays, undeclared $N
  in size position, and passing $N on as a generic argument.
- Literal value arguments (Buf(4)) do not parse: the type-argument list
  only takes types, so values come through named constants.
- Generic functions may declare $N, but calls cannot infer it.
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
from conftest import expect_exit, expect_ok, failure_text

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


class TestValueParamDeclaration:
    """Declared $N kinds type-check; undeclared $N keeps failing."""

    def test_usize_param_declaration_accepted(self):
        source = """
        Buf($N: usize) :: struct {
            data: [$N]u8,
        }
        main :: fn() {}
        """
        assert expect_success(source)

    def test_small_int_param_declaration_accepted(self):
        source = """
        Buf($N: u8) :: struct {
            data: [$N]u8,
        }
        main :: fn() {}
        """
        assert expect_success(source)

    def test_bool_param_declaration_accepted(self):
        source = """
        Flag($B: bool) :: struct {
            on: bool,
        }
        main :: fn() {}
        """
        assert expect_success(source)

    def test_undeclared_param_in_size_still_rejected(self):
        source = """
        Buf :: struct {
            data: [$N]u8,
        }
        main :: fn() {}
        """
        assert expect_error(source, "Array length")

    def test_unconstrained_param_in_size_still_rejected(self):
        source = """
        Buf($N) :: struct {
            data: [$N]u8,
        }
        main :: fn() {}
        """
        assert expect_error(source, "Array length")

    def test_bool_param_cannot_size_array(self):
        source = """
        Bad($B: bool) :: struct {
            data: [$B]u8,
        }
        main :: fn() {}
        """
        assert expect_error(source, "cannot size an array")

    def test_bare_value_param_is_not_a_type(self):
        source = """
        Wrap($N: usize) :: struct {
            n: $N,
        }
        main :: fn() {}
        """
        assert expect_error(source, "not a type")


class TestValueParamInstantiation:
    """Named-constant values instantiate; distinct values are distinct types."""

    def test_const_value_instantiates_and_checks_fields(self):
        source = """
        SIZE :: 4
        Buf($N: usize) :: struct {
            data: [$N]u8,
        }
        main :: fn() {
            b := Buf(SIZE){data: [1, 2, 3, 4]}
        }
        """
        assert expect_success(source)

    def test_wrong_element_count_rejected(self):
        source = """
        SIZE :: 4
        Buf($N: usize) :: struct {
            data: [$N]u8,
        }
        main :: fn() {
            b := Buf(SIZE){data: [1, 2]}
        }
        """
        assert expect_error(source)

    def test_distinct_values_do_not_mix(self):
        source = """
        A :: 2
        B :: 4
        Buf($N: usize) :: struct {
            data: [$N]u8,
        }
        main :: fn() {
            x: Buf(A) = Buf(B){data: [1, 2, 3, 4]}
        }
        """
        assert expect_error(source, "Type mismatch")

    def test_aliased_constant_value_instantiates(self):
        source = """
        SIZE :: 4
        ALIAS :: SIZE
        Buf($N: usize) :: struct {
            data: [$N]u8,
        }
        main :: fn() {
            b := Buf(ALIAS){data: [1, 2, 3, 4]}
        }
        """
        assert expect_success(source)

    def test_annotated_instance_field_access(self):
        source = """
        SIZE :: 4
        Buf($N: usize) :: struct {
            data: [$N]u8,
        }
        main :: fn() {
            b: Buf(SIZE) = Buf(SIZE){data: [1, 2, 3, 4]}
            first := b.data[0]
        }
        """
        assert expect_success(source)

    def test_union_value_param(self):
        source = """
        SIZE :: 4
        Slot($N: usize) :: union(tag) {
            raw: [$N]u8,
            empty: bool,
        }
        main :: fn() {
            s := Slot(SIZE){raw: [1, 2, 3, 4]}
        }
        """
        assert expect_success(source)

    def test_type_for_value_param_rejected(self):
        source = """
        Buf($N: usize) :: struct {
            data: [$N]u8,
        }
        main :: fn() {
            b := Buf(i32){data: [1]}
        }
        """
        assert expect_error(source, "requires a comptime usize")

    def test_value_for_type_param_rejected(self):
        source = """
        SIZE :: 4
        P($T) :: struct {
            x: $T,
        }
        main :: fn() {
            p := P(SIZE){x: 1}
        }
        """
        assert expect_error(source, "takes a type")

    def test_bool_const_instantiates_bool_param(self):
        source = """
        YES :: true
        Flag($B: bool) :: struct {
            on: bool,
        }
        main :: fn() {
            f := Flag(YES){on: true}
        }
        """
        assert expect_success(source)

    def test_int_for_bool_param_rejected(self):
        source = """
        SIZE :: 4
        Flag($B: bool) :: struct {
            on: bool,
        }
        main :: fn() {
            f := Flag(SIZE){on: true}
        }
        """
        assert expect_error(source, "requires a comptime bool")

    def test_bool_for_int_param_rejected(self):
        source = """
        YES :: true
        Buf($N: usize) :: struct {
            data: [$N]u8,
        }
        main :: fn() {
            b := Buf(YES){data: [1]}
        }
        """
        assert expect_error(source, "got bool")

    def test_out_of_range_value_rejected(self):
        source = """
        BIG :: 300
        Small($N: u8) :: struct {
            data: [$N]u8,
        }
        main :: fn() {
            s := Small(BIG){data: [1]}
        }
        """
        assert expect_error(source, "out of range")


class TestValueParamsOnFunctions:
    """Functions may declare $N; calls cannot infer it."""

    def test_function_value_param_declares(self):
        source = """
        fill($N: usize) :: fn(buf: [$N]u8) {
        }
        main :: fn() {}
        """
        assert expect_success(source)

    def test_function_value_param_call_needs_instantiation(self):
        source = """
        fill($N: usize) :: fn(buf: [$N]u8) {
        }
        main :: fn() {
            b: [4]u8 = [1, 2, 3, 4]
            fill(b)
        }
        """
        assert expect_error(source, "Could not infer")


class TestWhereClauseStage:
    def test_where_clause_parses_and_checks(self, tmp_path):
        main = tmp_path / "main.a7"
        main.write_text(
            "add :: fn(a: $T, b: $T) $T where T: Numeric {\n"
            "    ret a + b\n"
            "}\n"
            "main :: fn() {}\n",
            encoding="utf-8",
        )
        result = run_cli(["--mode", "semantic", str(main)])
        assert result.returncode == 0, result.stdout + result.stderr


VALUE_DECLS = """
SIZE :: 4
FLAG :: true
BIG :: 300
Buf($N: usize) :: struct {
    data: [$N]u8,
}
Small($N: u8) :: struct {
    x: i32,
}
Pair($T) :: struct {
    a: $T,
}
"""


class TestKindChecksAtAnnotations:
    """`name: Buf(ARG)` gets the same kind checks as `Buf(ARG){...}`."""

    def test_bool_for_usize_param_rejected(self, tmp_path):
        expect_exit(VALUE_DECLS + """
        main :: fn() {
            a: Buf(FLAG)
        }
        """, tmp_path, 6, "Value parameter '$N' of Buf requires a comptime usize, got bool")

    def test_out_of_range_for_u8_param_rejected(self, tmp_path):
        expect_exit(VALUE_DECLS + """
        main :: fn() {
            b: Small(BIG)
        }
        """, tmp_path, 6, "Value parameter '$N' of Small requires a comptime u8, got 300 out of range")

    def test_value_for_type_param_rejected(self, tmp_path):
        expect_exit(VALUE_DECLS + """
        main :: fn() {
            c: Pair(SIZE)
        }
        """, tmp_path, 6, "Generic parameter '$T' of Pair takes a type, got value 4")

    def test_type_for_value_param_rejected(self, tmp_path):
        expect_exit(VALUE_DECLS + """
        main :: fn() {
            d: Buf(i32)
        }
        """, tmp_path, 6, "Value parameter '$N' of Buf requires a comptime usize, got type i32")

    def test_parameter_annotation_checked(self, tmp_path):
        expect_exit(VALUE_DECLS + """
        take :: fn(b: ref Buf(FLAG)) {}
        main :: fn() {}
        """, tmp_path, 6, "Value parameter '$N' of Buf requires a comptime usize, got bool")

    def test_field_annotation_checked_before_its_struct_is_declared(self, tmp_path):
        expect_exit("""
        FLAG :: true
        Holder :: struct {
            inner: Buf(FLAG),
        }
        Buf($N: usize) :: struct {
            data: [$N]u8,
        }
        main :: fn() {}
        """, tmp_path, 6, "Value parameter '$N' of Buf requires a comptime usize, got bool")

    def test_union_annotation_checked(self, tmp_path):
        expect_exit("""
        FLAG :: true
        Slot($N: usize) :: union(tag) {
            data: [$N]u8,
            none: i32,
        }
        main :: fn() {
            s: Slot(FLAG)
        }
        """, tmp_path, 6, "Value parameter '$N' of Slot requires a comptime usize, got bool")

    def test_valid_annotation_passes_the_checker(self):
        assert expect_success(VALUE_DECLS + """
        main :: fn() {
            a: Buf(SIZE)
            p: Pair(i32)
        }
        """)


class TestValueArgFolding:
    """Constant arguments fold through the exact evaluator."""

    def test_negative_constant_is_a_value_arg(self):
        assert expect_success("""
        NEG :: -1
        Off($N: i8) :: struct {
            x: i32,
        }
        main :: fn() {
            a := Off(NEG){x: 1}
        }
        """)

    def test_constant_expression_sizes_the_array(self):
        assert expect_success("""
        SUM :: 2 + 2
        Buf($N: usize) :: struct {
            data: [$N]u8,
        }
        main :: fn() {
            b := Buf(SUM){data: [1, 2, 3, 4]}
        }
        """)

    def test_constant_expression_value_is_used(self, tmp_path):
        # SUM folds to 4, so three elements do not fit [4]u8.
        expect_exit("""
        SUM :: 2 + 2
        Buf($N: usize) :: struct {
            data: [$N]u8,
        }
        main :: fn() {
            b := Buf(SUM){data: [1, 2, 3]}
        }
        """, tmp_path, 6, "expected '[4]u8', got '[3]u8'")

    def test_negative_constant_out_of_unsigned_range_rejected(self, tmp_path):
        expect_exit("""
        NEG :: -1
        Buf($N: usize) :: struct {
            x: i32,
        }
        main :: fn() {
            b := Buf(NEG){x: 1}
        }
        """, tmp_path, 6, "Value parameter '$N' of Buf requires a comptime usize, got -1 out of range")

    def test_fractional_constant_is_not_a_value_arg(self, tmp_path):
        expect_exit("""
        HALF :: 1.5
        Buf($N: usize) :: struct {
            x: i32,
        }
        main :: fn() {
            b := Buf(HALF){x: 1}
        }
        """, tmp_path, 6, "Type 'HALF'")


class TestForwardedValueParam:
    """Passing $N on as a generic argument is one error per use."""

    def test_struct_field_forwarding_reported_once(self, tmp_path):
        result = expect_exit("""
        Buf($N: usize) :: struct {
            data: [$N]u8,
        }
        Holder($N: usize) :: struct {
            inner: Buf($N),
        }
        main :: fn() {}
        """, tmp_path, 6, "Value parameter '$N' cannot be passed on as a generic argument of Buf")
        assert len(result.failure.details) == 1, failure_text(result)

    def test_function_parameter_forwarding_reported_once(self, tmp_path):
        result = expect_exit("""
        Buf($N: usize) :: struct {
            data: [$N]u8,
        }
        get($N: usize) :: fn(b: ref Buf($N)) u8 {
            ret b.data[0]
        }
        main :: fn() {}
        """, tmp_path, 6, "Value parameter '$N' cannot be passed on as a generic argument of Buf")
        assert len(result.failure.details) == 1, failure_text(result)

    def test_bare_value_param_as_function_param_type_reported_once(self, tmp_path):
        result = expect_exit("""
        bad($N: usize) :: fn(x: $N) {}
        main :: fn() {}
        """, tmp_path, 6, "Value parameter '$N' holds a comptime value, not a type")
        assert len(result.failure.details) == 1, failure_text(result)


def test_value_kind_recorded_on_generic_param_node():
    """The backend reads `value_kind` from the declaration's GENERIC_PARAM nodes."""
    source = """
    Mixed($T, $N: usize, $B: bool) :: struct {
        data: [$N]$T,
    }
    main :: fn() {}
    """
    program = parse_program(source)
    resolver = NameResolutionPass()
    symbols = resolver.analyze(program, "<test>")
    TypeCheckingPass(symbols).analyze(program, "<test>")
    struct = next(decl for decl in program.declarations if decl.name == "Mixed")
    kinds = {param.name: getattr(param, "value_kind", None) for param in struct.generic_params}
    assert kinds == {"T": None, "N": "usize", "B": "bool"}
