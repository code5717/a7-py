"""
Tests for the AST preprocessor (a7/ast_preprocessor.py).

The AST preprocessor runs after parsing and semantic analysis, before code
generation. It performs several transformations and annotations:

1. Legacy field sugar compatibility (.adr/.val are no longer lowered)
2. Constant folding (compile-time arithmetic)
3. Mutation analysis (is_mutable on VAR nodes)
4. Usage analysis (is_used on VAR/PARAMETER nodes)
5. Nested function hoisting (hoisted flag)

Tests are organized into categories matching these passes.
"""

import pytest
from a7.parser import parse_a7
from a7.ast_nodes import (
    ASTNode, NodeKind, LiteralKind, BinaryOp, UnaryOp,
    create_program, create_function_decl, create_block,
    create_literal, create_identifier, create_var_decl,
)
from a7.ast_preprocessor import ASTPreprocessor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def preprocess(source: str) -> ASTNode:
    """Parse A7 source and run the preprocessor on the resulting AST."""
    ast = parse_a7(source)
    pp = ASTPreprocessor()
    return pp.process(ast)


def preprocess_with_changes(source: str):
    """Parse, preprocess, and return (ast, changes_made)."""
    ast = parse_a7(source)
    pp = ASTPreprocessor()
    result = pp.process(ast)
    return result, pp.changes_made


def get_function_stmts(ast: ASTNode, func_index: int = 0):
    """Return the statements from the body of the function at func_index."""
    func = ast.declarations[func_index]
    assert func.kind == NodeKind.FUNCTION
    return func.body.statements


def get_function(ast: ASTNode, name: str) -> ASTNode:
    """Find a function declaration by name."""
    for decl in ast.declarations:
        if decl.kind == NodeKind.FUNCTION and decl.name == name:
            return decl
    raise ValueError(f"No function named '{name}' found")


# ===========================================================================
# 1. Field Sugar Lowering
# ===========================================================================

class TestFieldSugarLowering:
    """Legacy .adr/.val are ordinary field names, not reference operations."""

    def test_adr_on_identifier_remains_field_access(self):
        ident = ASTNode(kind=NodeKind.IDENTIFIER, name="x")
        field_access = ASTNode(kind=NodeKind.FIELD_ACCESS, object=ident, field="adr")

        pp = ASTPreprocessor()
        result = pp._lower_field_sugar(field_access)

        assert result is field_access
        assert result.kind == NodeKind.FIELD_ACCESS
        assert result.field == "adr"
        assert pp.changes_made == 0

    def test_val_on_identifier_remains_field_access(self):
        ident = ASTNode(kind=NodeKind.IDENTIFIER, name="ptr")
        field_access = ASTNode(kind=NodeKind.FIELD_ACCESS, object=ident, field="val")

        pp = ASTPreprocessor()
        result = pp._lower_field_sugar(field_access)

        assert result is field_access
        assert result.kind == NodeKind.FIELD_ACCESS
        assert result.field == "val"
        assert pp.changes_made == 0

    def test_chained_adr_val_remains_field_access_chain(self):
        ident = ASTNode(kind=NodeKind.IDENTIFIER, name="x")
        inner_fa = ASTNode(kind=NodeKind.FIELD_ACCESS, object=ident, field="adr")
        outer_fa = ASTNode(kind=NodeKind.FIELD_ACCESS, object=inner_fa, field="val")

        # Wrap in a minimal program so _transform_tree processes bottom-up
        var_node = ASTNode(kind=NodeKind.VAR, name="result", value=outer_fa)
        block = create_block([var_node])
        func = create_function_decl("test", body=block)
        prog = create_program([func])

        pp = ASTPreprocessor()
        prog = pp.process(prog)

        result_value = prog.declarations[0].body.statements[0].value
        assert result_value.kind == NodeKind.FIELD_ACCESS
        assert result_value.field == "val"
        assert result_value.object.kind == NodeKind.FIELD_ACCESS
        assert result_value.object.field == "adr"

    def test_normal_field_access_not_lowered(self):
        """A regular field access (e.g., obj.name) should not be transformed."""
        ident = ASTNode(kind=NodeKind.IDENTIFIER, name="person")
        field_access = ASTNode(
            kind=NodeKind.FIELD_ACCESS, object=ident, field="name"
        )

        pp = ASTPreprocessor()
        result = pp._lower_field_sugar(field_access)

        assert result.kind == NodeKind.FIELD_ACCESS
        assert result.field == "name"
        assert result is field_access  # Same object, not replaced

    def test_non_field_access_node_unchanged(self):
        """Non-FIELD_ACCESS nodes pass through _lower_field_sugar unchanged."""
        lit = ASTNode(
            kind=NodeKind.LITERAL,
            literal_kind=LiteralKind.INTEGER,
            literal_value=42,
        )
        pp = ASTPreprocessor()
        result = pp._lower_field_sugar(lit)
        assert result is lit

    def test_adr_does_not_increment_changes_made(self):
        """Legacy .adr is no longer lowered."""
        ident = ASTNode(kind=NodeKind.IDENTIFIER, name="x")
        fa = ASTNode(kind=NodeKind.FIELD_ACCESS, object=ident, field="adr")

        pp = ASTPreprocessor()
        assert pp.changes_made == 0
        pp._lower_field_sugar(fa)
        assert pp.changes_made == 0

    def test_val_does_not_increment_changes_made(self):
        """Legacy .val is no longer lowered."""
        ident = ASTNode(kind=NodeKind.IDENTIFIER, name="p")
        fa = ASTNode(kind=NodeKind.FIELD_ACCESS, object=ident, field="val")

        pp = ASTPreprocessor()
        assert pp.changes_made == 0
        pp._lower_field_sugar(fa)
        assert pp.changes_made == 0

    def test_adr_preserves_original_node_and_span(self):
        """The original field-access node is preserved."""
        from a7.errors import SourceSpan

        span = SourceSpan(start_line=5, start_column=10, end_line=5, end_column=15)
        ident = ASTNode(kind=NodeKind.IDENTIFIER, name="x")
        fa = ASTNode(kind=NodeKind.FIELD_ACCESS, object=ident, field="adr", span=span)

        pp = ASTPreprocessor()
        result = pp._lower_field_sugar(fa)

        assert result is fa
        assert result.span is span


