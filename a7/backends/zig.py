"""
Zig code generation backend for the A7 compiler.

Translates A7 AST nodes to valid Zig source code.
"""

import math
import re
import struct
from io import StringIO
from typing import Optional, Dict, Set

from ..ast_nodes import ASTNode, NodeKind, LiteralKind, BinaryOp, UnaryOp, AssignOp
from ..cast_classifier import CastClass
from ..errors import CodegenError
from ..safety import BackendPlan
from ..types import ArrayType, PointerType, PrimitiveType, ReferenceType
from .base import CodeGenerator


class ZigCodeGenerator(CodeGenerator):
    """Generates Zig source code from A7 AST."""

    def __init__(self):
        super().__init__()
        self._needs_allocator = False
        self._needs_std = False
        self._type_map: Dict = {}
        self._symbol_table = None
        self._backend_plan: Optional[BackendPlan] = None
        self._profile = "debug"
        self._force_wrapping = False
        self._declared_structs: Set[str] = set()
        # Mutation analysis: variables that are targets of assignments
        self._mutated_vars: Set[str] = set()
        self._mutated_declarations: Set[int] = set()
        # Used identifiers in current scope (for unused var/param detection)
        self._used_identifiers: Set[str] = set()
        # Nested function hoisting
        self._hoisted_functions: list = []
        self._skip_nested_fn_names: Set[str] = set()
        # Variable shadowing prevention
        self._scope_stack: list = []  # List[Set[str]] - variable names per scope
        self._rename_map: Dict[str, str] = {}  # original -> renamed
        self._rename_snapshots: list[dict[str, str]] = []
        self._identifier_uses: Dict[str, int] = {}
        self._pending_discards: list[list[tuple[str, str, int]]] = []
        self._discard_replacements: dict[str, str] = {}
        self._targeted_loops: Set[int] = set()
        self._emitted_loop_labels: Set[str] = set()
        # Track if we're inside a function body
        self._in_function = False
        self._loop_label_stack: list[tuple[Optional[str], Optional[str]]] = []
        self._fall_context_stack: list[tuple[str, str]] = []
        self._name_counter = 0
        self._io_streams_needed: Set[str] = set()
        self._global_names: Set[str] = set()

    @property
    def file_extension(self) -> str:
        return ".zig"

    @property
    def language_name(self) -> str:
        return "Zig"

    def generate(self, ast: ASTNode, type_map: Optional[Dict] = None,
                 symbol_table=None, backend_plan: Optional[BackendPlan] = None,
                 profile: str = "debug", no_nonwrap: bool = False) -> str:
        """Generate Zig source code from an A7 AST."""
        self.reset()
        self._needs_allocator = False
        self._needs_std = False
        self._type_map = type_map or {}
        self._symbol_table = symbol_table
        self._backend_plan = backend_plan
        self._profile = profile if profile in ("debug", "release") else "debug"
        self._force_wrapping = bool(no_nonwrap)
        self._declared_structs = set()
        self._mutated_vars = set()
        self._used_identifiers = set()
        self._hoisted_functions = []
        self._skip_nested_fn_names = set()
        self._scope_stack = []
        self._rename_map = {}
        self._rename_snapshots = []
        self._identifier_uses = {}
        self._pending_discards = []
        self._discard_replacements = {}
        self._targeted_loops = self._collect_targeted_loops(ast)
        self._emitted_loop_labels = set()
        self._in_function = False
        self._loop_label_stack = []
        self._fall_context_stack = []
        self._name_counter = 0
        self._io_streams_needed = set()
        self._global_names = {d.name for d in (ast.declarations or []) if d.name}

        # First pass: scan for features that need preamble items
        self._scan_features(ast)

        # Generate the preamble
        preamble = self._emit_preamble()

        # Second pass: generate code
        self.visit(ast)

        code = re.sub(r"\x00discard_\d+\x00",
                      lambda match: self._discard_replacements[match.group()],
                      self.output.getvalue())
        return self._normalize_output(preamble + code)

    def _normalize_output(self, code: str) -> str:
        """Keep generated Zig stable against zig fmt's basic whitespace rules."""
        lines = [line.rstrip() for line in code.splitlines()]
        normalized: list[str] = []
        previous_blank = False
        for line in lines:
            blank = line == ""
            if blank and previous_blank:
                continue
            normalized.append(line)
            previous_blank = blank
        while normalized and normalized[-1] == "":
            normalized.pop()
        return "\n".join(normalized) + ("\n" if normalized else "")

    def _has_top_level_comma(self, text: str) -> bool:
        """Return True when an argument list has more than one top-level item."""
        depth = 0
        quote: Optional[str] = None
        escaped = False
        for ch in text:
            if quote:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == quote:
                    quote = None
                continue
            if ch in {"'", '"'}:
                quote = ch
            elif ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth = max(0, depth - 1)
            elif ch == "," and depth == 0:
                return True
        return False

    def _scan_features(self, root: ASTNode) -> None:
        """Scan the AST to determine what preamble items are needed. Iterative."""
        if root is None:
            return

        def visitor(node):
            if node.kind == NodeKind.NEW_EXPR or node.kind == NodeKind.DEL:
                self._needs_allocator = True
                self._needs_std = True

            # Infinity and NaN are emitted as std.math.inf / std.math.nan,
            # so a program that has one but no io call still needs the import.
            if self._is_nonfinite_float_literal(node):
                self._needs_std = True

            if node.kind == NodeKind.CALL:
                # Check for stdlib io print calls.
                canonical = getattr(node, "stdlib_canonical", None)
                if canonical in {"std.io.println", "std.io.print", "std.io.eprintln"}:
                    self._needs_std = True
                    field = canonical.split(".")[-1]
                    self._io_streams_needed.add("stderr" if field == "eprintln" else "stdout")

        self._walk_ast(root, visitor)

    def _emit_preamble(self) -> str:
        """Generate the Zig preamble (imports, allocator, etc.)."""
        lines = []
        if self._needs_std:
            lines.append("const std = @import(\"std\");")
        if self._needs_allocator:
            if self._profile == "release":
                lines.append("const allocator = std.heap.smp_allocator;")
            else:
                lines.append("const allocator = std.heap.page_allocator;")
        if self._io_streams_needed:
            lines.append("var __a7_io: ?std.Io = null;")
        if "stdout" in self._io_streams_needed:
            lines.append("var __a7_stdout_buf: [4096]u8 = undefined;")
            lines.append("var __a7_stdout_writer: ?std.Io.File.Writer = null;")
            lines.append("fn __a7_stdout_flush() void {")
            lines.append('    __a7_stdout_writer.?.interface.flush() catch @panic("a7 stdout flush failed");')
            lines.append("}")
            lines.append("fn __a7_stdout_print(comptime fmt: []const u8, args: anytype) void {")
            lines.append('    __a7_stdout_writer.?.interface.print(fmt, args) catch @panic("a7 stdout write failed");')
            lines.append("}")
        if "stderr" in self._io_streams_needed:
            lines.append("fn __a7_stderr_print(comptime fmt: []const u8, args: anytype) void {")
            if "stdout" in self._io_streams_needed:
                lines.append("    __a7_stdout_flush();")
            lines.append("    var __a7_stream_buf: [1024]u8 = undefined;")
            lines.append("    var __a7_writer = std.Io.File.stderr().writerStreaming(__a7_io.?, &__a7_stream_buf);")
            lines.append('    __a7_writer.interface.print(fmt, args) catch @panic("a7 stderr write failed");')
            lines.append('    __a7_writer.interface.flush() catch @panic("a7 stderr flush failed");')
            lines.append("}")
        if self._io_streams_needed:
            lines.append("pub fn main(init: std.process.Init) void {")
            lines.append("    __a7_io = init.io;")
            if "stdout" in self._io_streams_needed:
                # writerStreaming, not writer: Zig 0.16.0 File.writer starts
                # in positional mode at offset 0, so each fresh writer
                # overwrote earlier output when the stream is a regular file.
                lines.append("    __a7_stdout_writer = std.Io.File.stdout().writerStreaming(__a7_io.?, &__a7_stdout_buf);")
            lines.append("    __a7_user_main();")
            if "stdout" in self._io_streams_needed:
                lines.append("    __a7_stdout_flush();")
            lines.append("}")
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
        'target_type', 'element_type', 'size', 'parameter_types', 'type_args',
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
            """Resolve base identifier for assignment targets like a, a[i], or a.b."""
            while target is not None:
                if target.kind == NodeKind.IDENTIFIER:
                    return target.name
                if target.kind in (NodeKind.FIELD_ACCESS, NodeKind.INDEX):
                    target = getattr(target, 'object', None)
                    continue
                # A dereference mutates the pointee, not the pointer binding.
                return None
            return None

        def visitor(n):
            if n.kind == NodeKind.ASSIGNMENT:
                target = n.target
                base = base_identifier(target)
                if base:
                    mutations.add(base)
            elif n.kind == NodeKind.ADDRESS_OF:
                base = base_identifier(n.operand)
                if base:
                    mutations.add(base)
            elif n.kind == NodeKind.CALL:
                implicit_ref_args = set(getattr(n, "implicit_ref_args", set()) or set())
                for index, arg in enumerate(n.arguments or []):
                    if index in implicit_ref_args:
                        base = base_identifier(arg)
                        if base:
                            mutations.add(base)
            # Compound assignment operators also count as mutations
            # (they're also ASSIGNMENT nodes with non-ASSIGN op)

        self._walk_ast(node, visitor)
        return mutations

    def _collect_mutated_declarations(self, root: ASTNode) -> Set[int]:
        """Resolve writes to lexical bindings, including loop initializer scopes."""
        scopes: list[dict[str, ASTNode]] = [{}]
        mutated: Set[int] = set()
        stack = [("visit", root)]
        while stack:
            event, node = stack.pop()
            if event == "exit":
                scopes.pop()
                continue
            if event == "bind":
                scopes[-1][node.name] = node
                continue
            if node.kind == NodeKind.FUNCTION:
                continue
            if node.kind in {NodeKind.VAR, NodeKind.CONST}:
                if node.name:
                    stack.append(("bind", node))
                if node.value:
                    stack.append(("visit", node.value))
                continue
            targets = []
            if node.kind == NodeKind.ASSIGNMENT:
                targets.append(node.target)
            elif node.kind == NodeKind.ADDRESS_OF:
                targets.append(node.operand)
            elif node.kind == NodeKind.SLICE and isinstance(self._type_map.get(id(node.object)), ArrayType):
                # A7 slices are mutable views. Borrowing an array for a slice
                # requires mutable backing storage even without a local write.
                targets.append(node.object)
            elif node.kind == NodeKind.CALL:
                targets.extend(arg for i, arg in enumerate(node.arguments or []) if i in (getattr(node, "implicit_ref_args", set()) or set()))
            for target in targets:
                while target is not None and target.kind in {NodeKind.FIELD_ACCESS, NodeKind.INDEX}:
                    target = target.object
                if target is not None and target.kind == NodeKind.IDENTIFIER:
                    for scope in reversed(scopes):
                        if target.name in scope:
                            mutated.add(id(scope[target.name]))
                            break
            if node.kind in {NodeKind.BLOCK, NodeKind.FOR, NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED}:
                scopes.append({})
                stack.append(("exit", node))
            if node.kind in {NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED}:
                for name in (node.iterator, node.index_var):
                    if name:
                        scopes[-1][name] = node
            if node.kind == NodeKind.FOR:
                children = [n for n in (node.init, node.condition, node.body, node.update) if n is not None]
            else:
                children = []
                for attr in self._AST_CHILD_ATTRS:
                    value = getattr(node, attr, None)
                    if isinstance(value, ASTNode):
                        children.append(value)
                    elif isinstance(value, list):
                        children.extend(n for n in value if isinstance(n, ASTNode))
            stack.extend(("visit", child) for child in reversed(children))
        return mutated

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
        """Save bindings so nested shadowing cannot erase an outer rename."""
        self._scope_stack.append(set())
        self._pending_discards.append([])
        self._rename_snapshots.append(self._rename_map.copy())

    def _pop_scope(self):
        if self._scope_stack:
            for marker, name, before in self._pending_discards.pop():
                used = self._identifier_uses.get(name, 0) != before
                self._discard_replacements[marker] = "" if used else f"_ = {self._quote_identifier(name)};"
            self._scope_stack.pop()
            self._rename_map = self._rename_snapshots.pop()

    def _pending_discard(self, name: str) -> str:
        """Reserve a discard at the declaration, resolved before its scope is lost.

        Each marker belongs to one declaration. Counts start after its initializer
        and finish before a sibling can reuse the emitted name.
        """
        marker = f"\x00discard_{len(self._discard_replacements)}\x00"
        self._discard_replacements[marker] = ""
        self._pending_discards[-1].append((marker, name, self._identifier_uses.get(name, 0)))
        return marker

    def _use_name(self, name: str) -> str:
        emitted = self._resolve_name(name)
        self._identifier_uses[emitted] = self._identifier_uses.get(emitted, 0) + 1
        return self._quote_identifier(emitted)

    def _declare_var_in_scope(self, name: str, preferred: Optional[str] = None) -> str:
        """Assign a Zig name without colliding with an active outer binding."""
        emitted = preferred or name
        active = set(self._rename_map.values()) | self._global_names
        for bindings in self._rename_snapshots:
            active.update(bindings.values())
        if emitted in active:
            suffix = 1
            while f"{name}_{suffix}" in active or f"{name}_{suffix}" in self._used_identifiers:
                suffix += 1
            emitted = f"{name}_{suffix}"
        if self._scope_stack:
            self._scope_stack[-1].add(name)
        self._rename_map[name] = emitted
        return emitted

    @staticmethod
    def _quote_identifier(name: str) -> str:
        # A7 permits bindings whose spelling is reserved in Zig.
        reserved = {
            "addrspace", "align", "allowzero", "and", "anyframe", "anytype",
            "asm", "async", "await", "break", "callconv", "catch", "comptime",
            "const", "continue", "defer", "else", "enum", "errdefer", "error",
            "export", "extern", "fn", "for", "if", "inline", "linksection",
            "noalias", "noinline", "nosuspend", "opaque", "or", "orelse",
            "packed", "pub", "resume", "return", "section", "struct",
            "suspend", "switch", "test", "threadlocal", "try", "union",
            "unreachable", "usingnamespace", "var", "volatile", "while",
            "type", "undefined", "null", "not",
        }
        return f'@"{name}"' if name in reserved else name

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
            self._visit_fall(node)
        elif kind == NodeKind.DEFER:
            self._visit_defer(node)
        elif kind == NodeKind.DEL:
            self._visit_del(node)
        elif kind == NodeKind.ASSIGNMENT:
            self._visit_assignment(node)
        elif kind == NodeKind.EXPRESSION_STMT:
            self._visit_expression_stmt(node)
        else:
            raise CodegenError(
                f"Zig backend: unhandled node kind '{kind.name}'",
                getattr(node, "span", None),
            )

    # === Top-level declarations ===

    def _visit_program(self, node: ASTNode) -> None:
        """Visit program root."""
        for decl in (node.declarations or []):
            self.visit(decl)
            self.output.write("\n")

    def _visit_function(self, node: ASTNode) -> None:
        """Visit function declaration."""
        name = node.name or "anonymous"
        emit_prefix = getattr(node, "module_emit_prefix", "")

        # Skip if this function was hoisted (emitted earlier at module level)
        if name in self._skip_nested_fn_names:
            return

        is_main = (name == "main" and not emit_prefix)
        emitted_name = "__a7_user_main" if (is_main and self._io_streams_needed) else f"{emit_prefix}{name}"

        # Analyze function body for mutations, used identifiers, nested functions
        saved_mutated = self._mutated_vars
        saved_mutated_declarations = self._mutated_declarations
        saved_used = self._used_identifiers
        hoisted_names = set()
        if node.body:
            self._mutated_vars = self._collect_mutations(node.body)
            self._mutated_declarations = self._collect_mutated_declarations(node.body)
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
        prefix = "pub " if ((is_main and not self._io_streams_needed) or getattr(node, 'is_public', False)) else ""
        self._write_indent()
        self.output.write(f"{prefix}fn {self._quote_identifier(emitted_name)}(")
        self._push_scope()
        parameter_names = {p.name: self._declare_var_in_scope(p.name) for p in (node.parameters or []) if p.name}

        generic_params = [param.name for param in (node.generic_params or []) if param.name]
        for i, generic_name in enumerate(generic_params):
            if i > 0:
                self.output.write(", ")
            self.output.write(f"comptime {self._quote_identifier(generic_name)}: type")
        if generic_params and (node.parameters or []):
            self.output.write(", ")

        # Parameters — use _ for unused params in Zig
        params = node.parameters or []
        for i, param in enumerate(params):
            if i > 0:
                self.output.write(", ")
            pname = param.name or f"arg{i}"
            ptype = self._emit_type_node(param.param_type, generic_env=set(generic_params)) if param.param_type else "anytype"
            # Discard unused parameters with bare _
            if pname not in self._used_identifiers:
                pname = "_"
            self.output.write(f"{self._quote_identifier(parameter_names.get(pname, pname))}: {ptype}")

        self.output.write(") ")

        # Return type
        if node.return_type:
            if generic_params:
                ret_type = self._emit_type_node(node.return_type, generic_env=set(generic_params))
                self.output.write(f"{ret_type} ")
            elif self._type_contains_generic(node.return_type):
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
                    self.output.write(f"@TypeOf({self._quote_identifier(parameter_names.get(matching_param, matching_param))}) ")
                else:
                    raise CodegenError(
                        "Zig backend: cannot resolve generic return type and no parameter carries it",
                        node.span,
                    )
            else:
                ret_type = self._emit_type_node(node.return_type)
                self.output.write(f"{ret_type} ")
        else:
            self.output.write("void ")

        # Body
        was_in_function = self._in_function
        self._in_function = True
        if node.body and not (node.body.statements or []):
            self.output.write("{}\n")
        elif node.body:
            self._visit_block_inline(node.body, prelude_lines=[])
        else:
            self.output.write("{}\n")
        self._pop_scope()
        self._in_function = was_in_function

        # Clean up hoisted function names
        self._skip_nested_fn_names -= hoisted_names

        # Restore parent analysis context
        self._mutated_vars = saved_mutated
        self._mutated_declarations = saved_mutated_declarations
        self._used_identifiers = saved_used

    def _visit_struct(self, node: ASTNode) -> None:
        """Visit struct declaration."""
        name = node.name or "anon"
        self._declared_structs.add(name)

        # Check if struct has generic type fields. Keep encounter order because
        # Zig type-function arguments must match A7's instance argument order.
        generic_params = [param.name for param in (node.generic_params or []) if param.name]
        if not generic_params:
            for field in (node.fields or []):
                self._collect_generic_type_names(field.field_type, generic_params)
            generic_params = list(dict.fromkeys(generic_params))

        self._write_indent()
        if generic_params:
            # Emit as comptime generic function: fn Name(comptime T: type) type { return struct { ... }; }
            param_list = ", ".join(f"comptime {self._quote_identifier(p)}: type" for p in generic_params)
            self.output.write(f"fn {self._quote_identifier(name)}({param_list}) type {{\n")
            self.indent()
            self._write_indent()
            self.output.write("return struct {\n")
        else:
            self.output.write(f"const {self._quote_identifier(name)} = struct {{\n")
        self.indent()

        for field in (node.fields or []):
            fname = field.name or "unknown"
            ftype = self._emit_type_node(field.field_type, generic_env=set(generic_params)) if field.field_type else "anytype"
            self._write_indent()
            self.output.write(f"{self._quote_identifier(fname)}: {ftype},\n")

        self.dedent()
        self._write_indent()
        if generic_params:
            self.output.write("};\n")
            self.dedent()
            self._write_indent()
            self.output.write("}\n")
        else:
            self.output.write("};\n")

    def _collect_generic_type_names(self, type_node, result):
        """Collect all generic type parameter names from a type expression. Iterative."""
        stack = [type_node]
        while stack:
            n = stack.pop()
            if n is None:
                continue
            if n.kind == NodeKind.TYPE_GENERIC:
                name = n.name or "T"
                if name not in result:
                    result.append(name)
            if n.kind == NodeKind.TYPE_POINTER and n.target_type:
                stack.append(n.target_type)
            if n.kind == NodeKind.TYPE_ARRAY and n.element_type:
                stack.append(n.element_type)
            if n.kind == NodeKind.TYPE_SLICE and n.element_type:
                stack.append(n.element_type)

    def _visit_enum(self, node: ASTNode) -> None:
        """Visit enum declaration."""
        name = node.name or "anon"
        # Check if any variant has an explicit value — needs enum(i32) tag type
        has_explicit_values = any(
            v.value is not None for v in (node.variants or [])
        )
        self._write_indent()
        if has_explicit_values:
            self.output.write(f"const {self._quote_identifier(name)} = enum(i32) {{\n")
        else:
            self.output.write(f"const {self._quote_identifier(name)} = enum {{\n")
        self.indent()

        for variant in (node.variants or []):
            vname = variant.name or "unknown"
            self._write_indent()
            if variant.value is not None:
                self.output.write(f"{self._quote_identifier(vname)} = {self._emit_expr(variant.value)},\n")
            else:
                self.output.write(f"{self._quote_identifier(vname)},\n")

        self.dedent()
        self._write_indent()
        self.output.write("};\n")

    def _visit_union(self, node: ASTNode) -> None:
        """Visit union declaration."""
        name = node.name or "anon"
        is_tagged = getattr(node, 'is_tagged', False)
        self._write_indent()
        if is_tagged:
            self.output.write(f"const {self._quote_identifier(name)} = union(enum) {{\n")
        else:
            self.output.write(f"const {self._quote_identifier(name)} = union {{\n")
        self.indent()

        for field in (node.fields or []):
            fname = field.name or "unknown"
            ftype = self._emit_type_node(field.field_type) if field.field_type else "void"
            self._write_indent()
            self.output.write(f"{self._quote_identifier(fname)}: {ftype},\n")

        self.dedent()
        self._write_indent()
        self.output.write("};\n")

    def _visit_const(self, node: ASTNode) -> None:
        """Visit constant declaration."""
        if getattr(node, 'untyped_binding', False):
            return
        name = node.name or "unnamed"
        val = self._emit_expr(node.value) if node.value else "undefined"
        if self._in_function:
            name = self._declare_var_in_scope(name)
        self._write_indent()
        self.output.write(f"const {self._quote_identifier(name)} = {val};\n")
        if self._in_function:
            self._write_indent()
            self.output.write(self._pending_discard(name) + "\n")

    def _visit_var(self, node: ASTNode) -> None:
        """Visit variable declaration."""
        name = node.name or "unnamed"

        # Initializers see the outer binding, before this declaration exists.
        initial_value = None
        if node.value:
            initial_value = (self._emit_array_binary_expr(node.value)
                             if self._is_array_binary_value(node.value)
                             else self._emit_expr(node.value))

        explicit_type = getattr(node, 'explicit_type', None)
        resolved = node.resolved_type if node.resolved_type else None
        type_node = explicit_type or resolved
        declaration_type = self._type_map.get(id(node))
        needs_type = explicit_type or not isinstance(declaration_type, PrimitiveType)
        rendered_type = self._emit_type_node(type_node) if type_node and needs_type else None
        default_value = self._default_value(explicit_type) if explicit_type and not node.value else None

        # Handle variable shadowing: prefer preprocessor annotation, fall back to scope analysis
        emit_name = node.emit_name if node.emit_name else name
        if self._in_function:
            emit_name = self._declare_var_in_scope(name, node.emit_name)
        binding_name = emit_name
        emit_name = self._quote_identifier(emit_name)

        # Determine var vs const: in Zig, only directly-reassigned vars need 'var'.
        # The preprocessor's is_mutable includes field-access mutations which
        # don't require 'var' in Zig (pointer targets can be modified via const pointer).
        # So we use the backend's own direct-assignment mutation analysis.
        is_mutated = id(node) in self._mutated_declarations
        keyword = "var" if is_mutated or not self._in_function else "const"

        self._write_indent()
        if node.value and self._is_array_binary_value(node.value):
            if not type_node:
                raise CodegenError("Zig backend: array binary initializer requires a known array type", node.span)
            if not self._in_function:
                raise CodegenError("Zig backend: array binary initializer requires block scope", node.span)
            zig_type = rendered_type
            value = initial_value
            self.output.write(f"{keyword} {emit_name}: {zig_type} = {value};\n")
            if self._in_function:
                self._write_indent()
                self.output.write(self._pending_discard(binding_name) + "\n")
            return

        if node.value:
            val = initial_value
            if explicit_type:
                zig_type = rendered_type
                self.output.write(f"{keyword} {emit_name}: {zig_type} = {val};\n")
            elif isinstance(declaration_type, PrimitiveType):
                # Semantic analysis owns inferred scalar widths. Zig would infer
                # comptime_int/float for literal initializers, which cannot be
                # mutated and can disagree with A7 even for immutable bindings.
                zig_type = self._emit_semantic_type(declaration_type)
                self.output.write(f"{keyword} {emit_name}: {zig_type} = {val};\n")
            elif resolved:
                zig_type = rendered_type
                self.output.write(f"{keyword} {emit_name}: {zig_type} = {val};\n")
            else:
                self.output.write(f"{keyword} {emit_name} = {val};\n")
        elif explicit_type:
            zig_type = rendered_type
            self.output.write(f"{keyword} {emit_name}: {zig_type} = ")
            self.output.write(default_value)
            self.output.write(";\n")
        else:
            self.output.write(f"{keyword} {emit_name} = undefined;\n")

        if self._in_function:
            self._write_indent()
            self.output.write(self._pending_discard(binding_name) + "\n")

    def _visit_type_alias(self, node: ASTNode) -> None:
        """Visit type alias declaration, resolving its initializer first."""
        name = node.name or "unnamed"
        if node.value:
            val = self._emit_type_node(node.value)
            if self._in_function:
                name = self._declare_var_in_scope(name)
            self._write_indent()
            self.output.write(f"const {self._quote_identifier(name)} = {val};\n")
            if self._in_function:
                self._write_indent()
                self.output.write(self._pending_discard(name) + "\n")

    # === Statements ===

    def _visit_block(self, node: ASTNode) -> None:
        """Visit block statement (as a standalone statement)."""
        self._write_indent()
        self._visit_block_inline(node)

    def _visit_block_inline(self, node: ASTNode, prelude_lines: Optional[list[str]] = None) -> None:
        """Visit block and output braces + indented contents."""
        self.output.write("{\n")
        self.indent()
        self._push_scope()

        for line in prelude_lines or []:
            self._write_indent()
            self.output.write(line)
            self.output.write("\n")

        for stmt in (node.statements or []):
            # Skip nested functions that were hoisted to module level
            if stmt.kind == NodeKind.FUNCTION:
                if stmt.hoisted or stmt.name in self._skip_nested_fn_names:
                    continue
            self.visit(stmt)

        self._pop_scope()
        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    def _visit_switch_block(self, node: ASTNode) -> None:
        """Visit a block inside a switch prong (needs trailing comma)."""
        self.output.write("{\n")
        self.indent()
        self._push_scope()

        for stmt in (node.statements or []):
            self.visit(stmt)

        self._pop_scope()
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
            self._push_scope()
            self.visit(node.then_stmt)
            self._pop_scope()
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
                self._visit_else_chain(node.else_stmt)
            else:
                self.output.write("{\n")
                self.indent()
                self._push_scope()
                self.visit(node.else_stmt)
                self._pop_scope()
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
                elif current.then_stmt:
                    self.output.write("{\n")
                    self.indent()
                    self._push_scope()
                    self.visit(current.then_stmt)
                    self._pop_scope()
                    self.dedent()
                    self._write_indent()
                    self.output.write("}\n")
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
                self._push_scope()
                self.visit(current)
                self._pop_scope()
                self.dedent()
                self._write_indent()
                self.output.write("}\n")
                break

    def _visit_while(self, node: ASTNode) -> None:
        """Visit while statement."""
        self._write_indent()
        emitted_label = self._loop_label_name(node)
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
            self._push_scope()
            self.visit(node.body)
            self._pop_scope()
            self.dedent()
            self._write_indent()
            self.output.write("}\n")
        self._loop_label_stack.pop()

    def _visit_for(self, node: ASTNode) -> None:
        """Visit for statement (C-style or infinite)."""
        self._write_indent()

        # Infinite loop: for { ... }
        if not node.init and not node.condition and not node.update:
            emitted_label = self._loop_label_name(node)
            if emitted_label:
                self.output.write(f"{emitted_label}: ")
            self.output.write("while (true) ")
            self._loop_label_stack.append((node.label, emitted_label))
            if node.body and node.body.kind == NodeKind.BLOCK:
                self._visit_block_inline(node.body)
            elif node.body:
                self.output.write("{\n")
                self.indent()
                self._push_scope()
                self.visit(node.body)
                self._pop_scope()
                self.dedent()
                self._write_indent()
                self.output.write("}\n")
            self._loop_label_stack.pop()
            return

        # C-style for: for i := 0; i < 10; i += 1 { ... }
        # Zig doesn't have C-style for. Use a block with while + continue expression.
        self.output.write("{\n")
        self.indent()

        self._push_scope()
        # Init statement
        if node.init:
            self.visit(node.init)

        # While with continue expression
        self._write_indent()
        emitted_label = self._loop_label_name(node)
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
            self._push_scope()
            self.visit(node.body)
            self._pop_scope()
            self.dedent()
            self._write_indent()
            self.output.write("}\n")
        self._loop_label_stack.pop()
        self._pop_scope()

        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    def _visit_for_in(self, node: ASTNode) -> None:
        """Visit for-in loop: for val in arr → for (arr) |val|"""
        self._write_indent()
        iterable = self._emit_expr(node.iterable) if node.iterable else "undefined"
        self._push_scope()
        iter_name = self._declare_var_in_scope(node.iterator) if node.iterator else "_"
        before = {iter_name: self._identifier_uses.get(iter_name, 0)}
        emitted_label = self._loop_label_name(node)
        outer_output = self.output
        self.output = StringIO()

        self._loop_label_stack.append((node.label, emitted_label))
        if node.body and node.body.kind == NodeKind.BLOCK:
            self._visit_block_inline(node.body)
        elif node.body:
            self.output.write("{\n")
            self.indent()
            self._push_scope()
            self.visit(node.body)
            self._pop_scope()
            self.dedent()
            self._write_indent()
            self.output.write("}\n")
        self._loop_label_stack.pop()
        body = self.output.getvalue()
        self.output = outer_output
        self._pop_scope()
        if self._identifier_uses.get(iter_name, 0) == before.get(iter_name, 0):
            iter_name = "_"
        if emitted_label:
            self.output.write(f"{emitted_label}: ")
        self.output.write(f"for ({iterable}) |{self._quote_identifier(iter_name)}| ")
        self.output.write(body)

    def _visit_for_in_indexed(self, node: ASTNode) -> None:
        """Visit indexed for-in: for i, val in arr → for (arr, 0..) |val, i|"""
        self._write_indent()
        iterable = self._emit_expr(node.iterable) if node.iterable else "undefined"
        self._push_scope()
        iter_name = self._declare_var_in_scope(node.iterator) if node.iterator else "_"
        index_name = self._declare_var_in_scope(node.index_var) if node.index_var else "_"
        before = {name: self._identifier_uses.get(name, 0) for name in (iter_name, index_name)}
        emitted_label = self._loop_label_name(node)
        outer_output = self.output
        self.output = StringIO()

        self._loop_label_stack.append((node.label, emitted_label))
        if node.body and node.body.kind == NodeKind.BLOCK:
            self._visit_block_inline(node.body)
        elif node.body:
            self.output.write("{\n")
            self.indent()
            self._push_scope()
            self.visit(node.body)
            self._pop_scope()
            self.dedent()
            self._write_indent()
            self.output.write("}\n")
        self._loop_label_stack.pop()
        body = self.output.getvalue()
        self.output = outer_output
        self._pop_scope()
        if self._identifier_uses.get(iter_name, 0) == before.get(iter_name, 0):
            iter_name = "_"
        if self._identifier_uses.get(index_name, 0) == before.get(index_name, 0):
            index_name = "_"
        if emitted_label:
            self.output.write(f"{emitted_label}: ")
        if index_name == "_":
            self.output.write(f"for ({iterable}) |{self._quote_identifier(iter_name)}| ")
        else:
            self.output.write(f"for ({iterable}, 0..) |{self._quote_identifier(iter_name)}, {self._quote_identifier(index_name)}| ")
        self.output.write(body)

    def _visit_match(self, node: ASTNode) -> None:
        """Visit match statement → Zig switch."""
        if self._match_has_fall(node):
            self._visit_match_with_fall(node)
            return
        if self._match_has_capture(node) or not node.else_case:
            # A statement match may handle no arm. An if-chain preserves that
            # behavior without Zig switch exhaustiveness or redundant else arms.
            self._visit_match_as_if_chain(node)
            return

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
                    self._push_scope()
                    self.visit(stmt)
                    self._pop_scope()
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
                    self._push_scope()
                    self.visit(stmt)
                    self._pop_scope()
                    self.dedent()
                    self._write_indent()
                    self.output.write("},\n")
            elif isinstance(node.else_case, list):
                self.output.write("{\n")
                self.indent()
                self._push_scope()
                for stmt in node.else_case:
                    self.visit(stmt)
                self._pop_scope()
                self.dedent()
                self._write_indent()
                self.output.write("},\n")
            else:
                self.output.write("{},\n")

        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    def _visit_match_as_if_chain(self, node: ASTNode) -> None:
        """Visit capture-bearing match statements as an if/else chain."""
        scrutinee = self._unique_name("__a7_match")
        expr = self._emit_expr(node.expression) if node.expression else "undefined"

        self._write_indent()
        self.output.write("{\n")
        self.indent()
        self._write_indent()
        self.output.write(f"const {scrutinee} = {expr};\n")

        emitted_branch = False
        emitted_unconditional = False
        for case in node.cases or []:
            if emitted_unconditional:
                continue
            condition = self._emit_match_condition_zig(scrutinee, case.patterns or [])
            if emitted_branch:
                self.output.write(" else ")
            else:
                self._write_indent()
            if condition == "true":
                self.output.write("{\n")
                emitted_unconditional = True
            else:
                self.output.write(f"if ({condition}) {{\n")
            self.indent()
            self._push_scope()
            self._emit_match_capture_bindings_zig(case.patterns or [], scrutinee)
            stmt = getattr(case, "statement", None)
            if stmt:
                if stmt.kind == NodeKind.BLOCK:
                    for inner in stmt.statements or []:
                        self.visit(inner)
                else:
                    self.visit(stmt)
            else:
                for inner in case.statements or []:
                    self.visit(inner)
            self._pop_scope()
            self.dedent()
            self._write_indent()
            self.output.write("}")
            emitted_branch = True

        if node.else_case and not emitted_unconditional:
            if emitted_branch:
                self.output.write(" else ")
            else:
                self._write_indent()
            self.output.write("{\n")
            self.indent()
            self._push_scope()
            for stmt in self._else_case_statements(node.else_case):
                self.visit(stmt)
            self._pop_scope()
            self.dedent()
            self._write_indent()
            self.output.write("}")

        if emitted_branch or node.else_case:
            self.output.write("\n")

        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    def _visit_match_with_fall(self, node: ASTNode) -> None:
        """Visit a fall-capable match statement as a sequential state machine."""
        scrutinee = self._unique_name("__a7_match")
        done_flag = self._unique_name("__a7_match_done")
        fall_flag = self._unique_name("__a7_match_fall")
        expr = self._emit_expr(node.expression) if node.expression else "undefined"

        self._write_indent()
        self.output.write("{\n")
        self.indent()
        self._write_indent()
        self.output.write(f"const {scrutinee} = {expr};\n")
        self._write_indent()
        self.output.write(f"var {done_flag}: bool = false;\n")
        self._write_indent()
        self.output.write(f"var {fall_flag}: bool = false;\n")

        case_index = 0
        for case in (node.cases or []):
            condition = self._emit_match_condition_zig(scrutinee, case.patterns or [])
            self._write_indent()
            self.output.write(f"if (!{done_flag} and !{fall_flag} and ({condition})) {fall_flag} = true;\n")
            self._emit_fall_case_body(case, scrutinee, fall_flag, done_flag, case_index)
            case_index += 1

        if node.else_case:
            self._write_indent()
            self.output.write(f"if (!{done_flag} and !{fall_flag}) {fall_flag} = true;\n")
            self._emit_fall_else_body(node.else_case, fall_flag, done_flag, case_index)

        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    def _emit_fall_case_body(
        self,
        case: ASTNode,
        scrutinee: str,
        fall_flag: str,
        done_flag: str,
        case_index: int,
    ) -> None:
        stmt = getattr(case, "statement", None)
        body_has_fall = self._case_has_direct_fall(case)
        end_label = self._unique_name(f"__a7_match_case_{case_index}") if body_has_fall else ""
        self._write_indent()
        if end_label:
            self.output.write(f"if ({fall_flag}) {end_label}: {{\n")
        else:
            self.output.write(f"if ({fall_flag}) {{\n")
        self.indent()
        self._push_scope()
        self._write_indent()
        self.output.write(f"{fall_flag} = false;\n")
        self._emit_match_capture_bindings_zig(case.patterns or [], scrutinee)

        if end_label:
            self._fall_context_stack.append((fall_flag, end_label))
        try:
            if stmt:
                if stmt.kind == NodeKind.BLOCK:
                    self._write_indent()
                    self._visit_block_inline(stmt)
                else:
                    self.visit(stmt)
            else:
                for stmt in case.statements or []:
                    self.visit(stmt)
        finally:
            if end_label:
                self._fall_context_stack.pop()

        self._write_indent()
        self.output.write(f"if (!{fall_flag}) {done_flag} = true;\n")
        self._pop_scope()
        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    def _emit_fall_else_body(
        self,
        else_case: object,
        fall_flag: str,
        done_flag: str,
        case_index: int,
    ) -> None:
        self._write_indent()
        self.output.write(f"if ({fall_flag}) {{\n")
        self.indent()
        self._push_scope()
        self._write_indent()
        self.output.write(f"{fall_flag} = false;\n")

        for stmt in self._else_case_statements(else_case):
            self.visit(stmt)

        self._write_indent()
        self.output.write(f"if (!{fall_flag}) {done_flag} = true;\n")
        self._pop_scope()
        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    def _visit_fall(self, node: ASTNode) -> None:
        if not self._fall_context_stack:
            raise CodegenError("Zig backend: fall used outside a fall-capable match case", node.span)
        fall_flag, end_label = self._fall_context_stack[-1]
        self._write_indent()
        self.output.write(f"{fall_flag} = true;\n")
        self._write_indent()
        self.output.write(f"break :{end_label};\n")

    def _match_has_fall(self, node: ASTNode) -> bool:
        return any(self._case_has_direct_fall(case) for case in (node.cases or []))

    def _match_has_capture(self, node: ASTNode) -> bool:
        return any(
            self._is_capture_pattern(pattern)
            or pattern.kind == NodeKind.PATTERN_WILDCARD
            or (pattern.kind == NodeKind.PATTERN_IDENTIFIER and pattern.name == "_")
            for case in (node.cases or [])
            for pattern in (case.patterns or [])
        )

    def _is_capture_pattern(self, pattern: ASTNode) -> bool:
        return (
            pattern.kind == NodeKind.PATTERN_IDENTIFIER
            and bool(getattr(pattern, "is_capture_pattern", False))
            and (pattern.name or "") != "_"
        )

    def _emit_match_capture_bindings_zig(self, patterns: list[ASTNode], scrutinee: str) -> None:
        for pattern in patterns:
            if not self._is_capture_pattern(pattern):
                continue
            name = self._declare_var_in_scope(pattern.name or "value")
            self._write_indent()
            self.output.write(f"const {self._quote_identifier(name)} = {scrutinee};\n")
            self._write_indent()
            self.output.write(self._pending_discard(name) + "\n")

    def _case_has_direct_fall(self, case: ASTNode) -> bool:
        stmt = getattr(case, "statement", None)
        if stmt is None:
            statements = list(case.statements or [])
        elif stmt.kind == NodeKind.BLOCK:
            statements = list(stmt.statements or [])
        else:
            statements = [stmt]
        return any(stmt.kind == NodeKind.FALL for stmt in statements)

    def _else_case_statements(self, else_case: object) -> list[ASTNode]:
        if isinstance(else_case, list):
            return [stmt for stmt in else_case if isinstance(stmt, ASTNode)]
        if isinstance(else_case, ASTNode):
            if else_case.kind == NodeKind.BLOCK:
                return list(else_case.statements or [])
            return [else_case]
        return []

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
        if node.statement:
            if node.statement.kind == NodeKind.BLOCK:
                self._write_indent()
                self.output.write("defer ")
                self._visit_block_inline(node.statement)
            else:
                if node.statement.kind == NodeKind.EXPRESSION_STMT and node.statement.expression:
                    if self._is_io_call(node.statement.expression):
                        self._write_indent()
                        self.output.write("defer {\n")
                        self.indent()
                        self._emit_io_call(node.statement.expression)
                        self.dedent()
                        self._write_indent()
                        self.output.write("}\n")
                        return
                self._write_indent()
                self.output.write("defer ")
                stmt_str = self._emit_statement_inline(node.statement)
                self.output.write(f"{stmt_str};\n")
        elif node.expression:
            self._write_indent()
            self.output.write("defer ")
            expr_str = self._emit_expr(node.expression)
            if not self._expression_returns_void(node.expression):
                expr_str = "_ = " + expr_str
            self.output.write(f"{expr_str};\n")

    def _visit_del(self, node: ASTNode) -> None:
        """Visit del statement → Zig allocator.destroy."""
        self._write_indent()
        expr_node = getattr(node, 'expression', None) or getattr(node, 'expr', None)
        if expr_node:
            target_type = self._type_map.get(id(expr_node))
            if target_type is not None and not isinstance(target_type, (ReferenceType, PointerType)):
                raise CodegenError("Zig backend: del requires a reference type", expr_node.span or node.span)
            expr = self._emit_expr(expr_node)
            self.output.write(f"if ({expr}) |p| allocator.destroy(p);\n")

    def _visit_assignment(self, node: ASTNode) -> None:
        """Visit assignment statement."""
        op = getattr(node, 'operator', None) or getattr(node, 'op', AssignOp.ASSIGN)
        if op == AssignOp.ASSIGN and self._emit_array_binary_assignment(node.target, node.value):
            return

        self._write_indent()
        if getattr(node, "implicit_deref_target", False):
            self._require_backend_approval(node, "deref")
            target = self._emit_implicit_deref(node.target)
        else:
            target = self._emit_expr(node.target) if node.target else "undefined"
        value = self._emit_expr(node.value) if node.value else "undefined"
        self.output.write(self._assignment_text(node, target, value) + ";\n")

    def _assignment_text(self, node: ASTNode, target: str, value: str) -> str:
        """Lower compound operations once, including nontrivial lvalue targets."""
        op = node.operator
        if op == AssignOp.ASSIGN and node.value and node.value.kind == NodeKind.ARRAY_INIT:
            # Zig forwards an anonymous literal's result location into its
            # elements. Materialize the RHS before overwriting storage it reads.
            self._name_counter += 1
            temp = f"__a7_array_value_{self._name_counter}"
            value = (f"{temp}_block: {{ const {temp}: @TypeOf({target}) = {value}; "
                     f"break :{temp}_block {temp}; }}")
        target_type = self._type_map.get(id(node.target))
        if getattr(node, "implicit_deref_target", False):
            target_type = getattr(target_type, "referent_type", target_type)
        integral = isinstance(target_type, PrimitiveType) and target_type.is_integral()
        if op in {AssignOp.DIV_ASSIGN, AssignOp.MOD_ASSIGN}:
            self._require_backend_approval(node, op.name.lower())
            if op == AssignOp.MOD_ASSIGN or integral:
                builtin = "@rem" if op == AssignOp.MOD_ASSIGN else "@divTrunc"
                self._name_counter += 1
                ptr = f"__a7_compound_{self._name_counter}"
                return f"_ = {ptr}_block: {{ const {ptr} = &{target}; {ptr}.* = {builtin}({ptr}.*, {value}); break :{ptr}_block {{}}; }}"
        zig_op = self._assign_op_to_zig(op)
        if integral and op in {AssignOp.ADD_ASSIGN, AssignOp.SUB_ASSIGN, AssignOp.MUL_ASSIGN}:
            if self._use_wrapping(node, op):
                zig_op = zig_op[0] + "%="
        return f"{target} {zig_op} {value}"

    def _emit_array_binary_assignment(self, target: Optional[ASTNode], value: Optional[ASTNode]) -> bool:
        """Lower fixed-array binary assignment to per-element stores."""
        if target is None:
            return False
        info = self._array_binary_assignment_info(self._emit_expr(target), value)
        if info is None:
            return False
        self._emit_array_binary_assignment_info(info)
        return True

    def _emit_array_binary_assignment_info(self, info: tuple[str, str, str, str, int, str]) -> None:
        target_expr, left_expr, right_expr, op, size, elem_type = info
        self._write_indent()
        self.output.write(f"{target_expr} = {self._emit_array_vector_expr(left_expr, right_expr, op, size, elem_type)};\n")

    def _emit_array_binary_expr(self, value: ASTNode) -> str:
        info = self._array_binary_assignment_info("_", value)
        if info is None:
            raise CodegenError("Zig backend: expected fixed-array binary expression", value.span)
        _, left_expr, right_expr, op, size, elem_type = info
        return self._emit_array_vector_expr(left_expr, right_expr, op, size, elem_type)

    def _emit_array_vector_expr(self, left_expr: str, right_expr: str, op: str, size: int, elem_type: str) -> str:
        vector_type = f"@Vector({size}, {elem_type})"
        return f"(@as({vector_type}, {left_expr}) {op} @as({vector_type}, {right_expr}))"

    def _array_binary_assignment_info(
        self,
        target_expr: str,
        value: Optional[ASTNode],
    ) -> Optional[tuple[str, str, str, str, int, str]]:
        if value is None or value.kind != NodeKind.BINARY:
            return None
        result_type = self._type_map.get(id(value))
        if not isinstance(result_type, ArrayType):
            return None
        if value.operator != BinaryOp.ADD:
            raise CodegenError("Zig backend: unsupported array binary assignment", value.span)
        if not isinstance(result_type.size, int):
            raise CodegenError("Zig backend: array binary assignment requires fixed-size arrays", value.span)
        if not isinstance(result_type.element_type, PrimitiveType):
            raise CodegenError("Zig backend: array vector lowering requires primitive numeric elements", value.span)
        return (
            target_expr,
            self._emit_array_operand_expr(value.left, "Zig", value.span),
            self._emit_array_operand_expr(value.right, "Zig", value.span),
            self._binary_op_to_zig(value.operator, value.span) + ("%" if result_type.element_type.is_integral() else ""),
            result_type.size,
            self._map_primitive_type(result_type.element_type.name),
        )

    def _is_array_binary_value(self, value: Optional[ASTNode]) -> bool:
        return (
            value is not None
            and value.kind == NodeKind.BINARY
            and isinstance(self._type_map.get(id(value)), ArrayType)
        )

    def _emit_array_operand_expr(self, node: Optional[ASTNode], backend_name: str, span=None) -> str:
        if node is None:
            raise CodegenError(f"{backend_name} backend: missing array binary operand", span)
        if node.kind not in {NodeKind.IDENTIFIER, NodeKind.FIELD_ACCESS, NodeKind.INDEX}:
            raise CodegenError(
                f"{backend_name} backend: array binary operands must be named or indexed arrays",
                node.span,
            )
        return self._emit_expr(node)

    def _visit_expression_stmt(self, node: ASTNode) -> None:
        """Visit expression statement."""
        if node.expression:
            # Special-case io.println / io.print calls
            if self._is_io_call(node.expression):
                self._emit_io_call(node.expression)
                return

            self._write_indent()
            expr = self._emit_expr(node.expression)
            if self._expression_returns_void(node.expression):
                self.output.write(f"{expr};\n")
            else:
                self.output.write(f"_ = {expr};\n")

    def _expression_returns_void(self, node: ASTNode) -> bool:
        """Return True when an expression has semantic void type."""
        ty = self._type_map.get(id(node)) if node is not None else None
        return ty is not None and getattr(getattr(ty, "kind", None), "name", "") == "VOID"

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
            return self._emit_binary_iterative(node)
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
            bits = getattr(node, 'exact_float_bits', None)
            if bits is not None:
                width, value = bits
                if isinstance(val, float) and math.isfinite(val):
                    # Emit the decimal text when it round-trips to the same
                    # bits; keep @bitCast for values with no faithful literal.
                    fmt = '>f' if width == 32 else '>d'
                    try:
                        same = struct.unpack(fmt, struct.pack(fmt, float(raw)))[0] == val
                    except (ValueError, OverflowError):
                        same = False
                    if same:
                        s = raw
                        if "." not in s and "e" not in s and "E" not in s:
                            s += ".0"
                        return s
                return f'@as(f{width}, @bitCast(@as(u{width}, {value})))'
            if isinstance(val, float) and not math.isfinite(val):
                return self._emit_nonfinite_float(node, val)
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
                if escaped == val and len(val) == 1 and (ord(val) < 0x20 or ord(val) == 0x7f):
                    escaped = f"\\x{ord(val):02x}"
                return f"'{escaped}'"
            return raw if raw else "'\\x00'"
        elif lk == LiteralKind.BOOLEAN:
            return "true" if val else "false"
        elif lk == LiteralKind.NIL:
            return "null"
        else:
            return str(val) if val is not None else raw

    def _emit_nonfinite_float(self, node: ASTNode, val: float) -> str:
        """Emit infinity or NaN as a typed Zig expression.

        Zig has no float literal for these values: `inf` and `nan` are not
        tokens, and a decimal literal that overflows f64 is still finite in
        `comptime_float` (f128). `std.math.inf` and `std.math.nan` give the
        value in the float type the node was checked at, so an expression
        built on one is evaluated in that type and not in comptime_float.

        The sign of a NaN is not preserved: IEEE 754 leaves it unspecified
        and the hardware result of, say, `inf - inf` differs between
        optimization levels.
        """
        name = self._float_type_name(node)
        if math.isnan(val):
            return f"std.math.nan({name})"
        if val < 0:
            return f"(-std.math.inf({name}))"
        return f"std.math.inf({name})"

    def _float_type_name(self, node: ASTNode) -> str:
        """Float type the checker gave this node; f64 is the literal default."""
        ty = self._type_map.get(id(node))
        if isinstance(ty, PrimitiveType) and ty.name in ("f32", "f64"):
            return ty.name
        return "f64"

    @staticmethod
    def _is_nonfinite_float_literal(node: ASTNode) -> bool:
        if node.kind != NodeKind.LITERAL or node.literal_kind != LiteralKind.FLOAT:
            return False
        val = getattr(node, 'literal_value', None)
        return isinstance(val, float) and not math.isfinite(val)

    def _emit_identifier(self, node: ASTNode) -> str:
        """Emit an identifier."""
        return self._use_name(node.name or "undefined")

    def _emit_binary_iterative(self, root: ASTNode) -> str:
        """Emit nested binary expressions without using the Python call stack."""
        rendered: dict[int, str] = {}
        stack: list[tuple[ASTNode, bool]] = [(root, False)]
        while stack:
            node, ready = stack.pop()
            if node.kind != NodeKind.BINARY:
                rendered[id(node)] = self._emit_expr(node)
                continue
            if ready:
                left = rendered.pop(id(node.left))
                right = rendered.pop(id(node.right))
                rendered[id(node)] = self._emit_binary_from_parts(node, left, right)
                continue
            stack.append((node, True))
            if node.right is not None:
                stack.append((node.right, False))
            if node.left is not None:
                stack.append((node.left, False))
        return rendered[id(root)]

    def _emit_binary_from_parts(self, node: ASTNode, left: str, right: str) -> str:
        """Render a binary node from already-rendered child expressions."""
        op = node.operator

        zig_op = self._binary_op_to_zig(op, node.span)

        result_type = self._type_map.get(id(node))
        arithmetic_type = result_type.element_type if isinstance(result_type, ArrayType) else result_type
        if op in {BinaryOp.ADD, BinaryOp.SUB, BinaryOp.MUL} and isinstance(arithmetic_type, PrimitiveType) and arithmetic_type.is_integral():
            if self._use_wrapping(node, op):
                zig_op += "%"
                if not isinstance(result_type, ArrayType) and node.left.kind == NodeKind.LITERAL and node.right.kind == NodeKind.LITERAL:
                    left = f"@as({self._emit_semantic_type(arithmetic_type)}, {left})"
        if isinstance(result_type, ArrayType):
            if op != BinaryOp.ADD:
                raise CodegenError("Zig backend: unsupported array binary expression", node.span)
            if not isinstance(result_type.size, int):
                raise CodegenError("Zig backend: array binary expression requires fixed-size arrays", node.span)
            if not isinstance(result_type.element_type, PrimitiveType):
                raise CodegenError("Zig backend: array vector lowering requires primitive numeric elements", node.span)
            return self._emit_array_vector_expr(
                left,
                right,
                zig_op,
                result_type.size,
                self._map_primitive_type(result_type.element_type.name),
            )

        if op in {BinaryOp.DIV, BinaryOp.MOD}:
            self._require_backend_approval(node, op.name.lower())

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
            return f"@rem({left}, {right})"
        elif op == BinaryOp.BIT_SHL:
            if self._is_nonnegative_integer_literal(node.right):
                return f"({left} << {right})"
            return f"({left} << @intCast({right}))"
        elif op == BinaryOp.BIT_SHR:
            if self._is_nonnegative_integer_literal(node.right):
                return f"({left} >> {right})"
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

    def _generic_call_args(self, node: ASTNode) -> list[str]:
        """Emit the comptime type arguments a generic call carries, in order."""
        generic_mapping = getattr(node, "generic_mapping", None) or {}
        if not generic_mapping:
            return []
        func_type = self._type_map.get(id(node.function)) if node.function else None
        generic_order = tuple(getattr(func_type, "generic_param_order", ()) or ())
        ordered_names = generic_order or tuple(generic_mapping.keys())
        return [
            self._emit_semantic_type(generic_mapping[name])
            for name in ordered_names
            if name in generic_mapping
        ]

    def _emit_call(self, node: ASTNode) -> str:
        """Emit a function call."""
        # Special-case io.println / io.print
        if self._is_io_call(node):
            return self._emit_io_call_expr(node)

        file_module_call = getattr(node, "file_module_call", None)
        if file_module_call:
            prefix, field = file_module_call
            args_list = self._generic_call_args(node)
            implicit_ref_args = set(getattr(node, "implicit_ref_args", set()) or set())
            for index, arg in enumerate(node.arguments or []):
                if index in implicit_ref_args:
                    args_list.append(f"&{self._emit_expr(arg)}")
                else:
                    args_list.append(self._emit_expr(arg))
            return f"{prefix}{field}({', '.join(args_list)})"

        canonical = getattr(node, "stdlib_canonical", None)
        if canonical and canonical.startswith("std.math."):
            short = canonical.split(".")[-1]
            if short in ('sqrt', 'abs', 'floor', 'ceil', 'sin', 'cos', 'tan',
                         'log', 'exp', 'min', 'max'):
                args = ", ".join(self._emit_expr(a) for a in (node.arguments or []))
                if short == "abs":
                    result_type = self._type_map.get(id(node))
                    if isinstance(result_type, PrimitiveType) and result_type.is_integral() and result_type.name.startswith("i"):
                        return f"@as({self._emit_semantic_type(result_type)}, @intCast(@abs({args})))"
                return f"@{short}({args})"

        func = self._emit_expr(node.function)

        args_list = self._generic_call_args(node)
        implicit_ref_args = set(getattr(node, "implicit_ref_args", set()) or set())
        for index, arg in enumerate(node.arguments or []):
            if index in implicit_ref_args:
                args_list.append(f"&{self._emit_expr(arg)}")
            else:
                args_list.append(self._emit_expr(arg))
        args = ", ".join(args_list)
        return f"{func}({args})"

    def _emit_index(self, node: ASTNode) -> str:
        """Emit array indexing."""
        self._require_backend_approval(node, "index")
        obj = self._emit_expr(node.object)
        if (
            node.index
            and node.index.kind == NodeKind.LITERAL
            and node.index.literal_kind == LiteralKind.INTEGER
            and isinstance(node.index.literal_value, int)
            and node.index.literal_value >= 0
        ):
            return f"{obj}[{node.index.literal_value}]"
        idx = self._emit_expr(node.index)
        index_type = self._type_map.get(id(node.index)) if node.index else None
        if index_type is not None and getattr(index_type, "name", None) == "usize":
            return f"{obj}[{idx}]"
        return f"{obj}[@intCast({idx})]"

    def _emit_slice(self, node: ASTNode) -> str:
        """Emit slice expression."""
        self._require_backend_approval(node, "slice")
        obj = self._emit_expr(node.object)
        start = self._emit_slice_bound(node.start, default="0")
        end = self._emit_slice_bound(node.end, default="")
        return f"{obj}[{start}..{end}]"

    def _emit_slice_bound(self, bound: Optional[ASTNode], *, default: str) -> str:
        """Emit a slice bound, coercing non-usize values via @intCast."""
        if bound is None:
            return default
        if (
            bound.kind == NodeKind.LITERAL
            and bound.literal_kind == LiteralKind.INTEGER
            and isinstance(bound.literal_value, int)
            and bound.literal_value >= 0
        ):
            return str(bound.literal_value)
        emitted = self._emit_expr(bound)
        bound_type = self._type_map.get(id(bound))
        if bound_type is not None and getattr(bound_type, "name", None) == "usize":
            return emitted
        return f"@intCast({emitted})"

    def _emit_field_access(self, node: ASTNode) -> str:
        """Emit field access."""
        if getattr(node, "implicit_deref_object", False):
            self._require_backend_approval(node, "deref")
            obj = self._emit_implicit_ref_field_base(node.object)
        else:
            obj = self._emit_expr(node.object)
        field = node.field or "unknown"
        return f"{obj}.{self._quote_identifier(field)}"

    def _emit_address_of(self, node: ASTNode) -> str:
        """Emit internal address-of."""
        operand = self._emit_expr(node.operand)
        return f"&{operand}"

    def _emit_deref(self, node: ASTNode) -> str:
        """Emit internal dereference."""
        self._require_backend_approval(node, "deref")
        pointer = self._emit_expr(node.pointer)
        pointer_type = self._type_map.get(id(node.pointer)) if node.pointer else None
        if isinstance(pointer_type, PointerType):
            return f"{pointer}[0]"
        return f"{pointer}.?.*"

    def _emit_implicit_deref(self, node: Optional[ASTNode]) -> str:
        expr = self._emit_expr(node) if node else "undefined"
        node_type = self._type_map.get(id(node)) if node else None
        if isinstance(node_type, PointerType):
            return f"{expr}[0]"
        return f"{expr}.?.*"

    def _emit_implicit_ref_field_base(self, node: Optional[ASTNode]) -> str:
        expr = self._emit_expr(node) if node else "undefined"
        node_type = self._type_map.get(id(node)) if node else None
        if isinstance(node_type, PointerType):
            return f"{expr}[0]"
        return f"{expr}.?"

    def _emit_cast(self, node: ASTNode) -> str:
        """Emit cast expression."""
        self._require_backend_approval(node, "cast")
        decision = getattr(node, "cast_decision", None)
        if decision is None or not decision.allowed:
            raise CodegenError("Zig backend: cast was not approved by semantic analysis", node.span)

        target_type = self._emit_type_node(node.target_type) if node.target_type else "anytype"
        expr = self._emit_expr(node.expression)
        source_type = getattr(node, "cast_source_type", None)
        cast_target_type = getattr(node, "cast_target_type", None)
        source_name = getattr(source_type, "name", None)
        target_name = getattr(cast_target_type, "name", None)

        if decision.kind is CastClass.LOSSLESS:
            return f"@as({target_type}, {expr})"
        if source_name in {"f32", "f64"} and target_name in {"f32", "f64"}:
            return f"@as({target_type}, @floatCast({expr}))"
        if source_name in {"f32", "f64"}:
            return f"@as({target_type}, @intFromFloat({expr}))"
        if target_name in {"f32", "f64"}:
            return f"@as({target_type}, @floatFromInt({expr}))"
        if self._is_nonnegative_integer_literal(node.expression):
            return f"@as({target_type}, {expr})"
        return f"@as({target_type}, @intCast({expr}))"

    def _is_nonnegative_integer_literal(self, node: Optional[ASTNode]) -> bool:
        return bool(
            node
            and node.kind == NodeKind.LITERAL
            and node.literal_kind == LiteralKind.INTEGER
            and isinstance(node.literal_value, int)
            and node.literal_value >= 0
        )

    def _require_backend_approval(self, node: ASTNode, operation: str) -> None:
        if self._backend_plan is None:
            raise CodegenError(
                f"Zig backend: {operation} was not approved by safety proof analysis",
                node.span,
            )
        try:
            self._backend_plan.require(node, operation)
        except KeyError as exc:
            raise CodegenError(f"Zig backend: {operation} was not approved by safety proof analysis", node.span) from exc

    def _use_wrapping(self, node: ASTNode, op) -> bool:
        """Debug always wraps. Release drops the wrapping suffix when the
        safety pass proved the result fits the type range. --no-nonwrap keeps
        wrapping in every profile, so a release build stays bit-identical to
        debug regardless of which proofs happen to be discharged."""
        if self._force_wrapping:
            return True
        if self._profile != "release" or self._backend_plan is None:
            return True
        return not self._backend_plan.is_approved(node, f"{op.name.lower()}_nonwrap")

    def _emit_if_expr(self, node: ASTNode) -> str:
        """Emit if expression."""
        cond = self._emit_expr(node.condition)
        then_val = self._emit_expr(node.then_expr)
        else_val = self._emit_expr(node.else_expr) if node.else_expr else "undefined"
        # Parenthesize: a bare Zig `if` expression extends its else branch over
        # any operator that follows, so `(if c a else b) + 10` must keep the
        # parentheses to select before the operator applies.
        return f"(if ({cond}) {then_val} else {else_val})"

    def _emit_match_expr(self, node: ASTNode) -> str:
        """Emit match expression → Zig switch expression."""
        if self._match_has_capture(node):
            return self._emit_match_expr_with_captures(node)

        expr = self._emit_expr(node.expression) if node.expression else "undefined"
        case_indent = "    " * (self.indent_level + 1)
        close_indent = "    " * self.indent_level
        parts = [f"switch ({expr}) {{"]

        for case in (node.cases or []):
            patterns = case.patterns or []
            pattern_str = ", ".join(self._emit_pattern(p) for p in patterns)
            case_expr = getattr(case, 'expression', None)
            val = self._emit_expr(case_expr) if case_expr else "undefined"
            parts.append(f"\n{case_indent}{pattern_str} => {val},")

        if node.else_case:
            if isinstance(node.else_case, ASTNode):
                val = self._emit_expr(node.else_case)
            else:
                val = "undefined"
            parts.append(f"\n{case_indent}else => {val},")

        parts.append(f"\n{close_indent}}}")
        return "".join(parts)

    def _emit_match_expr_with_captures(self, node: ASTNode) -> str:
        """Emit a capture-bearing match expression as a Zig block expression."""
        label = self._unique_name("__a7_match_expr")
        scrutinee = self._unique_name("__a7_match")
        expr = self._emit_expr(node.expression) if node.expression else "undefined"
        parts = [f"{label}: {{ const {scrutinee} = {expr};"]

        emitted_branch = False
        emitted_unconditional = False
        for case in node.cases or []:
            if emitted_unconditional:
                continue
            case_expr = getattr(case, "expression", None)
            if case_expr is None:
                continue
            condition = self._emit_match_condition_zig(scrutinee, case.patterns or [])
            prefix = " else " if emitted_branch else " "
            if condition == "true":
                parts.append(f"{prefix}{{")
                emitted_unconditional = True
            else:
                parts.append(f"{prefix}if ({condition}) {{")
            self._push_scope()
            for pattern in case.patterns or []:
                if self._is_capture_pattern(pattern):
                    name = self._declare_var_in_scope(pattern.name or "value")
                    parts.append(f" const {self._quote_identifier(name)} = {scrutinee};")
                    parts.append(" " + self._pending_discard(name))
            parts.append(f" break :{label} {self._emit_expr(case_expr)}; }}")
            self._pop_scope()
            emitted_branch = True

        if not emitted_unconditional:
            else_expr = self._emit_expr(node.else_case) if isinstance(node.else_case, ASTNode) else "undefined"
            prefix = " else " if emitted_branch else " "
            parts.append(f"{prefix}{{ break :{label} {else_expr}; }}")

        parts.append(" }")
        return "".join(parts)

    def _emit_struct_init(self, node: ASTNode) -> str:
        """Emit struct initialization."""
        struct_name = self._use_name(node.struct_type or "")
        field_inits = node.field_inits or []
        type_args = getattr(node, "type_arguments", None) or []

        if struct_name and struct_name != "__inline__":
            if type_args:
                rendered_args = ", ".join(self._emit_type_node(arg) for arg in type_args)
                parts = [f"{struct_name}({rendered_args}){{ "]
            else:
                parts = [f"{struct_name}{{ "]
        else:
            parts = [".{ "]

        for i, fi in enumerate(field_inits):
            if i > 0:
                parts.append(", ")
            val = self._emit_expr(fi.value) if fi.value else "undefined"
            if fi.name:
                parts.append(f".{self._quote_identifier(fi.name)} = {val}")
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
            return self._use_name(node.name) if node.name and node.name != "_" else "_"
        elif kind == NodeKind.PATTERN_ENUM:
            return f".{node.variant}" if node.variant else "_"
        elif kind == NodeKind.PATTERN_RANGE:
            start = self._emit_pattern(node.start)
            end = self._emit_pattern(node.end)
            return f"{start}...{end}"
        elif kind == NodeKind.PATTERN_WILDCARD:
            return "_"
        else:
            try:
                return self._emit_expr(node)
            except CodegenError as exc:
                raise CodegenError(
                    f"Zig backend: unsupported match pattern '{kind.name}'",
                    node.span,
                ) from exc

    def _emit_match_condition_zig(self, scrutinee_expr: str, patterns: list[ASTNode]) -> str:
        conditions: list[str] = []
        for pattern in patterns:
            condition = self._emit_match_pattern_condition_zig(scrutinee_expr, pattern)
            if condition is None:
                return "true"
            conditions.append(condition)
        if not conditions:
            return "false"
        if len(conditions) == 1:
            return conditions[0]
        return " or ".join(f"({condition})" for condition in conditions)

    def _emit_match_pattern_condition_zig(
        self,
        scrutinee_expr: str,
        pattern: ASTNode,
    ) -> Optional[str]:
        if pattern.kind == NodeKind.PATTERN_WILDCARD:
            return None
        if pattern.kind == NodeKind.PATTERN_LITERAL:
            value = self._emit_expr(pattern.literal) if pattern.literal else "0"
            return f"{scrutinee_expr} == {value}"
        if pattern.kind == NodeKind.PATTERN_ENUM:
            value = f".{pattern.variant}" if pattern.variant else "_"
            return f"{scrutinee_expr} == {value}"
        if pattern.kind == NodeKind.PATTERN_IDENTIFIER:
            name = pattern.name or ""
            if name == "_":
                return None
            if self._is_capture_pattern(pattern):
                return None
            return f"{scrutinee_expr} == {self._use_name(name)}"
        if pattern.kind == NodeKind.PATTERN_RANGE:
            start = self._emit_pattern(pattern.start) if pattern.start else "0"
            end = self._emit_pattern(pattern.end) if pattern.end else "0"
            return f"{scrutinee_expr} >= {start} and {scrutinee_expr} <= {end}"
        value = self._emit_expr(pattern)
        return f"{scrutinee_expr} == {value}"

    def _unique_name(self, prefix: str) -> str:
        self._name_counter += 1
        return f"{prefix}_{self._name_counter}"

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

    def _emit_type_node(self, node: ASTNode, generic_env: Optional[Set[str]] = None, span=None) -> str:
        """Emit a type as a Zig type string. Iterative for linear chains."""
        if node is None:
            raise CodegenError("Zig backend: missing type node", span)

        generic_env = generic_env or set()
        if self._type_contains_generic(node) and not generic_env:
            raise CodegenError("Zig backend: generic type requires an explicit generic environment", node.span)

        # Build prefix iteratively for linear chains: ref ref [N][M]... base
        prefix_parts = []
        current = node
        while current is not None:
            kind = current.kind

            if kind == NodeKind.TYPE_POINTER:
                if (
                    current.target_type
                    and current.target_type.kind == NodeKind.TYPE_GENERIC
                    and current.target_type.name not in generic_env
                ):
                    raise CodegenError("Zig backend: unresolved generic pointer type", current.span)
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
                base = self._emit_type_leaf(current, generic_env=generic_env)
                return "".join(prefix_parts) + base

        raise CodegenError("Zig backend: incomplete type expression", node.span)

    def _emit_type_leaf(self, node: ASTNode, generic_env: Optional[Set[str]] = None, span=None) -> str:
        """Emit a non-chain (leaf) type node."""
        if node is None:
            raise CodegenError("Zig backend: missing type leaf", span)

        generic_env = generic_env or set()
        kind = node.kind
        if kind == NodeKind.TYPE_PRIMITIVE:
            return self._map_primitive_type(node.type_name or "i32")
        elif kind == NodeKind.TYPE_IDENTIFIER:
            if node.generic_params:
                args = ", ".join(self._emit_type_node(p, generic_env=generic_env) for p in node.generic_params)
                if not node.name:
                    raise CodegenError("Zig backend: generic type identifier is missing a name", node.span)
                return f"{self._use_name(node.name)}({args})"
            if not node.name:
                raise CodegenError("Zig backend: type identifier is missing a name", node.span)
            return self._use_name(node.name)
        elif kind == NodeKind.TYPE_GENERIC:
            if node.name in generic_env:
                return self._quote_identifier(node.name)
            raise CodegenError(f"Zig backend: unresolved generic type '{node.name or '?'}'", node.span)
        elif kind == NodeKind.TYPE_FUNCTION:
            params = ", ".join(self._emit_type_node(p, generic_env=generic_env) for p in (node.parameter_types or []))
            ret = self._emit_type_node(node.return_type, generic_env=generic_env) if node.return_type else "void"
            return f"*const fn ({params}) {ret}"
        elif kind == NodeKind.TYPE_STRUCT:
            fields = node.fields or []
            parts = ["struct {"]
            for f in fields:
                fname = f.name or "unknown"
                ftype = self._emit_type_node(f.field_type, generic_env=generic_env) if f.field_type else "anytype"
                parts.append(f"\n    {self._quote_identifier(fname)}: {ftype},")
            parts.append("\n}")
            return "".join(parts)
        else:
            raise CodegenError(f"Zig backend: unsupported type node '{kind.name}'", node.span)

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

    def _emit_semantic_type(self, type_obj) -> str:
        """Emit a semantic Type object as a Zig type expression."""
        if type_obj is None:
            return "anytype"
        name = getattr(type_obj, "name", None)
        if name:
            return self._map_primitive_type(name)
        if isinstance(type_obj, ArrayType):
            return f"[{type_obj.size}]{self._emit_semantic_type(type_obj.element_type)}"
        if isinstance(type_obj, PointerType):
            return f"?*{self._emit_semantic_type(type_obj.pointee_type)}"
        referent = getattr(type_obj, "referent_type", None)
        if referent is not None:
            return f"?*{self._emit_semantic_type(referent)}"
        element = getattr(type_obj, "element_type", None)
        if element is not None:
            return f"[]{self._emit_semantic_type(element)}"
        base_name = getattr(type_obj, "base_name", None)
        type_args = getattr(type_obj, "type_args", None)
        if base_name and type_args is not None:
            args = ", ".join(self._emit_semantic_type(arg) for arg in type_args)
            return f"{base_name}({args})"
        return str(type_obj)

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
        """Build nested array defaults iteratively, including strings and refs."""
        arrays = []
        current = type_node
        while current is not None and current.kind == NodeKind.TYPE_ARRAY:
            arrays.append(current)
            current = current.element_type
        if current is not None and current.kind == NodeKind.TYPE_PRIMITIVE:
            name = current.type_name
            value = {"f32": "0.0", "f64": "0.0", "bool": "false", "string": '\"\"'}.get(name, "0")
        elif current is not None and current.kind == NodeKind.TYPE_POINTER:
            value = "null"
        else:
            value = "undefined"
        for array in reversed(arrays):
            elem = self._emit_type_node(array.element_type)
            size = self._emit_expr(array.size) if array.size else "0"
            value = f"[_]{elem}{{{value}}} ** {size}"
        return value

    # === I/O special-casing ===

    def _is_io_call(self, node: ASTNode) -> bool:
        """Check if this is an stdlib io print call."""
        if node.kind != NodeKind.CALL:
            return False
        canonical = getattr(node, "stdlib_canonical", None)
        return canonical in {"std.io.println", "std.io.print", "std.io.eprintln"}

    def _emit_io_call(self, node: ASTNode) -> None:
        """Emit an io.println/io.print call as a statement."""
        func = node.function
        canonical = getattr(node, "stdlib_canonical", None)
        field = canonical.split(".")[-1] if canonical else getattr(func, 'field', 'println')
        args = node.arguments or []

        self._write_indent()

        if not args:
            fmt_str = '"\\n"' if field in {"println", "eprintln"} else '""'
            self._write_io_print(field, fmt_str, "")
            return

        # First arg is the format string
        fmt_arg = args[0]
        rest_args = args[1:]

        fmt_str = self._emit_expr(fmt_arg)
        # Convert A7 {} format to Zig with type-aware placeholders.
        fmt_str = self._convert_format_string(fmt_str, rest_args)

        if field in {"println", "eprintln"}:
            # Add newline
            if fmt_str.endswith('"'):
                fmt_str = fmt_str[:-1] + '\\n"'

        if rest_args:
            zig_args = ", ".join(self._emit_expr(a) for a in rest_args)
            self._write_io_print(field, fmt_str, zig_args)
        else:
            self._write_io_print(field, fmt_str, "")

    def _write_io_print(self, field: str, fmt_str: str, zig_args: str) -> None:
        """Write std/io calls to the correct output stream."""
        stream = "stderr" if field == "eprintln" else "stdout"
        if not zig_args:
            args = ".{}"
        elif self._has_top_level_comma(zig_args):
            args = f".{{ {zig_args} }}"
        else:
            args = f".{{{zig_args}}}"
        self.output.write(f"__a7_{stream}_print({fmt_str}, {args});\n")

    def _emit_io_call_expr(self, node: ASTNode) -> str:
        """io.print/io.println return void; using them as expressions is rejected."""
        raise CodegenError(
            "Zig backend: io.print/io.println cannot be used as expression values",
            node.span,
        )

    def _format_spec_for_arg(self, arg: ASTNode) -> str:
        """Pick a Zig print formatter for an argument node."""
        ty = self._type_map.get(id(arg)) if arg else None
        if ty is not None:
            name = getattr(ty, 'name', None)
            if name == "string":
                return "s"
            if name == "char":
                return "c"
            if name in {
                "i8", "i16", "i32", "i64",
                "u8", "u16", "u32", "u64",
                "isize", "usize",
                "f32", "f64",
                "bool",
            }:
                return ""
        if arg and arg.kind == NodeKind.LITERAL:
            if arg.literal_kind == LiteralKind.STRING:
                return "s"
            if arg.literal_kind == LiteralKind.CHAR:
                return "c"
            if arg.literal_kind in {
                LiteralKind.INTEGER,
                LiteralKind.FLOAT,
                LiteralKind.BOOLEAN,
            }:
                return ""
        return "any"

    def _convert_format_string(self, fmt_str: str, args: Optional[list[ASTNode]] = None) -> str:
        """Convert A7 format string {} to Zig placeholders.

        Bare {} pairs become Zig placeholders with a per-arg format spec.
        Any standalone '{' or '}' is escaped to '{{' / '}}' so a literal
        brace in user text does not get reinterpreted by Zig's std.fmt.
        """
        placeholder_idx = 0
        result = []
        i = 0
        s = fmt_str
        while i < len(s):
            if s[i:i + 2] in {'{{', '}}'}:
                result.append(s[i:i + 2])
                i += 2
            elif s[i] == '{' and i + 1 < len(s) and s[i + 1] == '}':
                if args and placeholder_idx < len(args):
                    spec = self._format_spec_for_arg(args[placeholder_idx])
                else:
                    spec = "any"
                result.append('{' + spec + '}')
                placeholder_idx += 1
                i += 2
            elif s[i] == '{':
                result.append('{{')
                i += 1
            elif s[i] == '}':
                result.append('}}')
                i += 1
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
            else:
                code = ord(ch)
                if code < 0x20 or code == 0x7F:
                    # Zig string literals reject most control bytes; emit
                    # an explicit hex escape so the generated source is
                    # always valid regardless of the input bytes.
                    out.append(f"\\x{code:02x}")
                else:
                    out.append(ch)
        out.append('"')
        return "".join(out)

    def _collect_targeted_loops(self, root: ASTNode) -> Set[int]:
        """Resolve each labeled transfer to its nearest enclosing loop identity."""
        targeted: Set[int] = set()
        stack = [(root, ())]
        loop_kinds = {NodeKind.WHILE, NodeKind.FOR, NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED}
        while stack:
            node, loops = stack.pop()
            if node.kind == NodeKind.FUNCTION:
                # Nested functions cannot transfer into their enclosing function.
                if node.body:
                    stack.append((node.body, ()))
                continue
            if node.kind in {NodeKind.BREAK, NodeKind.CONTINUE} and node.label:
                for loop in reversed(loops):
                    if loop.label == node.label:
                        targeted.add(id(loop))
                        break
            if node.kind in loop_kinds:
                loops = (*loops, node)
            children = []
            for attr in self._AST_CHILD_ATTRS:
                value = getattr(node, attr, None)
                if isinstance(value, ASTNode):
                    children.append(value)
                elif isinstance(value, list):
                    children.extend(child for child in value if isinstance(child, ASTNode))
            stack.extend((child, loops) for child in reversed(children))
        return targeted

    def _loop_label_name(self, node: ASTNode) -> Optional[str]:
        if id(node) not in self._targeted_loops:
            return None
        name = "a7_loop_" + node.label
        base = name
        while name in self._emitted_loop_labels:
            name = self._unique_name(base)
        self._emitted_loop_labels.add(name)
        return name

    def _resolve_loop_label(self, label: Optional[str]) -> Optional[str]:
        if label is None:
            return None
        for original, emitted in reversed(self._loop_label_stack):
            if original == label:
                return emitted
        return None

    # === Helper methods ===

    def _binary_op_to_zig(self, op: BinaryOp, span=None) -> str:
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
        if op not in mapping:
            raise CodegenError(f"Zig backend: unsupported binary operator '{op.name}'", span)
        return mapping[op]

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
            if getattr(node, "implicit_deref_target", False):
                self._require_backend_approval(node, "deref")
                target = self._emit_implicit_deref(node.target)
            else:
                target = self._emit_expr(node.target) if node.target else "_"
            value = self._emit_expr(node.value) if node.value else "0"
            return self._assignment_text(node, target, value)
        elif node.kind == NodeKind.EXPRESSION_STMT and node.expression:
            value = self._emit_expr(node.expression)
            return value if self._expression_returns_void(node.expression) else "_ = " + value
        return "void"

    def _emit_statement_inline(self, node: ASTNode) -> str:
        """Emit a single statement as an inline string (no newline)."""
        if node.kind == NodeKind.EXPRESSION_STMT and node.expression:
            if self._is_io_call(node.expression):
                return self._emit_io_call_expr(node.expression)
            value = self._emit_expr(node.expression)
            return value if self._expression_returns_void(node.expression) else "_ = " + value
        elif node.kind == NodeKind.ASSIGNMENT:
            return self._emit_statement_as_expr(node)
        elif node.kind == NodeKind.CALL:
            value = self._emit_expr(node)
            return value if self._expression_returns_void(node) else "_ = " + value
        elif node.kind == NodeKind.DEL:
            expr = node.expression or node.expr
            if expr:
                e = self._emit_expr(expr)
                return f"if ({e}) |p| allocator.destroy(p)"
        return "void"

    def _write_indent(self) -> None:
        """Write current indentation to output."""
        self.output.write("    " * self.indent_level)
