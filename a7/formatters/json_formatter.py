"""
JSON output formatter for A7 compiler.

Converts compilation results (tokens, AST, metadata) to JSON format.
"""

from datetime import datetime
from typing import Optional


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
        """
        Convert compilation results to JSON format.

        Args:
            tokens: List of tokens from tokenizer
            ast: AST root node
            source_code: Original source code
            input_path: Input file path

        Returns:
            Dictionary with metadata, tokens, and AST
        """
        # Convert tokens to serializable format
        token_list = []
        for token in tokens:
            token_list.append(
                {
                    "type": token.type.name,
                    "value": token.value,
                    "line": token.line,
                    "column": token.column,
                    "length": token.length,
                }
            )

        # Create comprehensive JSON structure
        result = {
            "metadata": {
                "filename": input_path,
                "compiler": "a7-py",
                "backend": self.backend,
                "timestamp": datetime.now().isoformat(),
                "token_count": len(tokens),
                "source_lines": len(source_code.splitlines()),
                "source_size_bytes": len(source_code.encode("utf-8")),
                "parse_success": ast is not None,
            },
            "source_code": source_code,
            "tokens": token_list,
            "ast": self._ast_to_dict(ast) if ast else None,
        }

        return result

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
                result[field] = value

        # Add literal information
        if hasattr(node, "literal_kind") and node.literal_kind:
            result["literal_kind"] = node.literal_kind.name
            result["literal_value"] = node.literal_value
            result["raw_text"] = node.raw_text

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

        # Add list fields (child nodes)
        list_fields = [
            "declarations",
            "parameters",
            "statements",
            "arguments",
            "fields",
            "variants",
            "generic_params",
            "type_arguments",
            "parameter_types",
            "type_args",
            "types",
            "elements",
            "field_inits",
            "cases",
            "else_case",
            "patterns",
            "imported_items",
        ]

        # Add single node fields
        node_fields = [
            "value",
            "body",
            "condition",
            "left",
            "right",
            "operand",
            "function",
            "expression",
            "return_type",
            "explicit_type",
            "target_type",
            "element_type",
            "size",
            "object",
            "index",
            "start",
            "end",
            "pointer",
            "then_expr",
            "else_expr",
            "then_stmt",
            "else_stmt",
            "init",
            "update",
            "iterable",
            "statement",
            "target",
            "literal",
            "param_type",
            "field_type",
            "variant_type",
            "constraint",
        ]

        result = self._ast_node_shallow_dict(node)
        stack = [(node, result)]

        while stack:
            current, current_result = stack.pop()

            for field in list_fields:
                field_value = getattr(current, field, None)
                if field_value is not None:
                    children = []
                    for child in field_value:
                        if hasattr(child, "kind"):
                            child_result = self._ast_node_shallow_dict(child)
                            children.append(child_result)
                            stack.append((child, child_result))
                        else:
                            children.append(child)
                    current_result[field] = children

            for field in node_fields:
                field_value = getattr(current, field, None)
                if field_value is not None:
                    if hasattr(field_value, "kind"):
                        child_result = self._ast_node_shallow_dict(field_value)
                        current_result[field] = child_result
                        stack.append((field_value, child_result))
                    else:
                        current_result[field] = field_value

        return result
