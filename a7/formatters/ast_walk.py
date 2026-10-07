"""Shared AST child enumeration for the JSON, console and markdown views.

The three views list a node's children through `iter_child_fields` or
`iter_children`, so a child field named here appears in all of them and a
field missing here is missing from all of them.
"""

from typing import Any, Iterator, Optional, Tuple

# ASTNode fields that hold child nodes, in reading order.
CHILD_FIELDS = (
    "declarations",
    "generic_params",
    "parameters",
    "param_type",
    "return_type",
    "constraint",
    "explicit_type",
    "field_type",
    "variant_type",
    "fields",
    "variants",
    "imported_items",
    "target",
    "init",
    "iterable",
    "condition",
    "update",
    "expression",
    "object",
    "pointer",
    "function",
    "type_arguments",
    "arguments",
    "type_args",
    "parameter_types",
    "types",
    "size",
    "element_type",
    "target_type",
    "index",
    "start",
    "end",
    "left",
    "right",
    "operand",
    "literal",
    "patterns",
    "value",
    "elements",
    "field_inits",
    "then_expr",
    "else_expr",
    "then_stmt",
    "else_stmt",
    "statement",
    "body",
    "statements",
    "cases",
    "else_case",
)

# The subset whose children are statements. The console tree shows one line
# per statement and descends only through these.
STATEMENT_FIELDS = frozenset({
    "init",
    "update",
    "then_stmt",
    "else_stmt",
    "statement",
    "body",
    "statements",
    "cases",
    "else_case",
})


def iter_child_fields(node) -> Iterator[Tuple[str, Any]]:
    """Yield (field, value) for each child field that is set on `node`.

    The value is a node, a list, or a scalar: `else_case` is a statement
    list on a statement match and one expression node on a match
    expression, and `imported_items` is a list of names.
    """
    for field in CHILD_FIELDS:
        value = getattr(node, field, None)
        if value is not None:
            yield field, value


def iter_children(node) -> Iterator[Tuple[str, Optional[int], Any]]:
    """Yield (field, index, child) for each child node of `node`.

    `index` is the position in a list field and None for a single-node
    field. Scalars are skipped.
    """
    for field, value in iter_child_fields(node):
        if hasattr(value, "kind"):
            yield field, None, value
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                if hasattr(item, "kind"):
                    yield field, index, item
