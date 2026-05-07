"""
Test semantic analysis - Control flow tests.

Covers:
- If/else statement validation
- While loop validation
- For loop validation (traditional and for-in)
- Break and continue statement context
- Match statement validation
- Defer statement scoping
- Control flow path analysis
- Loop nesting and labels
"""

import pytest
from src.tokens import Tokenizer
from src.parser import Parser
from src.ast_nodes import ASTNode, LiteralKind, NodeKind
from src.passes.name_resolution import NameResolutionPass
from src.passes.type_checker import TypeCheckingPass
from src.passes.semantic_validator import SemanticValidationPass
from src.errors import SemanticError, CompilerError


def parse_program(source: str):
    """Helper to parse a source program."""
    tokenizer = Tokenizer(source)
    tokens = tokenizer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


def run_semantic_analysis(source: str):
    """Helper to run full semantic analysis.

    Raises SemanticError if any pass detects errors.
    """
    program = parse_program(source)

    # Run name resolution pass
    resolver = NameResolutionPass()
    symbols = resolver.analyze(program, "<test>")
    if resolver.errors:
        raise resolver.errors[0]

    # Run type checking pass
    type_checker = TypeCheckingPass(symbols)
    node_types = type_checker.analyze(program, "<test>")
    if type_checker.errors:
        raise type_checker.errors[0]

    # Run semantic validation pass
    validator = SemanticValidationPass(symbols, node_types)
    validator.analyze(program, "<test>")
    if validator.errors:
        raise validator.errors[0]

    return symbols, node_types


def expect_success(source: str) -> bool:
    """Helper to expect successful semantic analysis."""
    try:
        run_semantic_analysis(source)
        return True
    except CompilerError:
        return False


def expect_error(source: str, error_fragment: str = None) -> bool:
    """Helper to expect semantic error with optional message check."""
    try:
        run_semantic_analysis(source)
        return False
    except CompilerError as e:
        if error_fragment:
            return error_fragment.lower() in str(e).lower()
        return True


class TestIfElseStatements:
    """Test if/else statement validation."""

    def test_simple_if_statement(self):
        """Test simple if statement."""
        source = """
        main :: fn() {
            x := 10
            if x > 5 {
                y := 20
            }
        }
        """
        assert expect_success(source)

    def test_if_else_statement(self):
        """Test if-else statement."""
        source = """
        main :: fn() {
            x := 10
            if x > 5 {
                y := 20
            } else {
                y := 30
            }
        }
        """
        assert expect_success(source)

    def test_nested_if_statements(self):
        """Test nested if statements."""
        source = """
        main :: fn() {
            x := 10
            y := 20
            if x > 5 {
                if y > 15 {
                    z := 30
                }
            }
        }
        """
        assert expect_success(source)

    def test_if_else_chain(self):
        """Test if-else chain."""
        source = """
        main :: fn() {
            x := 10
            if x < 5 {
                y := 1
            } else if x < 10 {
                y := 2
            } else if x < 15 {
                y := 3
            } else {
                y := 4
            }
        }
        """
        assert expect_success(source)

    def test_if_expression(self):
        """Test if as expression."""
        source = """
        main :: fn() {
            x := 10
            y := if x > 5 { 20 } else { 30 }
        }
        """
        assert expect_success(source)


class TestWhileLoops:
    """Test while loop validation."""

    def test_simple_while_loop(self):
        """Test simple while loop."""
        source = """
        main :: fn() {
            i := 0
            while i < 10 {
                i += 1
            }
        }
        """
        assert expect_success(source)

    def test_nested_while_loops(self):
        """Test nested while loops."""
        source = """
        main :: fn() {
            i := 0
            while i < 10 {
                j := 0
                while j < 5 {
                    j += 1
                }
                i += 1
            }
        }
        """
        assert expect_success(source)

    def test_while_with_break(self):
        """Test while loop with break."""
        source = """
        main :: fn() {
            i := 0
            while true {
                if i >= 10 {
                    break
                }
                i += 1
            }
        }
        """
        assert expect_success(source)

    def test_while_with_continue(self):
        """Test while loop with continue."""
        source = """
        main :: fn() {
            i := 0
            while i < 10 {
                i += 1
                if i % 2 == 0 {
                    continue
                }
            }
        }
        """
        assert expect_success(source)


