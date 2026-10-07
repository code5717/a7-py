"""Nested-function annotation must not consume Python stack per function.

These AST-level checks isolate preprocessing. They do not qualify parsing,
semantic acceptance, or native execution of deeply nested source.
"""

import sys

from a7.ast_nodes import (
    create_block, create_function_decl, create_identifier, create_parameter,
    create_primitive_type, create_program, create_return_stmt,
    create_var_decl,
)
from a7.ast_preprocessor import ASTPreprocessor
from conftest import low_recursion_limit


def test_deep_nested_functions_keep_hoisting_and_parameter_usage():
    """Every direct nested declaration is hoisted and uses its own parameters."""
    functions = []
    child = None
    for index in range(160):
        used = create_parameter(f"used_{index}", create_primitive_type("i32"))
        unused = create_parameter(f"unused_{index}", create_primitive_type("i32"))
        statements = ([child] if child is not None else [])
        statements.append(create_return_stmt(create_identifier(used.name)))
        child = create_function_decl(
            f"function_{index}", [used, unused], body=create_block(statements)
        )
        functions.append(child)
    program = create_program([child])
    old_limit = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(low_recursion_limit())
        result = ASTPreprocessor().process(program)
    finally:
        sys.setrecursionlimit(old_limit)

    assert result is program
    assert child.hoisted is False
    for function in functions[:-1]:
        assert function.hoisted is True
    for function in functions:
        assert function.parameters[0].is_used is True
        assert function.parameters[1].is_used is False


def test_hoisting_preserves_direct_body_boundary_and_bodyless_declarations():
    """Keep the existing direct-body rule; do not start hoisting through blocks."""
    bodyless = create_function_decl("external")
    buried = create_function_decl("buried", body=create_block())
    direct = create_function_decl("direct", body=create_block([bodyless]))
    outer = create_function_decl(
        "outer", body=create_block([direct, create_block([buried])])
    )
    processor = ASTPreprocessor()
    processor.process(create_program([outer]))

    assert direct.hoisted is True
    assert bodyless.hoisted is True
    assert outer.hoisted is False
    assert buried.hoisted is False
    assert processor.changes_made == 2


def test_nested_usage_is_finalized_in_its_own_function():
    """An outer use of a name must not make an unused child local used."""
    outer_local = create_var_decl("value", None)
    child_local = create_var_decl("value", None)
    child = create_function_decl("child", body=create_block([child_local]))
    outer = create_function_decl(
        "outer", body=create_block([
            outer_local, child, create_return_stmt(create_identifier("value")),
        ])
    )
    ASTPreprocessor().process(create_program([outer]))

    assert outer_local.is_used is True
    assert child_local.is_used is False
