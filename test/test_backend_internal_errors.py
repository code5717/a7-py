"""The backend raises on a node it cannot lower (audit P2-51).

It used to emit a guess: negation for an unknown unary operator, `=` for an
unknown assignment operator, the raw name for an unknown primitive, `str()`
of a type object, and `undefined`/`anytype` for a missing node. The checker
never passes such a node, so each case is a hand-built AST or a direct call;
this verifies the failure mode, not any user-reachable program.
"""

import pytest

from a7.ast_nodes import ASTNode, NodeKind
from a7.backends.zig import ZigCodeGenerator
from a7.errors import CodegenError
from a7.types import UNKNOWN


def test_unknown_unary_operator():
    node = ASTNode(kind=NodeKind.UNARY, operator="spread",
                   operand=ASTNode(kind=NodeKind.IDENTIFIER, name="x"))
    with pytest.raises(CodegenError, match="unary operator 'spread' has no lowering"):
        ZigCodeGenerator()._emit_expr(node)


def test_unknown_assignment_operator():
    with pytest.raises(CodegenError, match="assignment operator 'pow_assign' has no lowering"):
        ZigCodeGenerator()._assign_op_to_zig("pow_assign")


def test_unknown_primitive_type_name():
    node = ASTNode(kind=NodeKind.TYPE_PRIMITIVE, type_name="u128")
    with pytest.raises(CodegenError, match="'u128' is not a primitive type"):
        ZigCodeGenerator()._emit_type_node(node)


def test_semantic_type_without_a_zig_spelling():
    with pytest.raises(CodegenError, match="no Zig type for semantic type 'UnknownType'"):
        ZigCodeGenerator()._emit_semantic_type(UNKNOWN)
    with pytest.raises(CodegenError, match="no Zig type for semantic type 'NoneType'"):
        ZigCodeGenerator()._emit_semantic_type(None)


def test_missing_expression_and_missing_types():
    generator = ZigCodeGenerator()
    with pytest.raises(CodegenError, match="missing expression node"):
        generator._emit_expr(None)
    untyped_parameter = ASTNode(kind=NodeKind.PROGRAM, declarations=[
        ASTNode(kind=NodeKind.FUNCTION, name="f",
                parameters=[ASTNode(kind=NodeKind.PARAMETER, name="n")],
                body=ASTNode(kind=NodeKind.BLOCK, statements=[])),
    ])
    with pytest.raises(CodegenError, match="parameter 'n' of 'f' has no type"):
        generator.generate(untyped_parameter)
    untyped_field = ASTNode(kind=NodeKind.PROGRAM, declarations=[
        ASTNode(kind=NodeKind.STRUCT, name="S", fields=[ASTNode(kind=NodeKind.FIELD, name="x")]),
    ])
    with pytest.raises(CodegenError, match="field 'x' of struct 'S' has no type"):
        generator.generate(untyped_field)