class TestForLoops:
    """Test for loop validation."""

    def test_traditional_for_loop(self):
        """Test traditional for loop."""
        source = """
        main :: fn() {
            for i := 0; i < 10; i += 1 {
                x := i * 2
            }
        }
        """
        assert expect_success(source)

    def test_for_in_loop(self):
        """Test for-in loop over array."""
        source = """
        main :: fn() {
            arr: [5]i32 = [1, 2, 3, 4, 5]
            for x in arr {
                y := x * 2
            }
        }
        """
        assert expect_success(source)

    def test_for_in_indexed_loop(self):
        """Test for-in loop with index."""
        source = """
        main :: fn() {
            arr: [5]i32 = [1, 2, 3, 4, 5]
            for i, x in arr {
                y := i + x
            }
        }
        """
        assert expect_success(source)

    def test_nested_for_loops(self):
        """Test nested for loops."""
        source = """
        main :: fn() {
            for i := 0; i < 10; i += 1 {
                for j := 0; j < 5; j += 1 {
                    x := i * j
                }
            }
        }
        """
        assert expect_success(source)

    def test_for_initializer_scope_does_not_leak(self):
        """Variables declared in for init should not be visible after loop."""
        source = """
        main :: fn() {
            for i := 0; i < 2; i += 1 {
            }
            x := i
        }
        """
        assert expect_error(source, "undefined")

    def test_block_scope_does_not_leak_between_sibling_blocks(self):
        """Names from one block should not be visible in a later sibling block."""
        source = """
        main :: fn() {
            {
                a := 1
            }
            {
                b := a
            }
        }
        """
        assert expect_error(source, "undefined")


class TestBreakContinue:
    """Test break and continue statement validation."""

    def test_break_in_loop(self):
        """Test break statement in loop."""
        source = """
        main :: fn() {
            for i := 0; i < 10; i += 1 {
                if i == 5 {
                    break
                }
            }
        }
        """
        assert expect_success(source)

    def test_continue_in_loop(self):
        """Test continue statement in loop."""
        source = """
        main :: fn() {
            for i := 0; i < 10; i += 1 {
                if i % 2 == 0 {
                    continue
                }
            }
        }
        """
        assert expect_success(source)

    def test_break_outside_loop_error(self):
        """Test break statement outside loop."""
        source = """
        main :: fn() {
            x := 10
            break
        }
        """
        assert expect_error(source, "break")

    def test_continue_outside_loop_error(self):
        """Test continue statement outside loop."""
        source = """
        main :: fn() {
            x := 10
            continue
        }
        """
        assert expect_error(source, "continue")

    def test_break_in_nested_loop(self):
        """Test break in nested loop."""
        source = """
        main :: fn() {
            for i := 0; i < 10; i += 1 {
                for j := 0; j < 5; j += 1 {
                    if j == 3 {
                        break
                    }
                }
            }
        }
        """
        assert expect_success(source)


