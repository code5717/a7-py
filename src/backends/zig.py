"""
Zig code generation backend for the A7 compiler.

Translates A7 AST nodes to valid Zig source code.
"""

from io import StringIO
from typing import Optional, Dict, Set

from ..ast_nodes import ASTNode, NodeKind, LiteralKind, BinaryOp, UnaryOp, AssignOp
from ..errors import CodegenError
from .base import CodeGenerator


class ZigCodeGenerator(CodeGenerator):
    """Generates Zig source code from A7 AST."""

    def __init__(self):
        super().__init__()
        self._needs_allocator = False
        self._needs_std = False
        self._type_map: Dict = {}
        self._symbol_table = None
        self._declared_structs: Set[str] = set()
        # Mutation analysis: variables that are targets of assignments
        self._mutated_vars: Set[str] = set()
        # Used identifiers in current scope (for unused var/param detection)
        self._used_identifiers: Set[str] = set()
        # Nested function hoisting
        self._hoisted_functions: list = []
        self._skip_nested_fn_names: Set[str] = set()
        # Variable shadowing prevention
        self._scope_stack: list = []  # List[Set[str]] - variable names per scope
        self._rename_map: Dict[str, str] = {}  # original -> renamed
        # Track if we're inside a function body
        self._in_function = False
        self._loop_label_stack: list[tuple[Optional[str], Optional[str]]] = []

    @property
    def file_extension(self) -> str:
        return ".zig"

    @property
    def language_name(self) -> str:
        return "Zig"

    def generate(self, ast: ASTNode, type_map: Optional[Dict] = None,
                 symbol_table=None) -> str:
        """Generate Zig source code from an A7 AST."""
        self.reset()
        self._needs_allocator = False
        self._needs_std = False
        self._type_map = type_map or {}
        self._symbol_table = symbol_table
        self._declared_structs = set()
        self._mutated_vars = set()
        self._used_identifiers = set()
        self._hoisted_functions = []
        self._skip_nested_fn_names = set()
        self._scope_stack = []
        self._rename_map = {}
        self._in_function = False
        self._loop_label_stack = []

        # First pass: scan for features that need preamble items
        self._scan_features(ast)

        # Generate the preamble
        preamble = self._emit_preamble()

        # Second pass: generate code
        self.visit(ast)

        code = self.output.getvalue()
        return preamble + code

    def _scan_features(self, root: ASTNode) -> None:
        """Scan the AST to determine what preamble items are needed. Iterative."""
        if root is None:
            return

        def visitor(node):
            if node.kind == NodeKind.NEW_EXPR or node.kind == NodeKind.DEL:
                self._needs_allocator = True
                self._needs_std = True

            if node.kind == NodeKind.CALL:
                # Check for io.println / io.print calls
                if node.function and node.function.kind == NodeKind.FIELD_ACCESS:
                    obj = getattr(node.function, 'object', None)
                    if obj and obj.kind == NodeKind.IDENTIFIER and getattr(obj, 'name', '') == 'io':
                        self._needs_std = True

        self._walk_ast(root, visitor)

    def _emit_preamble(self) -> str:
        """Generate the Zig preamble (imports, allocator, etc.)."""
        lines = []
        if self._needs_std:
            lines.append("const std = @import(\"std\");")
        if self._needs_allocator:
            lines.append("const allocator = std.heap.page_allocator;")
        if lines:
            lines.append("")
        return "\n".join(lines) + ("\n" if lines else "")

    # === AST analysis helpers (iterative to avoid stack overflow) ===

    _AST_CHILD_ATTRS = (
        'declarations', 'statements', 'body', 'then_stmt', 'else_stmt',
        'init', 'update', 'cases', 'else_case', 'expression', 'condition',
        'value', 'target', 'function', 'arguments', 'field_inits', 'elements',
        'operand', 'left', 'right', 'pointer', 'then_expr', 'else_expr',
        'iterable', 'statement', 'patterns', 'object', 'index', 'literal',
        'start', 'end', 'explicit_type', 'param_type', 'return_type',
        'target_type', 'element_type', 'parameter_types', 'type_args',
        'type_arguments', 'fields', 'parameters', 'variants',
    )

    def _walk_ast(self, node: ASTNode, visitor):
        """Walk AST calling visitor(node) on every node. Iterative."""
        if node is None:
            return
        stack = [node]
        while stack:
            n = stack.pop()
            visitor(n)
            children = []
            for attr_name in self._AST_CHILD_ATTRS:
                val = getattr(n, attr_name, None)
                if isinstance(val, ASTNode):
                    children.append(val)
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, ASTNode):
                            children.append(item)
            stack.extend(reversed(children))

    def _collect_mutations(self, node: ASTNode) -> Set[str]:
        """Collect variable names that are targets of assignments in a subtree."""
        mutations = set()

        def base_identifier(target: ASTNode) -> Optional[str]:
            """Resolve base identifier for assignment targets like a, a[i], a.b, p.val.x."""
            if target is None:
                return None
            if target.kind == NodeKind.IDENTIFIER:
                return target.name
            if target.kind == NodeKind.FIELD_ACCESS:
                return base_identifier(getattr(target, 'object', None))
            if target.kind == NodeKind.INDEX:
                return base_identifier(getattr(target, 'object', None))
            if target.kind == NodeKind.DEREF:
                # Dereferencing mutates the pointee, not the pointer binding itself.
                return None
            return None

        def visitor(n):
            if n.kind == NodeKind.ASSIGNMENT:
                target = n.target
                base = base_identifier(target)
                if base:
                    mutations.add(base)
            # Compound assignment operators also count as mutations
            # (they're also ASSIGNMENT nodes with non-ASSIGN op)

        self._walk_ast(node, visitor)
        return mutations

    def _collect_used_identifiers(self, node: ASTNode) -> Set[str]:
        """Collect all identifier names referenced in a subtree.

        Includes both expression identifiers and type identifiers (e.g., type
        names used in type annotations like `x: Handle`).
        """
        used = set()

        def visitor(n):
            if n.kind == NodeKind.IDENTIFIER:
                if n.name:
                    used.add(n.name)
            elif n.kind == NodeKind.TYPE_IDENTIFIER:
                if n.name:
                    used.add(n.name)

        self._walk_ast(node, visitor)
        return used

    def _collect_nested_functions(self, node: ASTNode) -> list:
        """Collect FUNCTION nodes that are direct children of a block's statements."""
        nested = []
        if node is None:
            return nested
        for stmt in (node.statements or []):
            if stmt.kind == NodeKind.FUNCTION:
                nested.append(stmt)
        return nested

    def _push_scope(self):
        """Push a new variable scope for shadowing detection."""
        self._scope_stack.append(set())

    def _pop_scope(self):
        """Pop a variable scope and clean up renames."""
        if self._scope_stack:
            scope = self._scope_stack.pop()
            for name in scope:
                self._rename_map.pop(name, None)

    def _declare_var_in_scope(self, name: str) -> str:
        """Declare a variable in current scope, renaming if it shadows an outer one."""
        # Check if name exists in any outer scope
        for outer_scope in self._scope_stack[:-1]:
            if name in outer_scope:
                # Name shadows — find a unique rename
                suffix = 1
                new_name = f"{name}_{suffix}"
                all_names = set()
                for s in self._scope_stack:
                    all_names.update(s)
                while new_name in all_names or new_name in self._rename_map.values():
                    suffix += 1
                    new_name = f"{name}_{suffix}"
                self._rename_map[name] = new_name
                if self._scope_stack:
                    self._scope_stack[-1].add(name)
                return new_name
        # No shadow — register in current scope
        if self._scope_stack:
            self._scope_stack[-1].add(name)
        return name

    def _resolve_name(self, name: str) -> str:
        """Resolve a variable name through the rename map."""
        return self._rename_map.get(name, name)

    def visit(self, node: ASTNode) -> None:
        """Visit an AST node and generate Zig code."""
        if node is None:
            return

        kind = node.kind

        if kind == NodeKind.PROGRAM:
            self._visit_program(node)
        elif kind == NodeKind.FUNCTION:
            self._visit_function(node)
        elif kind == NodeKind.STRUCT:
            self._visit_struct(node)
        elif kind == NodeKind.ENUM:
            self._visit_enum(node)
        elif kind == NodeKind.UNION:
            self._visit_union(node)
        elif kind == NodeKind.CONST:
            self._visit_const(node)
        elif kind == NodeKind.VAR:
            self._visit_var(node)
        elif kind == NodeKind.TYPE_ALIAS:
            self._visit_type_alias(node)
        elif kind == NodeKind.IMPORT:
            pass  # Imports handled via preamble / special-casing
        elif kind == NodeKind.BLOCK:
            self._visit_block(node)
        elif kind == NodeKind.IF_STMT:
            self._visit_if_stmt(node)
        elif kind == NodeKind.WHILE:
            self._visit_while(node)
        elif kind == NodeKind.FOR:
            self._visit_for(node)
        elif kind == NodeKind.FOR_IN:
            self._visit_for_in(node)
        elif kind == NodeKind.FOR_IN_INDEXED:
            self._visit_for_in_indexed(node)
        elif kind == NodeKind.MATCH:
            self._visit_match(node)
        elif kind == NodeKind.RETURN:
            self._visit_return(node)
        elif kind == NodeKind.BREAK:
            self._visit_break(node)
        elif kind == NodeKind.CONTINUE:
            self._visit_continue(node)
        elif kind == NodeKind.FALL:
            raise CodegenError("Zig backend: fallthrough is not implemented", node.span)
        elif kind == NodeKind.DEFER:
            self._visit_defer(node)
        elif kind == NodeKind.DEL:
            self._visit_del(node)
        elif kind == NodeKind.ASSIGNMENT:
            self._visit_assignment(node)
        elif kind == NodeKind.EXPRESSION_STMT:
            self._visit_expression_stmt(node)
        else:
            # Skip unknown node kinds
            pass

    # === Top-level declarations ===

    def _visit_program(self, node: ASTNode) -> None:
        """Visit program root."""
        for decl in (node.declarations or []):
            self.visit(decl)
            self.output.write("\n")

    def _visit_function(self, node: ASTNode) -> None:
        """Visit function declaration."""
        name = node.name or "anonymous"

        # Skip if this function was hoisted (emitted earlier at module level)
        if name in self._skip_nested_fn_names:
            return

        is_main = (name == "main")

        # Analyze function body for mutations, used identifiers, nested functions
        saved_mutated = self._mutated_vars
        saved_used = self._used_identifiers
        hoisted_names = set()
        if node.body:
            self._mutated_vars = self._collect_mutations(node.body)
            self._used_identifiers = self._collect_used_identifiers(node.body)

            # Hoist nested functions to module level
            nested_fns = self._collect_nested_functions(node.body)
            if nested_fns:
                # First emit all nested functions (before adding to skip set)
                for nf in nested_fns:
                    nf_name = nf.name or "anonymous"
                    hoisted_names.add(nf_name)
                    self._visit_function(nf)
                    self.output.write("\n")
                # Then mark them to be skipped during body traversal
                self._skip_nested_fn_names.update(hoisted_names)
        else:
            self._mutated_vars = set()
            self._used_identifiers = set()

        # Function signature
        prefix = "pub " if (is_main or getattr(node, 'is_public', False)) else ""
        self._write_indent()
        self.output.write(f"{prefix}fn {name}(")

        # Parameters — use _ for unused params in Zig
        params = node.parameters or []
        for i, param in enumerate(params):
            if i > 0:
                self.output.write(", ")
            pname = param.name or f"arg{i}"
            ptype = self._emit_type_node(param.param_type) if param.param_type else "anytype"
            # Discard unused parameters with bare _
            if pname not in self._used_identifiers:
                pname = "_"
            self.output.write(f"{pname}: {ptype}")

        self.output.write(") ")

        # Return type
        if node.return_type:
            if self._type_contains_generic(node.return_type):
                # Generic return type → try @TypeOf(matching_param)
                generic_name = None
                if node.return_type.kind == NodeKind.TYPE_GENERIC:
                    generic_name = node.return_type.name
                elif node.return_type.kind == NodeKind.TYPE_POINTER and node.return_type.target_type:
                    if node.return_type.target_type.kind == NodeKind.TYPE_GENERIC:
                        generic_name = node.return_type.target_type.name

                matching_param = None
                if generic_name:
                    for param in params:
                        pt = param.param_type
                        if pt and pt.kind == NodeKind.TYPE_GENERIC and pt.name == generic_name:
                            if param.name in self._used_identifiers:
                                matching_param = param.name
                            break
                        if pt and pt.kind == NodeKind.TYPE_POINTER and pt.target_type:
                            if pt.target_type.kind == NodeKind.TYPE_GENERIC and pt.target_type.name == generic_name:
                                if param.name in self._used_identifiers:
                                    matching_param = param.name
                                break

                if matching_param:
                    self.output.write(f"@TypeOf({matching_param}) ")
                else:
                    # Can't resolve generic return type — use void as fallback
                    self.output.write("void ")
            else:
                ret_type = self._emit_type_node(node.return_type)
                self.output.write(f"{ret_type} ")
        else:
            self.output.write("void ")

        # Body
        was_in_function = self._in_function
        self._in_function = True
        self._push_scope()
        if node.body:
            self._visit_block_inline(node.body)
        else:
            self.output.write("{}\n")
        self._pop_scope()
        self._in_function = was_in_function

        # Clean up hoisted function names
        self._skip_nested_fn_names -= hoisted_names

        # Restore parent analysis context
        self._mutated_vars = saved_mutated
        self._used_identifiers = saved_used

    def _visit_struct(self, node: ASTNode) -> None:
        """Visit struct declaration."""
        name = node.name or "anon"
        self._declared_structs.add(name)

        # Check if struct has generic type fields
        generic_params = set()
        for field in (node.fields or []):
            self._collect_generic_type_names(field.field_type, generic_params)

        self._write_indent()
        if generic_params:
            # Emit as comptime generic function: fn Name(comptime T: type) type { return struct { ... }; }
            param_list = ", ".join(f"comptime {p}: type" for p in sorted(generic_params))
            self.output.write(f"fn {name}({param_list}) type {{\n")
            self.indent()
            self._write_indent()
            self.output.write("return struct {\n")
        else:
            self.output.write(f"const {name} = struct {{\n")
        self.indent()

        for field in (node.fields or []):
            fname = field.name or "unknown"
            ftype = self._emit_type_node_generic(field.field_type) if field.field_type else "anytype"
            self._write_indent()
            self.output.write(f"{fname}: {ftype},\n")

        self.dedent()
        self._write_indent()
        if generic_params:
            self.output.write("};\n")
            self.dedent()
            self._write_indent()
            self.output.write("}\n")
        else:
            self.output.write("};\n")

    def _collect_generic_type_names(self, type_node, result: set):
        """Collect all generic type parameter names from a type expression. Iterative."""
        stack = [type_node]
        while stack:
            n = stack.pop()
            if n is None:
                continue
            if n.kind == NodeKind.TYPE_GENERIC:
                result.add(n.name or "T")
            if n.kind == NodeKind.TYPE_POINTER and n.target_type:
                stack.append(n.target_type)
            if n.kind == NodeKind.TYPE_ARRAY and n.element_type:
                stack.append(n.element_type)
            if n.kind == NodeKind.TYPE_SLICE and n.element_type:
                stack.append(n.element_type)

    def _emit_type_node_generic(self, node: ASTNode) -> str:
        """Emit a type node, preserving generic parameter names (for struct fields)."""
        if node is None:
            return "anytype"
        if node.kind == NodeKind.TYPE_GENERIC:
            return node.name or "anytype"
        # For non-generic types, use the regular emitter
        return self._emit_type_node(node)

    def _visit_enum(self, node: ASTNode) -> None:
        """Visit enum declaration."""
        name = node.name or "anon"
        # Check if any variant has an explicit value — needs enum(i32) tag type
        has_explicit_values = any(
            v.value is not None for v in (node.variants or [])
        )
        self._write_indent()
        if has_explicit_values:
            self.output.write(f"const {name} = enum(i32) {{\n")
        else:
            self.output.write(f"const {name} = enum {{\n")
        self.indent()

        for variant in (node.variants or []):
            vname = variant.name or "unknown"
            self._write_indent()
            if variant.value is not None:
                self.output.write(f"{vname} = {self._emit_expr(variant.value)},\n")
            else:
                self.output.write(f"{vname},\n")

        self.dedent()
        self._write_indent()
        self.output.write("};\n")

    def _visit_union(self, node: ASTNode) -> None:
        """Visit union declaration."""
        name = node.name or "anon"
        is_tagged = getattr(node, 'is_tagged', False)
        self._write_indent()
        if is_tagged:
            self.output.write(f"const {name} = union(enum) {{\n")
        else:
            self.output.write(f"const {name} = union {{\n")
        self.indent()

        for field in (node.fields or []):
            fname = field.name or "unknown"
            ftype = self._emit_type_node(field.field_type) if field.field_type else "void"
            self._write_indent()
            self.output.write(f"{fname}: {ftype},\n")

        self.dedent()
        self._write_indent()
        self.output.write("};\n")

    def _visit_const(self, node: ASTNode) -> None:
        """Visit constant declaration."""
        name = node.name or "unnamed"
        self._write_indent()

        if node.value:
            val = self._emit_expr(node.value)
            self.output.write(f"const {name} = {val};\n")
        else:
            self.output.write(f"const {name} = undefined;\n")

    def _visit_var(self, node: ASTNode) -> None:
        """Visit variable declaration."""
        name = node.name or "unnamed"

        # Handle variable shadowing: prefer preprocessor annotation, fall back to scope analysis
        emit_name = node.emit_name if node.emit_name else name
        if not node.emit_name and self._in_function:
            emit_name = self._declare_var_in_scope(name)

        # Determine var vs const: in Zig, only directly-reassigned vars need 'var'.
        # The preprocessor's is_mutable includes field-access mutations which
        # don't require 'var' in Zig (pointer targets can be modified via const pointer).
        # So we use the backend's own direct-assignment mutation analysis.
        is_mutated = name in self._mutated_vars
        keyword = "var" if is_mutated or not self._in_function else "const"

        self._write_indent()
        explicit_type = getattr(node, 'explicit_type', None)
        # Use preprocessor-inferred type if no explicit type
        resolved = node.resolved_type if node.resolved_type else None

        if node.value:
            val = self._emit_expr(node.value)
            if explicit_type:
                zig_type = self._emit_type_node(explicit_type)
                self.output.write(f"{keyword} {emit_name}: {zig_type} = {val};\n")
            elif resolved:
                zig_type = self._emit_type_node(resolved)
                self.output.write(f"{keyword} {emit_name}: {zig_type} = {val};\n")
            else:
                self.output.write(f"{keyword} {emit_name} = {val};\n")
        elif explicit_type:
            zig_type = self._emit_type_node(explicit_type)
            self.output.write(f"{keyword} {emit_name}: {zig_type} = ")
            self.output.write(self._default_value(explicit_type))
            self.output.write(";\n")
        else:
            self.output.write(f"{keyword} {emit_name} = undefined;\n")

        # Emit discard for unused local variables (Zig requires it)
        is_used = node.is_used if hasattr(node, 'is_used') else (name in self._used_identifiers)
        if self._in_function and not is_used:
            self._write_indent()
            self.output.write(f"_ = {emit_name};\n")

    def _visit_type_alias(self, node: ASTNode) -> None:
        """Visit type alias declaration."""
        name = node.name or "unnamed"
        if node.value:
            val = self._emit_type_node(node.value)
            self._write_indent()
            self.output.write(f"const {name} = {val};\n")
            # Suppress unused local constant warning if inside a function
            if self._in_function and name not in self._used_identifiers:
                self._write_indent()
                self.output.write(f"_ = {name};\n")

    # === Statements ===

    def _visit_block(self, node: ASTNode) -> None:
        """Visit block statement (as a standalone statement)."""
        self._visit_block_inline(node)

    def _visit_block_inline(self, node: ASTNode) -> None:
        """Visit block and output braces + indented contents."""
        self.output.write("{\n")
        self.indent()

        for stmt in (node.statements or []):
            # Skip nested functions that were hoisted to module level
            if stmt.kind == NodeKind.FUNCTION:
                if stmt.hoisted or stmt.name in self._skip_nested_fn_names:
                    continue
            self.visit(stmt)

        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    def _visit_switch_block(self, node: ASTNode) -> None:
        """Visit a block inside a switch prong (needs trailing comma)."""
        self.output.write("{\n")
        self.indent()

        for stmt in (node.statements or []):
            self.visit(stmt)

        self.dedent()
        self._write_indent()
        self.output.write("},\n")

    def _visit_if_stmt(self, node: ASTNode) -> None:
        """Visit if statement."""
        self._write_indent()
        cond = self._emit_expr(node.condition)
        self.output.write(f"if ({cond}) ")

        if node.then_stmt and node.then_stmt.kind == NodeKind.BLOCK:
            self._visit_block_inline(node.then_stmt)
        elif node.then_stmt:
            self.output.write("{\n")
            self.indent()
            self.visit(node.then_stmt)
            self.dedent()
            self._write_indent()
            self.output.write("}\n")

        if node.else_stmt:
            # Remove trailing newline for else
            buf = self.output.getvalue()
            if buf.endswith("}\n"):
                self.output = StringIO()
                self.output.write(buf[:-1])  # Remove the trailing \n
                self.output.write(" else ")
            else:
                self._write_indent()
                self.output.write("else ")

            if node.else_stmt.kind == NodeKind.BLOCK:
                self._visit_block_inline(node.else_stmt)
            elif node.else_stmt.kind == NodeKind.IF_STMT:
                # else if chain - don't wrap in block
                cond2 = self._emit_expr(node.else_stmt.condition)
                self.output.write(f"if ({cond2}) ")
                if node.else_stmt.then_stmt and node.else_stmt.then_stmt.kind == NodeKind.BLOCK:
                    self._visit_block_inline(node.else_stmt.then_stmt)
                if node.else_stmt.else_stmt:
                    buf = self.output.getvalue()
                    if buf.endswith("}\n"):
                        self.output = StringIO()
                        self.output.write(buf[:-1])
                        self.output.write(" else ")
                    self._visit_else_chain(node.else_stmt.else_stmt)
            else:
                self.output.write("{\n")
                self.indent()
                self.visit(node.else_stmt)
                self.dedent()
                self._write_indent()
                self.output.write("}\n")

    def _visit_else_chain(self, node: ASTNode) -> None:
        """Handle else / else if chains. Iterative to avoid stack overflow."""
        current = node
        while current is not None:
            if current.kind == NodeKind.IF_STMT:
                cond = self._emit_expr(current.condition)
                self.output.write(f"if ({cond}) ")
                if current.then_stmt and current.then_stmt.kind == NodeKind.BLOCK:
                    self._visit_block_inline(current.then_stmt)
                if current.else_stmt:
                    buf = self.output.getvalue()
                    if buf.endswith("}\n"):
                        self.output = StringIO()
                        self.output.write(buf[:-1])
                        self.output.write(" else ")
                    current = current.else_stmt
                    continue
                break
            elif current.kind == NodeKind.BLOCK:
                self._visit_block_inline(current)
                break
            else:
                self.output.write("{\n")
                self.indent()
                self.visit(current)
                self.dedent()
                self._write_indent()
                self.output.write("}\n")
                break

    def _visit_while(self, node: ASTNode) -> None:
        """Visit while statement."""
        self._write_indent()
        emitted_label = self._loop_label_name(node.label)
        if emitted_label:
            self.output.write(f"{emitted_label}: ")
        if node.condition:
            cond = self._emit_expr(node.condition)
            self.output.write(f"while ({cond}) ")
        else:
            self.output.write("while (true) ")

        self._loop_label_stack.append((node.label, emitted_label))
        if node.body and node.body.kind == NodeKind.BLOCK:
            self._visit_block_inline(node.body)
        elif node.body:
            self.output.write("{\n")
            self.indent()
            self.visit(node.body)
            self.dedent()
            self._write_indent()
            self.output.write("}\n")
        self._loop_label_stack.pop()

    def _visit_for(self, node: ASTNode) -> None:
        """Visit for statement (C-style or infinite)."""
        self._write_indent()

        # Infinite loop: for { ... }
        if not node.init and not node.condition and not node.update:
            emitted_label = self._loop_label_name(node.label)
            if emitted_label:
                self.output.write(f"{emitted_label}: ")
            self.output.write("while (true) ")
            self._loop_label_stack.append((node.label, emitted_label))
            if node.body and node.body.kind == NodeKind.BLOCK:
                self._visit_block_inline(node.body)
            elif node.body:
                self.output.write("{\n")
                self.indent()
                self.visit(node.body)
                self.dedent()
                self._write_indent()
                self.output.write("}\n")
            self._loop_label_stack.pop()
            return

        # C-style for: for i := 0; i < 10; i += 1 { ... }
        # Zig doesn't have C-style for. Use a block with while + continue expression.
        self.output.write("{\n")
        self.indent()

        # Init statement
        if node.init:
            self.visit(node.init)

        # While with continue expression
        self._write_indent()
        emitted_label = self._loop_label_name(node.label)
        if emitted_label:
            self.output.write(f"{emitted_label}: ")
        if node.condition:
            cond = self._emit_expr(node.condition)
            self.output.write(f"while ({cond})")
        else:
            self.output.write("while (true)")

        # Continue expression (update)
        if node.update:
            update_str = self._emit_statement_as_expr(node.update)
            self.output.write(f" : ({update_str})")

        self.output.write(" ")

        self._loop_label_stack.append((node.label, emitted_label))
        if node.body and node.body.kind == NodeKind.BLOCK:
            self._visit_block_inline(node.body)
        elif node.body:
            self.output.write("{\n")
            self.indent()
            self.visit(node.body)
            self.dedent()
            self._write_indent()
            self.output.write("}\n")
        self._loop_label_stack.pop()

        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    def _visit_for_in(self, node: ASTNode) -> None:
        """Visit for-in loop: for val in arr → for (arr) |val|"""
        self._write_indent()
        iterable = self._emit_expr(node.iterable) if node.iterable else "undefined"
        iter_name = node.iterator or "_"
        emitted_label = self._loop_label_name(node.label)
        if emitted_label:
            self.output.write(f"{emitted_label}: ")
        self.output.write(f"for ({iterable}) |{iter_name}| ")

        self._loop_label_stack.append((node.label, emitted_label))
        if node.body and node.body.kind == NodeKind.BLOCK:
            self._visit_block_inline(node.body)
        elif node.body:
            self.output.write("{\n")
            self.indent()
            self.visit(node.body)
            self.dedent()
            self._write_indent()
            self.output.write("}\n")
        self._loop_label_stack.pop()

    def _visit_for_in_indexed(self, node: ASTNode) -> None:
        """Visit indexed for-in: for i, val in arr → for (arr, 0..) |val, i|"""
        self._write_indent()
        iterable = self._emit_expr(node.iterable) if node.iterable else "undefined"
        iter_name = node.iterator or "_"
        index_name = node.index_var or "_"
        emitted_label = self._loop_label_name(node.label)
        if emitted_label:
            self.output.write(f"{emitted_label}: ")
        # Zig: for (arr, 0..) |val, i|  (note: reversed order from A7)
        self.output.write(f"for ({iterable}, 0..) |{iter_name}, {index_name}| ")

        self._loop_label_stack.append((node.label, emitted_label))
        if node.body and node.body.kind == NodeKind.BLOCK:
            self._visit_block_inline(node.body)
        elif node.body:
            self.output.write("{\n")
            self.indent()
            self.visit(node.body)
            self.dedent()
            self._write_indent()
            self.output.write("}\n")
        self._loop_label_stack.pop()

    def _visit_match(self, node: ASTNode) -> None:
        """Visit match statement → Zig switch."""
        self._write_indent()
        expr = self._emit_expr(node.expression) if node.expression else "undefined"
        self.output.write(f"switch ({expr}) {{\n")
        self.indent()

        for case in (node.cases or []):
            self._write_indent()
            # Emit patterns
            patterns = case.patterns or []
            for i, pattern in enumerate(patterns):
                if i > 0:
                    self.output.write(", ")
                self.output.write(self._emit_pattern(pattern))

            self.output.write(" => ")

            # Case body
            stmt = getattr(case, 'statement', None)
            if stmt:
                if stmt.kind == NodeKind.BLOCK:
                    self._visit_switch_block(stmt)
                else:
                    self.output.write("{\n")
                    self.indent()
                    self.visit(stmt)
                    self.dedent()
                    self._write_indent()
                    self.output.write("},\n")
            else:
                self.output.write("{},\n")

        if node.else_case:
            self._write_indent()
            self.output.write("else => ")
            if isinstance(node.else_case, list) and len(node.else_case) == 1:
                stmt = node.else_case[0]
                if stmt.kind == NodeKind.BLOCK:
                    self._visit_switch_block(stmt)
                else:
                    self.output.write("{\n")
                    self.indent()
                    self.visit(stmt)
                    self.dedent()
                    self._write_indent()
                    self.output.write("},\n")
            elif isinstance(node.else_case, list):
                self.output.write("{\n")
                self.indent()
                for stmt in node.else_case:
                    self.visit(stmt)
                self.dedent()
                self._write_indent()
                self.output.write("},\n")
            else:
                self.output.write("{},\n")

        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    def _visit_return(self, node: ASTNode) -> None:
        """Visit return statement."""
        self._write_indent()
        if node.value:
            val = self._emit_expr(node.value)
            self.output.write(f"return {val};\n")
        else:
            self.output.write("return;\n")

    def _visit_break(self, node: ASTNode) -> None:
        """Visit break statement."""
        self._write_indent()
        target = self._resolve_loop_label(node.label)
        if target:
            self.output.write(f"break :{target};\n")
        else:
            self.output.write("break;\n")

    def _visit_continue(self, node: ASTNode) -> None:
        """Visit continue statement."""
        self._write_indent()
        target = self._resolve_loop_label(node.label)
        if target:
            self.output.write(f"continue :{target};\n")
        else:
            self.output.write("continue;\n")

    def _visit_defer(self, node: ASTNode) -> None:
        """Visit defer statement."""
        self._write_indent()
        self.output.write("defer ")
        if node.statement:
            if node.statement.kind == NodeKind.BLOCK:
                self._visit_block_inline(node.statement)
            else:
                # Single statement defer
                stmt_str = self._emit_statement_inline(node.statement)
                self.output.write(f"{stmt_str};\n")
        elif node.expression:
            expr_str = self._emit_expr(node.expression)
            self.output.write(f"{expr_str};\n")

    def _visit_del(self, node: ASTNode) -> None:
        """Visit del statement → Zig allocator.destroy."""
        self._write_indent()
        expr_node = getattr(node, 'expression', None) or getattr(node, 'expr', None)
        if expr_node:
            expr = self._emit_expr(expr_node)
            self.output.write(f"if ({expr}) |p| allocator.destroy(p);\n")

    def _visit_assignment(self, node: ASTNode) -> None:
        """Visit assignment statement."""
        self._write_indent()
        target = self._emit_expr(node.target) if node.target else "undefined"
        value = self._emit_expr(node.value) if node.value else "undefined"

        op = getattr(node, 'operator', None) or getattr(node, 'op', AssignOp.ASSIGN)
        zig_op = self._assign_op_to_zig(op)

        self.output.write(f"{target} {zig_op} {value};\n")

    def _visit_expression_stmt(self, node: ASTNode) -> None:
        """Visit expression statement."""
        if node.expression:
            # Special-case io.println / io.print calls
            if self._is_io_call(node.expression):
                self._emit_io_call(node.expression)
                return

            self._write_indent()
            expr = self._emit_expr(node.expression)
            self.output.write(f"_ = {expr};\n")

    # === Expression emission (returns string) ===

    def _emit_expr(self, node: ASTNode) -> str:
        """Emit an expression as a Zig string."""
        if node is None:
            return "undefined"

        kind = node.kind

        if kind == NodeKind.LITERAL:
            return self._emit_literal(node)
        elif kind == NodeKind.IDENTIFIER:
            return self._emit_identifier(node)
        elif kind == NodeKind.BINARY:
            return self._emit_binary(node)
        elif kind == NodeKind.UNARY:
            return self._emit_unary(node)
        elif kind == NodeKind.CALL:
            return self._emit_call(node)
        elif kind == NodeKind.INDEX:
            return self._emit_index(node)
        elif kind == NodeKind.SLICE:
            return self._emit_slice(node)
        elif kind == NodeKind.FIELD_ACCESS:
            return self._emit_field_access(node)
        elif kind == NodeKind.ADDRESS_OF:
            return self._emit_address_of(node)
        elif kind == NodeKind.DEREF:
            return self._emit_deref(node)
        elif kind == NodeKind.CAST:
            return self._emit_cast(node)
        elif kind == NodeKind.IF_EXPR:
            return self._emit_if_expr(node)
        elif kind == NodeKind.MATCH_EXPR:
            return self._emit_match_expr(node)
        elif kind == NodeKind.STRUCT_INIT:
            return self._emit_struct_init(node)
        elif kind == NodeKind.ARRAY_INIT:
            return self._emit_array_init(node)
        elif kind == NodeKind.NEW_EXPR:
            return self._emit_new_expr(node)
        elif kind in (NodeKind.TYPE_PRIMITIVE, NodeKind.TYPE_IDENTIFIER,
                      NodeKind.TYPE_ARRAY, NodeKind.TYPE_SLICE,
                      NodeKind.TYPE_POINTER, NodeKind.TYPE_FUNCTION,
                      NodeKind.TYPE_GENERIC):
            return self._emit_type_node(node)
        else:
            raise CodegenError(f"Zig backend: unsupported expression node '{kind.name}'", node.span)

    def _emit_literal(self, node: ASTNode) -> str:
        """Emit a literal value."""
        lk = node.literal_kind
        # Literal value is stored in literal_value, raw text in raw_text
        val = getattr(node, 'literal_value', None)
        raw = getattr(node, 'raw_text', None) or str(val)

        if lk == LiteralKind.INTEGER:
            return str(val)
        elif lk == LiteralKind.FLOAT:
            s = str(val)
            if "." not in s and "e" not in s and "E" not in s:
                s += ".0"
            return s
        elif lk == LiteralKind.STRING:
            if isinstance(val, str):
                return self._quote_zig_string(val)
            return raw if raw else '""'
        elif lk == LiteralKind.CHAR:
            if isinstance(val, str):
                # Escape special characters for Zig char literals
                char_escapes = {
                    '\n': '\\n', '\t': '\\t', '\r': '\\r',
                    '\\': '\\\\', "'": "\\'", '\0': '\\x00',
                }
                escaped = char_escapes.get(val, val)
                return f"'{escaped}'"
            return raw if raw else "'\\x00'"
        elif lk == LiteralKind.BOOLEAN:
            return "true" if val else "false"
        elif lk == LiteralKind.NIL:
            return "null"
        else:
            return str(val) if val is not None else raw

    def _emit_identifier(self, node: ASTNode) -> str:
        """Emit an identifier."""
        # Prefer preprocessor annotation, fall back to scope rename map
        name = node.emit_name if node.emit_name else (node.name or "undefined")
        if not node.emit_name:
            name = self._resolve_name(name)
        # Zig reserved words that might clash
        zig_reserved = {"type", "error", "test", "unreachable", "undefined",
                        "null", "and", "or", "not"}
        if name in zig_reserved:
            return f"@\"{name}\""
        return name

    def _emit_binary(self, node: ASTNode) -> str:
        """Emit a binary expression."""
        left = self._emit_expr(node.left)
        right = self._emit_expr(node.right)
        op = node.operator

        zig_op = self._binary_op_to_zig(op)

        # Special cases
        if op == BinaryOp.AND:
            return f"({left} and {right})"
        elif op == BinaryOp.OR:
            return f"({left} or {right})"
        elif op == BinaryOp.DIV:
            # Use / for floating-point division, @divTrunc for integral division.
            left_ty = self._type_map.get(id(node.left)) if node.left else None
            right_ty = self._type_map.get(id(node.right)) if node.right else None
            left_is_float = bool(left_ty and hasattr(left_ty, "is_floating") and left_ty.is_floating())
            right_is_float = bool(right_ty and hasattr(right_ty, "is_floating") and right_ty.is_floating())
            if left_is_float or right_is_float:
                return f"({left} / {right})"
            return f"@divTrunc({left}, {right})"
        elif op == BinaryOp.MOD:
            return f"@mod({left}, {right})"
        elif op == BinaryOp.BIT_SHL:
            return f"({left} << @intCast({right}))"
        elif op == BinaryOp.BIT_SHR:
            return f"({left} >> @intCast({right}))"
        else:
            return f"({left} {zig_op} {right})"

    def _emit_unary(self, node: ASTNode) -> str:
        """Emit a unary expression."""
        operand = self._emit_expr(node.operand)
        op = node.operator

        if op == UnaryOp.NEG:
            return f"(-{operand})"
        elif op == UnaryOp.NOT:
            return f"(!{operand})"
        elif op == UnaryOp.BIT_NOT:
            return f"(~{operand})"
        else:
            return f"(-{operand})"

    # A7 math functions → Zig builtins
    _MATH_BUILTIN_MAP = {
        'sqrt_f32': '@sqrt', 'sqrt_f64': '@sqrt',
        'abs_f32': '@abs', 'abs_f64': '@abs',
        'floor_f32': '@floor', 'floor_f64': '@floor',
        'ceil_f32': '@ceil', 'ceil_f64': '@ceil',
    }

    def _emit_call(self, node: ASTNode) -> str:
        """Emit a function call."""
        # Special-case io.println / io.print
        if self._is_io_call(node):
            return self._emit_io_call_expr(node)

        func = self._emit_expr(node.function)

        # Map A7 math builtins to Zig builtins
        if func in self._MATH_BUILTIN_MAP:
            func = self._MATH_BUILTIN_MAP[func]
        # Also map math.sqrt etc.
        elif func.startswith('math.'):
            short = func.split('.', 1)[1]
            zig_builtin = f'@{short}'
            if short in ('sqrt', 'abs', 'floor', 'ceil', 'sin', 'cos', 'tan',
                         'log', 'exp', 'min', 'max'):
                func = zig_builtin

        args = ", ".join(self._emit_expr(a) for a in (node.arguments or []))
        return f"{func}({args})"

    def _emit_index(self, node: ASTNode) -> str:
        """Emit array indexing."""
        obj = self._emit_expr(node.object)
        idx = self._emit_expr(node.index)
        return f"{obj}[@intCast({idx})]"

    def _emit_slice(self, node: ASTNode) -> str:
        """Emit slice expression."""
        obj = self._emit_expr(node.object)
        start = self._emit_expr(node.start) if node.start else "0"
        end = self._emit_expr(node.end) if node.end else ""
        return f"{obj}[{start}..{end}]"

    def _emit_field_access(self, node: ASTNode) -> str:
        """Emit field access."""
        obj = self._emit_expr(node.object)
        field = node.field or "unknown"
        return f"{obj}.{field}"

    def _emit_address_of(self, node: ASTNode) -> str:
        """Emit address-of (.adr → &)."""
        operand = self._emit_expr(node.operand)
        return f"&{operand}"

    def _emit_deref(self, node: ASTNode) -> str:
        """Emit dereference (.val → .?.*)."""
        pointer = self._emit_expr(node.pointer)
        return f"{pointer}.?.*"

    def _emit_cast(self, node: ASTNode) -> str:
        """Emit cast expression."""
        target_type = self._emit_type_node(node.target_type) if node.target_type else "anytype"
        expr = self._emit_expr(node.expression)
        # Use appropriate Zig cast builtin
        return f"@as({target_type}, {expr})"

    def _emit_if_expr(self, node: ASTNode) -> str:
        """Emit if expression."""
        cond = self._emit_expr(node.condition)
        then_val = self._emit_expr(node.then_expr)
        else_val = self._emit_expr(node.else_expr) if node.else_expr else "undefined"
        return f"if ({cond}) {then_val} else {else_val}"

    def _emit_match_expr(self, node: ASTNode) -> str:
        """Emit match expression → Zig switch expression."""
        expr = self._emit_expr(node.expression) if node.expression else "undefined"
        parts = [f"switch ({expr}) {{"]

        for case in (node.cases or []):
            patterns = case.patterns or []
            pattern_str = ", ".join(self._emit_pattern(p) for p in patterns)
            case_expr = getattr(case, 'expression', None)
            val = self._emit_expr(case_expr) if case_expr else "undefined"
            parts.append(f" {pattern_str} => {val},")

        if node.else_case:
            if isinstance(node.else_case, ASTNode):
                val = self._emit_expr(node.else_case)
            else:
                val = "undefined"
            parts.append(f" else => {val},")

        parts.append(" }")
        return "".join(parts)

    def _emit_struct_init(self, node: ASTNode) -> str:
        """Emit struct initialization."""
        struct_name = node.struct_type or ""
        field_inits = node.field_inits or []

        if struct_name and struct_name != "__inline__":
            parts = [f"{struct_name}{{ "]
        else:
            parts = [".{ "]

        for i, fi in enumerate(field_inits):
            if i > 0:
                parts.append(", ")
            val = self._emit_expr(fi.value) if fi.value else "undefined"
            if fi.name:
                parts.append(f".{fi.name} = {val}")
            else:
                parts.append(val)

        parts.append(" }")
        return "".join(parts)

    def _emit_array_init(self, node: ASTNode) -> str:
        """Emit array initialization."""
        elements = node.elements or []
        elems = ", ".join(self._emit_expr(e) for e in elements)
        return f".{{ {elems} }}"

    def _emit_new_expr(self, node: ASTNode) -> str:
        """Emit new expression → allocator.create."""
        type_node = getattr(node, 'target_type', None)
        if type_node:
            zig_type = self._emit_type_node(type_node)
            # Check if it's an array type
            if type_node.kind == NodeKind.TYPE_ARRAY:
                elem_type = self._emit_type_node(type_node.element_type) if type_node.element_type else "u8"
                size = self._emit_expr(type_node.size) if type_node.size else "0"
                return f"allocator.alloc({elem_type}, {size}) catch null"
            return f"allocator.create({zig_type}) catch null"
        return "allocator.create(u8) catch null"

    def _emit_pattern(self, node: ASTNode) -> str:
        """Emit a match pattern."""
        if node is None:
            return "_"

        kind = node.kind
        if kind == NodeKind.PATTERN_LITERAL:
            return self._emit_expr(node.literal) if node.literal else "0"
        elif kind == NodeKind.PATTERN_IDENTIFIER:
            return node.name or "_"
        elif kind == NodeKind.PATTERN_ENUM:
            return f".{node.variant}" if node.variant else "_"
        elif kind == NodeKind.PATTERN_RANGE:
            start = self._emit_pattern(node.start)
            end = self._emit_pattern(node.end)
            return f"{start}...{end}"
        elif kind == NodeKind.PATTERN_WILDCARD:
            return "_"
        else:
            return self._emit_expr(node)

    # === Type emission ===

    def _type_contains_generic(self, node: ASTNode) -> bool:
        """Check if a type expression contains any generic type parameters. Iterative."""
        stack = [node]
        while stack:
            n = stack.pop()
            if n is None:
                continue
            if n.kind == NodeKind.TYPE_GENERIC:
                return True
            if n.kind == NodeKind.TYPE_POINTER:
                stack.append(n.target_type)
            elif n.kind in (NodeKind.TYPE_ARRAY, NodeKind.TYPE_SLICE):
                stack.append(n.element_type)
            elif n.kind == NodeKind.TYPE_FUNCTION:
                for pt in (n.parameter_types or []):
                    stack.append(pt)
                stack.append(n.return_type)
        return False

    def _emit_type_node(self, node: ASTNode) -> str:
        """Emit a type as a Zig type string. Iterative for linear chains."""
        if node is None:
            return "anytype"

        if self._type_contains_generic(node):
            return "anytype"

        # Build prefix iteratively for linear chains: ref ref [N][M]... base
        prefix_parts = []
        current = node
        while current is not None:
            kind = current.kind

            if kind == NodeKind.TYPE_POINTER:
                if current.target_type and current.target_type.kind == NodeKind.TYPE_GENERIC:
                    return "anytype"
                prefix_parts.append("?*")
                current = current.target_type
            elif kind == NodeKind.TYPE_ARRAY:
                size = self._emit_expr(current.size) if current.size else "0"
                prefix_parts.append(f"[{size}]")
                current = current.element_type
            elif kind == NodeKind.TYPE_SLICE:
                prefix_parts.append("[]")
                current = current.element_type
            else:
                # Base type — emit and prepend all prefixes
                base = self._emit_type_leaf(current)
                return "".join(prefix_parts) + base

        return "".join(prefix_parts) + "anytype"

    def _emit_type_leaf(self, node: ASTNode) -> str:
        """Emit a non-chain (leaf) type node."""
        if node is None:
            return "anytype"

        kind = node.kind
        if kind == NodeKind.TYPE_PRIMITIVE:
            return self._map_primitive_type(node.type_name or "i32")
        elif kind == NodeKind.TYPE_IDENTIFIER:
            return node.name or "anytype"
        elif kind == NodeKind.TYPE_GENERIC:
            return "anytype"
        elif kind == NodeKind.TYPE_FUNCTION:
            params = ", ".join(self._emit_type_node(p) for p in (node.parameter_types or []))
            ret = self._emit_type_node(node.return_type) if node.return_type else "void"
            return f"*const fn ({params}) {ret}"
        elif kind == NodeKind.TYPE_STRUCT:
            fields = node.fields or []
            parts = ["struct { "]
            for f in fields:
                fname = f.name or "unknown"
                ftype = self._emit_type_node(f.field_type) if f.field_type else "anytype"
                parts.append(f"{fname}: {ftype}, ")
            parts.append("}")
            return "".join(parts)
        else:
            return "anytype"

    def _map_primitive_type(self, type_name: str) -> str:
        """Map an A7 primitive type to Zig."""
        mapping = {
            "i8": "i8", "i16": "i16", "i32": "i32", "i64": "i64",
            "u8": "u8", "u16": "u16", "u32": "u32", "u64": "u64",
            "isize": "isize", "usize": "usize",
            "f32": "f32", "f64": "f64",
            "bool": "bool",
            "char": "u8",
            "string": "[]const u8",
        }
        return mapping.get(type_name, type_name)

    def _default_value(self, type_node: ASTNode) -> str:
        """Generate a default value for a type."""
        if type_node is None:
            return "undefined"

        kind = type_node.kind
        if kind == NodeKind.TYPE_PRIMITIVE:
            name = type_node.type_name or ""
            if name in ("i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64", "isize", "usize"):
                return "0"
            elif name in ("f32", "f64"):
                return "0.0"
            elif name == "bool":
                return "false"
            elif name == "string":
                return '""'
            elif name == "char":
                return "0"
        elif kind == NodeKind.TYPE_ARRAY:
            elem = self._emit_type_node(type_node.element_type)
            size = self._emit_expr(type_node.size) if type_node.size else "0"
            inner_default = self._default_value_for_elem(type_node.element_type)
            return f"[_]{elem}{{{inner_default}}} ** {size}"
        elif kind == NodeKind.TYPE_POINTER:
            return "null"

        return "undefined"

    def _default_value_for_elem(self, type_node: ASTNode) -> str:
        """Default value used in array initialization."""
        if type_node and type_node.kind == NodeKind.TYPE_PRIMITIVE:
            name = type_node.type_name or ""
            if name in ("f32", "f64"):
                return "0.0"
            elif name == "bool":
                return "false"
        return "0"

    # === I/O special-casing ===

    def _is_io_call(self, node: ASTNode) -> bool:
        """Check if this is an io.println or io.print call."""
        if node.kind != NodeKind.CALL:
            return False
        func = node.function
        if func and func.kind == NodeKind.FIELD_ACCESS:
            obj = getattr(func, 'object', None)
            if obj and obj.kind == NodeKind.IDENTIFIER and getattr(obj, 'name', '') == 'io':
                field = getattr(func, 'field', '')
                return field in ('println', 'print')
        return False

    def _emit_io_call(self, node: ASTNode) -> None:
        """Emit an io.println/io.print call as a statement."""
        func = node.function
        field = getattr(func, 'field', 'println')
        args = node.arguments or []

        self._write_indent()

        if not args:
            if field == "println":
                self.output.write('std.debug.print("\\n", .{});\n')
            else:
                self.output.write('std.debug.print("", .{});\n')
            return

        # First arg is the format string
        fmt_arg = args[0]
        rest_args = args[1:]

        fmt_str = self._emit_expr(fmt_arg)
        # Convert A7 {} format to Zig with type-aware placeholders.
        fmt_str = self._convert_format_string(fmt_str, rest_args)

        if field == "println":
            # Add newline
            if fmt_str.endswith('"'):
                fmt_str = fmt_str[:-1] + '\\n"'

        if rest_args:
            zig_args = ", ".join(self._emit_expr(a) for a in rest_args)
            self.output.write(f"std.debug.print({fmt_str}, .{{{zig_args}}});\n")
        else:
            self.output.write(f"std.debug.print({fmt_str}, .{{}});\n")

    def _emit_io_call_expr(self, node: ASTNode) -> str:
        """Emit io call as an expression (returns void)."""
        # This shouldn't normally be used as an expression but handle it
        func = node.function
        field = getattr(func, 'field', 'println')
        args = node.arguments or []

        if not args:
            return 'std.debug.print("\\n", .{})'

        fmt_arg = args[0]
        rest_args = args[1:]
        fmt_str = self._emit_expr(fmt_arg)
        fmt_str = self._convert_format_string(fmt_str, rest_args)

        if field == "println" and fmt_str.endswith('"'):
            fmt_str = fmt_str[:-1] + '\\n"'

        if rest_args:
            zig_args = ", ".join(self._emit_expr(a) for a in rest_args)
            return f'std.debug.print({fmt_str}, .{{{zig_args}}})'
        return f'std.debug.print({fmt_str}, .{{}})'

    def _format_spec_for_arg(self, arg: ASTNode) -> str:
        """Pick a Zig print formatter for an argument node."""
        ty = self._type_map.get(id(arg)) if arg else None
        if ty is not None:
            name = getattr(ty, 'name', None)
            if name == "string":
                return "s"
            if name == "char":
                return "c"
        if arg and arg.kind == NodeKind.LITERAL:
            if arg.literal_kind == LiteralKind.STRING:
                return "s"
            if arg.literal_kind == LiteralKind.CHAR:
                return "c"
        return "any"

    def _convert_format_string(self, fmt_str: str, args: Optional[list[ASTNode]] = None) -> str:
        """Convert A7 format string {} to Zig placeholders."""
        # Replace {} placeholders but keep explicit Zig-like placeholders untouched.
        placeholder_idx = 0
        result = []
        i = 0
        s = fmt_str
        while i < len(s):
            if s[i] == '{' and i + 1 < len(s) and s[i + 1] == '}':
                if args and placeholder_idx < len(args):
                    spec = self._format_spec_for_arg(args[placeholder_idx])
                else:
                    spec = "any"
                result.append('{' + spec + '}')
                placeholder_idx += 1
                i += 2
            else:
                result.append(s[i])
                i += 1
        return "".join(result)

    def _quote_zig_string(self, text: str) -> str:
        out: list[str] = ['"']
        for ch in text:
            if ch == "\\":
                out.append("\\\\")
            elif ch == '"':
                out.append('\\"')
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\t":
                out.append("\\t")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\0":
                out.append("\\x00")
            else:
                out.append(ch)
        out.append('"')
        return "".join(out)

    def _loop_label_name(self, label: Optional[str]) -> Optional[str]:
        if not label:
            return None
        safe = label.replace("$", "_").replace(".", "_").replace("-", "_")
        return f"a7_loop_{safe}"

    def _resolve_loop_label(self, label: Optional[str]) -> Optional[str]:
        if label is None:
            return None
        for original, emitted in reversed(self._loop_label_stack):
            if original == label:
                return emitted
        return None

    # === Helper methods ===

    def _binary_op_to_zig(self, op: BinaryOp) -> str:
        """Convert A7 binary operator to Zig."""
        mapping = {
            BinaryOp.ADD: "+",
            BinaryOp.SUB: "-",
            BinaryOp.MUL: "*",
            BinaryOp.DIV: "/",
            BinaryOp.MOD: "%",
            BinaryOp.EQ: "==",
            BinaryOp.NE: "!=",
            BinaryOp.LT: "<",
            BinaryOp.LE: "<=",
            BinaryOp.GT: ">",
            BinaryOp.GE: ">=",
            BinaryOp.AND: "and",
            BinaryOp.OR: "or",
            BinaryOp.BIT_AND: "&",
            BinaryOp.BIT_OR: "|",
            BinaryOp.BIT_XOR: "^",
            BinaryOp.BIT_SHL: "<<",
            BinaryOp.BIT_SHR: ">>",
        }
        return mapping.get(op, "??")

    def _assign_op_to_zig(self, op: AssignOp) -> str:
        """Convert A7 assignment operator to Zig."""
        mapping = {
            AssignOp.ASSIGN: "=",
            AssignOp.ADD_ASSIGN: "+=",
            AssignOp.SUB_ASSIGN: "-=",
            AssignOp.MUL_ASSIGN: "*=",
            AssignOp.DIV_ASSIGN: "/=",
            AssignOp.MOD_ASSIGN: "%=",
            AssignOp.AND_ASSIGN: "&=",
            AssignOp.OR_ASSIGN: "|=",
            AssignOp.XOR_ASSIGN: "^=",
            AssignOp.SHL_ASSIGN: "<<=",
            AssignOp.SHR_ASSIGN: ">>=",
        }
        return mapping.get(op, "=")

    def _emit_statement_as_expr(self, node: ASTNode) -> str:
        """Emit a statement as an expression string (for while continue expressions)."""
        if node.kind == NodeKind.ASSIGNMENT:
            target = self._emit_expr(node.target) if node.target else "_"
            value = self._emit_expr(node.value) if node.value else "0"
            op = getattr(node, 'operator', None) or getattr(node, 'op', AssignOp.ASSIGN)
            zig_op = self._assign_op_to_zig(op)
            return f"{target} {zig_op} {value}"
        elif node.kind == NodeKind.EXPRESSION_STMT and node.expression:
            return self._emit_expr(node.expression)
        return "void"

    def _emit_statement_inline(self, node: ASTNode) -> str:
        """Emit a single statement as an inline string (no newline)."""
        if node.kind == NodeKind.EXPRESSION_STMT and node.expression:
            if self._is_io_call(node.expression):
                return self._emit_io_call_expr(node.expression)
            return self._emit_expr(node.expression)
        elif node.kind == NodeKind.CALL:
            return self._emit_expr(node)
        elif node.kind == NodeKind.DEL:
            expr = node.expression or node.expr
            if expr:
                e = self._emit_expr(expr)
                return f"if ({e}) |p| allocator.destroy(p)"
        return "void"

    def _write_indent(self) -> None:
        """Write current indentation to output."""
        self.output.write("    " * self.indent_level)
