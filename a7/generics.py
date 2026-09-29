"""Resolve generic constraint syntax for the production type checker.

Specialization lives in the type checker and Zig backend. Keep constraint
resolution here so there is no second, unused specialization engine.
"""

from typing import Optional

from a7.ast_nodes import ASTNode, NodeKind
from a7.types import Type, TypeSet, get_primitive_type, get_predefined_type_set


def resolve_generic_constraint(constraint_node: Optional[ASTNode]) -> Optional[TypeSet]:
    """
    Resolve a generic constraint node to a TypeSet.

    Args:
        constraint_node: Constraint AST node (TYPE_SET or TYPE_IDENTIFIER)

    Returns:
        Resolved TypeSet, or None if no constraint
    """
    if constraint_node is None:
        return None

    # Check for predefined type set by name
    type_set_name = getattr(constraint_node, 'type_name', None) or getattr(constraint_node, 'name', None)
    if type_set_name:
        predefined = get_predefined_type_set(type_set_name)
        if predefined:
            return predefined

    # Check for inline type set
    if constraint_node.kind == NodeKind.TYPE_SET:
        resolved_types = []
        for type_node in constraint_node.types or []:
            resolved = _resolve_constraint_member_type(type_node)
            if resolved is None:
                return None
            resolved_types.append(resolved)
        return TypeSet(types=frozenset(resolved_types))

    return None


def _resolve_constraint_member_type(type_node: Optional[ASTNode]) -> Optional[Type]:
    """Resolve a type node that appears inside an inline generic constraint set."""
    if type_node is None:
        return None

    if type_node.kind == NodeKind.TYPE_PRIMITIVE:
        return get_primitive_type(type_node.type_name or "")

    if type_node.kind == NodeKind.TYPE_IDENTIFIER:
        return get_primitive_type(type_node.name or type_node.type_name or "")

    return None