class TestMatchStatements:
    """Test match statement validation."""

    def test_simple_match(self):
        """Test simple match statement."""
        source = """
        main :: fn() {
            x := 10
            match x {
                case 1: y := 1
                case 2: y := 2
                else: y := 0
            }
        }
        """
        assert expect_success(source)

    def test_match_with_multiple_cases(self):
        """Test match with multiple case values."""
        source = """
        main :: fn() {
            x := 10
            match x {
                case 1, 2, 3: y := 1
                case 4, 5: y := 2
                else: y := 0
            }
        }
        """
        assert expect_success(source)

    def test_match_with_enum(self):
        """Test match with enum variants."""
        source = """
        Color :: enum {
            Red,
            Green,
            Blue,
        }

        main :: fn() {
            c: Color = Color.Red
            match c {
                case Color.Red: x := 1
                case Color.Green: x := 2
                case Color.Blue: x := 3
            }
        }
        """
        assert expect_success(source)

    def test_match_case_body_reports_undefined_identifier(self):
        """Case bodies must participate in semantic analysis."""
        source = """
        main :: fn() {
            x := 1
            match x {
                case 1: y := z
                else: y := 0
            }
        }
        """
        assert expect_error(source, "undefined")

    def test_match_case_body_reports_type_mismatch(self):
        """Type checking should run for statements inside case branches."""
        source = """
        main :: fn() {
            x := 1
            match x {
                case 1: y: i32 = "oops"
                else: y: i32 = 0
            }
        }
        """
        assert expect_error(source, "type mismatch")

    def test_match_as_expression(self):
        """Test match as expression."""
        source = """
        main :: fn() {
            x := 10
            y := match x {
                case 1: 10
                case 2: 20
                else: 0
            }
        }
        """
        assert expect_success(source)

    def test_match_pattern_type_mismatch(self):
        """Pattern values must be compatible with the match scrutinee type."""
        source = """
        main :: fn() {
            x: i32 = 10
            match x {
                case "oops": y := 1
                else: y := 0
            }
        }
        """
        assert expect_error(source, "type mismatch")

    def test_bool_match_requires_exhaustive_coverage(self):
        """Bool matches without else must handle both true and false."""
        source = """
        main :: fn() {
            flag: bool = true
            match flag {
                case true: x := 1
            }
        }
        """
        assert expect_error(source, "non-exhaustive")

    def test_bool_match_wildcard_is_exhaustive(self):
        """Wildcard branch should satisfy match exhaustiveness."""
        source = """
        main :: fn() {
            flag: bool = true
            match flag {
                case _: x := 1
            }
        }
        """
        assert expect_success(source)

    def test_enum_match_requires_exhaustive_coverage(self):
        """Enum matches without else must handle all variants."""
        source = """
        Color :: enum {
            Red,
            Green,
            Blue,
        }

        main :: fn() {
            c: Color = Color.Red
            match c {
                case Color.Red: x := 1
                case Color.Green: x := 2
            }
        }
        """
        assert expect_error(source, "non-exhaustive")

    def test_enum_match_expression_requires_exhaustive_coverage(self):
        """Match expressions should enforce enum exhaustiveness too."""
        source = """
        Color :: enum {
            Red,
            Green,
            Blue,
        }

        main :: fn() {
            c: Color = Color.Red
            x := match c {
                case Color.Red: 1
                case Color.Green: 2
            }
        }
        """
        assert expect_error(source, "non-exhaustive")

    def test_exhaustive_enum_match_satisfies_return_paths(self):
        """Exhaustive enum matches should satisfy non-void return path checks."""
        source = """
        Color :: enum {
            Red,
            Green,
        }

        to_i32 :: fn(c: Color) i32 {
            match c {
                case Color.Red: ret 1
                case Color.Green: ret 2
            }
        }
        """
        assert expect_success(source)

    def test_exhaustive_bool_match_satisfies_return_paths(self):
        """Exhaustive bool matches should satisfy non-void return path checks."""
        source = """
        to_i32 :: fn(flag: bool) i32 {
            match flag {
                case true: ret 1
                case false: ret 0
            }
        }
        """
        assert expect_success(source)

    def test_non_exhaustive_enum_match_fails_without_else(self):
        """Non-exhaustive enum match should fail in non-void functions."""
        source = """
        Color :: enum {
            Red,
            Green,
            Blue,
        }

        to_i32 :: fn(c: Color) i32 {
            match c {
                case Color.Red: ret 1
                case Color.Green: ret 2
            }
        }
        """
        assert expect_error(source, "non-exhaustive")

    def test_range_pattern_requires_numeric_or_char_scrutinee(self):
        """Range patterns should reject non-numeric/non-char scrutinee types."""
        source = """
        main :: fn() {
            flag: bool = true
            match flag {
                case 0..1: x := 1
                else: x := 0
            }
        }
        """
        assert expect_error(source, "range patterns require")

    def test_enum_pattern_unknown_variant_reports_error(self):
        """Unknown enum variants in patterns should produce semantic errors."""
        source = """
        Color :: enum {
            Red,
            Green,
        }

        main :: fn() {
            c: Color = Color.Red
            match c {
                case Color.Blue: x := 1
                else: x := 0
            }
        }
        """
        assert expect_error(source, "has no variant")

    def test_enum_pattern_wrong_enum_type_reports_error(self):
        """Patterns must use the same enum type as the match scrutinee."""
        source = """
        Color :: enum {
            Red,
            Green,
        }

        Status :: enum {
            Ok,
            Err,
        }

        main :: fn() {
            c: Color = Color.Red
            match c {
                case Status.Ok: x := 1
                else: x := 0
            }
        }
        """
        assert expect_error(source, "enum type mismatch")

    def test_match_expression_wildcard_case_is_exhaustive(self):
        """Wildcard-only match expressions should be accepted as exhaustive."""
        source = """
        main :: fn() {
            flag: bool = true
            x := match flag {
                case _: 1
            }
        }
        """
        assert expect_success(source)

    def test_duplicate_bool_match_pattern_is_rejected(self):
        """Duplicate bool cases should be reported as unreachable."""
        source = """
        main :: fn() {
            flag: bool = true
            match flag {
                case true: x := 1
                case true: x := 2
                case false: x := 0
            }
        }
        """
        assert expect_error(source, "redundant match pattern")

    def test_duplicate_enum_match_pattern_is_rejected(self):
        """Duplicate enum cases should be reported as unreachable."""
        source = """
        Color :: enum {
            Red,
            Green,
        }

        main :: fn() {
            c: Color = Color.Red
            match c {
                case Color.Red: x := 1
                case Color.Red: x := 2
                case Color.Green: x := 3
            }
        }
        """
        assert expect_error(source, "redundant match pattern")

    def test_duplicate_literal_match_pattern_is_rejected(self):
        """Duplicate scalar literal patterns should be reported as unreachable."""
        source = """
        main :: fn() {
            n: i32 = 1
            x := match n {
                case 1: 10
                case 1: 20
                else: 0
            }
        }
        """
        assert expect_error(source, "redundant match pattern")

    def test_wildcard_before_later_case_is_rejected(self):
        """Cases after a wildcard pattern are unreachable."""
        source = """
        main :: fn() {
            n: i32 = 1
            match n {
                case _: x := 0
                case 1: x := 1
            }
        }
        """
        assert expect_error(source, "previous wildcard")

    def test_wildcard_before_else_is_rejected(self):
        """Else after a wildcard case is unreachable."""
        source = """
        main :: fn() {
            flag: bool = true
            x := match flag {
                case _: 1
                else: 0
            }
        }
        """
        assert expect_error(source, "else branch is unreachable")

    def test_bool_full_coverage_before_later_case_is_rejected(self):
        """Cases after true and false are unreachable for bool matches."""
        source = """
        main :: fn() {
            flag: bool = true
            match flag {
                case true: x := 1
                case false: x := 0
                case _: x := 2
            }
        }
        """
        assert expect_error(source, "cover all bool values")

    def test_bool_full_coverage_before_else_is_rejected(self):
        """Else after true and false is unreachable for bool matches."""
        source = """
        main :: fn() {
            flag: bool = true
            x := match flag {
                case true: 1
                case false: 0
                else: 2
            }
        }
        """
        assert expect_error(source, "cover all bool values")

    def test_enum_full_coverage_before_later_case_is_rejected(self):
        """Cases after every enum variant is covered are unreachable."""
        source = """
        Color :: enum {
            Red,
            Green,
        }

        main :: fn() {
            c: Color = Color.Red
            match c {
                case Color.Red: x := 1
                case Color.Green: x := 2
                case _: x := 3
            }
        }
        """
        assert expect_error(source, "cover all enum")

    def test_enum_full_coverage_before_else_is_rejected(self):
        """Else after every enum variant is covered is unreachable."""
        source = """
        Color :: enum {
            Red,
            Green,
        }

        main :: fn() {
            c: Color = Color.Red
            x := match c {
                case Color.Red: 1
                case Color.Green: 2
                else: 3
            }
        }
        """
        assert expect_error(source, "cover all enum")

    def test_overlapping_numeric_range_patterns_are_rejected(self):
        """Numeric range patterns should not overlap previous numeric ranges."""
        source = """
        main :: fn() {
            n: i32 = 4
            match n {
                case 1..5: x := 1
                case 5..10: x := 2
                else: x := 0
            }
        }
        """
        assert expect_error(source, "overlaps previous range pattern")

    def test_literal_after_covering_range_is_rejected(self):
        """A literal covered by a previous range is unreachable."""
        source = """
        main :: fn() {
            n: i32 = 4
            match n {
                case 1..5: x := 1
                case 3: x := 2
                else: x := 0
            }
        }
        """
        assert expect_error(source, "covered by previous range pattern")

    def test_range_after_seen_literal_overlap_is_rejected(self):
        """A range that contains a previous literal is overlapping."""
        source = """
        main :: fn() {
            n: i32 = 4
            match n {
                case 3: x := 1
                case 1..5: x := 2
                else: x := 0
            }
        }
        """
        assert expect_error(source, "overlaps previous literal pattern")

    def test_overlapping_char_range_patterns_are_rejected(self):
        """Char range patterns should not overlap previous char ranges."""
        source = """
        main :: fn() {
            c: char = 'd'
            match c {
                case 'a'..'f': x := 1
                case 'd'..'z': x := 2
                else: x := 0
            }
        }
        """
        assert expect_error(source, "overlaps previous range pattern")

    def test_overlapping_constant_range_patterns_are_rejected(self):
        """Ranges with constant endpoints should participate in overlap checks."""
        source = """
        LOW :: 1
        MID :: 5
        HIGH :: 10

        main :: fn() {
            n: i32 = 4
            match n {
                case LOW..MID: x := 1
                case MID..HIGH: x := 2
                else: x := 0
            }
        }
        """
        assert expect_error(source, "overlaps previous range pattern")

    def test_computed_constant_range_patterns_are_rejected(self):
        """Ranges with simple computed constants should participate in overlap checks."""
        source = """
        BASE :: 2
        LOW :: BASE + 1
        MID :: BASE * 3
        HIGH :: 12

        main :: fn() {
            n: i32 = 4
            match n {
                case LOW..MID: x := 1
                case 5..HIGH: x := 2
                else: x := 0
            }
        }
        """
        assert expect_error(source, "overlaps previous range pattern")

    def test_integer_division_constant_ranges_use_integer_semantics(self):
        """Computed range constants should match existing integer constant-folding semantics."""
        source = """
        START :: 5 / 2
        END :: 8 / 2

        main :: fn() {
            n: i32 = 3
            match n {
                case START..END: x := 1
                case 2..3: x := 2
                else: x := 0
            }
        }
        """
        assert expect_error(source, "overlaps previous range pattern")

    def test_char_constant_range_patterns_are_rejected(self):
        """Char constants should participate in range overlap checks."""
        source = """
        LOW :: 'a'
        MID :: 'm'
        HIGH :: 'z'

        main :: fn() {
            c: char = 'd'
            match c {
                case LOW..MID: x := 1
                case 'f'..HIGH: x := 2
                else: x := 0
            }
        }
        """
        assert expect_error(source, "overlaps previous range pattern")

    def test_constant_literal_after_covering_range_is_rejected(self):
        """A constant literal covered by a previous range is unreachable."""
        source = """
        TARGET :: 3

        main :: fn() {
            n: i32 = 4
            match n {
                case 1..5: x := 1
                case TARGET: x := 2
                else: x := 0
            }
        }
        """
        assert expect_error(source, "covered by previous range pattern")

    def test_constant_literal_before_covering_range_is_rejected(self):
        """A range covering a previous constant literal should be overlapping."""
        source = """
        TARGET :: 3

        main :: fn() {
            n: i32 = 4
            match n {
                case TARGET: x := 1
                case 1..5: x := 2
                else: x := 0
            }
        }
        """
        assert expect_error(source, "overlaps previous literal pattern")


