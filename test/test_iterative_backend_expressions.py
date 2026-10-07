"""Expression/type emission depth, order and wrapped diagnostics."""
import subprocess
import sys
import textwrap

import pytest

from a7.ast_nodes import ASTNode, NodeKind
from a7.backends.zig import ZigCodeGenerator
from a7.errors import CodegenError, SourceSpan


@pytest.mark.parametrize("shape", ["unary", "call", "if", "array", "function_type", "generic_type"])
def test_deep_expression_or_type_has_exact_spelling_at_limit_100(shape):
    code = textwrap.dedent('''
        import sys
        from a7.ast_nodes import ASTNode, NodeKind, LiteralKind, UnaryOp
        from a7.backends.zig import ZigCodeGenerator
        shape = sys.argv[1]
        for depth in (4, 200):
            for limit in (1000, 100):
                sys.setrecursionlimit(limit)
                leaf = ASTNode(NodeKind.LITERAL, literal_kind=LiteralKind.BOOLEAN, literal_value=True)
                root = ASTNode(NodeKind.TYPE_PRIMITIVE, type_name="i32") if shape.endswith("_type") else leaf
                for _ in range(depth):
                    if shape == "unary":
                        root = ASTNode(NodeKind.UNARY, operator=UnaryOp.NOT, operand=root)
                    elif shape == "call":
                        root = ASTNode(NodeKind.CALL, function=ASTNode(NodeKind.IDENTIFIER, name="identity"), arguments=[root])
                    elif shape == "if":
                        root = ASTNode(NodeKind.IF_EXPR, condition=leaf, then_expr=leaf, else_expr=root)
                    elif shape == "array":
                        root = ASTNode(NodeKind.ARRAY_INIT, elements=[root])
                    elif shape == "function_type":
                        root = ASTNode(NodeKind.TYPE_FUNCTION, parameter_types=[], return_type=root)
                    else:
                        root = ASTNode(NodeKind.TYPE_IDENTIFIER, name="Box", generic_params=[root])
                prefix, value, suffix = {
                    "unary": ("(!", "true", ")"),
                    "call": ("identity(", "true", ")"),
                    "if": ("(if (true) true else ", "true", ")"),
                    "array": (".{ ", "true", " }"),
                    "function_type": ("*const fn () ", "i32", ""),
                    "generic_type": ("Box(", "i32", ")"),
                }[shape]
                gen = ZigCodeGenerator()
                actual = gen._emit_type_node(root) if shape.endswith("_type") else gen._emit_expr(root)
                assert actual == prefix * depth + value + suffix * depth
    ''')
    result = subprocess.run([sys.executable, "-c", code, shape], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("shape", ["field", "call"])
@pytest.mark.parametrize("profile", ["debug", "release", "fast"])
def test_deep_source_emits_identically_at_limit_100(shape, profile, tmp_path):
    code = textwrap.dedent('''
        import sys, pathlib
        from a7.compile import A7Compiler
        shape, profile, directory = sys.argv[1:]
        depth = 60
        if shape == "field":
            source = "R0 :: struct {value:i32}\\n" + "".join(f"R{i} :: struct {{child:R{i-1}}}\\n" for i in range(1,depth+1))
            source += f"main :: fn(){{r:R{depth}; x:=r" + ".child" * depth + ".value}"
        else:
            source = "identity :: fn(x:i32) i32 {ret x}\\nmain :: fn(){x:i32=1;y:=" + "identity(" * depth + "x" + ")" * depth + "}"
        path = pathlib.Path(directory) / "deep.a7"
        path.write_text(source)
        output = []
        for limit in (1000,100):
            sys.setrecursionlimit(limit)
            result = A7Compiler(build_profile=profile).compile_file_detailed(str(path), str(path.with_suffix(".zig")))
            assert result.ok, result.failure
            output.append(result.codegen_result["output_code"])
        assert output[0] == output[1]
        assert ".child" * depth + ".value" in output[0] if shape == "field" else "identity(" * depth + "x" in output[0]
    ''')
    result = subprocess.run([sys.executable, "-c", code, shape, profile, str(tmp_path)], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_deep_pattern_failure_preserves_outer_span_and_child_cause():
    code = textwrap.dedent('''
        import sys
        from a7.ast_nodes import ASTNode, NodeKind
        from a7.backends.zig import ZigCodeGenerator
        from a7.errors import CodegenError, SourceSpan
        sys.setrecursionlimit(100)
        child_span = SourceSpan(9,2,9,3)
        outer_span = SourceSpan(3,4,3,5)
        root = ASTNode(NodeKind.BLOCK, span=child_span)
        for _ in range(200):
            root = ASTNode(NodeKind.ARRAY_INIT, elements=[root])
        root.span = outer_span
        try:
            ZigCodeGenerator()._emit_pattern(root)
        except CodegenError as error:
            assert "unsupported match pattern 'ARRAY_INIT'" in str(error)
            assert error.span == outer_span
            assert isinstance(error.__cause__, CodegenError)
            assert "unsupported expression node 'BLOCK'" in str(error.__cause__)
            assert error.__cause__.span == child_span
        else:
            raise AssertionError("unsupported child accepted")
    ''')
    result = subprocess.run([sys.executable, "-c", code], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_callee_error_precedes_argument_error():
    gen = ZigCodeGenerator()
    node = ASTNode(NodeKind.CALL, function=ASTNode(NodeKind.IDENTIFIER), arguments=[ASTNode(NodeKind.BLOCK)])
    with pytest.raises(CodegenError, match="identifier has no name"):
        gen._emit_expr(node)


def test_generic_argument_error_precedes_missing_type_name():
    gen = ZigCodeGenerator()
    node = ASTNode(NodeKind.TYPE_IDENTIFIER, generic_params=[ASTNode(NodeKind.TYPE_PRIMITIVE, type_name="u128")])
    with pytest.raises(CodegenError, match="'u128' is not a primitive type"):
        gen._emit_type_node(node)
