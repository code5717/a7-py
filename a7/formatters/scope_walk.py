"""Shared scope-walk helper for symbol-table formatters."""

from typing import Iterator, Optional, Set, Tuple


def iter_scopes(
    root_scope,
    root_name: str = "global",
    visited: Optional[Set[int]] = None,
) -> Iterator[Tuple[object, str]]:
    """Yield (scope, scope_name) pairs in deterministic pre-order.

    Iterative worklist with id-based cycle guard. Callers format symbols
    per scope; this helper owns only traversal order and child naming.
    """
    if visited is None:
        visited = set()
    if root_scope is None:
        return
    stack = [(root_scope, root_name)]
    while stack:
        current, cur_name = stack.pop()
        if current is None or id(current) in visited:
            continue
        visited.add(id(current))
        yield current, cur_name
        children = getattr(current, "children", [])
        for i, child in enumerate(reversed(children)):
            child_name = getattr(child, "name", f"scope_{len(children) - 1 - i}")
            stack.append((child, child_name))