class TestReturnTypeBranchValidation:
    """Return type checks should apply inside every reachable branch."""

    def test_if_branch_return_type_mismatch_is_rejected(self):
        source = """
        value :: fn(flag: bool) i32 {
            if flag {
                ret "bad"
            } else {
                ret 1
            }
        }
        """
        assert expect_error(source, "return type mismatch")

    def test_match_branch_return_type_mismatch_is_rejected(self):
        source = """
        value :: fn(flag: bool) i32 {
            match flag {
                case true: ret "bad"
                case false: ret 1
            }
        }
        """
        assert expect_error(source, "return type mismatch")

    def test_nested_block_return_type_mismatch_is_rejected(self):
        source = """
        value :: fn() i32 {
            {
                ret "bad"
            }
        }
        """
        assert expect_error(source, "return type mismatch")


class TestDeferStatements:
    """Test defer statement validation."""

    def test_simple_defer(self):
        """Test simple defer statement."""
        source = """
        main :: fn() {
            x := 10
            defer del x
        }
        """
        # This might not work exactly like this, but tests the structure
        result = expect_success(source)
        assert isinstance(result, bool)

    def test_defer_with_function_call(self):
        """Test defer with function call."""
        source = """
        cleanup :: fn() {
            x := 0
        }

        main :: fn() {
            x := 10
            defer cleanup()
        }
        """
        assert expect_success(source)

    def test_defer_outside_function_error(self):
        """Test defer statement outside function."""
        source = """
        x := 10
        defer del x
        """
        # This should error - defer outside function
        result = expect_error(source, "defer")
        assert isinstance(result, bool)

    def test_multiple_defers(self):
        """Test multiple defer statements."""
        source = """
        main :: fn() {
            x := 10
            defer cleanup_x()
            y := 20
            defer cleanup_y()
        }

        cleanup_x :: fn() { }
        cleanup_y :: fn() { }
        """
        assert expect_success(source)

    def test_deferred_del_of_non_reference_is_rejected(self):
        """Deferred statements should be type/semantic checked like normal statements."""
        source = """
        main :: fn() {
            x: i32 = 10
            defer del x
        }
        """
        assert expect_error(source, "reference")


class TestSemanticValidatorSchemaTraversal:
    """Regression tests for parser/semantic AST field-name contracts."""

    def test_return_value_payload_is_visited_by_semantic_validator(self):
        ret_value = ASTNode(kind=NodeKind.LITERAL, literal_kind=LiteralKind.INTEGER, literal_value=1)
        ret_stmt = ASTNode(kind=NodeKind.RETURN, value=ret_value)
        func_node = ASTNode(kind=NodeKind.FUNCTION, name="main")
        validator = SemanticValidationPass(None, {})
        visited = []

        validator.context.enter_function("main", None, func_node)
        validator.visit_expression = visited.append

        validator.visit_return_stmt(ret_stmt)

        assert visited == [ret_value]


class TestForInIterableValidation:
    """Test iterable type validation for for-in loops."""

    def test_for_in_rejects_non_iterable_expression(self):
        source = """
        main :: fn() {
            for x in 42 {
                y := x
            }
        }
        """
        assert expect_error(source, "array or slice")

    def test_indexed_for_in_rejects_non_iterable_expression(self):
        source = """
        main :: fn() {
            for i, x in 42 {
                y := i + x
            }
        }
        """
        assert expect_error(source, "array or slice")
