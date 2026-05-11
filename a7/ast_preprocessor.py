"""
AST preprocessing pass for A7.

Simplifies and normalizes the AST before code generation.
Runs after semantic analysis, before codegen. Sub-passes:

1. Resolve stdlib calls → annotate with stdlib_canonical
2. Normalize struct inits → positional → named fields
3. Analyze mutations → set is_mutable on VAR nodes
4. Analyze usage → set is_used on VAR/PARAMETER nodes
5. Infer type annotations → set resolved_type on untyped mutable vars
6. Resolve variable shadowing → set emit_name
7. Hoist nested functions → move to module level, set hoisted flag
8. Fold constants → compile-time arithmetic

All tree walks use explicit stacks (no recursion) to avoid Python stack overflow.
"""

from typing import Optional, List, Set, Dict
from .ast_nodes import (
    ASTNode, NodeKind, LiteralKind, BinaryOp, UnaryOp,
    create_literal, create_primitive_type, SourceSpan,
)


# Shared list of all AST child attribute names
_AST_LIST_ATTRS = (
    'declarations', 'statements', 'parameters', 'arguments',
    'fields', 'variants', 'field_inits', 'elements',
    'cases', 'else_case', 'patterns', 'imported_items',
    'generic_params', 'parameter_types', 'types',
    'type_args', 'type_arguments',
)

_AST_SINGLE_ATTRS = (
    'body', 'then_stmt', 'else_stmt', 'init', 'update',
    'condition', 'expression', 'value', 'target',
    'function', 'left', 'right', 'operand', 'pointer',
    'object', 'index', 'start', 'end', 'iterable',
    'then_expr', 'else_expr', 'return_type', 'param_type',
    'field_type', 'element_type', 'target_type',
    'explicit_type', 'statement', 'literal', 'size',
    'constraint', 'variant_type', 'struct_type',
    'resolved_type',
)

_AST_ALL_CHILD_ATTRS = _AST_LIST_ATTRS + _AST_SINGLE_ATTRS


def _iter_children(node: ASTNode):
    """Yield all child ASTNodes of a given node (non-recursive)."""
    for attr_name in _AST_ALL_CHILD_ATTRS:
        val = getattr(node, attr_name, None)
        if isinstance(val, ASTNode):
            yield attr_name, val, None
        elif isinstance(val, list):
            for i, item in enumerate(val):
                if isinstance(item, ASTNode):
                    yield attr_name, item, i


def _walk_ast_iterative(root: ASTNode, visitor) -> None:
    """Walk AST calling visitor(node) on every node. Uses explicit stack."""
    if root is None:
        return
    stack = [root]
    while stack:
        node = stack.pop()
        visitor(node)
        # Push children in reverse order so left-to-right traversal is preserved
        children = []
        for _, child, _ in _iter_children(node):
            children.append(child)
        stack.extend(reversed(children))


