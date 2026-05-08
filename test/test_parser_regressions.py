"""
Targeted parser regression tests for recent parser/tokenizer changes.
"""

from a7.ast_nodes import NodeKind
from a7.parser import parse_a7


class TestIntrinsicAndCallRegressions:
    """Regression tests for builtin intrinsics and multiline calls."""

    def test_builtin_intrinsic_with_underscore_parses(self):
        source = """
        main :: fn() {
            x := @size_of(i32)
        }
        """

        ast = parse_a7(source)
        fn = ast.declarations[0]
        var_decl = fn.body.statements[0]
        call = var_decl.value

        assert call.kind == NodeKind.CALL
        assert call.function.kind == NodeKind.IDENTIFIER
        assert call.function.name == "@size_of"
        assert len(call.arguments) == 1

    def test_multiline_call_with_trailing_comma_parses(self):
        source = """
        main :: fn() {
            foo(
                1,
                2,
            )
        }
        """

        ast = parse_a7(source)
        fn = ast.declarations[0]
        stmt = fn.body.statements[0]

        assert stmt.kind == NodeKind.EXPRESSION_STMT
        assert stmt.expression.kind == NodeKind.CALL
        assert len(stmt.expression.arguments) == 2


class TestRecentParserRefactorGuards:
    """Guardrails around recent type alias and generic declaration parsing paths."""

    def test_fn_type_alias_parses_as_type_alias(self):
        ast = parse_a7("Handler :: fn(i32) i32")
        decl = ast.declarations[0]

        assert decl.kind == NodeKind.TYPE_ALIAS
        assert decl.value is not None
        assert decl.value.kind == NodeKind.TYPE_FUNCTION

    def test_fn_declaration_with_named_params_still_parses_as_function(self):
        ast = parse_a7(
            """
            add :: fn(a: i32, b: i32) i32 {
                ret a + b
            }
            """
        )
        decl = ast.declarations[0]

        assert decl.kind == NodeKind.FUNCTION
        assert decl.parameters is not None
        assert len(decl.parameters) == 2

    def test_top_level_type_alias_parses(self):
        ast = parse_a7("MyInt :: i32")
        decl = ast.declarations[0]

        assert decl.kind == NodeKind.TYPE_ALIAS
        assert decl.value is not None
        assert decl.value.kind == NodeKind.TYPE_PRIMITIVE

    def test_local_type_alias_parses(self):
        ast = parse_a7(
            """
            main :: fn() {
                LocalInt :: i32
                x: LocalInt = 1
            }
            """
        )
        fn = ast.declarations[0]
        stmts = fn.body.statements

        assert stmts[0].kind == NodeKind.TYPE_ALIAS
        assert stmts[1].kind == NodeKind.VAR

    def test_generic_struct_declaration_parses(self):
        ast = parse_a7(
            """
            Box($T) :: struct {
                value: $T
            }
            """
        )
        decl = ast.declarations[0]

        assert decl.kind == NodeKind.STRUCT
        assert decl.generic_params is not None
        assert [p.name for p in decl.generic_params] == ["T"]

    def test_generic_function_declaration_parses(self):
        ast = parse_a7(
            """
            identity($T) :: fn(value: $T) $T {
                ret value
            }
            """
        )
        decl = ast.declarations[0]

        assert decl.kind == NodeKind.FUNCTION
        assert decl.generic_params is not None
        assert [p.name for p in decl.generic_params] == ["T"]
