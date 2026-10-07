"""
JSON output formatter for A7 compiler.

Converts tokens and the AST to JSON-serializable values.
"""

import json
from typing import Any, Optional

from .ast_walk import iter_child_fields


def _safe_scalar(value: Any) -> Any:
    """Return scalar unchanged when JSON-serializable, else str(value)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return str(value)
    return value


def _safe_json_value(value: Any) -> Any:
    """Return value unchanged when JSON-serializable, else str(value).

    AST literal values can hold non-serializable objects (Fraction from
    constant folding, byte blobs). The JSON payload must degrade those to
    their string form instead of raising in json.dumps.

    Iterative: explicit stack, no recursion (see no-recursion rule).
    """
    if isinstance(value, dict):
        root: Any = {}
        stack: list = [(value, root)]
    elif isinstance(value, (list, tuple)):
        root = []
        stack = [(list(value), root)]
    else:
        return _safe_scalar(value)
    while stack:
        src, dst = stack.pop()
        if isinstance(src, dict):
            for key, item in src.items():
                if isinstance(item, dict):
                    child: Any = {}
                    dst[key] = child
                    stack.append((item, child))
                elif isinstance(item, (list, tuple)):
                    child = []
                    dst[key] = child
                    stack.append((list(item), child))
                else:
                    dst[key] = _safe_scalar(item)
        else:
            for item in src:
                if isinstance(item, dict):
                    child = {}
                    dst.append(child)
                    stack.append((item, child))
                elif isinstance(item, (list, tuple)):
                    child = []
                    dst.append(child)
                    stack.append((list(item), child))
                else:
                    dst.append(_safe_scalar(item))
    return root


class JSONFormatter:
    """Formats compilation results as JSON."""

    def __init__(self, backend: str = "zig"):
        """
        Initialize JSON formatter.

        Args:
            backend: Target backend name
        """
        self.backend = backend

    def format_compilation(
        self, tokens: list, ast, source_code: str, input_path: str
    ) -> dict:
        """Return {"tokens": [...], "ast": {...} or None} for the JSON payload.

        Token-count definition: source tokens only; the synthetic EOF
        sentinel is excluded here and in stages["tokenize"]["token_count"]
        (see compile.py).
        """
        token_list = []
        for token in tokens:
            if token.type.name == "EOF":
                continue
            token_list.append(
                {
                    "type": token.type.name,
                    "value": _safe_json_value(token.value),
                    "line": token.line,
                    "column": token.column,
                    "length": token.length,
                }
            )

        return {
            "tokens": token_list,
            "ast": self._ast_to_dict(ast) if ast else None,
        }

    def _ast_node_shallow_dict(self, node) -> dict:
        """
        Convert one AST node to a dictionary without traversing child nodes.

        Args:
            node: AST node

        Returns:
            Shallow dictionary representation of AST
        """
        result = {
            "kind": node.kind.name,
            "span": {
                "start_line": node.span.start_line,
                "start_column": node.span.start_column,
                "end_line": node.span.end_line,
                "end_column": node.span.end_column,
                "length": getattr(node.span, "length", None),
            }
            if node.span
            else None,
        }

        # Add all relevant scalar fields
        scalar_fields = [
            "name",
            "is_public",
            "is_using",
            "is_tagged",
            "is_variadic",
            "has_fallthrough",
            "module_path",
            "alias",
            "type_name",
            "field",
            "iterator",
            "index_var",
            "label",
            "enum_type",
            "variant",
            "raw_text",
            "struct_type",
        ]

        for field in scalar_fields:
            value = getattr(node, field, None)
            if value is not None:
                result[field] = _safe_json_value(value)

        # Add literal information
        if hasattr(node, "literal_kind") and node.literal_kind:
            result["literal_kind"] = node.literal_kind.name
            result["literal_value"] = _safe_json_value(node.literal_value)

        # Add operator information
        if hasattr(node, "operator") and node.operator:
            result["operator"] = (
                node.operator.name
                if hasattr(node.operator, "name")
                else str(node.operator)
            )

        return result

    def _ast_to_dict(self, node) -> Optional[dict]:
        """
        Convert AST node to dictionary using an explicit traversal stack.

        Args:
            node: AST node

        Returns:
            Dictionary representation of AST
        """
        if node is None:
            return None

        result = self._ast_node_shallow_dict(node)
        stack = [(node, result)]

        while stack:
            current, current_result = stack.pop()

            for field, field_value in iter_child_fields(current):
                if hasattr(field_value, "kind"):
                    child_result = self._ast_node_shallow_dict(field_value)
                    current_result[field] = child_result
                    stack.append((field_value, child_result))
                elif isinstance(field_value, (list, tuple)):
                    children = []
                    for child in field_value:
                        if hasattr(child, "kind"):
                            child_result = self._ast_node_shallow_dict(child)
                            children.append(child_result)
                            stack.append((child, child_result))
                        else:
                            children.append(_safe_json_value(child))
                    current_result[field] = children
                else:
                    current_result[field] = _safe_json_value(field_value)

        return result