class ASTPreprocessor:
    """
    Preprocesses the AST to simplify code generation.

    This pass runs after semantic analysis and before code generation.
    It does NOT modify semantic meaning, only structure and annotations.
    All walks use iterative traversal (no recursion).
    """

    def __init__(self, symbol_table=None, type_map=None, stdlib=None):
        self.symbol_table = symbol_table
        self.type_map = type_map or {}
        self.stdlib = stdlib
        self.changes_made = 0

        # Struct definitions: name -> list of field names (for positional init normalization)
        self._struct_defs: Dict[str, List[str]] = {}

    def process(self, ast: ASTNode) -> ASTNode:
        """Process the full AST tree. Returns the (potentially modified) root."""
        self.changes_made = 0

        # Phase 1: Collect struct definitions for later lookup (iterative)
        self._collect_struct_defs(ast)

        # Phase 2: Bottom-up transform pass (lower sugar, fold constants, annotate stdlib)
        ast = self._transform_tree(ast)

        # Phase 3: Annotation passes on functions (mutation, usage, shadowing, hoisting)
        self._annotate_program(ast)

        return ast

    # ================================================================
    # Iterative bottom-up tree transform
    # ================================================================

    def _transform_tree(self, root: ASTNode) -> ASTNode:
        """
        Transform the AST bottom-up using an explicit stack.

        We do a post-order traversal: visit children first, then apply
        transforms to the parent (which can then see transformed children).
        """
        if root is None:
            return None

        # Stack items: (node, parent, attr_name, list_index, visited)
        # visited=False means we need to push children first
        # visited=True means children are done, process this node
        stack = [(root, None, None, None, False)]

        while stack:
            node, parent, attr_name, list_idx, visited = stack[-1]

            if visited:
                stack.pop()
                # Apply transforms to this node
                new_node = self._lower_field_sugar(node)
                new_node = self._fold_constants(new_node)
                self._resolve_stdlib_call(new_node)
                self._normalize_struct_init(new_node)

                # Update parent reference if node was replaced
                if new_node is not node and parent is not None:
                    if list_idx is not None:
                        getattr(parent, attr_name)[list_idx] = new_node
                    else:
                        setattr(parent, attr_name, new_node)

                # Update root reference
                if parent is None:
                    root = new_node
            else:
                # Mark as visited, then push children
                stack[-1] = (node, parent, attr_name, list_idx, True)

                # Push children in reverse order for correct processing order
                children_to_push = []
                for child_attr in _AST_ALL_CHILD_ATTRS:
                    val = getattr(node, child_attr, None)
                    if isinstance(val, ASTNode):
                        children_to_push.append((val, node, child_attr, None, False))
                    elif isinstance(val, list):
                        for i, item in enumerate(val):
                            if isinstance(item, ASTNode):
                                children_to_push.append((item, node, child_attr, i, False))

                # Push in reverse so first child is processed first
                for child in reversed(children_to_push):
                    stack.append(child)

        return root

    # ================================================================
    # Pass 0: Collect struct definitions (iterative)
    # ================================================================

    def _collect_struct_defs(self, root: ASTNode) -> None:
        """Walk AST to collect struct name → field names map. Iterative."""
        def visitor(node):
            if node.kind == NodeKind.STRUCT and node.name:
                field_names = []
                for f in (node.fields or []):
                    if f.name:
                        field_names.append(f.name)
                self._struct_defs[node.name] = field_names

        _walk_ast_iterative(root, visitor)

    def _lower_field_sugar(self, node: ASTNode) -> ASTNode:
        """Compatibility no-op: .adr/.val are no longer pointer syntax."""
        return node

    # ================================================================
    # Pass 2: Resolve stdlib calls
    # ================================================================

    def _resolve_stdlib_call(self, node: ASTNode) -> None:
        """Annotate CALL nodes with stdlib_canonical if they match a stdlib function."""
        if self.stdlib is None or node.kind != NodeKind.CALL:
            return

        func = node.function
        if func is None:
            return

        # module.method pattern: io.println, math.sqrt
        if func.kind == NodeKind.FIELD_ACCESS:
            obj = getattr(func, 'object', None)
            field = getattr(func, 'field', '')
            if obj and obj.kind == NodeKind.IDENTIFIER and obj.name:
                module_name = self._resolve_module_import_path(obj.name) or obj.name
                canonical = self.stdlib.resolve_call(module_name, field)
                if canonical:
                    node.stdlib_canonical = canonical
                    self.changes_made += 1

        # Bare builtin: sqrt_f32, abs_f64
        elif func.kind == NodeKind.IDENTIFIER and func.name:
            canonical = self.stdlib.resolve_builtin(func.name)
            if canonical:
                node.stdlib_canonical = canonical
                self.changes_made += 1

    def _resolve_module_import_path(self, alias: str) -> Optional[str]:
        """Return the import path for a module alias in the semantic symbol table."""
        if self.symbol_table is None:
            return None

        symbol = self.symbol_table.lookup(alias)
        if symbol is None or getattr(getattr(symbol, "kind", None), "name", None) != "MODULE":
            return None

        node = getattr(symbol, "node", None)
        return getattr(node, "module_path", None)

    # ================================================================
    # Pass 3: Normalize struct initialization
    # ================================================================

    def _normalize_struct_init(self, node: ASTNode) -> None:
        """Convert positional struct inits to named field inits."""
        if node.kind != NodeKind.STRUCT_INIT:
            return

        field_inits = node.field_inits or []
        if not field_inits:
            return

        # Check if any init is positional (no name)
        has_positional = any(fi.name is None for fi in field_inits)
        if not has_positional:
            return

        # Look up struct definition
        struct_name = None
        if isinstance(node.struct_type, str):
            struct_name = node.struct_type
        elif isinstance(node.struct_type, ASTNode) and node.struct_type.name:
            struct_name = node.struct_type.name

        if not struct_name or struct_name not in self._struct_defs:
            return

        field_names = self._struct_defs[struct_name]
        if len(field_inits) > len(field_names):
            return  # Too many inits; leave for error reporting

        for i, fi in enumerate(field_inits):
            if fi.name is None and i < len(field_names):
                fi.name = field_names[i]
                self.changes_made += 1

    # ================================================================
    # Pass 4-8: Annotation passes (run on complete AST)
    # ================================================================

    def _annotate_program(self, ast: ASTNode) -> None:
        """Run annotation passes on the program."""
        if ast.kind != NodeKind.PROGRAM:
            return

        for decl in (ast.declarations or []):
            if decl.kind == NodeKind.FUNCTION:
                self._annotate_function(decl)

    def _annotate_function(self, func_node: ASTNode) -> None:
        """Annotate a function with mutation, usage, shadowing, and hoisting info."""
        if func_node.body is None:
            return

        # Pass 4: Mutation analysis (iterative)
        mutated = self._collect_mutations(func_node.body)
        self._mark_mutations(func_node, mutated)

        # Pass 5: Usage analysis (iterative)
        used = self._collect_used_identifiers(func_node.body)
        self._mark_usage(func_node, used)

        # Pass 6: Type inference for untyped mutable vars (iterative)
        self._infer_types(func_node.body)

        # Pass 7: Variable shadowing resolution (iterative)
        self._resolve_shadowing(func_node)

        # Pass 8: Nested function hoisting
        self._hoist_nested_functions(func_node)

    # ---- Pass 4: Mutation analysis (iterative) ----

    def _get_root_identifier(self, node: ASTNode) -> Optional[str]:
        """Walk through indexing/field access to find root variable name. Iterative."""
        current = node
        while current is not None:
            if current.kind == NodeKind.IDENTIFIER:
                return current.name
            if current.kind == NodeKind.INDEX:
                current = current.object
            elif current.kind == NodeKind.FIELD_ACCESS:
                current = current.object
            elif current.kind == NodeKind.DEREF:
                current = current.pointer
            else:
                return None
        return None

    def _collect_mutations(self, node: ASTNode) -> Set[str]:
        """Collect variable names that need mutable Zig storage."""
        mutations: Set[str] = set()

        def visitor(n):
            if n.kind == NodeKind.ASSIGNMENT and n.target:
                root = self._get_root_identifier(n.target)
                if root:
                    mutations.add(root)
            elif n.kind == NodeKind.ADDRESS_OF and n.operand:
                root = self._get_root_identifier(n.operand)
                if root:
                    mutations.add(root)
            elif n.kind == NodeKind.CALL:
                implicit_ref_args = set(getattr(n, "implicit_ref_args", set()) or set())
                for index, arg in enumerate(n.arguments or []):
                    if index in implicit_ref_args:
                        root = self._get_root_identifier(arg)
                        if root:
                            mutations.add(root)

        _walk_ast_iterative(node, visitor)
        return mutations

    def _mark_mutations(self, func_node: ASTNode, mutated: Set[str]) -> None:
        """Mark VAR nodes and for-loop variables as mutable. Iterative."""
        def visitor(n):
            if n.kind == NodeKind.VAR and n.name and n.name in mutated:
                n.is_mutable = True
            if n.kind == NodeKind.FOR and n.init:
                if n.init.kind == NodeKind.VAR and n.init.name:
                    n.init.is_mutable = True

        _walk_ast_iterative(func_node.body, visitor)

    # ---- Pass 5: Usage analysis (iterative) ----

    def _collect_used_identifiers(self, node: ASTNode) -> Set[str]:
        """Collect all identifier names referenced in a subtree. Iterative."""
        used: Set[str] = set()

        def visitor(n):
            if n.kind == NodeKind.IDENTIFIER and n.name:
                used.add(n.name)
            elif n.kind == NodeKind.TYPE_IDENTIFIER and n.name:
                used.add(n.name)

        _walk_ast_iterative(node, visitor)
        return used

    def _mark_usage(self, func_node: ASTNode, used: Set[str]) -> None:
        """Mark VAR/PARAMETER nodes as used or unused."""
        for param in (func_node.parameters or []):
            if param.kind == NodeKind.PARAMETER:
                param.is_used = param.name in used if param.name else True

        def visitor(n):
            if n.kind == NodeKind.VAR and n.name:
                n.is_used = n.name in used

        _walk_ast_iterative(func_node.body, visitor)

    # ---- Pass 6: Type inference (iterative) ----

    def _infer_types(self, body: ASTNode) -> None:
        """Infer type annotations for untyped mutable variables. Iterative."""
        def visitor(n):
            if n.kind != NodeKind.VAR:
                return
            if not n.is_mutable:
                return
            if n.explicit_type is not None:
                return
            if n.value is None:
                return

            node_id = id(n)
            if node_id in self.type_map:
                return

            inferred = self._infer_from_value(n.value)
            if inferred:
                n.resolved_type = inferred
                self.changes_made += 1

        _walk_ast_iterative(body, visitor)

    def _infer_from_value(self, value_node: ASTNode) -> Optional[ASTNode]:
        """Infer a type annotation node from an initializer value."""
        if value_node is None:
            return None

        if value_node.kind == NodeKind.LITERAL:
            lk = value_node.literal_kind
            if lk == LiteralKind.INTEGER:
                return create_primitive_type("i32")
            elif lk == LiteralKind.FLOAT:
                return create_primitive_type("f64")
            elif lk == LiteralKind.BOOLEAN:
                return create_primitive_type("bool")
            elif lk == LiteralKind.STRING:
                return create_primitive_type("string")
            elif lk == LiteralKind.CHAR:
                return create_primitive_type("char")

        return None

    # ---- Pass 7: Variable shadowing (iterative) ----

    def _resolve_shadowing(self, func_node: ASTNode) -> None:
        """Resolve variable shadowing by setting emit_name on shadowed vars. Iterative."""
        scope_stack: List[Set[str]] = [set()]
        all_emitted: Set[str] = set()

        # Register parameters in first scope
        for param in (func_node.parameters or []):
            if param.name:
                scope_stack[-1].add(param.name)
                all_emitted.add(param.name)

        def declare_var(name: str) -> Optional[str]:
            for outer in scope_stack[:-1]:
                if name in outer:
                    suffix = 1
                    new_name = f"{name}_{suffix}"
                    while new_name in all_emitted:
                        suffix += 1
                        new_name = f"{name}_{suffix}"
                    all_emitted.add(new_name)
                    scope_stack[-1].add(name)
                    return new_name
            scope_stack[-1].add(name)
            all_emitted.add(name)
            return None

        # Iterative tree walk with scope enter/exit events
        # Stack items: ('enter_scope',) | ('exit_scope',) | ('visit', node)
        if func_node.body is None:
            return

        stack = [('visit', func_node.body)]
        while stack:
            item = stack.pop()

            if item[0] == 'enter_scope':
                scope_stack.append(set())
                continue
            if item[0] == 'exit_scope':
                if len(scope_stack) > 1:
                    scope_stack.pop()
                continue

            _, node = item
            if node is None:
                continue

            if node.kind == NodeKind.VAR and node.name:
                rename = declare_var(node.name)
                if rename:
                    node.emit_name = rename
                    self.changes_made += 1

            elif node.kind == NodeKind.BLOCK:
                # Push exit_scope, then statements (reversed), then enter_scope
                stack.append(('exit_scope',))
                for stmt in reversed(node.statements or []):
                    stack.append(('visit', stmt))
                stack.append(('enter_scope',))

            elif node.kind in (NodeKind.IF_STMT, NodeKind.WHILE, NodeKind.FOR,
                               NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED, NodeKind.MATCH):
                # Push relevant children in reverse order
                for case_stmt in reversed(node.else_case or []):
                    if isinstance(case_stmt, ASTNode):
                        stack.append(('visit', case_stmt))
                for case in reversed(node.cases or []):
                    stmt = getattr(case, 'statement', None)
                    if stmt:
                        stack.append(('visit', stmt))
                for attr in reversed(('init', 'body', 'then_stmt', 'else_stmt')):
                    child = getattr(node, attr, None)
                    if isinstance(child, ASTNode):
                        stack.append(('visit', child))
            else:
                # Generic: push block/statement children
                for attr in reversed(('body', 'then_stmt', 'else_stmt', 'init', 'statement')):
                    child = getattr(node, attr, None)
                    if isinstance(child, ASTNode):
                        stack.append(('visit', child))
                for attr in reversed(('statements', 'cases', 'else_case')):
                    children = getattr(node, attr, None)
                    if isinstance(children, list):
                        for child in reversed(children):
                            if isinstance(child, ASTNode):
                                stack.append(('visit', child))

    # ---- Pass 8: Nested function hoisting ----

    def _hoist_nested_functions(self, func_node: ASTNode) -> None:
        """Find nested function declarations and mark them as hoisted."""
        if func_node.body is None:
            return

        body = func_node.body
        if body.kind != NodeKind.BLOCK or not body.statements:
            return

        for stmt in body.statements:
            if stmt.kind == NodeKind.FUNCTION:
                stmt.hoisted = True
                self.changes_made += 1
                # Process nested functions too (non-recursive: they go through
                # _annotate_function which is called from _annotate_program)
                self._annotate_function(stmt)

    # ================================================================
    # Pass 9: Constant folding (node-local, no recursion)
    # ================================================================

    def _fold_constants(self, node: ASTNode) -> ASTNode:
        """Fold simple constant expressions."""
        if node.kind == NodeKind.UNARY:
            return self._fold_unary(node)
        elif node.kind == NodeKind.BINARY:
            return self._fold_binary(node)
        return node

    def _fold_unary(self, node: ASTNode) -> ASTNode:
        """Fold unary constant expressions."""
        operand = getattr(node, 'operand', None)
        op = getattr(node, 'operator', None)
        if operand is None or op is None:
            return node

        if operand.kind != NodeKind.LITERAL:
            return node

        val = getattr(operand, 'literal_value', None)
        if val is None:
            return node

        if op == UnaryOp.NEG and isinstance(val, (int, float)):
            result = -val
            lk = operand.literal_kind
            self.changes_made += 1
            return ASTNode(
                kind=NodeKind.LITERAL,
                literal_kind=lk,
                literal_value=result,
                raw_text=str(result),
                span=node.span,
            )

        if op == UnaryOp.NOT and isinstance(val, bool):
            result = not val
            self.changes_made += 1
            return ASTNode(
                kind=NodeKind.LITERAL,
                literal_kind=LiteralKind.BOOLEAN,
                literal_value=result,
                raw_text=str(result).lower(),
                span=node.span,
            )

        return node

    def _fold_binary(self, node: ASTNode) -> ASTNode:
        """Fold binary constant expressions."""
        left = getattr(node, 'left', None)
        right = getattr(node, 'right', None)
        op = getattr(node, 'operator', None)
        if left is None or right is None or op is None:
            return node

        if left.kind != NodeKind.LITERAL or right.kind != NodeKind.LITERAL:
            return node

        lval = getattr(left, 'literal_value', None)
        rval = getattr(right, 'literal_value', None)
        if lval is None or rval is None:
            return node

        numeric_literals = (
            isinstance(lval, (int, float)) and not isinstance(lval, bool) and
            isinstance(rval, (int, float)) and not isinstance(rval, bool)
        )

        if numeric_literals:
            result = None
            try:
                if op == BinaryOp.ADD:
                    result = lval + rval
                elif op == BinaryOp.SUB:
                    result = lval - rval
                elif op == BinaryOp.MUL:
                    result = lval * rval
                elif op == BinaryOp.DIV and rval != 0:
                    result = int(lval / rval) if isinstance(lval, int) and isinstance(rval, int) else lval / rval
                elif op == BinaryOp.MOD and rval != 0:
                    if isinstance(lval, int) and isinstance(rval, int):
                        result = lval - (int(lval / rval) * rval)
                    else:
                        result = lval % rval
                elif op == BinaryOp.BIT_AND and isinstance(lval, int) and isinstance(rval, int):
                    result = lval & rval
                elif op == BinaryOp.BIT_OR and isinstance(lval, int) and isinstance(rval, int):
                    result = lval | rval
                elif op == BinaryOp.BIT_XOR and isinstance(lval, int) and isinstance(rval, int):
                    result = lval ^ rval
                elif op == BinaryOp.BIT_SHL and isinstance(lval, int) and isinstance(rval, int) and rval >= 0:
                    result = lval << rval
                elif op == BinaryOp.BIT_SHR and isinstance(lval, int) and isinstance(rval, int) and rval >= 0:
                    result = lval >> rval
            except (ZeroDivisionError, OverflowError):
                return node

            if result is not None:
                lk = LiteralKind.FLOAT if isinstance(result, float) else LiteralKind.INTEGER
                self.changes_made += 1
                return ASTNode(
                    kind=NodeKind.LITERAL,
                    literal_kind=lk,
                    literal_value=result,
                    raw_text=str(result),
                    span=node.span,
                )

        comparable_literals = numeric_literals or left.literal_kind == right.literal_kind
        if comparable_literals:
            result = None
            if op == BinaryOp.EQ:
                result = lval == rval
            elif op == BinaryOp.NE:
                result = lval != rval
            elif numeric_literals and op == BinaryOp.LT:
                result = lval < rval
            elif numeric_literals and op == BinaryOp.LE:
                result = lval <= rval
            elif numeric_literals and op == BinaryOp.GT:
                result = lval > rval
            elif numeric_literals and op == BinaryOp.GE:
                result = lval >= rval

            if result is not None:
                self.changes_made += 1
                return ASTNode(
                    kind=NodeKind.LITERAL,
                    literal_kind=LiteralKind.BOOLEAN,
                    literal_value=result,
                    raw_text=str(result).lower(),
                    span=node.span,
                )

        if isinstance(lval, bool) and isinstance(rval, bool):
            result = None
            if op == BinaryOp.AND:
                result = lval and rval
            elif op == BinaryOp.OR:
                result = lval or rval

            if result is not None:
                self.changes_made += 1
                return ASTNode(
                    kind=NodeKind.LITERAL,
                    literal_kind=LiteralKind.BOOLEAN,
                    literal_value=result,
                    raw_text=str(result).lower(),
                    span=node.span,
                )

        return node
