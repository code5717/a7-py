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
from ..passes.safety import BackendPlan
from ..types import (
    ArrayType, EnumType, FunctionType, GenericInstanceType, GenericParamType,
    GenericValueArg, PointerType, PrimitiveType, ReferenceType, SliceType,
    StructType, UnionType,
)
from .base import CodeGenerator


# The one map from an A7 build profile to the Zig optimize mode. `release`
# keeps Zig's runtime safety checks; `fast` removes them.
ZIG_OPTIMIZE_MODE = {"debug": "Debug", "release": "ReleaseSafe", "fast": "ReleaseFast"}


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
        self._mutated_declarations: Set[int] = set()
        # Names the current function body mentions; a renamed local avoids them.
        self._used_identifiers: Set[str] = set()
        # Zig name of each nested function, keyed by node identity. A nested
        # function is emitted at file scope under this name.
        self._hoisted_names: Dict[int, str] = {}
        # Generic parameter names of the declaration being emitted.
        self._generic_env: Set[str] = set()
        # Top-level A7 names whose Zig name differs (`std` -> `std_1`).
        self._global_renames: Dict[str, str] = {}
        # Global variables another file-scope initializer reads.
        self._global_init_refs: Set[str] = set()
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
        # Preamble helpers (`__a7_zero`, `__a7_shl`, ...) the emitted code calls.
        self._helpers: Set[str] = set()
        self._global_names: Set[str] = set()
        self._global_consts: Set[str] = set()
        # Tag names of each top-level union, for matches on a generic instance.
        self._union_tags: Dict[str, tuple[str, ...]] = {}
        # Untyped constants in scope (`SIZE :: 4`); `_visit_const` emits no
        # Zig declaration for them.
        self._untyped_consts: Dict[str, ASTNode] = {}

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
        if profile not in ZIG_OPTIMIZE_MODE:
            raise CodegenError(f"Zig backend: unknown build profile '{profile}'")
        self._profile = profile
        self._force_wrapping = bool(no_nonwrap)
        self._used_identifiers = set()
        self._hoisted_names = {}
        self._generic_env = set()
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
        self._helpers = set()
        self._global_renames = self._plan_global_renames(ast)
        # Every file-scope Zig name a local must not shadow: the user's
        # declarations under their emitted names, and the preamble's.
        self._global_names = {
            self._global_renames.get(d.name, d.name) for d in (ast.declarations or []) if d.name
        } | self._PREAMBLE_NAMES
        self._global_init_refs = self._collect_global_init_refs(ast)
        self._global_consts = {
            d.name for d in (ast.declarations or []) if d.name and d.kind == NodeKind.CONST
        }
        self._union_tags = {
            d.name: tuple(field.name for field in (d.fields or []) if field.name)
            for d in (ast.declarations or []) if d.name and d.kind == NodeKind.UNION
        }
        self._untyped_consts = {
            d.name: d for d in (ast.declarations or [])
            if d.name and d.kind == NodeKind.CONST and d.value and getattr(d, "untyped_binding", False)
        }

        # Implicit declarations emit only when user code or a runtime hook uses them.
        self._stdlib_decl_names = {d.name for d in ast.declarations or []
                                   if getattr(d, "stdlib_declaration", False)}
        self._stdlib_types_needed = set()
        # First pass: scan for features that need preamble items
        self._scan_features(ast)

        # Second pass: generate code
        self.visit(ast)

        # After the body: emission records which helpers it called.
        preamble = self._emit_preamble()

        code = self._substitute_discards(self.output.getvalue())
        return self._normalize_output(preamble + code)

    def _substitute_discards(self, text: str) -> str:
        """Replace discard markers, dropping the line when the discard is empty.

        Most markers sit on their own indented line (`_visit_var`,
        `_visit_const`). When the declared name is used later the discard
        resolves to "" and the whole line — indent and newline included —
        is removed so no stray blank line survives. A mid-line marker
        (`_emit_match_expr_with_captures`) falls through to the plain
        substitution, which matches the previous behavior exactly.
        """
        def _replace_line(match: "re.Match[str]") -> str:
            marker = f"\x00discard_{match.group(2)}\x00"
            replacement = self._discard_replacements.get(marker, "")
            if not replacement:
                return ""
            return f"{match.group(1)}{replacement}{match.group(3)}"

        text = re.sub(
            r"(?m)^([ \t]*)\x00discard_(\d+)\x00[ \t]*(\n|\Z)",
            _replace_line,
            text,
        )
        return re.sub(
            r"\x00discard_\d+\x00",
            lambda match: self._discard_replacements.get(match.group(), ""),
            text,
        )

    #: Binary operators whose left-nested same-operator chains regroup
    #: without changing evaluation order: `((a + b) + c)` parses exactly
    #: like `(a + b + c)`. Only the left child is ever stripped; stripping
    #: a right-nested chain would regroup float rounding.
    _ASSOC_CHAIN_OPS = frozenset({
        BinaryOp.ADD, BinaryOp.MUL,
        BinaryOp.AND, BinaryOp.OR,
        BinaryOp.BIT_AND, BinaryOp.BIT_OR, BinaryOp.BIT_XOR,
    })

    @staticmethod
    def _strip_condition_parens(text: str, node: Optional[ASTNode]) -> str:
        """Drop one outer parenthesis pair from a branch condition.

        Binary and unary expressions render fully parenthesized, and the
        `if (...)` / `while (...)` wrapper already groups, so `if ((x == 1))`
        becomes `if (x == 1)`. Shapes that render bare (calls, builtins such
        as `@divTrunc`, identifiers) or multiline (switch) pass through.
        A static leaf on purpose: it calls no generator method, so the
        no-recursion call-graph ratchet is unaffected.
        """
        if node is not None and node.kind in (NodeKind.BINARY, NodeKind.UNARY):
            if len(text) >= 2 and text.startswith("(") and text.endswith(")"):
                return text[1:-1]
        return text

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

        seen_types = set()

        def visitor(node):
            if not getattr(node, "stdlib_declaration", False):
                # Inferred types and nested generic arguments need declarations too.
                pending_types = [self._type_map.get(id(node))]
                while pending_types:
                    type_ = pending_types.pop()
                    if type_ is None or id(type_) in seen_types:
                        continue
                    seen_types.add(id(type_))
                    name = type_.base_name if isinstance(type_, GenericInstanceType) else getattr(type_, "name", None)
                    if name in self._stdlib_decl_names:
                        self._stdlib_types_needed.add(name)
                    if isinstance(type_, GenericInstanceType):
                        pending_types.extend(type_.type_args)
                    elif isinstance(type_, (ArrayType, SliceType)):
                        pending_types.append(type_.element_type)
                    elif isinstance(type_, ReferenceType):
                        pending_types.append(type_.referent_type)
                    elif isinstance(type_, PointerType):
                        pending_types.append(type_.pointee_type)
                    elif isinstance(type_, FunctionType):
                        pending_types.extend((*type_.param_types, type_.return_type))
                    elif isinstance(type_, (StructType, UnionType)):
                        pending_types.extend(field.field_type for field in type_.fields)
                for name in (node.name, node.struct_type, node.enum_type):
                    if name in self._stdlib_decl_names:
                        self._stdlib_types_needed.add(name)
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
                elif canonical == "std.io.println_ok":
                    self._needs_std = True
                    self._io_streams_needed.update(("stdout", "print_ok"))
                elif canonical == "std.io.read_line":
                    self._needs_std = True
                    self._io_streams_needed.update(("stdin", "read_line"))

        self._walk_ast(root, visitor)
        if {"print_ok", "read_line"} & self._io_streams_needed:
            self._stdlib_types_needed.update((
                self._symbol_table.prelude_symbols["Result"].type.name,
                self._symbol_table.stdlib_type_symbols["IoErr"].type.name,
            ))

    _HELPER_SOURCE = {
        "zero": (
            "// A declaration without an initializer starts as all zeros.",
            "fn __a7_zero(comptime T: type) T {",
            "    switch (@typeInfo(T)) {",
            "        .int, .float => return 0,",
            "        .bool => return false,",
            "        .optional => return null,",
            '        .@"enum" => |info| return @field(T, info.fields[0].name),',
            "        // Fill in place. A `**` constant of many structs makes LLVM take",
            "        // minutes on an optimized build.",
            "        .array => |info| {",
            "            var value: T = undefined;",
            "            @memset(&value, __a7_zero(info.child));",
            "            return value;",
            "        },",
            "        // A7 references are optionals, so a bare pointer is a function",
            "        // pointer. It has no zero value and stays undefined.",
            "        .pointer => |info| return if (info.size == .slice) &.{} else undefined,",
            '        .@"struct" => |info| {',
            "            var value: T = undefined;",
            "            inline for (info.fields) |field| @field(value, field.name) = __a7_zero(field.type);",
            "            return value;",
            "        },",
            '        .@"union" => |info| return @unionInit(T, info.fields[0].name, __a7_zero(info.fields[0].type)),',
            '        else => @compileError("a7: no zero value for " ++ @typeName(T)),',
            "    }",
            "}",
        ),
        "new": (
            "// `new T` returns zeroed memory, or nil when the allocation fails.",
            "fn __a7_new(comptime T: type) ?*T {",
            "    const ptr = allocator.create(T) catch return null;",
            "    ptr.* = __a7_zero(T);",
            "    return ptr;",
            "}",
        ),
        "div": (
            "// Signed `MIN / -1` wraps to MIN in every profile.",
            "fn __a7_div(comptime T: type, a: T, b: T) T {",
            "    if (@typeInfo(T) == .int and @typeInfo(T).int.signedness == .signed and b == -1) return 0 -% a;",
            "    return @divTrunc(a, b);",
            "}",
        ),
        "rem": (
            "// Signed `MIN % -1` is 0 in every profile.",
            "fn __a7_rem(comptime T: type, a: T, b: T) T {",
            "    if (@typeInfo(T) == .int and @typeInfo(T).int.signedness == .signed and b == -1) return 0;",
            "    return @rem(a, b);",
            "}",
        ),
        "shl": (
            "// A shift count below zero or not below the bit width panics in every profile.",
            "fn __a7_shl(comptime T: type, a: T, n: anytype) T {",
            '    if (n < 0 or n >= @bitSizeOf(T)) @panic("shift count out of range");',
            "    return a << @intCast(n);",
            "}",
        ),
        "shr": (
            "// A shift count below zero or not below the bit width panics in every profile.",
            "fn __a7_shr(comptime T: type, a: T, n: anytype) T {",
            '    if (n < 0 or n >= @bitSizeOf(T)) @panic("shift count out of range");',
            "    return a >> @intCast(n);",
            "}",
        ),
    }

    def _emit_preamble(self) -> str:
        """Generate the Zig preamble (imports, allocator, etc.)."""
        lines = []
        if self._needs_std:
            lines.append("const std = @import(\"std\");")
        if self._needs_allocator:
            if self._profile != "debug":
                lines.append("const allocator = std.heap.smp_allocator;")
            else:
                lines.append("const allocator = std.heap.page_allocator;")
        if "new" in self._helpers:
            self._helpers.add("zero")
        for helper, source in self._HELPER_SOURCE.items():
            if helper in self._helpers:
                lines.extend(source)
        if self._io_streams_needed:
            lines.append("var __a7_io: ?std.Io = null;")
        if "stdout" in self._io_streams_needed:
            lines.append("var __a7_stdout_buf: [4096]u8 = undefined;")
            lines.append("var __a7_stdout_writer: ?std.Io.File.Writer = null;")
            lines.append("var __a7_stdout_is_tty = false;")
            lines.append("// A reader that closed the pipe ends the program quietly, as SIGPIPE does in C.")
            lines.append("fn __a7_stdout_failed(comptime what: []const u8) noreturn {")
            lines.append("    if (__a7_stdout_writer.?.err) |err| if (err == error.BrokenPipe) std.process.exit(0);")
            lines.append('    @panic("a7 stdout " ++ what ++ " failed");')
            lines.append("}")
            lines.append("fn __a7_stdout_flush() void {")
            lines.append('    __a7_stdout_writer.?.interface.flush() catch __a7_stdout_failed("flush");')
            lines.append("}")
            lines.append("fn __a7_stdout_print(comptime fmt: []const u8, args: anytype) void {")
            lines.append("    const out = &__a7_stdout_writer.?.interface;")
            lines.append('    out.print(fmt, args) catch __a7_stdout_failed("write");')
            lines.append("    // A terminal is line-buffered: a finished line is shown at once.")
            lines.append("    if (__a7_stdout_is_tty and std.mem.indexOfScalar(u8, out.buffered(), '\\n') != null) __a7_stdout_flush();")
            lines.append("}")
            lines.append("// Text printed before a panic reaches stdout before the panic message.")
            lines.append("fn __a7_panic(msg: []const u8, first_trace_addr: ?usize) noreturn {")
            lines.append("    if (__a7_stdout_writer) |*writer| writer.interface.flush() catch {};")
            lines.append("    std.debug.defaultPanic(msg, first_trace_addr orelse @returnAddress());")
            lines.append("}")
            lines.append("pub const panic = std.debug.FullPanic(__a7_panic);")
        if "stderr" in self._io_streams_needed:
            lines.append("fn __a7_stderr_print(comptime fmt: []const u8, args: anytype) void {")
            if "stdout" in self._io_streams_needed:
                lines.append("    __a7_stdout_flush();")
            lines.append("    var __a7_stream_buf: [1024]u8 = undefined;")
            lines.append("    var __a7_writer = std.Io.File.stderr().writerStreaming(__a7_io.?, &__a7_stream_buf);")
            lines.append('    __a7_writer.interface.print(fmt, args) catch @panic("a7 stderr write failed");')
            lines.append('    __a7_writer.interface.flush() catch @panic("a7 stderr flush failed");')
            lines.append("}")
        if {"print_ok", "read_line"} & self._io_streams_needed:
            result_name = self._emit_semantic_type(self._symbol_table.prelude_symbols["Result"].type)
            error_name = self._emit_semantic_type(self._symbol_table.stdlib_type_symbols["IoErr"].type)
            lines.append(f"const __a7_IoResult = {result_name}(usize, {error_name});")
        if "print_ok" in self._io_streams_needed:
            lines.append("fn __a7_stdout_print_ok(comptime fmt: []const u8, args: anytype) __a7_IoResult {")
            lines.append("    __a7_stdout_writer.?.interface.print(fmt, args) catch return .{ .err = .WriteFailed };")
            lines.append("    __a7_stdout_writer.?.interface.flush() catch return .{ .err = .FlushFailed };")
            lines.append("    return .{ .ok = std.fmt.count(fmt, args) };")
            lines.append("}")
        if "read_line" in self._io_streams_needed:
            # One reader for the whole program: a reader made per call would
            # drop the bytes it buffered past the first newline.
            lines.append("var __a7_stdin_buf: [4096]u8 = undefined;")
            lines.append("var __a7_stdin_reader: ?std.Io.File.Reader = null;")
            lines.append("fn __a7_stdin_read_line(buf: []u8) __a7_IoResult {")
            if "stdout" in self._io_streams_needed:
                # A prompt written with `io.print` must reach the terminal first.
                lines.append("    __a7_stdout_flush();")
            lines.append("    var n: usize = 0;")
            lines.append("    while (n < buf.len) {")
            lines.append("        const b = __a7_stdin_reader.?.interface.takeByte() catch |e| switch (e) {")
            lines.append("            error.EndOfStream => if (n == 0) return .{ .err = .EndOfStream } else break,")
            lines.append("            error.ReadFailed => return .{ .err = .ReadFailed },")
            lines.append("        };")
            lines.append("        buf[n] = b;")
            lines.append("        n += 1;")
            lines.append("        if (b == '\\n') break;")
            lines.append("    }")
            lines.append("    return .{ .ok = n };")
            lines.append("}")
        if self._io_streams_needed:
            lines.append("pub fn main(init: std.process.Init) void {")
            lines.append("    __a7_io = init.io;")
            if "stdout" in self._io_streams_needed:
                # writerStreaming, not writer: Zig 0.16.0 File.writer starts
                # in positional mode at offset 0, so each fresh writer
                # overwrote earlier output when the stream is a regular file.
                lines.append("    __a7_stdout_writer = std.Io.File.stdout().writerStreaming(__a7_io.?, &__a7_stdout_buf);")
                lines.append("    __a7_stdout_is_tty = std.Io.File.stdout().isTty(__a7_io.?) catch false;")
            if "stdin" in self._io_streams_needed:
                lines.append("    __a7_stdin_reader = std.Io.File.stdin().readerStreaming(__a7_io.?, &__a7_stdin_buf);")
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
        'type_arguments', 'generic_params', 'fields', 'field_type',
        'resolved_type', 'parameters', 'variants',
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
                # `p = 9` on a `ref` writes the referent (`p.?.* = 9`); the
                # binding itself stays constant.
                writes_referent = (
                    getattr(node, "implicit_deref_target", False)
                    and node.target is not None and node.target.kind == NodeKind.IDENTIFIER
                )
                if not writes_referent:
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
            elif n.kind == NodeKind.PATTERN_IDENTIFIER:
                # `case limit:` reads `limit`; a capture pattern declares it.
                if n.name and n.name != "_" and not getattr(n, "is_capture_pattern", False):
                    used.add(n.name)

        self._walk_ast(node, visitor)
        return used

    def _collect_nested_functions(self, body: ASTNode) -> list:
        """FUNCTION nodes declared in a function body, at any block depth.

        A nested function's own body is not entered: its nested functions are
        collected when it is emitted. Iterative.
        """
        nested = []
        stack = [body]
        while stack:
            node = stack.pop()
            children = []
            for attr in self._AST_CHILD_ATTRS:
                value = getattr(node, attr, None)
                if isinstance(value, ASTNode):
                    children.append(value)
                elif isinstance(value, list):
                    children.extend(child for child in value if isinstance(child, ASTNode))
            for child in reversed(children):
                if child.kind == NodeKind.FUNCTION:
                    nested.append(child)
                else:
                    stack.append(child)
        nested.reverse()
        return nested

    def _declared_names(self, function: ASTNode) -> Set[str]:
        """Parameters and locals a function declares, nested functions excluded."""
        names = {p.name for p in (function.parameters or []) if p.name}

        def visitor(node):
            if node.kind in (NodeKind.VAR, NodeKind.CONST, NodeKind.TYPE_ALIAS) and node.name:
                names.add(node.name)
            elif node.kind in (NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED):
                names.update(name for name in (node.iterator, node.index_var) if name)
            elif node.kind == NodeKind.PATTERN_IDENTIFIER and getattr(node, "is_capture_pattern", False):
                names.add(node.name)
            elif node.kind == NodeKind.PATTERN_ENUM and not (node.enum_type or "") and node.name:
                names.add(node.name)

        stack = [function.body] if function.body else []
        while stack:
            node = stack.pop()
            visitor(node)
            for attr in self._AST_CHILD_ATTRS:
                value = getattr(node, attr, None)
                if isinstance(value, ASTNode) and value.kind != NodeKind.FUNCTION:
                    stack.append(value)
                elif isinstance(value, list):
                    stack.extend(c for c in value if isinstance(c, ASTNode) and c.kind != NodeKind.FUNCTION)
        return names

    def _reject_captures(self, nested: ASTNode, outer_names: Set[str]) -> None:
        """A nested function is emitted at file scope, so it cannot read a
        parameter or local of the function it is declared in."""
        own = self._declared_names(nested)
        captured = sorted(
            name for name in self._collect_used_identifiers(nested.body)
            if name in outer_names and name not in own
        ) if nested.body else []
        if captured:
            raise CodegenError(
                f"Zig backend: nested function '{nested.name}' uses '{captured[0]}' from the "
                "enclosing function; pass it as a parameter",
                nested.span,
            )

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
        if emitted in active or emitted.startswith("__a7_"):
            base = self._user_base_name(name)
            suffix = 1
            while f"{base}_{suffix}" in active or f"{base}_{suffix}" in self._used_identifiers:
                suffix += 1
            emitted = f"{base}_{suffix}"
        if self._scope_stack:
            self._scope_stack[-1].add(name)
        self._rename_map[name] = emitted
        return emitted

    # File-scope names the preamble declares. `@"std"` is the same identifier
    # as `std`, so a user name that matches one is renamed, not quoted.
    _PREAMBLE_NAMES = frozenset({"std", "allocator", "panic", "main"})

    @staticmethod
    def _user_base_name(name: str) -> str:
        """Base for a renamed user binding; `__a7_` is the generator's prefix."""
        return "user" + name if name.startswith("__a7_") else name

    def _plan_global_renames(self, ast: ASTNode) -> Dict[str, str]:
        """Zig names for top-level declarations that collide with the preamble.

        `main` is not renamed here: `_visit_function` emits the entry point.
        A declaration of an imported file keeps its module prefix.
        """
        names = {d.name for d in (ast.declarations or []) if d.name}
        renames: Dict[str, str] = {}
        for decl in (ast.declarations or []):
            name = decl.name
            if not name or name in renames or getattr(decl, "module_emit_prefix", ""):
                continue
            if name == "main" or not (name in self._PREAMBLE_NAMES or name.startswith("__a7_")):
                continue
            base = self._user_base_name(name)
            suffix = 1
            while f"{base}_{suffix}" in names or f"{base}_{suffix}" in renames.values():
                suffix += 1
            renames[name] = f"{base}_{suffix}"
        return renames

    def _collect_global_init_refs(self, ast: ASTNode) -> Set[str]:
        """Global variables that a file-scope initializer reads.

        Zig evaluates a container-level initializer at compile time and a
        `var` is not a compile-time value. `_visit_var` gives each variable
        in this set a constant holding its initial value, and file-scope
        initializers read that constant.
        """
        global_vars = {
            d.name for d in (ast.declarations or []) if d.kind == NodeKind.VAR and d.name
        }
        refs: Set[str] = set()

        def visitor(node):
            if node.kind == NodeKind.IDENTIFIER and node.name in global_vars:
                refs.add(node.name)

        for decl in (ast.declarations or []):
            if decl.kind in (NodeKind.VAR, NodeKind.CONST) and decl.value is not None:
                self._walk_ast(decl.value, visitor)
        return refs

    _ZIG_KEYWORDS = frozenset({
        "addrspace", "align", "allowzero", "and", "anyframe", "anytype",
        "asm", "async", "await", "break", "callconv", "catch", "comptime",
        "const", "continue", "defer", "else", "enum", "errdefer", "error",
        "export", "extern", "fn", "for", "if", "inline", "linksection",
        "noalias", "noinline", "nosuspend", "opaque", "or", "orelse",
        "packed", "pub", "resume", "return", "section", "struct",
        "suspend", "switch", "test", "threadlocal", "try", "union",
        "unreachable", "usingnamespace", "var", "volatile", "while",
        "type", "undefined", "null", "not",
    })
    # Zig rejects a declaration that shadows a primitive ("name shadows
    # primitive 'u1'") unless it is written `@"u1"`.
    _ZIG_PRIMITIVES = frozenset({
        "isize", "usize", "c_char", "c_short", "c_ushort", "c_int", "c_uint",
        "c_long", "c_ulong", "c_longlong", "c_ulonglong", "c_longdouble",
        "f16", "f32", "f64", "f80", "f128", "bool", "void", "noreturn",
        "anyerror", "anyopaque", "comptime_int", "comptime_float",
        "true", "false",
    })
    _ZIG_SIZED_INT = re.compile(r"[iu][0-9]+\Z")

    @classmethod
    def _quote_identifier(cls, name: str) -> str:
        """Quote a declared or referenced name that Zig reserves."""
        if name in cls._ZIG_KEYWORDS or name in cls._ZIG_PRIMITIVES or cls._ZIG_SIZED_INT.match(name):
            return f'@"{name}"'
        return name

    @classmethod
    def _quote_field(cls, name: str) -> str:
        """Quote a field, variant or tag name.

        These live in their own namespace, so a primitive name is legal there
        and `zig fmt` removes the quotes; only a keyword needs them.
        """
        return f'@"{name}"' if name in cls._ZIG_KEYWORDS else name

    def _file_scope_name(self, name: str) -> str:
        """Zig name of a declaration: renamed only when it sits at file scope."""
        return name if self._in_function else self._global_renames.get(name, name)

    def _resolve_name(self, name: str) -> str:
        """Resolve a name through the local rename map, then the global one."""
        return self._rename_map.get(name, self._global_renames.get(name, name))

    def _statement_work(self, action, payload):
        # Only this driver resumes statement frames; children yield requests.
        pending = [self._statement_steps(action, payload)]
        result = None
        try:
            while pending:
                try:
                    action, payload = pending[-1].send(result)
                except StopIteration as finished:
                    pending.pop()
                    result = finished.value
                    continue
                pending.append(self._statement_steps(action, payload))
                result = None
        finally:
            for frame in reversed(pending):
                frame.close()

    def _statement_steps(self, action, payload):
        if action == "visit":
            node, = payload
            if node is None:
                return

            kind = node.kind

            if kind == NodeKind.PROGRAM:
                (yield ("_visit_program", (node,)))
            elif kind == NodeKind.FUNCTION:
                if id(node) in self._hoisted_names:
                    # Emitted at file scope by the enclosing `_visit_function`.
                    if node.name:
                        self._rename_map[node.name] = self._hoisted_names[id(node)]
                    return
                (yield ("_visit_function", (node,)))
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
                (yield ("_visit_block", (node,)))
            elif kind == NodeKind.IF_STMT:
                (yield ("_visit_if_stmt", (node,)))
            elif kind == NodeKind.WHILE:
                (yield ("_visit_while", (node,)))
            elif kind == NodeKind.FOR:
                (yield ("_visit_for", (node,)))
            elif kind == NodeKind.FOR_IN:
                (yield ("_visit_for_in", (node,)))
            elif kind == NodeKind.FOR_IN_INDEXED:
                (yield ("_visit_for_in_indexed", (node,)))
            elif kind == NodeKind.MATCH:
                (yield ("_visit_match", (node,)))
            elif kind == NodeKind.RETURN:
                self._visit_return(node)
            elif kind == NodeKind.BREAK:
                self._visit_break(node)
            elif kind == NodeKind.CONTINUE:
                self._visit_continue(node)
            elif kind == NodeKind.FALL:
                self._visit_fall(node)
            elif kind == NodeKind.DEFER:
                (yield ("_visit_defer", (node,)))
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
            return

        if action == "_visit_program":
            node, = payload
            for decl in (node.declarations or []):
                if getattr(decl, "stdlib_declaration", False) and decl.name not in self._stdlib_types_needed:
                    continue
                (yield ("visit", (decl,)))
                self.output.write("\n")
            return

        if action == "_visit_function":
            node, = payload
            name = node.name or "anonymous"
            emit_prefix = getattr(node, "module_emit_prefix", "")

            is_main = (name == "main" and not emit_prefix and id(node) not in self._hoisted_names)
            if id(node) in self._hoisted_names:
                emitted_name = self._hoisted_names[id(node)]
            elif is_main and self._io_streams_needed:
                emitted_name = "__a7_user_main"
            elif emit_prefix:
                emitted_name = f"{emit_prefix}{name}"
            else:
                emitted_name = self._global_renames.get(name, name)

            saved_mutated_declarations = self._mutated_declarations
            saved_used = self._used_identifiers
            saved_untyped_consts = self._untyped_consts
            saved_generic_env = self._generic_env
            saved_rename_map = self._rename_map
            saved_snapshots = self._rename_snapshots
            self._untyped_consts = dict(saved_untyped_consts)
            self._mutated_declarations = self._collect_mutated_declarations(node.body) if node.body else set()
            self._used_identifiers = self._collect_used_identifiers(node.body) if node.body else set()

            # A nested function is emitted at file scope, before its parent, under
            # a name no user declaration can spell. It sees no local of the parent.
            nested_functions = self._collect_nested_functions(node.body) if node.body else []
            if nested_functions:
                outer_names = self._declared_names(node)
                for nested in nested_functions:
                    self._reject_captures(nested, outer_names)
                    self._hoisted_names[id(nested)] = self._unique_name(f"__a7_fn_{nested.name or 'anonymous'}")
                # Nested functions call each other by their hoisted names.
                self._rename_map = dict(saved_rename_map)
                self._rename_map.update(
                    (nested.name, self._hoisted_names[id(nested)]) for nested in nested_functions if nested.name
                )
                self._rename_snapshots = []
                for nested in nested_functions:
                    (yield ("_visit_function", (nested,)))
                    self.output.write("\n")
                self._rename_map = saved_rename_map
                self._rename_snapshots = saved_snapshots

            # Generic parameters: the declared list, then every `$T` the
            # signature names, in the order `_generic_call_args` passes them.
            generic_params = [param.name for param in (node.generic_params or []) if param.name]
            discovered: list[str] = []
            for param in (node.parameters or []):
                self._collect_generic_type_names(param.param_type, discovered, signature_order=True)
            self._collect_generic_type_names(node.return_type, discovered, signature_order=True)
            generic_params.extend(n for n in dict.fromkeys(discovered) if n not in generic_params)
            self._generic_env = set(generic_params)

            self._push_scope()
            params = node.parameters or []
            for i, param in enumerate(params):
                if param.param_type is None:
                    raise CodegenError(
                        f"Zig backend: parameter '{param.name or i}' of '{name}' has no type",
                        param.span or node.span,
                    )
            parameter_names = [self._declare_var_in_scope(p.name) if p.name else "_" for p in params]
            parameter_types = [self._emit_type_node(p.param_type) for p in params]
            # A function without a return type returns nothing.
            return_type = self._emit_type_node(node.return_type) if node.return_type else "void"
            comptime_params = self._comptime_param_list(
                node, generic_params,
                [p.param_type for p in params] + [node.return_type, node.body],
            )

            # The body is emitted first: a parameter Zig never reads must be
            # written `_`, and only the emitted body says which bindings it read.
            uses_before = [self._identifier_uses.get(emitted, 0) for emitted in parameter_names]
            outer_output = self.output
            self.output = StringIO()
            was_in_function = self._in_function
            self._in_function = True
            if node.body and (node.body.statements or []):
                (yield ("_visit_block_inline", (node.body, [],)))
            else:
                self.output.write("{}\n")
            self._in_function = was_in_function
            body = self.output.getvalue()
            self.output = outer_output
            self._pop_scope()

            rendered_params = [comptime_params] if comptime_params else []
            for emitted, before, ptype in zip(parameter_names, uses_before, parameter_types):
                used = emitted != "_" and self._identifier_uses.get(emitted, 0) != before
                rendered_params.append(f"{self._quote_identifier(emitted) if used else '_'}: {ptype}")

            prefix = "pub " if ((is_main and not self._io_streams_needed) or getattr(node, 'is_public', False)) else ""
            self._write_indent()
            self.output.write(
                f"{prefix}fn {self._quote_identifier(emitted_name)}({', '.join(rendered_params)}) {return_type} "
            )
            self.output.write(body)

            self._mutated_declarations = saved_mutated_declarations
            self._used_identifiers = saved_used
            self._untyped_consts = saved_untyped_consts
            self._generic_env = saved_generic_env
            return

        if action == "_visit_block":
            node, = payload
            self._write_indent()
            (yield ("_visit_block_inline", (node, None,)))
            return

        if action == "_visit_block_inline":
            node, prelude_lines, = payload
            self.output.write("{\n")
            self.indent()
            self._push_scope()

            for line in prelude_lines or []:
                self._write_indent()
                self.output.write(line)
                self.output.write("\n")

            # A nested function is callable in its whole block, so its hoisted
            # name is bound before the first statement.
            for stmt in (node.statements or []):
                if stmt.kind == NodeKind.FUNCTION and stmt.name and id(stmt) in self._hoisted_names:
                    self._rename_map[stmt.name] = self._hoisted_names[id(stmt)]

            for stmt in (node.statements or []):
                (yield ("visit", (stmt,)))

            self._pop_scope()
            self.dedent()
            self._write_indent()
            self.output.write("}\n")
            return

        if action == "_visit_switch_block":
            node, = payload
            self.output.write("{\n")
            self.indent()
            self._push_scope()

            for stmt in (node.statements or []):
                (yield ("visit", (stmt,)))

            self._pop_scope()
            self.dedent()
            self._write_indent()
            self.output.write("},\n")
            return

        if action == "_visit_if_stmt":
            node, = payload
            self._write_indent()
            cond = self._strip_condition_parens(self._emit_expr(node.condition), node.condition)
            self.output.write(f"if ({cond}) ")

            if node.then_stmt and node.then_stmt.kind == NodeKind.BLOCK:
                (yield ("_visit_block_inline", (node.then_stmt, None,)))
            elif node.then_stmt:
                self.output.write("{\n")
                self.indent()
                self._push_scope()
                (yield ("visit", (node.then_stmt,)))
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
                    (yield ("_visit_block_inline", (node.else_stmt, None,)))
                elif node.else_stmt.kind == NodeKind.IF_STMT:
                    (yield ("_visit_else_chain", (node.else_stmt,)))
                else:
                    self.output.write("{\n")
                    self.indent()
                    self._push_scope()
                    (yield ("visit", (node.else_stmt,)))
                    self._pop_scope()
                    self.dedent()
                    self._write_indent()
                    self.output.write("}\n")
            return

        if action == "_visit_else_chain":
            node, = payload
            current = node
            while current is not None:
                if current.kind == NodeKind.IF_STMT:
                    cond = self._strip_condition_parens(self._emit_expr(current.condition), current.condition)
                    self.output.write(f"if ({cond}) ")
                    if current.then_stmt and current.then_stmt.kind == NodeKind.BLOCK:
                        (yield ("_visit_block_inline", (current.then_stmt, None,)))
                    elif current.then_stmt:
                        self.output.write("{\n")
                        self.indent()
                        self._push_scope()
                        (yield ("visit", (current.then_stmt,)))
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
                    (yield ("_visit_block_inline", (current, None,)))
                    break
                else:
                    self.output.write("{\n")
                    self.indent()
                    self._push_scope()
                    (yield ("visit", (current,)))
                    self._pop_scope()
                    self.dedent()
                    self._write_indent()
                    self.output.write("}\n")
                    break
            return

        if action == "_visit_while":
            node, = payload
            self._write_indent()
            emitted_label = self._loop_label_name(node)
            if emitted_label:
                self.output.write(f"{emitted_label}: ")
            if node.condition:
                cond = self._strip_condition_parens(self._emit_expr(node.condition), node.condition)
                self.output.write(f"while ({cond}) ")
            else:
                self.output.write("while (true) ")

            self._loop_label_stack.append((node.label, emitted_label))
            if node.body and node.body.kind == NodeKind.BLOCK:
                (yield ("_visit_block_inline", (node.body, None,)))
            elif node.body:
                self.output.write("{\n")
                self.indent()
                self._push_scope()
                (yield ("visit", (node.body,)))
                self._pop_scope()
                self.dedent()
                self._write_indent()
                self.output.write("}\n")
            self._loop_label_stack.pop()
            return

        if action == "_visit_for":
            node, = payload
            self._write_indent()

            # Infinite loop: for { ... }
            if not node.init and not node.condition and not node.update:
                emitted_label = self._loop_label_name(node)
                if emitted_label:
                    self.output.write(f"{emitted_label}: ")
                self.output.write("while (true) ")
                self._loop_label_stack.append((node.label, emitted_label))
                if node.body and node.body.kind == NodeKind.BLOCK:
                    (yield ("_visit_block_inline", (node.body, None,)))
                elif node.body:
                    self.output.write("{\n")
                    self.indent()
                    self._push_scope()
                    (yield ("visit", (node.body,)))
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
                (yield ("visit", (node.init,)))

            # While with continue expression
            self._write_indent()
            emitted_label = self._loop_label_name(node)
            if emitted_label:
                self.output.write(f"{emitted_label}: ")
            if node.condition:
                cond = self._strip_condition_parens(self._emit_expr(node.condition), node.condition)
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
                (yield ("_visit_block_inline", (node.body, None,)))
            elif node.body:
                self.output.write("{\n")
                self.indent()
                self._push_scope()
                (yield ("visit", (node.body,)))
                self._pop_scope()
                self.dedent()
                self._write_indent()
                self.output.write("}\n")
            self._loop_label_stack.pop()
            self._pop_scope()

            self.dedent()
            self._write_indent()
            self.output.write("}\n")
            return

        if action == "_visit_for_in":
            node, = payload
            self._write_indent()
            iterable = self._emit_expr(node.iterable)
            if node.iterable is not None and node.iterable.kind == NodeKind.ARRAY_INIT:
                iterable = self._typed_array_literal(node.iterable, iterable)
            self._push_scope()
            iter_name = self._declare_var_in_scope(node.iterator) if node.iterator else "_"
            before = {iter_name: self._identifier_uses.get(iter_name, 0)}
            emitted_label = self._loop_label_name(node)
            outer_output = self.output
            self.output = StringIO()

            self._loop_label_stack.append((node.label, emitted_label))
            if node.body and node.body.kind == NodeKind.BLOCK:
                (yield ("_visit_block_inline", (node.body, None,)))
            elif node.body:
                self.output.write("{\n")
                self.indent()
                self._push_scope()
                (yield ("visit", (node.body,)))
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
            return

        if action == "_visit_for_in_indexed":
            node, = payload
            self._write_indent()
            iterable = self._emit_expr(node.iterable)
            if node.iterable is not None and node.iterable.kind == NodeKind.ARRAY_INIT:
                iterable = self._typed_array_literal(node.iterable, iterable)
            self._push_scope()
            iter_name = self._declare_var_in_scope(node.iterator) if node.iterator else "_"
            index_name = self._declare_var_in_scope(node.index_var) if node.index_var else "_"
            before = {name: self._identifier_uses.get(name, 0) for name in (iter_name, index_name)}
            emitted_label = self._loop_label_name(node)
            outer_output = self.output
            self.output = StringIO()

            self._loop_label_stack.append((node.label, emitted_label))
            if node.body and node.body.kind == NodeKind.BLOCK:
                (yield ("_visit_block_inline", (node.body, None,)))
            elif node.body:
                self.output.write("{\n")
                self.indent()
                self._push_scope()
                (yield ("visit", (node.body,)))
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
            return

        if action == "_visit_match":
            node, = payload
            tags = self._match_union_tags(node)
            if tags is None:
                if self._match_has_fall(node):
                    (yield ("_visit_match_with_fall", (node,)))
                    return
                if self._match_has_capture(node) or not self._match_fits_switch(node):
                    (yield ("_visit_match_as_if_chain", (node,)))
                    return
                arms = list(node.cases or [])
                wildcard = None
                exhaustive = self._match_covers_closed_type(node)
            else:
                # Tag matches always take the switch: only a prong can bind a
                # payload (`.tag(bind)` → `.tag => |bind|`). A `fall` inside a tag
                # arm reaches `_visit_fall` with no fall context and fails there.
                arms, wildcard, exhaustive = self._tag_match_arms(node, tags)

            # The A7 body for values no arm names: `case _:` or `else:`.
            rest: Optional[list[ASTNode]] = None
            if wildcard is not None:
                rest = self._case_statements(wildcard)
            elif node.else_case:
                rest = self._else_case_statements(node.else_case)
                if len(rest) == 1 and rest[0].kind == NodeKind.BLOCK:
                    # `else: { ... }` parses as one block; the prong supplies the braces.
                    rest = list(rest[0].statements or [])

            if exhaustive and rest is not None:
                # Zig rejects an `else` prong once every value has a prong. The
                # body stays in a dead block so the names it uses still count as
                # used and mutated for Zig's unused-variable checks.
                self._write_indent()
                self.output.write("if (false) {\n")
                self.indent()
                self._push_scope()
                for stmt in rest:
                    (yield ("visit", (stmt,)))
                self._pop_scope()
                self.dedent()
                self._write_indent()
                self.output.write("}\n")
                rest = None

            self._write_indent()
            expr = self._emit_expr(node.expression)
            if tags is not None:
                expr = self._tag_scrutinee(node, expr)
            self.output.write(f"switch ({expr}) {{\n")
            self.indent()

            for case in arms:
                binding = self._match_tag_binding(case) if tags is not None else None
                patterns = ", ".join(self._emit_pattern(pattern) for pattern in (case.patterns or []))
                self._write_indent()
                body = getattr(case, "statement", None)
                if binding is None and body is not None and body.kind == NodeKind.BLOCK:
                    self.output.write(f"{patterns} => ")
                    (yield ("_visit_switch_block", (body,)))
                    continue
                self._push_scope()
                if binding is not None:
                    # Declared before it is written so a local, parameter or
                    # function of the same name renames the capture.
                    declared = self._declare_var_in_scope(binding)
                    self.output.write(f"{patterns} => |{self._quote_identifier(declared)}| {{\n")
                    self.indent()
                    self._write_indent()
                    self.output.write(self._pending_discard(declared) + "\n")
                else:
                    self.output.write(f"{patterns} => {{\n")
                    self.indent()
                for stmt in self._case_statements(case):
                    (yield ("visit", (stmt,)))
                self._pop_scope()
                self.dedent()
                self._write_indent()
                self.output.write("},\n")

            if rest is not None:
                self._write_indent()
                self.output.write("else => {\n")
                self.indent()
                self._push_scope()
                for stmt in rest:
                    (yield ("visit", (stmt,)))
                self._pop_scope()
                self.dedent()
                self._write_indent()
                self.output.write("},\n")
            elif tags is None and not exhaustive:
                # A statement match may handle no arm; the switch must still be
                # exhaustive for Zig. The validator rejects a tag match that
                # misses a tag, so a tag switch never needs this prong.
                self._write_indent()
                self.output.write("else => {},\n")

            self.dedent()
            self._write_indent()
            self.output.write("}\n")
            return

        if action == "_visit_match_as_if_chain":
            node, = payload
            scrutinee = self._unique_name("__a7_match")
            expr = self._emit_expr(node.expression)
            by_content = self._is_string_type(self._type_map.get(id(node.expression)))

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
                condition = self._emit_match_condition_zig(scrutinee, case.patterns or [], by_content)
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
                            (yield ("visit", (inner,)))
                    else:
                        (yield ("visit", (stmt,)))
                else:
                    for inner in case.statements or []:
                        (yield ("visit", (inner,)))
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
                    (yield ("visit", (stmt,)))
                self._pop_scope()
                self.dedent()
                self._write_indent()
                self.output.write("}")

            if emitted_branch or node.else_case:
                self.output.write("\n")

            self.dedent()
            self._write_indent()
            self.output.write("}\n")
            return

        if action == "_visit_match_with_fall":
            node, = payload
            scrutinee = self._unique_name("__a7_match")
            done_flag = self._unique_name("__a7_match_done")
            fall_flag = self._unique_name("__a7_match_fall")
            expr = self._emit_expr(node.expression)
            by_content = self._is_string_type(self._type_map.get(id(node.expression)))

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
                condition = self._emit_match_condition_zig(scrutinee, case.patterns or [], by_content)
                self._write_indent()
                self.output.write(f"if (!{done_flag} and !{fall_flag} and ({condition})) {fall_flag} = true;\n")
                (yield ("_emit_fall_case_body", (case, scrutinee, fall_flag, done_flag, case_index,)))
                case_index += 1

            if node.else_case:
                self._write_indent()
                self.output.write(f"if (!{done_flag} and !{fall_flag}) {fall_flag} = true;\n")
                (yield ("_emit_fall_else_body", (node.else_case, fall_flag, done_flag, case_index,)))

            self.dedent()
            self._write_indent()
            self.output.write("}\n")
            return

        if action == "_emit_fall_case_body":
            case, scrutinee, fall_flag, done_flag, case_index, = payload
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
                        (yield ("_visit_block_inline", (stmt, None,)))
                    else:
                        (yield ("visit", (stmt,)))
                else:
                    for stmt in case.statements or []:
                        (yield ("visit", (stmt,)))
            finally:
                if end_label:
                    self._fall_context_stack.pop()

            self._write_indent()
            self.output.write(f"if (!{fall_flag}) {done_flag} = true;\n")
            self._pop_scope()
            self.dedent()
            self._write_indent()
            self.output.write("}\n")
            return

        if action == "_emit_fall_else_body":
            else_case, fall_flag, done_flag, case_index, = payload
            self._write_indent()
            self.output.write(f"if ({fall_flag}) {{\n")
            self.indent()
            self._push_scope()
            self._write_indent()
            self.output.write(f"{fall_flag} = false;\n")

            for stmt in self._else_case_statements(else_case):
                (yield ("visit", (stmt,)))

            self._write_indent()
            self.output.write(f"if (!{fall_flag}) {done_flag} = true;\n")
            self._pop_scope()
            self.dedent()
            self._write_indent()
            self.output.write("}\n")
            return

        if action == "_visit_defer":
            node, = payload
            if node.statement:
                if node.statement.kind == NodeKind.BLOCK:
                    self._write_indent()
                    self.output.write("defer ")
                    (yield ("_visit_block_inline", (node.statement, None,)))
                else:
                    if node.statement.kind in (NodeKind.RETURN, NodeKind.BREAK, NodeKind.CONTINUE, NodeKind.FALL):
                        # Zig rejects control flow that leaves a defer.
                        raise CodegenError(
                            f"Zig backend: '{node.statement.kind.name}' cannot be deferred",
                            node.statement.span or node.span,
                        )
                    # One statement emitter for deferred and plain statements:
                    # `visit` raises a codegen error on a kind it does not know.
                    self._write_indent()
                    self.output.write("defer {\n")
                    self.indent()
                    self._push_scope()
                    (yield ("visit", (node.statement,)))
                    self._pop_scope()
                    self.dedent()
                    self._write_indent()
                    self.output.write("}\n")
            elif node.expression:
                self._write_indent()
                self.output.write("defer ")
                expr_str = self._emit_expr(node.expression)
                if not self._expression_returns_void(node.expression):
                    expr_str = "_ = " + expr_str
                self.output.write(f"{expr_str};\n")
            return

    def visit(self, node: ASTNode) -> None:
        """Visit an AST node and generate Zig code."""
        self._statement_work("visit", (node,))

    # === Top-level declarations ===

    def _visit_program(self, node: ASTNode) -> None:
        """Visit program root."""
        self._statement_work("_visit_program", (node,))

    def _visit_function(self, node: ASTNode) -> None:
        """Visit function declaration."""
        self._statement_work("_visit_function", (node,))

    def _visit_struct(self, node: ASTNode) -> None:
        """Visit struct declaration."""
        name = self._file_scope_name(node.name or "anon")

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
            param_list = self._comptime_param_list(node, generic_params, [f.field_type for f in (node.fields or [])])
            self.output.write(f"fn {self._quote_identifier(name)}({param_list}) type {{\n")
            self.indent()
            self._write_indent()
            self.output.write("return struct {\n")
        else:
            self.output.write(f"const {self._quote_identifier(name)} = struct {{\n")
        self.indent()

        saved_generic_env = self._generic_env
        self._generic_env = set(generic_params)
        for field in (node.fields or []):
            fname = field.name or "unknown"
            if field.field_type is None:
                raise CodegenError(f"Zig backend: field '{fname}' of struct '{name}' has no type", field.span or node.span)
            ftype = self._emit_type_node(field.field_type)
            self._write_indent()
            self.output.write(f"{self._quote_field(fname)}: {ftype},\n")
        self._generic_env = saved_generic_env

        self.dedent()
        self._write_indent()
        if generic_params:
            self.output.write("};\n")
            self.dedent()
            self._write_indent()
            self.output.write("}\n")
        else:
            self.output.write("};\n")

    def _comptime_param_list(self, node: ASTNode, names: list[str], readers: list[Optional[ASTNode]]) -> str:
        """Comptime parameters of a generic declaration, in A7 argument order.

        The checker records `value_kind` on a `$N: usize` parameter node: that
        parameter is a comptime value of its declared type, every other one is
        a type. Zig rejects an unused parameter, so a value parameter that no
        node in `readers` names (a `bool` cannot size an array) is written `_`.
        """
        kinds = {p.name: getattr(p, "value_kind", None) for p in (node.generic_params or [])}
        read: Set[str] = set()
        for reader in readers:
            read |= self._collect_used_identifiers(reader)
        parts = []
        for name in names:
            kind = kinds.get(name)
            if kind is None:
                parts.append(f"comptime {self._quote_identifier(name)}: type")
            else:
                shown = self._quote_identifier(name) if name in read else "_"
                parts.append(f"comptime {shown}: {self._map_primitive_type(kind)}")
        return ", ".join(parts)

    def _collect_generic_type_names(self, type_node, result, signature_order: bool = False):
        """Append the `$T` names a type expression mentions. Iterative.

        A record's implicit parameter list must match the checker's
        (`TypeCheckingPass._collect_generic_type_names`), which pops a stack:
        the arguments of `Pair($B, $A)` are found right to left. A function
        signature (`signature_order`) is read left to right, the same order
        `_generic_names_of_type` reads the checked signature at a call.
        """
        stack = [type_node]
        while stack:
            n = stack.pop()
            if n is None:
                continue
            children = []
            if n.kind == NodeKind.TYPE_GENERIC:
                if n.name and n.name not in result:
                    result.append(n.name)
            elif n.kind == NodeKind.TYPE_POINTER:
                children = [n.target_type]
            elif n.kind in (NodeKind.TYPE_ARRAY, NodeKind.TYPE_SLICE):
                children = [n.element_type]
            elif n.kind == NodeKind.TYPE_IDENTIFIER:
                children = list(n.generic_params or [])
            elif n.kind == NodeKind.TYPE_FUNCTION:
                children = list(n.parameter_types or []) + [n.return_type]
            stack.extend(reversed(children) if signature_order else children)

    @staticmethod
    def _generic_names_of_type(type_obj, result: list) -> None:
        """Append the generic parameter names of a checked type, left to right.

        The semantic twin of `_collect_generic_type_names(signature_order=True)`.
        Leaf: reads type objects only.
        """
        stack = [type_obj]
        while stack:
            current = stack.pop()
            children: list = []
            if isinstance(current, GenericParamType):
                if current.name not in result:
                    result.append(current.name)
            elif isinstance(current, ReferenceType):
                children = [current.referent_type]
            elif isinstance(current, PointerType):
                children = [current.pointee_type]
            elif isinstance(current, (ArrayType, SliceType)):
                children = [current.element_type]
            elif isinstance(current, GenericInstanceType):
                children = list(current.type_args)
            elif isinstance(current, FunctionType):
                children = list(current.param_types) + [current.return_type]
            stack.extend(reversed(children))

    # Tag types tried in order for an enum with explicit values.
    _ENUM_TAG_TYPES = (
        ("i32", -2**31, 2**31 - 1),
        ("u32", 0, 2**32 - 1),
        ("i64", -2**63, 2**63 - 1),
        ("u64", 0, 2**64 - 1),
    )

    def _enum_tag_type(self, node: ASTNode) -> Optional[str]:
        """Zig tag type of an enum; None lets Zig choose (no explicit value).

        `i32` when every value fits, else the first of `u32`, `i64`, `u64`
        that holds them all. A variant without a value takes the previous
        value plus one, as Zig numbers it. Leaf: reads AST shape only.
        """
        values: list[int] = []
        explicit = False
        following = 0
        for variant in (node.variants or []):
            value_node = variant.value
            if value_node is not None:
                explicit = True
                exact = getattr(value_node, "exact_constant", None)
                if exact is not None and exact[0].denominator == 1:
                    following = exact[0].numerator
                elif value_node.kind == NodeKind.LITERAL and isinstance(value_node.literal_value, int):
                    following = value_node.literal_value
                else:
                    # The checker folds every accepted enum value; without a
                    # folded value the historical `i32` tag stays.
                    return "i32"
            values.append(following)
            following += 1
        if not explicit:
            return None
        for tag, low, high in self._ENUM_TAG_TYPES:
            if all(low <= value <= high for value in values):
                return tag
        raise CodegenError(
            f"Zig backend: the values of enum '{node.name}' do not fit one 64-bit tag type "
            f"(lowest {min(values)}, highest {max(values)})",
            node.span,
        )

    def _visit_enum(self, node: ASTNode) -> None:
        """Visit enum declaration."""
        name = self._file_scope_name(node.name or "anon")
        tag = self._enum_tag_type(node)
        self._write_indent()
        if tag:
            self.output.write(f"const {self._quote_identifier(name)} = enum({tag}) {{\n")
        else:
            self.output.write(f"const {self._quote_identifier(name)} = enum {{\n")
        self.indent()

        for variant in (node.variants or []):
            vname = variant.name or "unknown"
            self._write_indent()
            if variant.value is not None:
                self.output.write(f"{self._quote_field(vname)} = {self._emit_expr(variant.value)},\n")
            else:
                self.output.write(f"{self._quote_field(vname)},\n")

        self.dedent()
        self._write_indent()
        self.output.write("};\n")

    def _visit_union(self, node: ASTNode) -> None:
        """Visit union declaration."""
        name = self._file_scope_name(node.name or "anon")
        is_tagged = getattr(node, 'is_tagged', False)
        tag = "union(enum)" if is_tagged else "union"

        # Generic unions lower exactly like generic structs: a comptime
        # type-function whose arguments follow A7's instance argument order.
        generic_params = [param.name for param in (node.generic_params or []) if param.name]
        if not generic_params:
            for field in (node.fields or []):
                self._collect_generic_type_names(field.field_type, generic_params)
            generic_params = list(dict.fromkeys(generic_params))

        self._write_indent()
        if generic_params:
            param_list = self._comptime_param_list(node, generic_params, [f.field_type for f in (node.fields or [])])
            self.output.write(f"fn {self._quote_identifier(name)}({param_list}) type {{\n")
            self.indent()
            self._write_indent()
            self.output.write(f"return {tag} {{\n")
        else:
            self.output.write(f"const {self._quote_identifier(name)} = {tag} {{\n")
        self.indent()

        saved_generic_env = self._generic_env
        self._generic_env = set(generic_params)
        for field in (node.fields or []):
            fname = field.name or "unknown"
            # A member written without a type carries no payload.
            ftype = self._emit_type_node(field.field_type) if field.field_type else "void"
            self._write_indent()
            self.output.write(f"{self._quote_field(fname)}: {ftype},\n")
        self._generic_env = saved_generic_env

        self.dedent()
        self._write_indent()
        if generic_params:
            self.output.write("};\n")
            self.dedent()
            self._write_indent()
            self.output.write("}\n")
        else:
            self.output.write("};\n")

    def _visit_const(self, node: ASTNode) -> None:
        """Visit constant declaration."""
        if node.value is None:
            raise CodegenError(f"Zig backend: internal error: constant '{node.name}' has no value", node.span)
        if node.value.kind == NodeKind.TYPE_SET:
            # A type-set alias exists only for the checker's constraint tests.
            return
        if getattr(node, 'untyped_binding', False):
            if self._in_function and node.name:
                self._untyped_consts[node.name] = node
            return
        name = node.name or "unnamed"
        val = self._emit_expr(node.value)
        name = self._declare_var_in_scope(name) if self._in_function else self._file_scope_name(name)
        self._write_indent()
        self.output.write(f"const {self._quote_identifier(name)} = {val};\n")
        if self._in_function:
            self._write_indent()
            self.output.write(self._pending_discard(name) + "\n")

    def _visit_var(self, node: ASTNode) -> None:
        """Visit variable declaration."""
        name = node.name or "unnamed"
        value = node.value
        explicit_type = getattr(node, 'explicit_type', None)
        if value is None and explicit_type is None:
            raise CodegenError(
                f"Zig backend: internal error: variable '{name}' has neither a type nor a value",
                node.span,
            )
        array_binary = self._is_array_binary_value(value)
        if array_binary and not self._in_function:
            raise CodegenError("Zig backend: array binary initializer requires block scope", node.span)

        # Initializers see the outer binding, before this declaration exists.
        if value is None:
            initial_value = self._default_value(explicit_type)
        elif array_binary:
            initial_value = self._emit_array_binary_expr(value)
        else:
            initial_value = self._emit_expr(value)

        declaration_type = self._type_map.get(id(node))
        if explicit_type:
            zig_type = self._emit_type_node(explicit_type)
        elif isinstance(declaration_type, PrimitiveType):
            # Semantic analysis owns inferred scalar widths. Zig would infer
            # comptime_int/float for literal initializers, which cannot be
            # mutated and can disagree with A7 even for immutable bindings.
            zig_type = self._emit_semantic_type(declaration_type)
        elif node.resolved_type:
            zig_type = self._emit_type_node(node.resolved_type)
        elif (
            (array_binary or value.kind == NodeKind.ARRAY_INIT)
            and isinstance(declaration_type, ArrayType)
            and isinstance(declaration_type.size, int)
        ):
            # `xs := [1, 2, 3]`: without the type Zig makes a tuple, which
            # has no runtime index and no `for`. A vector sum needs the type
            # to become an array again.
            zig_type = self._emit_semantic_type(declaration_type)
        elif array_binary:
            raise CodegenError("Zig backend: array binary initializer requires a known array type", node.span)
        else:
            zig_type = None
        annotation = f": {zig_type}" if zig_type else ""

        # The preprocessor names a shadowing local; scope analysis covers the rest.
        if self._in_function:
            binding_name = self._declare_var_in_scope(name, node.emit_name)
        else:
            binding_name = self._file_scope_name(name)
        emit_name = self._quote_identifier(binding_name)

        # In Zig only a reassigned binding needs `var`; a field write through
        # a reference does not. File-scope variables stay `var`.
        is_mutated = id(node) in self._mutated_declarations
        keyword = "var" if is_mutated or not self._in_function else "const"

        self._write_indent()
        if not self._in_function and name in self._global_init_refs:
            # Another file-scope initializer reads this variable's initial
            # value; Zig needs that value as a constant.
            initial = f"__a7_init_{binding_name}"
            self.output.write(f"const {initial}{annotation} = {initial_value};\n")
            self._write_indent()
            initial_value = initial
        self.output.write(f"{keyword} {emit_name}{annotation} = {initial_value};\n")

        if self._in_function:
            self._write_indent()
            self.output.write(self._pending_discard(binding_name) + "\n")

    def _visit_type_alias(self, node: ASTNode) -> None:
        """Visit type alias declaration, resolving its initializer first."""
        name = node.name or "unnamed"
        if node.value:
            val = self._emit_type_node(node.value)
            name = self._declare_var_in_scope(name) if self._in_function else self._file_scope_name(name)
            self._write_indent()
            self.output.write(f"const {self._quote_identifier(name)} = {val};\n")
            if self._in_function:
                self._write_indent()
                self.output.write(self._pending_discard(name) + "\n")

    # === Statements ===

    def _visit_block(self, node: ASTNode) -> None:
        """Visit block statement (as a standalone statement)."""
        self._statement_work("_visit_block", (node,))

    def _visit_block_inline(self, node: ASTNode, prelude_lines: Optional[list[str]] = None) -> None:
        """Visit block and output braces + indented contents."""
        self._statement_work("_visit_block_inline", (node, prelude_lines,))

    def _visit_switch_block(self, node: ASTNode) -> None:
        """Visit a block inside a switch prong (needs trailing comma)."""
        self._statement_work("_visit_switch_block", (node,))

    def _visit_if_stmt(self, node: ASTNode) -> None:
        """Visit if statement."""
        self._statement_work("_visit_if_stmt", (node,))

    def _visit_else_chain(self, node: ASTNode) -> None:
        """Handle else / else if chains. Iterative to avoid stack overflow."""
        self._statement_work("_visit_else_chain", (node,))

    def _visit_while(self, node: ASTNode) -> None:
        """Visit while statement."""
        self._statement_work("_visit_while", (node,))

    def _visit_for(self, node: ASTNode) -> None:
        """Visit for statement (C-style or infinite)."""
        self._statement_work("_visit_for", (node,))

    def _visit_for_in(self, node: ASTNode) -> None:
        """Visit for-in loop: for val in arr → for (arr) |val|"""
        self._statement_work("_visit_for_in", (node,))

    def _visit_for_in_indexed(self, node: ASTNode) -> None:
        """Visit indexed for-in: for i, val in arr → for (arr, 0..) |val, i|"""
        self._statement_work("_visit_for_in_indexed", (node,))

    def _match_has_tag_patterns(self, node: ASTNode) -> bool:
        """Return True when a match tests union tags with leading-dot patterns."""
        return any(
            pattern.kind == NodeKind.PATTERN_ENUM and not (pattern.enum_type or "")
            for case in (node.cases or [])
            for pattern in (case.patterns or [])
        )

    def _match_tag_binding(self, case: ASTNode) -> Optional[str]:
        """Return the payload binding for one tag-switch case, if exactly one.

        Raises a codegen error when bindings share a case: the validator
        rejects that shape first, so reaching here means hand-built AST input.
        Leaf helper: emits nothing and calls no visitor, so it stays outside
        the backend's known recursive visitor group (see test_no_recursion).
        """
        bound = [
            pattern.name for pattern in (case.patterns or [])
            if pattern.kind == NodeKind.PATTERN_ENUM
            and not (pattern.enum_type or "")
            and (pattern.name or "")
        ]
        if not bound:
            return None
        if len(bound) > 1 or len(case.patterns or []) > 1:
            raise CodegenError(
                "Zig backend: payload binding must be the only pattern in its case",
                case.span,
            )
        return bound[0]

    def _match_union_tags(self, node: ASTNode) -> Optional[tuple[str, ...]]:
        """Tag names of the union a match switches on; None for any other match.

        An empty tuple is a tag match whose union is not known here (dot arms
        on a scrutinee the checker left untyped); the validator's coverage
        check then decides whether the arms are complete.
        Leaf: reads types and AST shape only.
        """
        scrutinee = node.expression
        scrutinee_type = self._type_map.get(id(scrutinee)) if scrutinee else None
        if isinstance(scrutinee_type, ReferenceType):
            scrutinee_type = scrutinee_type.referent_type
        if isinstance(scrutinee_type, UnionType):
            return tuple(field.name for field in scrutinee_type.fields)
        if isinstance(scrutinee_type, GenericInstanceType) and scrutinee_type.base_name in self._union_tags:
            return self._union_tags[scrutinee_type.base_name]
        if scrutinee is not None and self._is_io_result_call(scrutinee):
            return ("ok", "err")
        if self._match_has_tag_patterns(node):
            return ()
        return None

    def _tag_scrutinee(self, node: ASTNode, expr: str) -> str:
        """Zig switches on the union value, so a `ref` scrutinee is dereferenced."""
        if isinstance(self._type_map.get(id(node.expression)), ReferenceType):
            return f"{expr}.?.*"
        return expr

    def _tag_match_arms(self, node: ASTNode, tags: tuple[str, ...]) -> tuple[list[ASTNode], Optional[ASTNode], bool]:
        """Split a tag match into tag arms, its `case _` arm, and full coverage.

        Arms after `case _` can never run, so they are not returned. Coverage
        counts the tag arms only. Leaf: reads AST shape only.
        """
        arms: list[ASTNode] = []
        covered: set[str] = set()
        for case in (node.cases or []):
            patterns = case.patterns or []
            if any(
                pattern.kind == NodeKind.PATTERN_WILDCARD
                or (pattern.kind == NodeKind.PATTERN_IDENTIFIER and pattern.name == "_")
                for pattern in patterns
            ):
                return arms, case, bool(tags) and covered >= set(tags)
            arms.append(case)
            covered.update(
                pattern.variant for pattern in patterns
                if pattern.kind == NodeKind.PATTERN_ENUM and pattern.variant
            )
        return arms, None, bool(tags) and covered >= set(tags)

    def _visit_match(self, node: ASTNode) -> None:
        """Visit match statement → Zig switch, or an if-chain when no switch fits."""
        self._statement_work("_visit_match", (node,))

    def _visit_match_as_if_chain(self, node: ASTNode) -> None:
        """Visit capture-bearing match statements as an if/else chain."""
        self._statement_work("_visit_match_as_if_chain", (node,))

    def _visit_match_with_fall(self, node: ASTNode) -> None:
        """Visit a fall-capable match statement as a sequential state machine."""
        self._statement_work("_visit_match_with_fall", (node,))

    def _emit_fall_case_body(
        self,
        case: ASTNode,
        scrutinee: str,
        fall_flag: str,
        done_flag: str,
        case_index: int,
    ) -> None:
        self._statement_work("_emit_fall_case_body", (case, scrutinee, fall_flag, done_flag, case_index,))

    def _emit_fall_else_body(
        self,
        else_case: object,
        fall_flag: str,
        done_flag: str,
        case_index: int,
    ) -> None:
        self._statement_work("_emit_fall_else_body", (else_case, fall_flag, done_flag, case_index,))

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

    def _match_fits_switch(self, node: ASTNode) -> bool:
        """True when a Zig `switch` can carry this match (ledger L60).

        The scrutinee must be an integer, char, bool or enum, and every arm
        value comptime-known. Zig rejects a switch on a float or a string and
        a prong that names a runtime value; those matches keep the if-chain.
        A match without `else` also keeps its ranges on the if-chain.
        Leaf: reads types and AST shape only.
        """
        scrutinee_type = self._type_map.get(id(node.expression)) if node.expression else None
        if isinstance(scrutinee_type, PrimitiveType):
            if not (scrutinee_type.is_integral() or scrutinee_type.name in ("bool", "char")):
                return False
        elif not isinstance(scrutinee_type, EnumType):
            return False
        for case in (node.cases or []):
            patterns = case.patterns or []
            if not patterns:
                return False
            for pattern in patterns:
                if pattern.kind == NodeKind.PATTERN_RANGE:
                    if not node.else_case:
                        return False
                    if not (self._is_comptime_pattern(pattern.start) and self._is_comptime_pattern(pattern.end)):
                        return False
                elif not self._is_comptime_pattern(pattern):
                    return False
        return True

    def _is_comptime_pattern(self, pattern: Optional[ASTNode]) -> bool:
        """True for an arm value Zig knows at compile time.

        A literal, a qualified enum variant, or a top-level `::` constant that
        no local shadows. A folded constant (`case ONE:` with `ONE :: 1`)
        arrives as a LITERAL node. Leaf: reads AST shape and scope state only.
        """
        if pattern is None:
            return False
        kind = pattern.kind
        literal = pattern.literal if kind == NodeKind.PATTERN_LITERAL else pattern
        if literal is not None and literal.kind == NodeKind.LITERAL:
            return literal.literal_kind in (LiteralKind.INTEGER, LiteralKind.CHAR, LiteralKind.BOOLEAN)
        if kind == NodeKind.PATTERN_ENUM:
            return bool(pattern.enum_type)
        if kind == NodeKind.PATTERN_IDENTIFIER and not self._is_capture_pattern(pattern):
            name = pattern.name or ""
            return name in self._global_consts and self._resolve_name(name) == name
        return False

    def _match_covers_closed_type(self, node: ASTNode) -> bool:
        """True when the arms name every value of an enum or bool scrutinee.

        Zig rejects an `else` prong once every value is handled. Any other
        scrutinee type is open, so its switch needs an else.
        Leaf: reads types and AST shape only.
        """
        scrutinee_type = self._type_map.get(id(node.expression)) if node.expression else None
        if isinstance(scrutinee_type, EnumType):
            covered: set[str] = set()
            for case in (node.cases or []):
                for pattern in (case.patterns or []):
                    if pattern.kind == NodeKind.PATTERN_ENUM and pattern.variant:
                        covered.add(pattern.variant)
            return bool(scrutinee_type.variants) and all(v.name in covered for v in scrutinee_type.variants)
        if isinstance(scrutinee_type, PrimitiveType) and scrutinee_type.name == "bool":
            seen: set[bool] = set()
            for case in (node.cases or []):
                for pattern in (case.patterns or []):
                    literal = pattern.literal if pattern.kind == NodeKind.PATTERN_LITERAL else pattern
                    if literal is not None and literal.kind == NodeKind.LITERAL and literal.literal_kind == LiteralKind.BOOLEAN:
                        seen.add(bool(literal.literal_value))
            return seen == {True, False}
        return False

    def _emit_match_capture_bindings_zig(self, patterns: list[ASTNode], scrutinee: str) -> None:
        for pattern in patterns:
            if not self._is_capture_pattern(pattern):
                continue
            name = self._declare_var_in_scope(pattern.name or "value")
            self._write_indent()
            self.output.write(f"const {self._quote_identifier(name)} = {scrutinee};\n")
            self._write_indent()
            self.output.write(self._pending_discard(name) + "\n")

    def _case_statements(self, case: ASTNode) -> list[ASTNode]:
        stmt = getattr(case, "statement", None)
        if stmt is None:
            return list(case.statements or [])
        if stmt.kind == NodeKind.BLOCK:
            return list(stmt.statements or [])
        return [stmt]

    def _case_has_direct_fall(self, case: ASTNode) -> bool:
        return any(stmt.kind == NodeKind.FALL for stmt in self._case_statements(case))

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
        self._statement_work("_visit_defer", (node,))

    def _visit_del(self, node: ASTNode) -> None:
        """Visit del statement → Zig allocator.destroy."""
        self._write_indent()
        expr_node = getattr(node, 'expression', None) or getattr(node, 'expr', None)
        if expr_node:
            target_type = self._type_map.get(id(expr_node))
            if target_type is not None and not isinstance(target_type, (ReferenceType, PointerType)):
                raise CodegenError("Zig backend: del requires a reference type", expr_node.span or node.span)
            expr = self._emit_expr(expr_node)
            # A fixed capture name would shadow a user local of the same name.
            capture = self._unique_name("__a7_del")
            self.output.write(f"if ({expr}) |{capture}| allocator.destroy({capture});\n")

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
            target = self._emit_expr(node.target)
        value = self._emit_expr(node.value)
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
                builtin = "@rem(" if op == AssignOp.MOD_ASSIGN else "@divTrunc("
                if self._divisor_may_be_minus_one(target_type, node.value):
                    helper = "rem" if op == AssignOp.MOD_ASSIGN else "div"
                    self._helpers.add(helper)
                    builtin = f"__a7_{helper}({self._emit_semantic_type(target_type)}, "
                self._name_counter += 1
                ptr = f"__a7_compound_{self._name_counter}"
                return f"_ = {ptr}_block: {{ const {ptr} = &{target}; {ptr}.* = {builtin}{ptr}.*, {value}); break :{ptr}_block {{}}; }}"
        if op in {AssignOp.SHL_ASSIGN, AssignOp.SHR_ASSIGN} and not self._is_nonnegative_integer_literal(node.value):
            helper = "shl" if op == AssignOp.SHL_ASSIGN else "shr"
            self._helpers.add(helper)
            if node.target.kind == NodeKind.IDENTIFIER and not getattr(node, "implicit_deref_target", False):
                return f"{target} = __a7_{helper}(@TypeOf({target}), {target}, {value})"
            self._name_counter += 1
            ptr = f"__a7_compound_{self._name_counter}"
            return (f"_ = {ptr}_block: {{ const {ptr} = &{target}; "
                    f"{ptr}.* = __a7_{helper}(@TypeOf({ptr}.*), {ptr}.*, {value}); break :{ptr}_block {{}}; }}")
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
            # Result-returning io calls discard their value as statements.
            if self._is_io_result_call(node.expression):
                self._write_indent()
                self.output.write(f"_ = {self._emit_call(node.expression)};\n")
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

    def _expression_work(self, action, payload):
        pending = [self._expression_steps(action, payload)]
        result = None
        failure = None
        try:
            while pending:
                try:
                    if failure is None:
                        action, payload = pending[-1].send(result)
                    else:
                        error, failure = failure, None
                        action, payload = pending[-1].throw(error)
                except StopIteration as finished:
                    pending.pop()
                    result = finished.value
                    continue
                except BaseException as error:
                    pending.pop()
                    if not pending:
                        raise
                    # A parent may translate a child's CodegenError.
                    failure = error
                    result = None
                    continue
                pending.append(self._expression_steps(action, payload))
                result = None
            return result
        finally:
            for frame in reversed(pending):
                frame.close()

    def _expression_steps(self, action, payload):
        if action == "_emit_expr":
            node, = payload
            if node is None:
                raise CodegenError("Zig backend: internal error: missing expression node")

            kind = node.kind

            if kind == NodeKind.LITERAL:
                return self._emit_literal(node)
            elif kind == NodeKind.IDENTIFIER:
                return self._emit_identifier(node)
            elif kind == NodeKind.BINARY:
                return (yield ("_emit_binary_iterative", (node,)))
            elif kind == NodeKind.UNARY:
                return (yield ("_emit_unary", (node,)))
            elif kind == NodeKind.CALL:
                return (yield ("_emit_call", (node,)))
            elif kind == NodeKind.INDEX:
                return (yield ("_emit_index", (node,)))
            elif kind == NodeKind.SLICE:
                return (yield ("_emit_slice", (node,)))
            elif kind == NodeKind.FIELD_ACCESS:
                return (yield ("_emit_field_access", (node,)))
            elif kind == NodeKind.ADDRESS_OF:
                return (yield ("_emit_address_of", (node,)))
            elif kind == NodeKind.DEREF:
                return (yield ("_emit_deref", (node,)))
            elif kind == NodeKind.CAST:
                return (yield ("_emit_cast", (node,)))
            elif kind == NodeKind.IF_EXPR:
                return (yield ("_emit_if_expr", (node,)))
            elif kind == NodeKind.MATCH_EXPR:
                return (yield ("_emit_match_expr", (node,)))
            elif kind == NodeKind.STRUCT_INIT:
                return (yield ("_emit_struct_init", (node,)))
            elif kind == NodeKind.ARRAY_INIT:
                return (yield ("_emit_array_init", (node,)))
            elif kind == NodeKind.NEW_EXPR:
                return (yield ("_emit_new_expr", (node,)))
            elif kind in (NodeKind.TYPE_PRIMITIVE, NodeKind.TYPE_IDENTIFIER,
                          NodeKind.TYPE_ARRAY, NodeKind.TYPE_SLICE,
                          NodeKind.TYPE_POINTER, NodeKind.TYPE_FUNCTION,
                          NodeKind.TYPE_GENERIC):
                return (yield ("_emit_type_node", (node, None,)))
            else:
                raise CodegenError(f"Zig backend: unsupported expression node '{kind.name}'", node.span)

        if action == "_emit_binary_iterative":
            root, = payload
            rendered: dict[int, str] = {}
            stack: list[tuple[ASTNode, bool]] = [(root, False)]
            while stack:
                node, ready = stack.pop()
                if node.kind != NodeKind.BINARY:
                    rendered[id(node)] = (yield ("_emit_expr", (node,)))
                    continue
                if ready:
                    left = rendered.pop(id(node.left))
                    right = rendered.pop(id(node.right))
                    if (
                        node.operator in self._ASSOC_CHAIN_OPS
                        and node.left is not None
                        and node.left.kind == NodeKind.BINARY
                        and node.left.operator == node.operator
                        and not isinstance(self._type_map.get(id(node)), ArrayType)
                        and left.startswith("(")
                        and left.endswith(")")
                    ):
                        # Same-operator left chains regroup identically under the
                        # wrapper (`((a +% b) +% c)` is `(a +% b +% c)`), so the
                        # inner pair is redundant. Array vector lowering keeps
                        # its parens: the child text is nested inside `@as`.
                        left = left[1:-1]
                    rendered[id(node)] = self._emit_binary_from_parts(node, left, right)
                    continue
                stack.append((node, True))
                if node.right is not None:
                    stack.append((node.right, False))
                if node.left is not None:
                    stack.append((node.left, False))
            return rendered[id(root)]

        if action == "_emit_unary":
            node, = payload
            operand = (yield ("_emit_expr", (node.operand,)))
            op = node.operator

            operand_type = self._type_map.get(id(node.operand))
            integral = isinstance(operand_type, PrimitiveType) and operand_type.is_integral()
            literal = node.operand.kind == NodeKind.LITERAL
            if op == UnaryOp.NOT:
                return f"(!{operand})"
            elif op == UnaryOp.BIT_NOT:
                if literal:
                    # Zig has no `~` on comptime_int.
                    return f"(~@as({self._emit_semantic_type(self._type_map.get(id(node)))}, {operand}))"
                return f"(~{operand})"
            elif op != UnaryOp.NEG:
                raise CodegenError(f"Zig backend: internal error: unary operator '{getattr(op, 'name', op)}' has no lowering", node.span)
            elif integral and not literal:
                # Wraps like binary `+ - *`: `-MIN` is MIN in every profile.
                return f"(-%{operand})"
            else:
                return f"(-{operand})"

        if action == "_emit_call":
            node, = payload
            # Special-case io.println / io.print
            if self._is_io_call(node):
                return self._emit_io_call_expr(node)
            # Result-returning io calls construct the union value inline here
            # (a helper method would join the _emit_call/_emit_expr cycle and
            # trip the no-recursion ratchet, so the emission stays inline).
            if self._is_io_result_call(node):
                canonical = getattr(node, "stdlib_canonical", None) or ""
                args = node.arguments or []
                if canonical == "std.io.read_line":
                    buf = (yield ("_emit_expr", (args[0],))) if args else "&[_]u8{}"
                    return f"__a7_stdin_read_line({buf})"
                if not args:
                    return '__a7_stdout_print_ok("\\n", .{})'
                fmt_str = self._convert_format_string((yield ("_emit_expr", (args[0],))), args[1:])
                if fmt_str.endswith('"'):
                    fmt_str = fmt_str[:-1] + '\\n"'
                if len(args) == 1:
                    return f"__a7_stdout_print_ok({fmt_str}, .{{}})"
                argument_parts = []
                for arg in args[1:]:
                    argument_parts.append((yield ("_emit_expr", (arg,))))
                zig_args = ", ".join(argument_parts)
                if self._has_top_level_comma(zig_args):
                    return f"__a7_stdout_print_ok({fmt_str}, .{{ {zig_args} }})"
                return f"__a7_stdout_print_ok({fmt_str}, .{{{zig_args}}})"

            file_module_call = getattr(node, "file_module_call", None)
            if file_module_call:
                prefix, field = file_module_call
                args_list = self._generic_call_args(node)
                implicit_ref_args = set(getattr(node, "implicit_ref_args", set()) or set())
                for index, arg in enumerate(node.arguments or []):
                    if index in implicit_ref_args:
                        args_list.append(f"&{(yield ("_emit_expr", (arg,)))}")
                    else:
                        args_list.append((yield ("_emit_expr", (arg,))))
                return f"{prefix}{field}({', '.join(args_list)})"

            canonical = getattr(node, "stdlib_canonical", None)
            if canonical and canonical.startswith("std.math."):
                short = canonical.split(".")[-1]
                if short in ('sqrt', 'abs', 'floor', 'ceil', 'sin', 'cos', 'tan',
                             'log', 'exp', 'min', 'max'):
                    argument_parts = []
                    for arg in node.arguments or []:
                        argument_parts.append((yield ("_emit_expr", (arg,))))
                    args = ", ".join(argument_parts)
                    if short == "abs":
                        result_type = self._type_map.get(id(node))
                        if isinstance(result_type, PrimitiveType) and result_type.is_integral() and result_type.name.startswith("i"):
                            # @bitCast wraps `abs(MIN)` to MIN; @intCast would trap or be
                            # undefined. The inner @as types a literal argument.
                            zig_type = self._emit_semantic_type(result_type)
                            return f"@as({zig_type}, @bitCast(@abs(@as({zig_type}, {args}))))"
                    return f"@{short}({args})"

            func = (yield ("_emit_expr", (node.function,)))

            args_list = self._generic_call_args(node)
            implicit_ref_args = set(getattr(node, "implicit_ref_args", set()) or set())
            for index, arg in enumerate(node.arguments or []):
                if index in implicit_ref_args:
                    args_list.append(f"&{(yield ("_emit_expr", (arg,)))}")
                else:
                    args_list.append((yield ("_emit_expr", (arg,))))
            args = ", ".join(args_list)
            return f"{func}({args})"

        if action == "_emit_index":
            node, = payload
            self._require_backend_approval(node, "index")
            obj = (yield ("_emit_expr", (node.object,)))
            if node.object is not None and node.object.kind == NodeKind.ARRAY_INIT:
                obj = self._typed_array_literal(node.object, obj)
            if (
                node.index
                and node.index.kind == NodeKind.LITERAL
                and node.index.literal_kind == LiteralKind.INTEGER
                and isinstance(node.index.literal_value, int)
                and node.index.literal_value >= 0
            ):
                return f"{obj}[{node.index.literal_value}]"
            idx = (yield ("_emit_expr", (node.index,)))
            index_type = self._type_map.get(id(node.index)) if node.index else None
            if index_type is not None and getattr(index_type, "name", None) == "usize":
                return f"{obj}[{idx}]"
            return f"{obj}[@intCast({idx})]"

        if action == "_emit_slice":
            node, = payload
            self._require_backend_approval(node, "slice")
            obj = (yield ("_emit_expr", (node.object,)))
            start = (yield ("_emit_slice_bound", (node.start, "0",)))
            end = (yield ("_emit_slice_bound", (node.end, "",)))
            return f"{obj}[{start}..{end}]"

        if action == "_emit_slice_bound":
            bound, default, = payload
            if bound is None:
                return default
            if (
                bound.kind == NodeKind.LITERAL
                and bound.literal_kind == LiteralKind.INTEGER
                and isinstance(bound.literal_value, int)
                and bound.literal_value >= 0
            ):
                return str(bound.literal_value)
            emitted = (yield ("_emit_expr", (bound,)))
            bound_type = self._type_map.get(id(bound))
            if bound_type is not None and getattr(bound_type, "name", None) == "usize":
                return emitted
            return f"@intCast({emitted})"

        if action == "_emit_field_access":
            node, = payload
            if getattr(node, "implicit_deref_object", False):
                self._require_backend_approval(node, "deref")
                obj = (yield ("_emit_implicit_ref_field_base", (node.object,)))
            else:
                obj = (yield ("_emit_expr", (node.object,)))
                if node.object is not None and node.object.kind == NodeKind.STRUCT_INIT:
                    # `P{ .x = 1 }.x` does not parse in Zig.
                    obj = f"({obj})"
                elif node.object is not None and node.object.kind == NodeKind.ARRAY_INIT:
                    obj = self._typed_array_literal(node.object, obj)
            if not node.field:
                raise CodegenError("Zig backend: internal error: field access has no field name", node.span)
            return f"{obj}.{self._quote_field(node.field)}"

        if action == "_emit_address_of":
            node, = payload
            operand = (yield ("_emit_expr", (node.operand,)))
            return f"&{operand}"

        if action == "_emit_deref":
            node, = payload
            self._require_backend_approval(node, "deref")
            pointer = (yield ("_emit_expr", (node.pointer,)))
            pointer_type = self._type_map.get(id(node.pointer)) if node.pointer else None
            if isinstance(pointer_type, PointerType):
                return f"{pointer}[0]"
            return f"{pointer}.?.*"

        if action == "_emit_implicit_ref_field_base":
            node, = payload
            expr = (yield ("_emit_expr", (node,)))
            node_type = self._type_map.get(id(node)) if node else None
            if isinstance(node_type, PointerType):
                return f"{expr}[0]"
            return f"{expr}.?"

        if action == "_emit_cast":
            node, = payload
            self._require_backend_approval(node, "cast")
            decision = getattr(node, "cast_decision", None)
            if decision is None or not decision.allowed:
                raise CodegenError("Zig backend: cast was not approved by semantic analysis", node.span)

            target_type = (yield ("_emit_type_node", (node.target_type, node.span,)))
            expr = (yield ("_emit_expr", (node.expression,)))
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

        if action == "_emit_if_expr":
            node, = payload
            cond = self._strip_condition_parens((yield ("_emit_expr", (node.condition,))), node.condition)
            then_val = (yield ("_emit_expr", (node.then_expr,)))
            else_val = (yield ("_emit_expr", (node.else_expr,)))
            # Parenthesize: a bare Zig `if` expression extends its else branch over
            # any operator that follows, so `(if c a else b) + 10` must keep the
            # parentheses to select before the operator applies.
            return f"(if ({cond}) {then_val} else {else_val})"

        if action == "_emit_match_expr":
            node, = payload
            tags = self._match_union_tags(node)
            if tags is None:
                if self._match_has_capture(node) or not self._match_fits_switch(node):
                    return (yield ("_emit_match_expr_with_captures", (node,)))
                arms = list(node.cases or [])
                wildcard = None
                exhaustive = self._match_covers_closed_type(node)
            else:
                arms, wildcard, exhaustive = self._tag_match_arms(node, tags)

            expr = (yield ("_emit_expr", (node.expression,)))
            if tags is not None:
                expr = self._tag_scrutinee(node, expr)
            case_indent = "    " * (self.indent_level + 1)
            close_indent = "    " * self.indent_level
            parts = [f"switch ({expr}) {{"]

            for case in arms:
                pattern_parts = []
                for pattern in case.patterns or []:
                    pattern_parts.append((yield ("_emit_pattern", (pattern,))))
                pattern_str = ", ".join(pattern_parts)
                binding = self._match_tag_binding(case) if tags is not None else None
                case_expr = getattr(case, 'expression', None)
                capture = ""
                self._push_scope()
                if binding is not None:
                    declared = self._declare_var_in_scope(binding)
                    uses_before = self._identifier_uses.get(declared, 0)
                val = (yield ("_emit_expr", (case_expr,)))
                # Zig rejects an unused capture, and a prong value has no room
                # for a `_ = name;` discard, so the capture is written only when
                # the value reads it.
                if binding is not None and self._identifier_uses.get(declared, 0) != uses_before:
                    capture = f"|{self._quote_identifier(declared)}| "
                self._pop_scope()
                parts.append(f"\n{case_indent}{pattern_str} => {capture}{val},")

            rest = None
            if wildcard is not None:
                rest_expr = getattr(wildcard, 'expression', None)
                rest = (yield ("_emit_expr", (rest_expr,)))
            elif node.else_case:
                rest = (yield ("_emit_expr", (node.else_case if isinstance(node.else_case, ASTNode) else None,)))

            if rest is not None and not exhaustive:
                parts.append(f"\n{case_indent}else => {rest},")
            parts.append(f"\n{close_indent}}}")
            if rest is not None and exhaustive:
                # Zig rejects an `else` prong once every value has a prong; the
                # dead branch keeps the names the A7 `else` value uses in use.
                return f"(if (false) {rest} else {''.join(parts)})"
            return "".join(parts)

        if action == "_emit_match_expr_with_captures":
            node, = payload
            label = self._unique_name("__a7_match_expr")
            scrutinee = self._unique_name("__a7_match")
            expr = (yield ("_emit_expr", (node.expression,)))
            by_content = self._is_string_type(self._type_map.get(id(node.expression)))
            parts = [f"{label}: {{ const {scrutinee} = {expr};"]

            emitted_branch = False
            emitted_unconditional = False
            for case in node.cases or []:
                if emitted_unconditional:
                    continue
                case_expr = getattr(case, "expression", None)
                if case_expr is None:
                    continue
                condition = (yield ("_emit_match_condition_zig", (scrutinee, case.patterns or [], by_content,)))
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
                parts.append(f" break :{label} {(yield ("_emit_expr", (case_expr,)))}; }}")
                self._pop_scope()
                emitted_branch = True

            if not emitted_unconditional:
                # The checker accepts a match expression without `else` only when
                # its arms cover every value, so this branch cannot run.
                else_expr = (yield ("_emit_expr", (node.else_case,))) if isinstance(node.else_case, ASTNode) else "unreachable"
                prefix = " else " if emitted_branch else " "
                parts.append(f"{prefix}{{ break :{label} {else_expr}; }}")

            parts.append(" }")
            return "".join(parts)

        if action == "_emit_struct_init":
            node, = payload
            struct_name = self._use_name(node.struct_type or "")
            field_inits = node.field_inits or []
            type_args = getattr(node, "type_arguments", None) or []

            if struct_name and struct_name != "__inline__":
                if type_args:
                    # The checker resolves a `$N` argument to a GenericValueArg on
                    # the literal's instance type; every other argument is a type.
                    resolved = getattr(self._type_map.get(id(node)), "type_args", None) or ()
                    type_parts = []
                    for i, arg in enumerate(type_args):
                        if i < len(resolved) and isinstance(resolved[i], GenericValueArg):
                            type_parts.append(self._emit_semantic_type(resolved[i]))
                        else:
                            type_parts.append((yield ("_emit_type_node", (arg, None,))))
                    rendered_args = ", ".join(type_parts)
                    parts = [f"{struct_name}({rendered_args}){{ "]
                else:
                    parts = [f"{struct_name}{{ "]
            else:
                parts = [".{ "]

            for i, fi in enumerate(field_inits):
                if i > 0:
                    parts.append(", ")
                val = (yield ("_emit_expr", (fi.value,)))
                if fi.name:
                    parts.append(f".{self._quote_field(fi.name)} = {val}")
                else:
                    parts.append(val)

            parts.append(" }")
            return "".join(parts)

        if action == "_emit_array_init":
            node, = payload
            elements = node.elements or []
            element_parts = []
            for element in elements:
                element_parts.append((yield ("_emit_expr", (element,))))
            elems = ", ".join(element_parts)
            return f".{{ {elems} }}"

        if action == "_emit_new_expr":
            node, = payload
            zig_type = (yield ("_emit_type_node", (getattr(node, 'target_type', None), node.span,)))
            self._helpers.add("new")
            return f"__a7_new({zig_type})"

        if action == "_emit_pattern":
            node, = payload
            if node is None:
                return "_"

            kind = node.kind
            if kind == NodeKind.PATTERN_LITERAL:
                return (yield ("_emit_expr", (node.literal,)))
            elif kind == NodeKind.PATTERN_IDENTIFIER:
                return self._use_name(node.name) if node.name and node.name != "_" else "_"
            elif kind == NodeKind.PATTERN_ENUM:
                return f".{self._quote_field(node.variant)}" if node.variant else "_"
            elif kind == NodeKind.PATTERN_RANGE:
                start = (yield ("_emit_pattern", (node.start,)))
                end = (yield ("_emit_pattern", (node.end,)))
                return f"{start}...{end}"
            elif kind == NodeKind.PATTERN_WILDCARD:
                return "_"
            else:
                try:
                    return (yield ("_emit_expr", (node,)))
                except CodegenError as exc:
                    raise CodegenError(
                        f"Zig backend: unsupported match pattern '{kind.name}'",
                        node.span,
                    ) from exc

        if action == "_emit_match_condition_zig":
            scrutinee_expr, patterns, by_content, = payload
            conditions: list[str] = []
            for pattern in patterns:
                condition = (yield ("_emit_match_pattern_condition_zig", (scrutinee_expr, pattern, by_content,)))
                if condition is None:
                    return "true"
                conditions.append(condition)
            if not conditions:
                return "false"
            if len(conditions) == 1:
                return conditions[0]
            return " or ".join(f"({condition})" for condition in conditions)

        if action == "_emit_match_pattern_condition_zig":
            scrutinee_expr, pattern, by_content, = payload
            if pattern.kind == NodeKind.PATTERN_WILDCARD:
                return None
            if by_content:
                # A string scrutinee: Zig's `==` on slices compares pointers.
                name = pattern.name or ""
                if pattern.kind == NodeKind.PATTERN_IDENTIFIER:
                    if name == "_" or self._is_capture_pattern(pattern):
                        return None
                    value = self._use_name(name)
                elif pattern.kind == NodeKind.PATTERN_LITERAL:
                    value = (yield ("_emit_expr", (pattern.literal,)))
                else:
                    raise CodegenError(
                        f"Zig backend: a string match cannot test pattern '{pattern.kind.name}'",
                        pattern.span,
                    )
                self._needs_std = True
                return f"std.mem.eql(u8, {scrutinee_expr}, {value})"
            if pattern.kind == NodeKind.PATTERN_LITERAL:
                value = (yield ("_emit_expr", (pattern.literal,)))
                return f"{scrutinee_expr} == {value}"
            if pattern.kind == NodeKind.PATTERN_ENUM:
                value = f".{self._quote_field(pattern.variant)}" if pattern.variant else "_"
                return f"{scrutinee_expr} == {value}"
            if pattern.kind == NodeKind.PATTERN_IDENTIFIER:
                name = pattern.name or ""
                if name == "_":
                    return None
                if self._is_capture_pattern(pattern):
                    return None
                return f"{scrutinee_expr} == {self._use_name(name)}"
            if pattern.kind == NodeKind.PATTERN_RANGE:
                start = (yield ("_emit_pattern", (pattern.start,))) if pattern.start else "0"
                end = (yield ("_emit_pattern", (pattern.end,))) if pattern.end else "0"
                return f"{scrutinee_expr} >= {start} and {scrutinee_expr} <= {end}"
            value = (yield ("_emit_expr", (pattern,)))
            return f"{scrutinee_expr} == {value}"

        if action == "_emit_type_node":
            node, span, = payload
            if node is None:
                raise CodegenError("Zig backend: missing type node", span)

            generic_env = self._generic_env

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
                    size = (yield ("_emit_expr", (current.size,)))
                    prefix_parts.append(f"[{size}]")
                    current = current.element_type
                elif kind == NodeKind.TYPE_SLICE:
                    prefix_parts.append("[]")
                    current = current.element_type
                else:
                    # Base type — emit and prepend all prefixes
                    base = (yield ("_emit_type_leaf", (current, None,)))
                    return "".join(prefix_parts) + base

            raise CodegenError("Zig backend: incomplete type expression", node.span)

        if action == "_emit_type_leaf":
            node, span, = payload
            if node is None:
                raise CodegenError("Zig backend: missing type leaf", span)

            generic_env = self._generic_env
            kind = node.kind
            if kind == NodeKind.TYPE_PRIMITIVE:
                return self._map_primitive_type(node.type_name)
            elif kind == NodeKind.TYPE_IDENTIFIER:
                if node.generic_params:
                    type_parts = []
                    for param in node.generic_params:
                        type_parts.append((yield ("_emit_type_node", (param, None,))))
                    args = ", ".join(type_parts)
                    if not node.name:
                        raise CodegenError("Zig backend: generic type identifier is missing a name", node.span)
                    return f"{self._use_name(node.name)}({args})"
                if not node.name:
                    raise CodegenError("Zig backend: type identifier is missing a name", node.span)
                if node.name in self._untyped_consts:
                    # A `$N` value argument in a type annotation (`x: Buf(SIZE)`).
                    # The checker records no type for this node, and an untyped
                    # constant has no Zig declaration, so its value is written here.
                    return (yield ("_emit_expr", (self._untyped_consts[node.name].value,)))
                return self._use_name(node.name)
            elif kind == NodeKind.TYPE_GENERIC:
                if node.name in generic_env:
                    return self._quote_identifier(node.name)
                raise CodegenError(f"Zig backend: unresolved generic type '{node.name or '?'}'", node.span)
            elif kind == NodeKind.TYPE_FUNCTION:
                parameter_parts = []
                for param in node.parameter_types or []:
                    parameter_parts.append((yield ("_emit_type_node", (param, None,))))
                params = ", ".join(parameter_parts)
                # A function type without a return type returns nothing.
                ret = (yield ("_emit_type_node", (node.return_type, None,))) if node.return_type else "void"
                return f"*const fn ({params}) {ret}"
            elif kind == NodeKind.TYPE_STRUCT:
                fields = node.fields or []
                parts = ["struct {"]
                for f in fields:
                    fname = f.name or "unknown"
                    ftype = (yield ("_emit_type_node", (f.field_type, f.span,)))
                    parts.append(f"\n    {self._quote_field(fname)}: {ftype},")
                parts.append("\n}")
                return "".join(parts)
            else:
                raise CodegenError(f"Zig backend: unsupported type node '{kind.name}'", node.span)

    def _emit_expr(self, node: ASTNode) -> str:
        """Emit an expression as a Zig string."""
        return self._expression_work("_emit_expr", (node,))

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
                if escaped == val and len(val) == 1 and (ord(val) < 0x20 or ord(val) >= 0x7f):
                    # A char is one byte. Raw text above 0x7f would be UTF-8,
                    # two bytes in the Zig source for one A7 byte.
                    escaped = f"\\x{ord(val):02x}"
                return f"'{escaped}'"
            return raw if raw else "'\\x00'"
        elif lk == LiteralKind.BOOLEAN:
            return "true" if val else "false"
        elif lk == LiteralKind.NIL:
            return "null"
        else:
            raise CodegenError(
                f"Zig backend: internal error: literal kind '{getattr(lk, 'name', lk)}' has no lowering",
                node.span,
            )

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
        if not node.name:
            raise CodegenError("Zig backend: internal error: identifier has no name", node.span)
        if not self._in_function and node.name in self._global_init_refs:
            # A file-scope initializer reads the initial value (see `_visit_var`).
            return f"__a7_init_{self._global_renames.get(node.name, node.name)}"
        return self._use_name(node.name)

    def _emit_binary_iterative(self, root: ASTNode) -> str:
        """Emit nested binary expressions without using the Python call stack."""
        return self._expression_work("_emit_binary_iterative", (root,))

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
        if op in {BinaryOp.EQ, BinaryOp.NE} and self._is_string_type(self._type_map.get(id(node.left))):
            # Zig compares slices by pointer; A7 compares strings by content.
            self._needs_std = True
            return f"{'!' if op == BinaryOp.NE else ''}std.mem.eql(u8, {left}, {right})"
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
            if self._divisor_may_be_minus_one(result_type, node.right):
                self._helpers.add("div")
                return f"__a7_div({self._emit_semantic_type(result_type)}, {left}, {right})"
            return f"@divTrunc({left}, {right})"
        elif op == BinaryOp.MOD:
            if self._divisor_may_be_minus_one(result_type, node.right):
                self._helpers.add("rem")
                return f"__a7_rem({self._emit_semantic_type(result_type)}, {left}, {right})"
            return f"@rem({left}, {right})"
        elif op in {BinaryOp.BIT_SHL, BinaryOp.BIT_SHR}:
            if self._is_nonnegative_integer_literal(node.right):
                return f"({left} {zig_op} {right})"
            # The explicit type also gives a literal left operand (`1 << n`)
            # a concrete width.
            helper = "shl" if op == BinaryOp.BIT_SHL else "shr"
            self._helpers.add(helper)
            return f"__a7_{helper}({self._emit_semantic_type(result_type)}, {left}, {right})"
        else:
            return f"({left} {zig_op} {right})"

    @staticmethod
    def _is_string_type(type_obj) -> bool:
        return isinstance(type_obj, PrimitiveType) and type_obj.name == "string"

    def _emit_unary(self, node: ASTNode) -> str:
        """Emit a unary expression."""
        return self._expression_work("_emit_unary", (node,))

    def _generic_call_args(self, node: ASTNode) -> list[str]:
        """Emit the comptime type arguments a generic call carries, in order."""
        generic_mapping = getattr(node, "generic_mapping", None) or {}
        if not generic_mapping:
            return []
        func_type = self._type_map.get(id(node.function)) if node.function else None
        # The declared list, then every `$T` of the signature left to right:
        # the order `_visit_function` declares the comptime parameters in.
        ordered_names = list(getattr(func_type, "generic_param_order", ()) or ())
        if isinstance(func_type, FunctionType):
            discovered: list = []
            for param_type in func_type.param_types:
                self._generic_names_of_type(param_type, discovered)
            self._generic_names_of_type(func_type.return_type, discovered)
            ordered_names.extend(n for n in discovered if n not in ordered_names)
        else:
            ordered_names.extend(n for n in generic_mapping if n not in ordered_names)
        return [
            self._emit_semantic_type(generic_mapping[name])
            for name in ordered_names
            if name in generic_mapping
        ]

    def _emit_call(self, node: ASTNode) -> str:
        """Emit a function call."""
        return self._expression_work("_emit_call", (node,))

    def _emit_index(self, node: ASTNode) -> str:
        """Emit array indexing."""
        return self._expression_work("_emit_index", (node,))

    def _emit_slice(self, node: ASTNode) -> str:
        """Emit slice expression."""
        return self._expression_work("_emit_slice", (node,))

    def _emit_slice_bound(self, bound: Optional[ASTNode], *, default: str) -> str:
        """Emit a slice bound, coercing non-usize values via @intCast."""
        return self._expression_work("_emit_slice_bound", (bound, default,))

    def _emit_field_access(self, node: ASTNode) -> str:
        """Emit field access."""
        return self._expression_work("_emit_field_access", (node,))

    def _emit_address_of(self, node: ASTNode) -> str:
        """Emit internal address-of."""
        return self._expression_work("_emit_address_of", (node,))

    def _emit_deref(self, node: ASTNode) -> str:
        """Emit internal dereference."""
        return self._expression_work("_emit_deref", (node,))

    def _emit_implicit_deref(self, node: Optional[ASTNode]) -> str:
        expr = self._emit_expr(node)
        node_type = self._type_map.get(id(node)) if node else None
        if isinstance(node_type, PointerType):
            return f"{expr}[0]"
        return f"{expr}.?.*"

    def _emit_implicit_ref_field_base(self, node: Optional[ASTNode]) -> str:
        return self._expression_work("_emit_implicit_ref_field_base", (node,))

    def _emit_cast(self, node: ASTNode) -> str:
        """Emit cast expression."""
        return self._expression_work("_emit_cast", (node,))

    def _divisor_may_be_minus_one(self, result_type, divisor: Optional[ASTNode]) -> bool:
        """True when an integral `/` or `%` could be `MIN / -1`.

        A leaf on purpose: it reads the type and the divisor node only.
        """
        if isinstance(result_type, PrimitiveType):
            if not result_type.is_integral() or not result_type.name.startswith("i"):
                return False
        elif not isinstance(result_type, GenericParamType):
            # `__a7_div` and `__a7_rem` test the instantiated type of a
            # generic parameter at Zig compile time.
            return False
        return not self._is_nonnegative_integer_literal(divisor)

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
        """Debug always wraps. Release and fast drop the wrapping suffix when
        the safety pass proved the result fits the type range. --no-nonwrap
        keeps wrapping in every profile, so an optimized build stays
        bit-identical to debug regardless of which proofs happen to be
        discharged."""
        if self._force_wrapping:
            return True
        if self._profile == "debug" or self._backend_plan is None:
            return True
        return not self._backend_plan.is_approved(node, f"{op.name.lower()}_nonwrap")

    def _emit_if_expr(self, node: ASTNode) -> str:
        """Emit if expression."""
        return self._expression_work("_emit_if_expr", (node,))

    def _emit_match_expr(self, node: ASTNode) -> str:
        """Emit match expression → Zig switch expression, or an if-chain block."""
        return self._expression_work("_emit_match_expr", (node,))

    def _emit_match_expr_with_captures(self, node: ASTNode) -> str:
        """Emit a capture-bearing match expression as a Zig block expression."""
        return self._expression_work("_emit_match_expr_with_captures", (node,))

    def _emit_struct_init(self, node: ASTNode) -> str:
        """Emit struct initialization."""
        return self._expression_work("_emit_struct_init", (node,))

    def _emit_array_init(self, node: ASTNode) -> str:
        """Emit array initialization.

        The literal is anonymous: Zig gives it the type of its destination
        (a declaration, parameter, field or return type). The checker records
        the literal's own type before fitting it to that destination, so a
        typed literal here would be `[3]i32` for `a: [3]i64 = [1, 2, 3]`.
        """
        return self._expression_work("_emit_array_init", (node,))

    def _typed_array_literal(self, node: ASTNode, rendered: str) -> str:
        """Give an array literal its own type where nothing supplies one.

        `[1, 2][i]` and `for v in [1, 2]` have no destination type; Zig would
        make a tuple, which has no runtime index. Leaf: takes rendered text.
        """
        array_type = self._type_map.get(id(node))
        if not (isinstance(array_type, ArrayType) and isinstance(array_type.size, int)):
            return rendered
        return f"({self._emit_semantic_type(array_type)}{rendered[1:]})"

    def _emit_new_expr(self, node: ASTNode) -> str:
        """Emit new expression → `__a7_new`. The checker rejects `new [N]T`."""
        return self._expression_work("_emit_new_expr", (node,))

    def _emit_pattern(self, node: ASTNode) -> str:
        """Emit a match pattern."""
        return self._expression_work("_emit_pattern", (node,))

    def _emit_match_condition_zig(self, scrutinee_expr: str, patterns: list[ASTNode], by_content: bool = False) -> str:
        """Condition of one if-chain arm. `by_content` marks a string scrutinee."""
        return self._expression_work("_emit_match_condition_zig", (scrutinee_expr, patterns, by_content,))

    def _emit_match_pattern_condition_zig(
        self,
        scrutinee_expr: str,
        pattern: ASTNode,
        by_content: bool = False,
    ) -> Optional[str]:
        return self._expression_work("_emit_match_pattern_condition_zig", (scrutinee_expr, pattern, by_content,))

    def _unique_name(self, prefix: str) -> str:
        self._name_counter += 1
        return f"{prefix}_{self._name_counter}"

    # === Type emission ===

    def _emit_type_node(self, node: ASTNode, span=None) -> str:
        """Emit a type as a Zig type string. Iterative for linear chains.

        A `$T` resolves against `self._generic_env`, the generic parameters
        of the declaration being emitted.
        """
        return self._expression_work("_emit_type_node", (node, span,))

    def _emit_type_leaf(self, node: ASTNode, span=None) -> str:
        """Emit a non-chain (leaf) type node."""
        return self._expression_work("_emit_type_leaf", (node, span,))

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
        if type_name not in mapping:
            raise CodegenError(f"Zig backend: internal error: '{type_name}' is not a primitive type")
        return mapping[type_name]

    def _emit_semantic_type(self, type_obj) -> str:
        parts = []
        pending = [("type", type_obj)]
        while pending:
            action, value = pending.pop()
            if action == "text":
                parts.append(value)
                continue
            if isinstance(value, PrimitiveType):
                parts.append(self._map_primitive_type(value.name))
            elif isinstance(value, GenericParamType):
                parts.append(self._quote_identifier(value.name))
            elif isinstance(value, GenericValueArg):
                parts.append(("true" if value.value else "false") if value.is_bool else str(value.value))
            elif isinstance(value, ArrayType):
                size = value.size if value.size is not None else value.size_param
                parts.append(f"[{size}]")
                pending.append(("type", value.element_type))
            elif isinstance(value, (PointerType, ReferenceType)):
                parts.append("?*")
                child = value.pointee_type if isinstance(value, PointerType) else value.referent_type
                pending.append(("type", child))
            elif isinstance(value, SliceType):
                parts.append("[]")
                pending.append(("type", value.element_type))
            elif isinstance(value, (GenericInstanceType, FunctionType)):
                if isinstance(value, GenericInstanceType):
                    name = self._global_renames.get(value.base_name, value.base_name)
                    parts.append(f"{self._quote_identifier(name)}(")
                    pending.append(("text", ")"))
                    args = value.type_args
                else:
                    parts.append("*const fn (")
                    pending.append(("type", value.return_type) if value.return_type is not None else ("text", "void"))
                    pending.append(("text", ") "))
                    args = value.param_types
                for i in range(len(args) - 1, -1, -1):
                    pending.append(("type", args[i]))
                    if i:
                        pending.append(("text", ", "))
            elif isinstance(value, (StructType, EnumType, UnionType)) and value.name:
                parts.append(self._quote_identifier(self._global_renames.get(value.name, value.name)))
            else:
                raise CodegenError(
                    f"Zig backend: internal error: no Zig type for semantic type '{type(value).__name__}'"
                )
        return "".join(parts)

    def _default_value(self, type_node: ASTNode) -> str:
        """Generate a default value for a type."""
        if type_node is None:
            raise CodegenError("Zig backend: internal error: default value of a missing type")

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
            size = self._emit_expr(type_node.size)
            inner_default = self._default_value_for_elem(type_node.element_type)
            if "__a7_zero(" in inner_default:
                # Aggregate elements: let the helper fill the array at run time.
                return f"__a7_zero({self._emit_type_node(type_node)})"
            return f"[_]{elem}{{{inner_default}}} ** {size}"
        elif kind == NodeKind.TYPE_POINTER:
            return "null"
        elif kind == NodeKind.TYPE_SLICE:
            return "&.{}"
        elif kind == NodeKind.TYPE_FUNCTION:
            # A function pointer has no zero value in Zig.
            return "undefined"

        self._helpers.add("zero")
        return f"__a7_zero({self._emit_type_node(type_node)})"

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
        elif current is not None and current.kind == NodeKind.TYPE_SLICE:
            value = "&.{}"
        elif current is None:
            raise CodegenError("Zig backend: internal error: array type has no element type", type_node.span if type_node else None)
        elif current.kind == NodeKind.TYPE_FUNCTION:
            # A function pointer has no zero value in Zig.
            value = "undefined"
        else:
            self._helpers.add("zero")
            value = f"__a7_zero({self._emit_type_node(current)})"
        for array in reversed(arrays):
            elem = self._emit_type_node(array.element_type)
            size = self._emit_expr(array.size)
            value = f"[_]{elem}{{{value}}} ** {size}"
        return value

    # === I/O special-casing ===

    def _is_io_call(self, node: ASTNode) -> bool:
        """Check if this is an stdlib io print call."""
        if node.kind != NodeKind.CALL:
            return False
        canonical = getattr(node, "stdlib_canonical", None)
        return canonical in {"std.io.println", "std.io.print", "std.io.eprintln"}

    def _is_io_result_call(self, node: ASTNode) -> bool:
        """Check if this is a Result-returning stdlib io call.

        A leaf on purpose: it reads node attributes only, so the
        no-recursion call-graph ratchet is unaffected.
        """
        if node is None or node.kind != NodeKind.CALL:
            return False
        canonical = getattr(node, "stdlib_canonical", None)
        return canonical in {"std.io.println_ok", "std.io.read_line"}

    def _emit_io_call(self, node: ASTNode) -> None:
        """Emit an io.println/io.print call as a statement."""
        self._write_indent()
        self.output.write(self._io_call_text(node) + ";\n")

    def _io_call_text(self, node: ASTNode) -> str:
        """An io.println/io.print/io.eprintln call as Zig text, without `;`.

        Called from statement positions only (`_emit_call` must not call it:
        that would join the expression emitters' recursive group).
        """
        field = node.stdlib_canonical.split(".")[-1]
        stream = "stderr" if field == "eprintln" else "stdout"
        newline = field in {"println", "eprintln"}
        args = node.arguments or []
        if not args:
            empty = '"\\n"' if newline else '""'
            return f"__a7_{stream}_print({empty}, .{{}})"

        # First arg is the format string; `{}` becomes a typed Zig placeholder.
        fmt_str = self._convert_format_string(self._emit_expr(args[0]), args[1:])
        if newline and fmt_str.endswith('"'):
            fmt_str = fmt_str[:-1] + '\\n"'
        zig_args = ", ".join(self._emit_expr(a) for a in args[1:])
        if not zig_args:
            rendered = ".{}"
        elif self._has_top_level_comma(zig_args):
            rendered = f".{{ {zig_args} }}"
        else:
            rendered = f".{{{zig_args}}}"
        return f"__a7_{stream}_print({fmt_str}, {rendered})"

    def _emit_io_call_expr(self, node: ASTNode) -> str:
        """io.print, io.println and io.eprintln return nothing."""
        name = node.stdlib_canonical.split(".")[-1]
        raise CodegenError(
            f"Zig backend: io.{name} is a void call and has no value; it cannot be used as an expression",
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
        if op not in mapping:
            raise CodegenError(f"Zig backend: internal error: assignment operator '{getattr(op, 'name', op)}' has no lowering")
        return mapping[op]

    def _emit_statement_as_expr(self, node: ASTNode) -> str:
        """Emit a statement as an expression string (for while continue expressions)."""
        if node.kind == NodeKind.ASSIGNMENT:
            if getattr(node, "implicit_deref_target", False):
                self._require_backend_approval(node, "deref")
                target = self._emit_implicit_deref(node.target)
            else:
                target = self._emit_expr(node.target)
            value = self._emit_expr(node.value)
            return self._assignment_text(node, target, value)
        elif node.kind == NodeKind.EXPRESSION_STMT and node.expression:
            if self._is_io_call(node.expression):
                return self._io_call_text(node.expression)
            value = self._emit_expr(node.expression)
            return value if self._expression_returns_void(node.expression) else "_ = " + value
        raise CodegenError(
            f"Zig backend: '{node.kind.name}' cannot be a loop update statement",
            node.span,
        )

    def _write_indent(self) -> None:
        """Write current indentation to output."""
        self.output.write("    " * self.indent_level)