# ===========================================================================
# 2. Constant Folding
# ===========================================================================

class TestConstantFolding:
    """Test compile-time evaluation of constant expressions."""

    def test_add_integers(self):
        """2 + 3 should fold to literal 5."""
        ast = preprocess("main :: fn() { x := 2 + 3 }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_kind == LiteralKind.INTEGER
        assert val.literal_value == 5

    def test_subtract_integers(self):
        """10 - 4 should fold to literal 6."""
        ast = preprocess("main :: fn() { x := 10 - 4 }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_value == 6

    def test_multiply_integers(self):
        """3 * 7 should fold to literal 21."""
        ast = preprocess("main :: fn() { x := 3 * 7 }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_value == 21

    def test_divide_integers(self):
        """10 / 2 should fold to literal 5 (integer division)."""
        ast = preprocess("main :: fn() { x := 10 / 2 }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_value == 5

    def test_modulo_integers(self):
        """10 % 3 should fold to literal 1."""
        ast = preprocess("main :: fn() { x := 10 % 3 }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_value == 1

    def test_negative_integer_division_truncates_toward_zero(self):
        """Integer constant folding must match backend truncating division."""
        ast = preprocess("main :: fn() { x := -17 / 5 }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_value == -3

    def test_negative_integer_modulo_uses_truncating_remainder(self):
        """Integer constant folding must match C `%` and Zig `@rem`."""
        ast = preprocess("main :: fn() { x := -17 % 5 }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_value == -2

    def test_and_booleans(self):
        """true and false should fold to literal false."""
        ast = preprocess("main :: fn() { x := true and false }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_kind == LiteralKind.BOOLEAN
        assert val.literal_value is False

    def test_or_booleans(self):
        """true or false should fold to literal true."""
        ast = preprocess("main :: fn() { x := true or false }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_kind == LiteralKind.BOOLEAN
        assert val.literal_value is True

    def test_unary_neg_on_literal(self):
        """-5 (unary negation on integer literal) should fold to literal -5."""
        ast = preprocess("main :: fn() { x := -5 }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_kind == LiteralKind.INTEGER
        assert val.literal_value == -5

    def test_nested_arithmetic(self):
        """(2 + 3) * 4 should fold to literal 20.

        Bottom-up processing ensures the inner (2 + 3) is folded to 5 first,
        then 5 * 4 is folded to 20.
        """
        ast = preprocess("main :: fn() { x := (2 + 3) * 4 }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_value == 20

    def test_division_by_zero_not_folded(self):
        """10 / 0 should not be folded (remains a BINARY node)."""
        ast = preprocess("main :: fn() { x := 10 / 0 }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.BINARY

    def test_modulo_by_zero_not_folded(self):
        """10 % 0 should not be folded."""
        ast = preprocess("main :: fn() { x := 10 % 0 }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.BINARY

    def test_unary_not_on_true(self):
        """not true should fold to literal false."""
        ast = preprocess("main :: fn() { x := not true }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_kind == LiteralKind.BOOLEAN
        assert val.literal_value is False

    def test_unary_not_on_false(self):
        """not false should fold to literal true."""
        ast = preprocess("main :: fn() { x := not false }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_kind == LiteralKind.BOOLEAN
        assert val.literal_value is True

    def test_float_addition(self):
        """1.5 + 2.5 should fold to literal 4.0."""
        ast = preprocess("main :: fn() { x := 1.5 + 2.5 }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_kind == LiteralKind.FLOAT
        assert val.literal_value == 4.0

    def test_negate_float(self):
        """-3.14 should fold to literal -3.14."""
        ast = preprocess("main :: fn() { x := -3.14 }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_kind == LiteralKind.FLOAT
        assert val.literal_value == -3.14

    def test_expression_with_identifier_not_folded(self):
        """An expression involving a variable should not be folded."""
        code = """
        main :: fn() {
            y := 10
            x := y + 5
        }
        """
        ast = preprocess(code)
        stmts = get_function_stmts(ast)
        # x := y + 5 should remain BINARY because y is not a constant literal
        val = stmts[1].value
        assert val.kind == NodeKind.BINARY

    def test_deeply_nested_folding(self):
        """((1 + 2) + (3 + 4)) should fold all the way to 10."""
        ast = preprocess("main :: fn() { x := (1 + 2) + (3 + 4) }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_value == 10

    def test_integer_division_truncates(self):
        """7 / 2 should fold to 3 (integer division floors)."""
        ast = preprocess("main :: fn() { x := 7 / 2 }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_kind == LiteralKind.INTEGER
        assert val.literal_value == 3

    def test_changes_made_incremented_for_folding(self):
        """Each fold operation should increment the changes counter."""
        ast, changes = preprocess_with_changes("main :: fn() { x := 2 + 3 }")
        # At minimum, the constant fold itself contributes to changes_made
        assert changes >= 1

    def test_and_true_true(self):
        """true and true should fold to true."""
        ast = preprocess("main :: fn() { x := true and true }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.literal_value is True

    def test_or_false_false(self):
        """false or false should fold to false."""
        ast = preprocess("main :: fn() { x := false or false }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.literal_value is False

    def test_numeric_comparison_folds_to_boolean(self):
        """2 + 3 == 5 should fold through arithmetic and comparison."""
        ast = preprocess("main :: fn() { x := 2 + 3 == 5 }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_kind == LiteralKind.BOOLEAN
        assert val.literal_value is True

    def test_string_equality_folds_to_boolean(self):
        """Equal literal strings should fold for == comparisons."""
        ast = preprocess('main :: fn() { x := "a" == "a" }')
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_kind == LiteralKind.BOOLEAN
        assert val.literal_value is True

    def test_bitwise_integer_ops_fold(self):
        """Integer bitwise expressions should fold when both operands are literals."""
        ast = preprocess("main :: fn() { x := (6 & 3) | 8 }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.LITERAL
        assert val.literal_kind == LiteralKind.INTEGER
        assert val.literal_value == 10

    def test_negative_shift_not_folded(self):
        """Invalid constant shifts stay in the AST for semantic/codegen diagnostics."""
        ast = preprocess("main :: fn() { x := 1 << -1 }")
        stmts = get_function_stmts(ast)
        val = stmts[0].value
        assert val.kind == NodeKind.BINARY


# ===========================================================================
# 3. Mutation Analysis
# ===========================================================================

class TestMutationAnalysis:
    """Test detection of variable mutation (assignment after initialization)."""

    def test_variable_assigned_after_init_is_mutable(self):
        """A variable that is assigned to after its declaration should be mutable."""
        code = """
        main :: fn() {
            x := 10
            x = 20
        }
        """
        ast = preprocess(code)
        stmts = get_function_stmts(ast)
        var_x = stmts[0]
        assert var_x.kind == NodeKind.VAR
        assert var_x.name == "x"
        assert var_x.is_mutable is True

    def test_variable_never_assigned_is_not_mutable(self):
        """A variable that is never assigned to after init should not be mutable."""
        code = """
        main :: fn() {
            x := 10
            y := x + 1
        }
        """
        ast = preprocess(code)
        stmts = get_function_stmts(ast)
        var_x = stmts[0]
        assert var_x.kind == NodeKind.VAR
        assert var_x.name == "x"
        assert var_x.is_mutable is False

    def test_index_assignment_makes_variable_mutable(self):
        """Assigning through an index (arr[0] = 1) should mark the variable as mutable."""
        code = """
        main :: fn() {
            arr := [1, 2, 3]
            arr[0] = 10
        }
        """
        ast = preprocess(code)
        stmts = get_function_stmts(ast)
        var_arr = stmts[0]
        assert var_arr.kind == NodeKind.VAR
        assert var_arr.name == "arr"
        assert var_arr.is_mutable is True

    def test_constant_is_not_mutable(self):
        """A constant declaration should never be marked as mutable."""
        code = """
        main :: fn() {
            PI :: 3.14
            x := PI
        }
        """
        ast = preprocess(code)
        stmts = get_function_stmts(ast)
        const_pi = stmts[0]
        assert const_pi.kind == NodeKind.CONST
        assert const_pi.is_mutable is False

    def test_compound_assignment_makes_mutable(self):
        """Compound assignment (x += 1) should mark the variable as mutable."""
        code = """
        main :: fn() {
            x := 0
            x += 1
        }
        """
        ast = preprocess(code)
        stmts = get_function_stmts(ast)
        var_x = stmts[0]
        assert var_x.name == "x"
        assert var_x.is_mutable is True

    def test_multiple_variables_selective_mutation(self):
        """Only variables that are actually assigned to should be marked mutable."""
        code = """
        main :: fn() {
            a := 1
            b := 2
            c := 3
            a = 10
            c = 30
        }
        """
        ast = preprocess(code)
        stmts = get_function_stmts(ast)
        vars_by_name = {s.name: s for s in stmts if s.kind == NodeKind.VAR}

        assert vars_by_name["a"].is_mutable is True
        assert vars_by_name["b"].is_mutable is False
        assert vars_by_name["c"].is_mutable is True

    def test_for_loop_variable_is_mutable(self):
        """The init variable in a C-style for loop should be marked mutable."""
        code = """
        main :: fn() {
            for i := 0; i < 10; i += 1 {
                x := i
            }
        }
        """
        ast = preprocess(code)
        stmts = get_function_stmts(ast)
        for_node = stmts[0]
        assert for_node.kind == NodeKind.FOR
        assert for_node.init.kind == NodeKind.VAR
        assert for_node.init.is_mutable is True

    def test_field_assignment_makes_root_mutable(self):
        """Assigning to a field (obj.x = 1) should mark the root variable as mutable."""
        code = """
        Point :: struct {
            x: i32
            y: i32
        }
        main :: fn() {
            p := Point { x: 0, y: 0 }
            p.x = 5
        }
        """
        ast = preprocess(code)
        func = get_function(ast, "main")
        stmts = func.body.statements
        var_p = stmts[0]
        assert var_p.name == "p"
        assert var_p.is_mutable is True

    def test_address_taken_variable_is_mutable(self):
        """Passing a local to a ref parameter should force mutable Zig storage."""
        code = """
        touch :: fn(p: ref i32) {
            p += 1
        }
        main :: fn() {
            x: i32 = 7
            touch(x)
        }
        """
        ast = parse_a7(code)
        call = get_function(ast, "main").body.statements[1].expression
        call.implicit_ref_args = {0}
        ast = ASTPreprocessor().process(ast)
        stmts = get_function(ast, "main").body.statements
        var_x = stmts[0]
        assert var_x.kind == NodeKind.VAR
        assert var_x.name == "x"
        assert var_x.is_mutable is True


# ===========================================================================
# 4. Usage Analysis
# ===========================================================================

class TestUsageAnalysis:
    """Test detection of whether variables and parameters are used."""

    def test_used_variable_marked_as_used(self):
        """A variable referenced in an expression should have is_used=True."""
        code = """
        main :: fn() {
            x := 10
            y := x + 1
        }
        """
        ast = preprocess(code)
        stmts = get_function_stmts(ast)
        var_x = stmts[0]
        assert var_x.name == "x"
        assert var_x.is_used is True

    def test_unused_variable_marked_as_unused(self):
        """A variable never referenced after declaration should have is_used=False."""
        code = """
        main :: fn() {
            x := 10
            y := 20
        }
        """
        ast = preprocess(code)
        stmts = get_function_stmts(ast)
        # Both x and y are unused since neither is referenced by any expression
        var_x = stmts[0]
        var_y = stmts[1]
        assert var_x.name == "x"
        assert var_x.is_used is False
        assert var_y.name == "y"
        assert var_y.is_used is False

    def test_default_is_used_true_on_ast_node(self):
        """The ASTNode dataclass defaults is_used to True.

        The preprocessor then sets it to False for unused variables.
        """
        node = ASTNode(kind=NodeKind.VAR, name="x")
        assert node.is_used is True

    def test_used_parameter_marked_as_used(self):
        """A function parameter referenced in the body should have is_used=True."""
        code = """
        add :: fn(x: i32, y: i32) i32 {
            ret x + y
        }
        """
        ast = preprocess(code)
        func = get_function(ast, "add")
        for param in func.parameters:
            assert param.is_used is True, f"Parameter '{param.name}' should be used"

    def test_unused_parameter_marked_as_unused(self):
        """A function parameter not referenced should have is_used=False."""
        code = """
        ignore :: fn(a: i32, b: i32) i32 {
            ret a
        }
        """
        ast = preprocess(code)
        func = get_function(ast, "ignore")
        params = {p.name: p for p in func.parameters}
        assert params["a"].is_used is True
        assert params["b"].is_used is False

    def test_variable_used_in_condition(self):
        """A variable used in an if-condition should be marked as used."""
        code = """
        main :: fn() {
            flag := true
            if flag {
                x := 1
            }
        }
        """
        ast = preprocess(code)
        stmts = get_function_stmts(ast)
        var_flag = stmts[0]
        assert var_flag.name == "flag"
        assert var_flag.is_used is True

    def test_variable_used_only_as_assignment_target_still_unused(self):
        """A variable that is only assigned to (target) but never read is still not 'used'
        in identifier reference terms, though it will appear in mutations."""
        code = """
        main :: fn() {
            x := 0
            x = 10
        }
        """
        ast = preprocess(code)
        stmts = get_function_stmts(ast)
        var_x = stmts[0]
        # x appears as an IDENTIFIER in the assignment target, so it IS found
        # in the identifier walk. The usage analysis collects all identifiers
        # in the body including assignment targets.
        assert var_x.name == "x"
        assert var_x.is_used is True

    def test_variable_used_in_function_call(self):
        """A variable passed as a function argument should be marked as used."""
        code = """
        helper :: fn(n: i32) i32 {
            ret n
        }
        main :: fn() {
            val := 42
            result := helper(val)
        }
        """
        ast = preprocess(code)
        func = get_function(ast, "main")
        stmts = func.body.statements
        var_val = stmts[0]
        assert var_val.name == "val"
        assert var_val.is_used is True

    def test_all_params_unused(self):
        """When all parameters are unused, all should be marked is_used=False."""
        code = """
        noop :: fn(a: i32, b: i32) {
        }
        """
        ast = preprocess(code)
        func = get_function(ast, "noop")
        for param in func.parameters:
            assert param.is_used is False, f"Parameter '{param.name}' should be unused"


# ===========================================================================
# 5. Nested Function Hoisting
# ===========================================================================

class TestNestedFunctionHoisting:
    """Test that functions defined inside other functions are flagged as hoisted."""

    def test_nested_function_hoisted_flag(self):
        """A function declared inside another function should have hoisted=True."""
        code = """
        main :: fn() {
            helper :: fn(x: i32) i32 {
                ret x * 2
            }
            result := helper(5)
        }
        """
        ast = preprocess(code)
        stmts = get_function_stmts(ast)
        inner_fn = stmts[0]
        assert inner_fn.kind == NodeKind.FUNCTION
        assert inner_fn.name == "helper"
        assert inner_fn.hoisted is True

    def test_top_level_function_not_hoisted(self):
        """A top-level function should not have hoisted=True."""
        code = """
        main :: fn() {
            x := 42
        }
        """
        ast = preprocess(code)
        func = ast.declarations[0]
        assert func.kind == NodeKind.FUNCTION
        assert func.hoisted is False

    def test_multiple_nested_functions_all_hoisted(self):
        """All nested functions in a parent should each be marked hoisted."""
        code = """
        main :: fn() {
            double :: fn(x: i32) i32 {
                ret x * 2
            }
            triple :: fn(x: i32) i32 {
                ret x * 3
            }
            a := double(5)
            b := triple(5)
        }
        """
        ast = preprocess(code)
        stmts = get_function_stmts(ast)
        nested_fns = [s for s in stmts if s.kind == NodeKind.FUNCTION]
        assert len(nested_fns) == 2
        for fn in nested_fns:
            assert fn.hoisted is True, f"Nested function '{fn.name}' should be hoisted"

    def test_hoisting_increments_changes_made(self):
        """Hoisting a nested function should increment changes_made."""
        code = """
        main :: fn() {
            inner :: fn() {
            }
        }
        """
        _, changes = preprocess_with_changes(code)
        assert changes >= 1

    def test_nested_function_body_also_annotated(self):
        """The body of a nested function should also be processed for mutations/usage."""
        code = """
        main :: fn() {
            inner :: fn(a: i32, b: i32) i32 {
                ret a
            }
            x := inner(1, 2)
        }
        """
        ast = preprocess(code)
        stmts = get_function_stmts(ast)
        inner = stmts[0]
        assert inner.kind == NodeKind.FUNCTION
        # Inner function's parameters should be analyzed for usage
        params = {p.name: p for p in inner.parameters}
        assert params["a"].is_used is True
        assert params["b"].is_used is False


# ===========================================================================
# 6. Empty and Minimal Input
# ===========================================================================

class TestEmptyAndMinimalInput:
    """Test that the preprocessor handles edge cases without crashing."""

    def test_empty_program(self):
        """An empty source string should produce a PROGRAM with no declarations."""
        ast = preprocess("")
        assert ast.kind == NodeKind.PROGRAM
        assert ast.declarations == []

    def test_program_with_only_constants(self):
        """A program with only top-level constants should process without error."""
        code = """
        PI :: 3.14
        E :: 2.718
        MAX :: 100
        """
        ast = preprocess(code)
        assert ast.kind == NodeKind.PROGRAM
        assert len(ast.declarations) == 3
        for decl in ast.declarations:
            assert decl.kind == NodeKind.CONST

    def test_function_with_empty_body(self):
        """A function with an empty body should process without error."""
        code = """
        noop :: fn() {
        }
        """
        ast = preprocess(code)
        func = ast.declarations[0]
        assert func.kind == NodeKind.FUNCTION
        assert func.name == "noop"
        assert func.body.kind == NodeKind.BLOCK
        assert func.body.statements == []

    def test_function_with_single_return(self):
        """A function with only a return statement should process correctly."""
        code = """
        answer :: fn() i32 {
            ret 42
        }
        """
        ast = preprocess(code)
        func = ast.declarations[0]
        assert func.kind == NodeKind.FUNCTION
        assert len(func.body.statements) == 1
        assert func.body.statements[0].kind == NodeKind.RETURN

    def test_program_with_struct_only(self):
        """A program with only a struct definition should process without error."""
        code = """
        Point :: struct {
            x: i32
            y: i32
        }
        """
        ast = preprocess(code)
        assert ast.kind == NodeKind.PROGRAM
        assert len(ast.declarations) == 1
        assert ast.declarations[0].kind == NodeKind.STRUCT

    def test_multiple_empty_functions(self):
        """Multiple empty functions should all be processed."""
        code = """
        a :: fn() {}
        b :: fn() {}
        c :: fn() {}
        """
        ast = preprocess(code)
        assert len(ast.declarations) == 3
        for decl in ast.declarations:
            assert decl.kind == NodeKind.FUNCTION

    def test_preprocessor_resets_changes_count(self):
        """Calling process() should reset changes_made to 0 at the start."""
        pp = ASTPreprocessor()
        pp.changes_made = 999  # Simulate leftover state

        ast = parse_a7("")
        pp.process(ast)
        # changes_made should have been reset (may be 0 if nothing to process)
        assert pp.changes_made < 999


# ===========================================================================
# 7. Integration: Multiple Passes Together
# ===========================================================================

class TestIntegration:
    """Test that multiple preprocessor passes interact correctly."""

    def test_constant_folding_and_mutation_together(self):
        """Constant folding and mutation analysis should both work in one pass."""
        code = """
        main :: fn() {
            x := 2 + 3
            x = 10
            y := 4 * 5
        }
        """
        ast = preprocess(code)
        stmts = get_function_stmts(ast)

        # x's init value should be folded
        var_x = stmts[0]
        assert var_x.value.kind == NodeKind.LITERAL
        assert var_x.value.literal_value == 5
        # x should be mutable (assigned later)
        assert var_x.is_mutable is True

        # y's init value should be folded
        var_y = stmts[2]
        assert var_y.value.kind == NodeKind.LITERAL
        assert var_y.value.literal_value == 20
        # y should not be mutable
        assert var_y.is_mutable is False

    def test_usage_and_mutation_combined(self):
        """Usage and mutation analysis should produce correct annotations together."""
        code = """
        main :: fn() {
            counter := 0
            counter += 1
            unused := 99
        }
        """
        ast = preprocess(code)
        stmts = get_function_stmts(ast)
        vars_by_name = {s.name: s for s in stmts if s.kind == NodeKind.VAR}

        # counter: mutable (assigned) and used (referenced in assignment target)
        assert vars_by_name["counter"].is_mutable is True
        assert vars_by_name["counter"].is_used is True

        # unused: not mutable, not used
        assert vars_by_name["unused"].is_mutable is False
        assert vars_by_name["unused"].is_used is False

    def test_hoisted_function_with_folded_constants(self):
        """A nested function with constant expressions should have both
        hoisting and constant folding applied."""
        code = """
        main :: fn() {
            compute :: fn() i32 {
                ret 3 + 4
            }
            result := compute()
        }
        """
        ast = preprocess(code)
        stmts = get_function_stmts(ast)
        inner_fn = stmts[0]

        # Should be hoisted
        assert inner_fn.hoisted is True

        # The return value should be folded
        ret_stmt = inner_fn.body.statements[0]
        assert ret_stmt.kind == NodeKind.RETURN
        assert ret_stmt.value.kind == NodeKind.LITERAL
        assert ret_stmt.value.literal_value == 7

    def test_full_pipeline_realistic(self):
        """A realistic function exercising multiple preprocessor features."""
        code = """
        compute :: fn(n: i32, unused_flag: bool) i32 {
            base := 10 + 5
            result := base
            for i := 0; i < n; i += 1 {
                result += i
            }
            ret result
        }
        """
        ast = preprocess(code)
        func = get_function(ast, "compute")

        # Parameter usage
        params = {p.name: p for p in func.parameters}
        assert params["n"].is_used is True
        assert params["unused_flag"].is_used is False

        # Constant folding on base
        stmts = func.body.statements
        var_base = stmts[0]
        assert var_base.name == "base"
        assert var_base.value.kind == NodeKind.LITERAL
        assert var_base.value.literal_value == 15

        # Mutation analysis
        var_result = stmts[1]
        assert var_result.name == "result"
        assert var_result.is_mutable is True
