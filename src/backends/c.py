"""
C code generation backend for the A7 compiler.

Translates A7 AST nodes to portable C11 source.
"""

from __future__ import annotations

from io import StringIO
from typing import Dict, Optional, Set

from ..ast_nodes import ASTNode, NodeKind, LiteralKind, BinaryOp, UnaryOp, AssignOp
from ..errors import CodegenError
from ..types import (
    ArrayType,
    CHAR,
    EnumType,
    FunctionType,
    GenericInstanceType,
    GenericParamType,
    PointerType,
    PrimitiveType,
    ReferenceType,
    SliceType,
    STRING,
    StructType,
    TypeKind,
    UnionType,
)
from .base import CodeGenerator


class CCodeGenerator(CodeGenerator):
    """Generates C11 source code from A7 AST."""

    _C_RESERVED = {
        "auto",
        "break",
        "case",
        "char",
        "const",
        "continue",
        "default",
        "do",
        "double",
        "else",
        "enum",
        "extern",
        "float",
        "for",
        "goto",
        "if",
        "inline",
        "int",
        "long",
        "register",
        "restrict",
        "return",
        "short",
        "signed",
        "sizeof",
        "static",
        "struct",
        "switch",
        "typedef",
        "union",
        "unsigned",
        "void",
        "volatile",
        "while",
        "_Alignas",
        "_Alignof",
        "_Atomic",
        "_Bool",
        "_Complex",
        "_Generic",
        "_Imaginary",
        "_Noreturn",
        "_Static_assert",
        "_Thread_local",
    }

    _C_GLOBAL_CONFLICTS = {
        "abs",
        "sqrt",
        "sin",
        "cos",
        "tan",
        "log",
        "exp",
        "floor",
        "ceil",
        "printf",
        "fprintf",
    }

    _AST_CHILD_ATTRS = (
        "declarations",
        "statements",
        "body",
        "then_stmt",
        "else_stmt",
        "init",
        "update",
        "cases",
        "else_case",
        "expression",
        "condition",
        "value",
        "target",
        "function",
        "arguments",
        "field_inits",
        "elements",
        "operand",
        "left",
        "right",
        "pointer",
        "then_expr",
        "else_expr",
        "iterable",
        "statement",
        "patterns",
        "object",
        "index",
        "literal",
        "start",
        "end",
        "explicit_type",
        "param_type",
        "return_type",
        "target_type",
        "element_type",
        "parameter_types",
        "type_args",
        "type_arguments",
        "fields",
        "parameters",
        "variants",
        "generic_params",
        "types",
    )

    _MATH_CALL_MAP = {
        "std.math.sqrt": "sqrt",
        "std.math.abs": "fabs",
        "std.math.floor": "floor",
        "std.math.ceil": "ceil",
        "std.math.sin": "sin",
        "std.math.cos": "cos",
        "std.math.tan": "tan",
        "std.math.log": "log",
        "std.math.exp": "exp",
        "std.math.min": "fmin",
        "std.math.max": "fmax",
    }

    def __init__(self):
        super().__init__()
        self._type_map: Dict = {}
        self._symbol_table = None

        self._needs_stdio = False
        self._needs_stdint = False
        self._needs_stdbool = False
        self._needs_stddef = False
        self._needs_stdlib = False
        self._needs_math = False
        self._needs_ptr_helper = False
        self._needs_float_helper = False
        self._needs_string = False

        self._declared_structs: Set[str] = set()
        self._declared_enums: Set[str] = set()
        self._enum_variants: Dict[str, Set[str]] = {}
        self._inline_struct_names: Dict[int, str] = {}
        self._inline_struct_defs: list[tuple[str, ASTNode]] = []
        self._slice_type_names: Dict[str, str] = {}
        self._slice_type_defs: list[tuple[str, ASTNode]] = []

        self._name_counter = 0
        self._function_return_nodes: Dict[str, Optional[ASTNode]] = {}
        self._current_function_name: Optional[str] = None
        self._current_function_return_type: str = "void"
        self._current_inline_return_type: Optional[str] = None
        self._inside_main = False
        self._main_has_return = False

        self._defer_scopes: list[list[str]] = []
        self._loop_frames: list[dict[str, object]] = []

    @property
    def file_extension(self) -> str:
        return ".c"

    @property
    def language_name(self) -> str:
        return "C"

    def generate(
        self, ast: ASTNode, type_map: Optional[Dict] = None, symbol_table=None
    ) -> str:
        """Generate C11 source code from an A7 AST."""
        self.reset()
        self._type_map = type_map or {}
        self._symbol_table = symbol_table

        self._needs_stdio = False
        self._needs_stdint = False
        self._needs_stdbool = False
        self._needs_stddef = False
        self._needs_stdlib = False
        self._needs_math = False
        self._needs_ptr_helper = False
        self._needs_float_helper = False
        self._needs_string = False

        self._declared_structs = set()
        self._declared_enums = set()
        self._enum_variants = {}
        self._inline_struct_names = {}
        self._inline_struct_defs = []
        self._slice_type_names = {}
        self._slice_type_defs = []

        self._name_counter = 0
        self._function_return_nodes = {}
        self._current_function_name = None
        self._current_function_return_type = "void"
        self._current_inline_return_type = None
        self._inside_main = False
        self._main_has_return = False

        self._defer_scopes = []
        self._loop_frames = []

        self._scan_features(ast)
        self.output.write(self._emit_preamble())
        self.visit(ast)
        return self.output.getvalue()

    def visit(self, node: ASTNode) -> None:
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
        elif kind == NodeKind.TYPE_ALIAS:
            self._visit_type_alias(node)
        elif kind == NodeKind.CONST:
            self._visit_const(node)
        elif kind == NodeKind.VAR:
            self._visit_var(node)
        elif kind == NodeKind.BLOCK:
            self._visit_block_inline(node)
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
            raise CodegenError("C backend: fallthrough is not implemented", node.span)
        elif kind == NodeKind.DEFER:
            self._visit_defer(node)
        elif kind == NodeKind.DEL:
            self._visit_del(node)
        elif kind == NodeKind.ASSIGNMENT:
            self._visit_assignment(node)
        elif kind == NodeKind.EXPRESSION_STMT:
            self._visit_expression_stmt(node)
        elif kind == NodeKind.IMPORT:
            return
        else:
            raise CodegenError(f"C backend: unsupported statement node '{kind.name}'", node.span)

    # ------------------------------------------------------------------
    # Scanning / preamble
    # ------------------------------------------------------------------

    def _scan_features(self, root: ASTNode) -> None:
        if root is None:
            return

        def visitor(node: ASTNode) -> None:
            if node.kind == NodeKind.ENUM and node.name:
                self._declared_enums.add(node.name)
                self._enum_variants[node.name] = {
                    (v.name or "") for v in (node.variants or []) if v.name
                }

            if node.kind == NodeKind.FUNCTION and node.return_type:
                fn_name = self._sanitize_name(node.name or "anon")
                self._function_return_nodes[fn_name] = node.return_type
                if node.return_type.kind == NodeKind.TYPE_STRUCT:
                    type_name = f"{fn_name}__ret_t"
                    self._register_inline_struct(node.return_type, type_name)
                    self._needs_stdint = True
            elif node.kind == NodeKind.FUNCTION:
                fn_name = self._sanitize_name(node.name or "anon")
                self._function_return_nodes[fn_name] = None

            if node.kind == NodeKind.TYPE_STRUCT:
                if id(node) not in self._inline_struct_names:
                    self._register_inline_struct(node, f"a7_inline_struct_{len(self._inline_struct_defs)}")
                self._needs_stdint = True

            if node.kind == NodeKind.TYPE_SLICE:
                self._needs_stddef = True
                self._register_slice_type(node)

            result_type = self._type_map.get(id(node))
            if isinstance(result_type, SliceType):
                self._needs_stddef = True
                self._semantic_type_to_c(result_type)

            if node.kind == NodeKind.SLICE:
                source_type = self._type_map.get(id(node.object)) if node.object else None
                if source_type is not None and source_type.equals(STRING):
                    self._needs_stddef = True
                    if node.end is None:
                        self._needs_string = True

            if node.kind in {NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED}:
                iterable_type = self._type_map.get(id(node.iterable)) if node.iterable else None
                if iterable_type is not None and iterable_type.equals(STRING):
                    self._needs_stddef = True
                    self._needs_string = True

            if node.kind in {NodeKind.NEW_EXPR, NodeKind.DEL}:
                self._needs_stdlib = True
                self._needs_stddef = True

            if node.kind == NodeKind.CALL:
                canonical = getattr(node, "stdlib_canonical", None)
                if canonical and canonical.startswith("std.io."):
                    self._needs_stdio = True
                    # Keep available for unknown/ref print arguments.
                    self._needs_ptr_helper = True
                    self._needs_float_helper = True
                    self._needs_stdbool = True
                if canonical and canonical.startswith("std.math."):
                    self._needs_math = True

            if node.kind == NodeKind.LITERAL:
                if node.literal_kind == LiteralKind.BOOLEAN:
                    self._needs_stdbool = True
                elif node.literal_kind == LiteralKind.NIL:
                    self._needs_stddef = True
                elif node.literal_kind == LiteralKind.INTEGER:
                    self._needs_stdint = True

            if node.kind == NodeKind.TYPE_PRIMITIVE:
                tname = node.type_name or ""
                if tname in {
                    "i8",
                    "i16",
                    "i32",
                    "i64",
                    "u8",
                    "u16",
                    "u32",
                    "u64",
                    "isize",
                    "usize",
                }:
                    self._needs_stdint = True
                if tname == "bool":
                    self._needs_stdbool = True
                if tname == "usize":
                    self._needs_stddef = True

            if node.kind in {
                NodeKind.TYPE_POINTER,
                NodeKind.TYPE_ARRAY,
                NodeKind.FOR_IN,
                NodeKind.FOR_IN_INDEXED,
            }:
                self._needs_stddef = True

        self._walk_ast(root, visitor)

    def _emit_preamble(self) -> str:
        lines: list[str] = []

        includes: list[str] = ["stdint.h"]
        if self._needs_stdio:
            includes.append("stdio.h")
        if self._needs_stdlib or self._needs_float_helper:
            includes.append("stdlib.h")
        if self._needs_stdbool:
            includes.append("stdbool.h")
        if self._needs_stddef:
            includes.append("stddef.h")
        if self._needs_math:
            includes.append("math.h")
        if self._needs_string:
            includes.append("string.h")

        for header in includes:
            lines.append(f"#include <{header}>")

        if includes:
            lines.append("")

        if self._needs_stddef:
            lines.append("#define A7_ARRAY_LEN(arr) (sizeof(arr) / sizeof((arr)[0]))")
            lines.append("")

        if self._needs_stdbool:
            lines.append("static inline const char* a7_bool_str(bool value) {")
            lines.append("    return value ? \"true\" : \"false\";")
            lines.append("}")
            lines.append("")

        if self._needs_ptr_helper:
            lines.append("static inline const char* a7_ptr_str(const void* p) {")
            lines.append("    return p ? \"<ptr>\" : \"null\";")
            lines.append("}")
            lines.append("")

        if self._needs_float_helper:
            lines.append("static inline const char* a7_f64_str(double value) {")
            lines.append("    enum { A7_FLOAT_SLOTS = 8, A7_FLOAT_BUF = 64 };")
            lines.append("    static char buffers[A7_FLOAT_SLOTS][A7_FLOAT_BUF];")
            lines.append("    static int idx = 0;")
            lines.append("    char* buf = buffers[idx];")
            lines.append("    idx = (idx + 1) % A7_FLOAT_SLOTS;")
            lines.append("    if (value <= 9.2233720368547758e18 && value >= -9.2233720368547758e18) {")
            lines.append("        long long as_int = (long long)value;")
            lines.append("        if (value == (double)as_int) {")
            lines.append("            snprintf(buf, A7_FLOAT_BUF, \"%lld\", as_int);")
            lines.append("            return buf;")
            lines.append("        }")
            lines.append("    }")
            lines.append("    for (int precision = 1; precision <= 17; ++precision) {")
            lines.append("        snprintf(buf, A7_FLOAT_BUF, \"%.*g\", precision, value);")
            lines.append("        char* end = NULL;")
            lines.append("        double roundtrip = strtod(buf, &end);")
            lines.append("        if (end && *end == '\\0' && roundtrip == value) {")
            lines.append("            return buf;")
            lines.append("        }")
            lines.append("    }")
            lines.append("    snprintf(buf, A7_FLOAT_BUF, \"%.17g\", value);")
            lines.append("    return buf;")
            lines.append("}")
            lines.append("")

        return "\n".join(lines)

    def _walk_ast(self, node: ASTNode, visitor) -> None:
        stack = [node]
        while stack:
            n = stack.pop()
            if n is None:
                continue
            visitor(n)
            children = []
            for attr_name in self._AST_CHILD_ATTRS:
                value = getattr(n, attr_name, None)
                if isinstance(value, ASTNode):
                    children.append(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, ASTNode):
                            children.append(item)
            stack.extend(reversed(children))

    def _register_inline_struct(self, node: ASTNode, name: str) -> str:
        key = id(node)
        if key in self._inline_struct_names:
            return self._inline_struct_names[key]
        self._inline_struct_names[key] = name
        self._inline_struct_defs.append((name, node))
        return name

    def _register_slice_type(self, node: ASTNode) -> str:
        elem = self._emit_type_node(node.element_type) if node.element_type else "uint8_t"
        safe_elem = elem.replace(" ", "_").replace("*", "ptr")
        name = f"a7_slice_{safe_elem}"
        if name not in self._slice_type_names:
            self._slice_type_names[name] = name
            self._slice_type_defs.append((name, node))
        return name

    # ------------------------------------------------------------------
    # Top-level declarations
    # ------------------------------------------------------------------

    def _visit_program(self, node: ASTNode) -> None:
        self._emit_inline_type_defs()
        self._emit_slice_type_defs()

        decls = node.declarations or []
        non_funcs = [d for d in decls if d.kind != NodeKind.FUNCTION]
        funcs = [d for d in decls if d.kind == NodeKind.FUNCTION]

        for decl in non_funcs:
            if decl.kind == NodeKind.IMPORT:
                continue
            self.visit(decl)
            self.output.write("\n")

        if funcs:
            for fn in funcs:
                self._emit_function_prototype(fn)
            if funcs:
                self.output.write("\n")
            for fn in funcs:
                self._visit_function(fn)
                self.output.write("\n")

    def _emit_inline_type_defs(self) -> None:
        for name, type_node in self._inline_struct_defs:
            self._write_indent()
            self.output.write("typedef struct {\n")
            self.indent()
            for field in (type_node.fields or []):
                fname = self._sanitize_name(field.name or "field")
                ftype = self._emit_type_node(field.field_type)
                self._write_indent()
                self.output.write(f"{ftype} {fname};\n")
            self.dedent()
            self._write_indent()
            self.output.write(f"}} {name};\n\n")

    def _emit_slice_type_defs(self) -> None:
        for name, type_node in self._slice_type_defs:
            elem_type = self._emit_type_node(type_node.element_type) if type_node.element_type else "uint8_t"
            self._write_indent()
            self.output.write("typedef struct {\n")
            self.indent()
            self._write_indent()
            self.output.write(f"{elem_type}* data;\n")
            self._write_indent()
            self.output.write("size_t len;\n")
            self.dedent()
            self._write_indent()
            self.output.write(f"}} {name};\n\n")

    def _emit_function_prototype(self, node: ASTNode) -> None:
        name = self._sanitize_name(node.name or "anonymous")
        sig = self._function_signature(node, prototype=True)
        self._write_indent()
        self.output.write(sig + ";\n")

    def _visit_function(self, node: ASTNode) -> None:
        name = self._sanitize_name(node.name or "anonymous")
        self._current_function_name = name
        self._inside_main = name == "main"
        self._main_has_return = False
        self._current_inline_return_type = (
            self._inline_struct_names.get(id(node.return_type))
            if node.return_type and node.return_type.kind == NodeKind.TYPE_STRUCT
            else None
        )
        self._current_function_return_type = self._function_return_type(node)

        self._write_indent()
        self.output.write(self._function_signature(node, prototype=False))
        self.output.write(" {\n")
        self.indent()

        self._defer_scopes.append([])
        body = node.body
        if body and body.kind == NodeKind.BLOCK:
            for stmt in (body.statements or []):
                if stmt.kind == NodeKind.FUNCTION:
                    raise CodegenError(
                        "C backend: nested function declarations are not supported",
                        stmt.span,
                    )
                self.visit(stmt)
        elif body:
            self.visit(body)

        # Implicit main return for valid C signature.
        if self._inside_main and not self._main_has_return:
            self._emit_deferred_unwind(0)
            self._write_indent()
            self.output.write("return 0;\n")
        else:
            self._emit_current_scope_defers()

        self._defer_scopes.pop()

        self.dedent()
        self._write_indent()
        self.output.write("}\n")

        self._current_function_name = None
        self._current_function_return_type = "void"
        self._current_inline_return_type = None
        self._inside_main = False

    def _visit_struct(self, node: ASTNode) -> None:
        name = self._sanitize_name(node.name or "anon")
        self._declared_structs.add(name)
        self._write_indent()
        self.output.write(f"typedef struct {name} {{\n")
        self.indent()
        for field in (node.fields or []):
            fname = self._sanitize_name(field.name or "field")
            ftype = self._emit_type_node(field.field_type)
            self._write_indent()
            self.output.write(f"{ftype} {fname};\n")
        self.dedent()
        self._write_indent()
        self.output.write(f"}} {name};\n")

    def _visit_union(self, node: ASTNode) -> None:
        name = self._sanitize_name(node.name or "anon")
        self._write_indent()
        self.output.write(f"typedef union {name} {{\n")
        self.indent()
        for field in (node.fields or []):
            fname = self._sanitize_name(field.name or "field")
            ftype = self._emit_type_node(field.field_type)
            self._write_indent()
            self.output.write(f"{ftype} {fname};\n")
        self.dedent()
        self._write_indent()
        self.output.write(f"}} {name};\n")

    def _visit_enum(self, node: ASTNode) -> None:
        name = self._sanitize_name(node.name or "anon")
        variants = node.variants or []
        self._write_indent()
        self.output.write(f"typedef enum {name} {{\n")
        self.indent()
        for i, variant in enumerate(variants):
            vname = self._sanitize_name(variant.name or f"Variant{i}")
            enum_value_name = f"{name}_{vname}"
            self._write_indent()
            if variant.value is not None:
                val = self._emit_expr(variant.value)
                self.output.write(f"{enum_value_name} = {val}")
            else:
                self.output.write(enum_value_name)
            self.output.write(",\n")
        self.dedent()
        self._write_indent()
        self.output.write(f"}} {name};\n")

    def _visit_type_alias(self, node: ASTNode) -> None:
        alias = self._sanitize_name(node.name or "Alias")
        if node.value is None:
            raise CodegenError("C backend: type alias missing target type", node.span)
        if node.value.kind == NodeKind.TYPE_FUNCTION:
            self._write_indent()
            self.output.write(f"typedef {self._emit_function_pointer_declarator(node.value, alias)};\n")
            return
        target = self._emit_type_node(node.value)
        self._write_indent()
        self.output.write(f"typedef {target} {alias};\n")

    def _visit_const(self, node: ASTNode) -> None:
        name = self._sanitize_name(node.name or "const_value")
        c_type = self._infer_decl_type(node.explicit_type, node.value, node)
        value = self._emit_expr(node.value) if node.value else self._default_value(node.explicit_type, c_type)
        self._write_indent()
        self.output.write(f"const {c_type} {name} = {value};\n")

    def _visit_var(self, node: ASTNode) -> None:
        name = self._sanitize_name(node.emit_name or node.name or "var_value")
        explicit_type = getattr(node, "explicit_type", None)

        if explicit_type and explicit_type.kind == NodeKind.TYPE_ARRAY:
            elem_type = self._emit_type_node(explicit_type.element_type)
            size = self._emit_expr(explicit_type.size) if explicit_type.size else "0"
            if node.value and node.value.kind == NodeKind.ARRAY_INIT:
                init = self._emit_array_init(node.value)
                self._write_indent()
                self.output.write(f"{elem_type} {name}[{size}] = {init};\n")
            elif node.value:
                raise CodegenError(
                    "C backend: array variable must be initialized with array literal",
                    node.span,
                )
            else:
                self._write_indent()
                self.output.write(f"{elem_type} {name}[{size}] = {{0}};\n")
            return

        if explicit_type and explicit_type.kind == NodeKind.TYPE_FUNCTION:
            self._write_indent()
            if node.value:
                init = self._emit_expr(node.value)
                self.output.write(f"{self._emit_declarator(explicit_type, name)} = {init};\n")
            else:
                self._needs_stddef = True
                self.output.write(f"{self._emit_declarator(explicit_type, name)} = NULL;\n")
            return

        c_type = self._infer_decl_type(explicit_type, node.value, node)
        if node.value:
            if (
                node.value.kind == NodeKind.MATCH_EXPR
                and not self._is_side_effect_free_match_scrutinee(node.value.expression)
            ):
                self._emit_side_effectful_match_var_init(name, c_type, node.value)
                return

            self._write_indent()
            init = self._emit_expr(node.value)
            if self._is_null_literal(node.value) and not c_type.endswith("*"):
                c_type = "void*"
            self.output.write(f"{c_type} {name} = {init};\n")
        else:
            self._write_indent()
            default = self._default_value(explicit_type, c_type)
            self.output.write(f"{c_type} {name} = {default};\n")

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def _visit_block_inline(self, node: ASTNode) -> None:
        self.output.write("{\n")
        self.indent()
        self._defer_scopes.append([])
        for stmt in (node.statements or []):
            if stmt.kind == NodeKind.FUNCTION:
                raise CodegenError(
                    "C backend: nested function declarations are not supported",
                    stmt.span,
                )
            self.visit(stmt)
        self._emit_current_scope_defers()
        self._defer_scopes.pop()
        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    def _visit_if_stmt(self, node: ASTNode) -> None:
        self._write_indent()
        cond = self._emit_expr(node.condition)
        self.output.write(f"if ({cond}) ")
        self._emit_stmt_or_block(node.then_stmt)

        if node.else_stmt:
            self._write_indent()
            self.output.write("else ")
            if node.else_stmt.kind == NodeKind.IF_STMT:
                # else-if chain
                cond2 = self._emit_expr(node.else_stmt.condition)
                self.output.write(f"if ({cond2}) ")
                self._emit_stmt_or_block(node.else_stmt.then_stmt)
                current = node.else_stmt.else_stmt
                while current and current.kind == NodeKind.IF_STMT:
                    self._write_indent()
                    self.output.write("else ")
                    cond3 = self._emit_expr(current.condition)
                    self.output.write(f"if ({cond3}) ")
                    self._emit_stmt_or_block(current.then_stmt)
                    current = current.else_stmt
                if current:
                    self._write_indent()
                    self.output.write("else ")
                    self._emit_stmt_or_block(current)
            else:
                self._emit_stmt_or_block(node.else_stmt)

    def _visit_while(self, node: ASTNode) -> None:
        if node.label:
            self._visit_labeled_while(node)
            return

        self._write_indent()
        cond = self._emit_expr(node.condition) if node.condition else "1"
        self.output.write(f"while ({cond}) ")
        marker = len(self._defer_scopes)
        self._push_loop_frame(label=None, unwind_depth=marker)
        self._emit_stmt_or_block(node.body)
        self._pop_loop_frame()

    def _visit_for(self, node: ASTNode) -> None:
        if node.label:
            self._visit_labeled_for(node)
            return

        init = self._emit_for_clause(node.init)
        cond = self._emit_expr(node.condition) if node.condition else "1"
        update = self._emit_for_clause(node.update)
        self._write_indent()
        self.output.write(f"for ({init}; {cond}; {update}) ")
        marker = len(self._defer_scopes)
        self._push_loop_frame(label=None, unwind_depth=marker)
        self._emit_stmt_or_block(node.body)
        self._pop_loop_frame()

    def _visit_for_in(self, node: ASTNode) -> None:
        if node.label:
            self._visit_labeled_for_in(node, indexed=False)
            return

        iterable_expr = self._emit_expr(node.iterable)
        iterable_type = self._type_map.get(id(node.iterable)) if node.iterable else None
        cache_name = self._unique_name("__a7_iter")
        cache_type = self._iterable_cache_type(iterable_type)
        elem_type = self._iterable_element_type(iterable_type)
        length_expr = self._iterable_length_expr(node.iterable, cache_name, iterable_type)

        idx_name = self._unique_name("__a7_i")
        iter_name = self._sanitize_name(node.iterator or "item")

        self._write_indent()
        self.output.write("{\n")
        self.indent()
        self._write_indent()
        self.output.write(f"{cache_type} {cache_name} = {iterable_expr};\n")
        self._write_indent()
        self.output.write(
            f"for (size_t {idx_name} = 0; {idx_name} < {length_expr}; ++{idx_name}) "
        )
        self.output.write("{\n")
        self.indent()
        self._defer_scopes.append([])
        self._write_indent()
        self.output.write(
            f"{elem_type} {iter_name} = {self._emit_iterable_element_expr(node.iterable, cache_name, iterable_type, idx_name)};\n"
        )

        marker = len(self._defer_scopes) - 1
        self._push_loop_frame(label=None, unwind_depth=marker)
        if node.body and node.body.kind == NodeKind.BLOCK:
            for stmt in (node.body.statements or []):
                self.visit(stmt)
        elif node.body:
            self.visit(node.body)
        self._pop_loop_frame()

        self._emit_current_scope_defers()
        self._defer_scopes.pop()
        self.dedent()
        self._write_indent()
        self.output.write("}\n")
        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    def _visit_for_in_indexed(self, node: ASTNode) -> None:
        if node.label:
            self._visit_labeled_for_in(node, indexed=True)
            return

        iterable_expr = self._emit_expr(node.iterable)
        iterable_type = self._type_map.get(id(node.iterable)) if node.iterable else None
        cache_name = self._unique_name("__a7_iter")
        cache_type = self._iterable_cache_type(iterable_type)
        elem_type = self._iterable_element_type(iterable_type)
        length_expr = self._iterable_length_expr(node.iterable, cache_name, iterable_type)

        idx_name = self._unique_name("__a7_i")
        index_var = self._sanitize_name(node.index_var or "index")
        iter_name = self._sanitize_name(node.iterator or "item")

        self._write_indent()
        self.output.write("{\n")
        self.indent()
        self._write_indent()
        self.output.write(f"{cache_type} {cache_name} = {iterable_expr};\n")
        self._write_indent()
        self.output.write(
            f"for (size_t {idx_name} = 0; {idx_name} < {length_expr}; ++{idx_name}) "
        )
        self.output.write("{\n")
        self.indent()
        self._defer_scopes.append([])
        self._write_indent()
        self.output.write(f"size_t {index_var} = {idx_name};\n")
        self._write_indent()
        self.output.write(
            f"{elem_type} {iter_name} = {self._emit_iterable_element_expr(node.iterable, cache_name, iterable_type, idx_name)};\n"
        )

        marker = len(self._defer_scopes) - 1
        self._push_loop_frame(label=None, unwind_depth=marker)
        if node.body and node.body.kind == NodeKind.BLOCK:
            for stmt in (node.body.statements or []):
                self.visit(stmt)
        elif node.body:
            self.visit(node.body)
        self._pop_loop_frame()

        self._emit_current_scope_defers()
        self._defer_scopes.pop()
        self.dedent()
        self._write_indent()
        self.output.write("}\n")
        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    def _visit_match(self, node: ASTNode) -> None:
        if self._match_stmt_needs_if_chain(node):
            self._visit_match_as_if_chain(node)
            return

        expr = self._emit_expr(node.expression) if node.expression else "0"
        self._write_indent()
        self.output.write(f"switch ({expr}) {{\n")
        self.indent()

        for case in (node.cases or []):
            patterns = case.patterns or []
            if not patterns:
                continue
            for pattern in patterns:
                self._write_indent()
                pattern_code = self._emit_pattern(pattern)
                if pattern_code == "default":
                    self.output.write("default:\n")
                else:
                    self.output.write(f"case {pattern_code}:\n")
            stmt = getattr(case, "statement", None)
            self._emit_stmt_or_block(stmt)
            self._write_indent()
            self.output.write("break;\n")

        if node.else_case:
            self._write_indent()
            self.output.write("default:\n")
            if isinstance(node.else_case, list):
                stmt = node.else_case[0] if node.else_case else None
                self._emit_stmt_or_block(stmt)
            elif isinstance(node.else_case, ASTNode):
                self._emit_stmt_or_block(node.else_case)
            else:
                self._emit_stmt_or_block(None)
            self._write_indent()
            self.output.write("break;\n")

        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    def _match_stmt_needs_if_chain(self, node: ASTNode) -> bool:
        return any(
            pattern.kind in {NodeKind.PATTERN_IDENTIFIER, NodeKind.PATTERN_RANGE}
            for case in (node.cases or [])
            for pattern in (case.patterns or [])
        )

    def _visit_match_as_if_chain(self, node: ASTNode) -> None:
        expr = self._emit_expr(node.expression) if node.expression else "0"
        expr_type = self._semantic_type_to_c(self._type_map.get(id(node.expression))) or "int32_t"
        if expr_type == "int32_t":
            self._needs_stdint = True

        temp_name = self._unique_name("__a7_match")
        self._write_indent()
        self.output.write("{\n")
        self.indent()
        self._write_indent()
        self.output.write(f"{expr_type} {temp_name} = {expr};\n")

        emitted_branch = False
        emitted_unconditional = False
        for case in (node.cases or []):
            patterns = case.patterns or []
            if not patterns or emitted_unconditional:
                continue

            condition = self._emit_match_expr_condition(temp_name, patterns)
            if condition is None:
                prefix = "else " if emitted_branch else ""
                self._write_indent()
                self.output.write(f"{prefix}")
                self._emit_stmt_or_block(getattr(case, "statement", None))
                emitted_branch = True
                emitted_unconditional = True
                continue

            self._write_indent()
            self.output.write("else " if emitted_branch else "")
            self.output.write(f"if ({condition}) ")
            self._emit_stmt_or_block(getattr(case, "statement", None))
            emitted_branch = True

        if node.else_case and not emitted_unconditional:
            self._write_indent()
            if emitted_branch:
                self.output.write("else ")
            if isinstance(node.else_case, list):
                stmt = node.else_case[0] if node.else_case else None
                self._emit_stmt_or_block(stmt)
            elif isinstance(node.else_case, ASTNode):
                self._emit_stmt_or_block(node.else_case)
            else:
                self._emit_stmt_or_block(None)

        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    def _visit_return(self, node: ASTNode) -> None:
        if self._inside_main:
            self._main_has_return = True

        self._emit_deferred_unwind(0)
        self._write_indent()

        if self._inside_main and node.value is None:
            self.output.write("return 0;\n")
            return

        if node.value is None:
            self.output.write("return;\n")
            return

        value_expr = self._emit_expr(node.value)
        self.output.write(f"return {value_expr};\n")

    def _visit_break(self, node: ASTNode) -> None:
        frame = self._resolve_loop_frame(node.label)
        keep_depth = int(frame["unwind_depth"]) if frame else 0
        self._emit_deferred_unwind(keep_depth)
        self._write_indent()
        break_target = frame.get("break_target") if frame else None
        if break_target:
            self.output.write(f"goto {break_target};\n")
        else:
            self.output.write("break;\n")

    def _visit_continue(self, node: ASTNode) -> None:
        frame = self._resolve_loop_frame(node.label)
        keep_depth = int(frame["unwind_depth"]) if frame else 0
        self._emit_deferred_unwind(keep_depth)
        self._write_indent()
        continue_target = frame.get("continue_target") if frame else None
        if continue_target:
            self.output.write(f"goto {continue_target};\n")
        else:
            self.output.write("continue;\n")

    def _visit_defer(self, node: ASTNode) -> None:
        if not self._defer_scopes:
            raise CodegenError("C backend: defer used outside of a block scope", node.span)
        stmt = self._emit_defer_action(node)
        self._defer_scopes[-1].append(stmt)

    def _visit_del(self, node: ASTNode) -> None:
        expr_node = getattr(node, "expression", None) or getattr(node, "expr", None)
        if expr_node is None:
            return
        expr = self._emit_expr(expr_node)
        self._needs_stdlib = True
        self._write_indent()
        self.output.write(f"free({expr});\n")

    def _visit_assignment(self, node: ASTNode) -> None:
        target = self._emit_expr(node.target) if node.target else "/*target*/"
        value = self._emit_expr(node.value) if node.value else "/*value*/"
        op = getattr(node, "operator", None) or getattr(node, "op", AssignOp.ASSIGN)
        cop = self._assign_op_to_c(op)
        self._write_indent()
        self.output.write(f"{target} {cop} {value};\n")

    def _visit_expression_stmt(self, node: ASTNode) -> None:
        if not node.expression:
            return
        if self._is_io_call(node.expression):
            self._emit_io_call_stmt(node.expression)
            return
        expr = self._emit_expr(node.expression)
        self._write_indent()
        self.output.write(f"{expr};\n")

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------

    def _emit_expr(self, node: ASTNode) -> str:
        if node is None:
            return "0"

        kind = node.kind
        if kind == NodeKind.LITERAL:
            return self._emit_literal(node)
        if kind == NodeKind.IDENTIFIER:
            return self._sanitize_name(node.emit_name or node.name or "value")
        if kind == NodeKind.BINARY:
            return self._emit_binary(node)
        if kind == NodeKind.UNARY:
            return self._emit_unary(node)
        if kind == NodeKind.CALL:
            return self._emit_call(node)
        if kind == NodeKind.INDEX:
            obj = self._emit_expr(node.object)
            idx = self._emit_expr(node.index)
            return f"{self._emit_index_base_expr(node.object, obj)}[(size_t)({idx})]"
        if kind == NodeKind.SLICE:
            return self._emit_slice_expr(node)
        if kind == NodeKind.FIELD_ACCESS:
            return self._emit_field_access(node)
        if kind == NodeKind.ADDRESS_OF:
            operand = self._emit_expr(node.operand)
            return f"&({operand})"
        if kind == NodeKind.DEREF:
            pointer = self._emit_expr(node.pointer)
            return f"*({pointer})"
        if kind == NodeKind.CAST:
            target = self._emit_type_node(node.target_type)
            expr = self._emit_expr(node.expression)
            return f"(({target})({expr}))"
        if kind == NodeKind.IF_EXPR:
            cond = self._emit_expr(node.condition)
            texpr = self._emit_expr(node.then_expr)
            eexpr = self._emit_expr(node.else_expr) if node.else_expr else "0"
            return f"(({cond}) ? ({texpr}) : ({eexpr}))"
        if kind == NodeKind.MATCH_EXPR:
            return self._emit_match_expr(node)
        if kind == NodeKind.STRUCT_INIT:
            return self._emit_struct_init(node)
        if kind == NodeKind.ARRAY_INIT:
            return self._emit_array_init(node)
        if kind == NodeKind.NEW_EXPR:
            return self._emit_new_expr(node)
        if kind in {
            NodeKind.TYPE_PRIMITIVE,
            NodeKind.TYPE_IDENTIFIER,
            NodeKind.TYPE_POINTER,
            NodeKind.TYPE_ARRAY,
            NodeKind.TYPE_SLICE,
            NodeKind.TYPE_STRUCT,
            NodeKind.TYPE_FUNCTION,
            NodeKind.TYPE_GENERIC,
        }:
            return self._emit_type_node(node)

        raise CodegenError(f"C backend: unsupported expression node '{kind.name}'", node.span)

    def _emit_literal(self, node: ASTNode) -> str:
        lk = node.literal_kind
        value = getattr(node, "literal_value", None)
        raw = getattr(node, "raw_text", None)

        if lk == LiteralKind.INTEGER:
            self._needs_stdint = True
            return str(value if value is not None else raw or 0)
        if lk == LiteralKind.FLOAT:
            s = str(value if value is not None else raw or "0.0")
            if "." not in s and "e" not in s and "E" not in s:
                s += ".0"
            return s
        if lk == LiteralKind.STRING:
            if value is None:
                return raw or "\"\""
            return self._quote_c_string(str(value))
        if lk == LiteralKind.CHAR:
            c = str(value) if value is not None else "\0"
            return self._quote_c_char(c)
        if lk == LiteralKind.BOOLEAN:
            self._needs_stdbool = True
            return "true" if bool(value) else "false"
        if lk == LiteralKind.NIL:
            self._needs_stddef = True
            return "NULL"
        return str(value if value is not None else raw or 0)

    def _emit_binary(self, node: ASTNode) -> str:
        left = self._emit_expr(node.left)
        right = self._emit_expr(node.right)
        op = node.operator
        cop = self._binary_op_to_c(op)
        return f"({left} {cop} {right})"

    def _emit_unary(self, node: ASTNode) -> str:
        operand = self._emit_expr(node.operand)
        op = node.operator
        if op == UnaryOp.NEG:
            return f"(-({operand}))"
        if op == UnaryOp.NOT:
            return f"(!({operand}))"
        if op == UnaryOp.BIT_NOT:
            return f"(~({operand}))"
        return f"({operand})"

    def _emit_call(self, node: ASTNode) -> str:
        if self._is_io_call(node):
            raise CodegenError(
                "C backend: io.print/io.println cannot be used as expression values",
                node.span,
            )

        canonical = getattr(node, "stdlib_canonical", None)
        if canonical in self._MATH_CALL_MAP:
            self._needs_math = True
            fn = self._MATH_CALL_MAP[canonical]
            args = ", ".join(self._emit_expr(a) for a in (node.arguments or []))
            return f"{fn}({args})"

        if canonical and canonical.startswith("std.math."):
            short_name = canonical.split(".")[-1]
            fn = self._MATH_CALL_MAP.get(canonical, short_name)
            self._needs_math = True
            args = ", ".join(self._emit_expr(a) for a in (node.arguments or []))
            return f"{fn}({args})"

        func = self._emit_expr(node.function)
        args = ", ".join(self._emit_expr(a) for a in (node.arguments or []))
        return f"{func}({args})"

    def _emit_field_access(self, node: ASTNode) -> str:
        field = self._sanitize_name(node.field or "field")

        if node.object and node.object.kind == NodeKind.IDENTIFIER:
            obj_name = node.object.name or ""
            if obj_name in self._declared_enums and field in self._enum_variants.get(obj_name, set()):
                return f"{self._sanitize_name(obj_name)}_{field}"

        object_type = self._type_map.get(id(node.object)) if node.object is not None else None
        if isinstance(object_type, SliceType):
            obj = self._emit_expr(node.object)
            if field == "ptr":
                return f"({obj}).data"
            if field == "len":
                return f"({obj}).len"

        if node.object and node.object.kind == NodeKind.DEREF:
            pointer = self._emit_expr(node.object.pointer)
            return f"({pointer})->{field}"

        obj = self._emit_expr(node.object)
        return f"({obj}).{field}"

    def _emit_struct_init(self, node: ASTNode) -> str:
        struct_name = node.struct_type if isinstance(node.struct_type, str) else ""
        field_inits = node.field_inits or []

        if struct_name and struct_name != "__inline__":
            c_name = self._sanitize_name(struct_name)
            parts = [f"({c_name}){{ "]
        elif self._current_inline_return_type:
            parts = [f"({self._current_inline_return_type}){{ "]
        else:
            raise CodegenError(
                "C backend: inline struct initializer requires concrete destination type",
                node.span,
            )

        for i, fi in enumerate(field_inits):
            if i > 0:
                parts.append(", ")
            val = self._emit_expr(fi.value) if fi.value else "0"
            if fi.name:
                parts.append(f".{self._sanitize_name(fi.name)} = {val}")
            else:
                parts.append(val)
        parts.append(" }")
        return "".join(parts)

    def _emit_array_init(self, node: ASTNode) -> str:
        elements = node.elements or []
        emitted = ", ".join(self._emit_expr(e) for e in elements)
        return f"{{ {emitted} }}"

    def _emit_new_expr(self, node: ASTNode) -> str:
        self._needs_stdlib = True
        self._needs_stddef = True

        target = getattr(node, "target_type", None)
        if target is None:
            return "(void*)malloc(1)"

        if target.kind == NodeKind.TYPE_ARRAY:
            elem_type = self._emit_type_node(target.element_type) if target.element_type else "uint8_t"
            size = self._emit_expr(target.size) if target.size else "0"
            return f"(({elem_type}*)malloc(sizeof({elem_type}) * ({size})))"

        target_type = self._emit_type_node(target)
        return f"(({target_type}*)malloc(sizeof({target_type})))"

    # ------------------------------------------------------------------
    # Type emission and inference
    # ------------------------------------------------------------------

    def _emit_type_node(self, node: ASTNode) -> str:
        if node is None:
            return "int32_t"

        kind = node.kind
        if kind == NodeKind.TYPE_PRIMITIVE:
            return self._map_primitive_type(node.type_name or "i32")
        if kind == NodeKind.TYPE_IDENTIFIER:
            return self._sanitize_name(node.name or "int32_t")
        if kind == NodeKind.TYPE_GENERIC:
            raise CodegenError(
                "C backend: unresolved generic type parameter cannot be emitted to C",
                node.span,
            )
        if kind == NodeKind.TYPE_POINTER:
            target = self._emit_type_node(node.target_type)
            return f"{target}*"
        if kind == NodeKind.TYPE_ARRAY:
            # In general type positions (not declarators), array decays to pointer.
            elem = self._emit_type_node(node.element_type)
            return f"{elem}*"
        if kind == NodeKind.TYPE_SLICE:
            return self._register_slice_type(node)
        if kind == NodeKind.TYPE_FUNCTION:
            raise CodegenError(
                "C backend: function types require a named declarator in C",
                node.span,
            )
        if kind == NodeKind.TYPE_STRUCT:
            mapped = self._inline_struct_names.get(id(node))
            if mapped:
                return mapped
            raise CodegenError(
                "C backend: anonymous inline struct type is missing a generated typedef",
                node.span,
            )
        return "int32_t"

    def _map_primitive_type(self, type_name: str) -> str:
        self._needs_stdint = True
        mapping = {
            "i8": "int8_t",
            "i16": "int16_t",
            "i32": "int32_t",
            "i64": "int64_t",
            "u8": "uint8_t",
            "u16": "uint16_t",
            "u32": "uint32_t",
            "u64": "uint64_t",
            "isize": "intptr_t",
            "usize": "size_t",
            "f32": "float",
            "f64": "double",
            "bool": "bool",
            "char": "char",
            "string": "const char*",
            "void": "void",
        }
        if type_name == "bool":
            self._needs_stdbool = True
        if type_name in {"usize"}:
            self._needs_stddef = True
        if type_name == "string":
            self._needs_stddef = True
        return mapping.get(type_name, self._sanitize_name(type_name))

    def _infer_decl_type(self, explicit_type: Optional[ASTNode], value_node: Optional[ASTNode], decl_node: ASTNode) -> str:
        if explicit_type is not None:
            return self._emit_type_node(explicit_type)

        resolved = getattr(decl_node, "resolved_type", None)
        if isinstance(resolved, ASTNode):
            return self._emit_type_node(resolved)

        sem = self._type_map.get(id(value_node)) if value_node is not None else None
        inferred = self._semantic_type_to_c(sem)
        if inferred:
            return inferred

        if value_node and value_node.kind == NodeKind.CALL and value_node.function:
            fn_node = value_node.function
            if fn_node.kind == NodeKind.IDENTIFIER and fn_node.name:
                fn_name = self._sanitize_name(fn_node.name)
                ret_node = self._function_return_nodes.get(fn_name)
                if ret_node is not None:
                    return self._emit_type_node(ret_node)

        if value_node and value_node.kind == NodeKind.LITERAL:
            lk = value_node.literal_kind
            if lk == LiteralKind.INTEGER:
                self._needs_stdint = True
                return "int32_t"
            if lk == LiteralKind.FLOAT:
                return "double"
            if lk == LiteralKind.STRING:
                return "const char*"
            if lk == LiteralKind.CHAR:
                return "char"
            if lk == LiteralKind.BOOLEAN:
                self._needs_stdbool = True
                return "bool"
            if lk == LiteralKind.NIL:
                self._needs_stddef = True
                return "void*"

        return "int32_t"

    def _semantic_type_to_c(self, type_obj) -> Optional[str]:
        if type_obj is None:
            return None

        kind = getattr(type_obj, "kind", None)

        if isinstance(type_obj, PrimitiveType):
            return self._map_primitive_type(type_obj.name)
        if isinstance(type_obj, ReferenceType):
            inner = self._semantic_type_to_c(type_obj.referent_type) or "void"
            return f"{inner}*"
        if isinstance(type_obj, PointerType):
            inner = self._semantic_type_to_c(type_obj.pointee_type) or "void"
            return f"{inner}*"
        if isinstance(type_obj, ArrayType):
            inner = self._semantic_type_to_c(type_obj.element_type) or "uint8_t"
            return f"{inner}*"
        if isinstance(type_obj, SliceType):
            # Runtime representation is struct { T* data; size_t len }.
            elem = self._semantic_type_to_c(type_obj.element_type) or "uint8_t"
            name = f"a7_slice_{elem.replace(' ', '_').replace('*', 'ptr')}"
            if name not in self._slice_type_names:
                if isinstance(type_obj.element_type, PrimitiveType):
                    fake_element = ASTNode(
                        kind=NodeKind.TYPE_PRIMITIVE,
                        type_name=type_obj.element_type.name,
                    )
                else:
                    fake_element = ASTNode(kind=NodeKind.TYPE_IDENTIFIER, name=elem)
                fake = ASTNode(kind=NodeKind.TYPE_SLICE, element_type=fake_element)
                self._slice_type_names[name] = name
                self._slice_type_defs.append((name, fake))
            self._needs_stddef = True
            return name
        if isinstance(type_obj, StructType):
            if type_obj.name:
                return self._sanitize_name(type_obj.name)
            return None
        if isinstance(type_obj, EnumType):
            return self._sanitize_name(type_obj.name)
        if isinstance(type_obj, UnionType):
            return self._sanitize_name(type_obj.name)
        if isinstance(type_obj, FunctionType):
            return None
        if isinstance(type_obj, GenericParamType):
            return None
        if isinstance(type_obj, GenericInstanceType):
            return None

        if kind == TypeKind.UNKNOWN:
            return "void*"
        if kind == TypeKind.VOID:
            return "void"
        return None

    def _default_value(self, explicit_type: Optional[ASTNode], c_type: str) -> str:
        if explicit_type is not None and explicit_type.kind == NodeKind.TYPE_ARRAY:
            return "{0}"

        if c_type in {"float", "double"}:
            return "0.0"
        if c_type == "bool":
            self._needs_stdbool = True
            return "false"
        if c_type == "char":
            return "'\\0'"
        if c_type == "const char*":
            return "\"\""
        if c_type.endswith("*"):
            self._needs_stddef = True
            return "NULL"
        if c_type.startswith("struct ") or c_type.startswith("union ") or c_type in self._declared_structs:
            return "{0}"
        return "0"

    def _function_return_type(self, node: ASTNode) -> str:
        name = self._sanitize_name(node.name or "anonymous")
        if name == "main":
            return "int"
        if node.return_type is None:
            return "void"
        return self._emit_type_node(node.return_type)

    def _function_signature(self, node: ASTNode, prototype: bool) -> str:
        name = self._sanitize_name(node.name or "anonymous")
        return_type = self._function_return_type(node)

        param_parts: list[str] = []
        for i, param in enumerate(node.parameters or []):
            pname = self._sanitize_name(param.name or f"arg{i}")
            if param.param_type:
                param_parts.append(self._emit_declarator(param.param_type, pname))
            else:
                param_parts.append(f"int32_t {pname}")
        params = ", ".join(param_parts) if param_parts else "void"

        prefix = ""
        if prototype and name != "main":
            prefix = "static "
        if not prototype and name != "main" and getattr(node, "is_public", False) is False:
            prefix = "static "
        return f"{prefix}{return_type} {name}({params})"

    def _emit_declarator(self, type_node: ASTNode, name: str) -> str:
        if type_node.kind == NodeKind.TYPE_FUNCTION:
            return self._emit_function_pointer_declarator(type_node, name)
        return f"{self._emit_type_node(type_node)} {name}"

    def _emit_function_pointer_declarator(self, type_node: ASTNode, name: str) -> str:
        return_type = self._emit_type_node(type_node.return_type) if type_node.return_type else "void"
        param_types = [
            self._emit_type_node(param_type)
            for param_type in (type_node.parameter_types or [])
        ]
        params = ", ".join(param_types) if param_types else "void"
        return f"{return_type} (*{name})({params})"

    # ------------------------------------------------------------------
    # IO lowering
    # ------------------------------------------------------------------

    def _is_io_call(self, node: ASTNode) -> bool:
        if node.kind != NodeKind.CALL:
            return False
        canonical = getattr(node, "stdlib_canonical", None)
        return canonical in {"std.io.print", "std.io.println", "std.io.eprintln"}

    def _emit_io_call_stmt(self, node: ASTNode) -> None:
        self._needs_stdio = True
        canonical = getattr(node, "stdlib_canonical", "std.io.println")
        args = node.arguments or []

        stream = "stdout"
        add_newline = canonical == "std.io.println"
        if canonical == "std.io.eprintln":
            stream = "stderr"
            add_newline = True

        if not args:
            fmt = "\\n" if add_newline else ""
            self._write_indent()
            if stream == "stderr":
                self.output.write(f"fprintf(stderr, \"{fmt}\");\n")
            else:
                self.output.write(f"printf(\"{fmt}\");\n")
            return

        fmt_arg = args[0]
        value_args = args[1:]
        fmt_raw = self._extract_plain_format(fmt_arg)
        printf_fmt, converted_args = self._convert_format(fmt_raw, value_args)

        if add_newline:
            printf_fmt += "\n"

        quoted_fmt = self._quote_c_string(printf_fmt)
        call_name = "fprintf" if stream == "stderr" else "printf"

        self._write_indent()
        if call_name == "fprintf":
            if converted_args:
                joined = ", ".join(converted_args)
                self.output.write(f"fprintf(stderr, {quoted_fmt}, {joined});\n")
            else:
                self.output.write(f"fprintf(stderr, {quoted_fmt});\n")
        else:
            if converted_args:
                joined = ", ".join(converted_args)
                self.output.write(f"printf({quoted_fmt}, {joined});\n")
            else:
                self.output.write(f"printf({quoted_fmt});\n")

    def _extract_plain_format(self, fmt_arg: ASTNode) -> str:
        if fmt_arg.kind == NodeKind.LITERAL and fmt_arg.literal_kind == LiteralKind.STRING:
            return str(getattr(fmt_arg, "literal_value", "") or "")
        # Fallback: emit as expression and strip quotes if possible.
        expr = self._emit_expr(fmt_arg)
        if len(expr) >= 2 and expr[0] == '"' and expr[-1] == '"':
            return expr[1:-1]
        return "{}"

    def _convert_format(self, fmt: str, args: list[ASTNode]) -> tuple[str, list[str]]:
        out: list[str] = []
        converted: list[str] = []
        i = 0
        arg_idx = 0

        while i < len(fmt):
            if i + 1 < len(fmt) and fmt[i] == "{" and fmt[i + 1] == "}":
                if arg_idx < len(args):
                    spec, expr = self._format_io_arg(args[arg_idx])
                    out.append(spec)
                    converted.append(expr)
                    arg_idx += 1
                else:
                    out.append("{}")
                i += 2
                continue

            ch = fmt[i]
            if ch == "%":
                out.append("%%")
            else:
                out.append(ch)
            i += 1

        # Append any extra args that had no placeholder.
        while arg_idx < len(args):
            spec, expr = self._format_io_arg(args[arg_idx])
            if out and not out[-1].endswith(" "):
                out.append(" ")
            out.append(spec)
            converted.append(expr)
            arg_idx += 1

        return "".join(out), converted

    def _format_io_arg(self, arg: ASTNode) -> tuple[str, str]:
        sem_type = self._type_map.get(id(arg))
        expr = self._emit_expr(arg)

        if arg.kind == NodeKind.CALL:
            canonical = getattr(arg, "stdlib_canonical", None)
            if canonical and canonical.startswith("std.math."):
                return "%s", f"a7_f64_str((double)({expr}))"

        if self._is_null_literal(arg):
            return "%s", "\"null\""

        if isinstance(sem_type, PrimitiveType):
            if sem_type.name in {"string"}:
                return "%s", expr
            if sem_type.name in {"char"}:
                return "%c", expr
            if sem_type.name in {"bool"}:
                self._needs_stdbool = True
                return "%s", f"a7_bool_str({expr})"
            if sem_type.name in {"f32", "f64"}:
                return "%s", f"a7_f64_str((double)({expr}))"
            if sem_type.name in {"u8", "u16", "u32", "u64", "usize"}:
                return "%llu", f"(unsigned long long)({expr})"
            return "%lld", f"(long long)({expr})"

        if isinstance(sem_type, EnumType):
            return "%lld", f"(long long)({expr})"

        if isinstance(sem_type, (ReferenceType, PointerType)):
            self._needs_ptr_helper = True
            return "%s", f"a7_ptr_str((const void*)({expr}))"

        if getattr(sem_type, "kind", None) == TypeKind.UNKNOWN:
            self._needs_ptr_helper = True
            return "%s", f"a7_ptr_str((const void*)({expr}))"

        if arg.kind == NodeKind.LITERAL:
            if arg.literal_kind == LiteralKind.STRING:
                return "%s", expr
            if arg.literal_kind == LiteralKind.CHAR:
                return "%c", expr
            if arg.literal_kind == LiteralKind.BOOLEAN:
                self._needs_stdbool = True
                return "%s", f"a7_bool_str({expr})"
            if arg.literal_kind == LiteralKind.FLOAT:
                return "%s", f"a7_f64_str((double)({expr}))"
            if arg.literal_kind == LiteralKind.INTEGER:
                return "%lld", f"(long long)({expr})"
            if arg.literal_kind == LiteralKind.NIL:
                return "%s", "\"null\""

        if arg.kind == NodeKind.BINARY and arg.operator in {
            BinaryOp.EQ,
            BinaryOp.NE,
            BinaryOp.LT,
            BinaryOp.LE,
            BinaryOp.GT,
            BinaryOp.GE,
            BinaryOp.AND,
            BinaryOp.OR,
        }:
            self._needs_stdbool = True
            return "%s", f"a7_bool_str({expr})"

        # Conservative fallback: print as signed integer cast.
        return "%lld", f"(long long)({expr})"

    # ------------------------------------------------------------------
    # Defer helpers
    # ------------------------------------------------------------------

    def _emit_defer_action(self, node: ASTNode) -> str:
        stmt = getattr(node, "statement", None)
        expr = getattr(node, "expression", None)

        if stmt:
            return self._emit_statement_inline(stmt)
        if expr:
            if self._is_io_call(expr):
                return self._emit_io_call_inline(expr)
            return self._emit_expr(expr)
        return "/* defer noop */"

    def _emit_statement_inline(self, node: ASTNode) -> str:
        if node.kind == NodeKind.EXPRESSION_STMT and node.expression:
            if self._is_io_call(node.expression):
                return self._emit_io_call_inline(node.expression)
            return self._emit_expr(node.expression)
        if node.kind == NodeKind.CALL:
            if self._is_io_call(node):
                return self._emit_io_call_inline(node)
            return self._emit_expr(node)
        if node.kind == NodeKind.ASSIGNMENT:
            target = self._emit_expr(node.target) if node.target else "x"
            value = self._emit_expr(node.value) if node.value else "0"
            op = getattr(node, "operator", None) or getattr(node, "op", AssignOp.ASSIGN)
            return f"{target} {self._assign_op_to_c(op)} {value}"
        if node.kind == NodeKind.DEL:
            expr_node = getattr(node, "expression", None) or getattr(node, "expr", None)
            if expr_node:
                self._needs_stdlib = True
                expr = self._emit_expr(expr_node)
                return f"free({expr})"
        raise CodegenError(
            f"C backend: unsupported deferred statement kind '{node.kind.name}'",
            node.span,
        )

    def _emit_io_call_inline(self, node: ASTNode) -> str:
        canonical = getattr(node, "stdlib_canonical", "std.io.println")
        args = node.arguments or []
        stream = "stdout"
        newline = canonical == "std.io.println"
        if canonical == "std.io.eprintln":
            stream = "stderr"
            newline = True

        if not args:
            fmt = "\\n" if newline else ""
            if stream == "stderr":
                return f"fprintf(stderr, \"{fmt}\")"
            return f"printf(\"{fmt}\")"

        fmt = self._extract_plain_format(args[0])
        printf_fmt, converted = self._convert_format(fmt, args[1:])
        if newline:
            printf_fmt += "\n"
        quoted = self._quote_c_string(printf_fmt)
        if stream == "stderr":
            if converted:
                return f"fprintf(stderr, {quoted}, {', '.join(converted)})"
            return f"fprintf(stderr, {quoted})"
        if converted:
            return f"printf({quoted}, {', '.join(converted)})"
        return f"printf({quoted})"

    def _emit_current_scope_defers(self) -> None:
        if not self._defer_scopes:
            return
        for stmt in reversed(self._defer_scopes[-1]):
            self._write_indent()
            self.output.write(f"{stmt};\n")

    def _emit_deferred_unwind(self, keep_scopes: int) -> None:
        if not self._defer_scopes:
            return
        for scope in reversed(self._defer_scopes[keep_scopes:]):
            for stmt in reversed(scope):
                self._write_indent()
                self.output.write(f"{stmt};\n")

    def _push_loop_frame(
        self,
        *,
        label: Optional[str],
        unwind_depth: int,
        break_target: Optional[str] = None,
        continue_target: Optional[str] = None,
    ) -> None:
        self._loop_frames.append(
            {
                "label": label,
                "unwind_depth": unwind_depth,
                "break_target": break_target,
                "continue_target": continue_target,
            }
        )

    def _pop_loop_frame(self) -> None:
        if self._loop_frames:
            self._loop_frames.pop()

    def _resolve_loop_frame(self, label: Optional[str]) -> Optional[dict[str, object]]:
        if not self._loop_frames:
            return None
        if label is None:
            return self._loop_frames[-1]
        for frame in reversed(self._loop_frames):
            if frame["label"] == label:
                return frame
        return None

    def _visit_labeled_while(self, node: ASTNode) -> None:
        cond_label = self._unique_name("a7_loop_cond")
        continue_label = self._unique_name("a7_loop_continue")
        break_label = self._unique_name("a7_loop_break")
        cond = self._emit_expr(node.condition) if node.condition else "1"

        self._write_indent()
        self.output.write(f"{cond_label}:\n")
        self._write_indent()
        self.output.write(f"if (!({cond})) goto {break_label};\n")
        marker = len(self._defer_scopes)
        self._push_loop_frame(
            label=node.label,
            unwind_depth=marker,
            break_target=break_label,
            continue_target=continue_label,
        )
        self._emit_stmt_or_block(node.body)
        self._pop_loop_frame()
        self._write_indent()
        self.output.write(f"{continue_label}:\n")
        self._write_indent()
        self.output.write(f"goto {cond_label};\n")
        self._write_indent()
        self.output.write(f"{break_label}:\n")

    def _visit_labeled_for(self, node: ASTNode) -> None:
        cond_label = self._unique_name("a7_loop_cond")
        continue_label = self._unique_name("a7_loop_continue")
        break_label = self._unique_name("a7_loop_break")

        self._write_indent()
        self.output.write("{\n")
        self.indent()
        if node.init:
            self.visit(node.init)
        cond = self._emit_expr(node.condition) if node.condition else "1"
        self._write_indent()
        self.output.write(f"{cond_label}:\n")
        self._write_indent()
        self.output.write(f"if (!({cond})) goto {break_label};\n")
        marker = len(self._defer_scopes)
        self._push_loop_frame(
            label=node.label,
            unwind_depth=marker,
            break_target=break_label,
            continue_target=continue_label,
        )
        self._emit_stmt_or_block(node.body)
        self._pop_loop_frame()
        self._write_indent()
        self.output.write(f"{continue_label}:\n")
        update = self._emit_for_clause(node.update)
        if update:
            self._write_indent()
            self.output.write(f"{update};\n")
        self._write_indent()
        self.output.write(f"goto {cond_label};\n")
        self._write_indent()
        self.output.write(f"{break_label}:\n")
        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    def _visit_labeled_for_in(self, node: ASTNode, *, indexed: bool) -> None:
        cond_label = self._unique_name("a7_loop_cond")
        continue_label = self._unique_name("a7_loop_continue")
        break_label = self._unique_name("a7_loop_break")
        idx_name = self._unique_name("__a7_i")
        iterable_expr = self._emit_expr(node.iterable)
        iterable_type = self._type_map.get(id(node.iterable)) if node.iterable else None
        cache_name = self._unique_name("__a7_iter")
        cache_type = self._iterable_cache_type(iterable_type)
        elem_type = self._iterable_element_type(iterable_type)
        length_expr = self._iterable_length_expr(node.iterable, cache_name, iterable_type)
        iter_name = self._sanitize_name(node.iterator or "item")

        self._write_indent()
        self.output.write("{\n")
        self.indent()
        self._write_indent()
        self.output.write(f"{cache_type} {cache_name} = {iterable_expr};\n")
        self._write_indent()
        self.output.write(f"size_t {idx_name} = 0;\n")
        self._write_indent()
        self.output.write(f"{cond_label}:\n")
        self._write_indent()
        self.output.write(f"if (!({idx_name} < {length_expr})) goto {break_label};\n")
        self._write_indent()
        self.output.write("{\n")
        self.indent()
        self._defer_scopes.append([])
        if indexed:
            index_var = self._sanitize_name(node.index_var or "index")
            self._write_indent()
            self.output.write(f"size_t {index_var} = {idx_name};\n")
        self._write_indent()
        self.output.write(
            f"{elem_type} {iter_name} = {self._emit_iterable_element_expr(node.iterable, cache_name, iterable_type, idx_name)};\n"
        )
        marker = len(self._defer_scopes) - 1
        self._push_loop_frame(
            label=node.label,
            unwind_depth=marker,
            break_target=break_label,
            continue_target=continue_label,
        )
        if node.body and node.body.kind == NodeKind.BLOCK:
            for stmt in (node.body.statements or []):
                self.visit(stmt)
        elif node.body:
            self.visit(node.body)
        self._pop_loop_frame()
        self._emit_current_scope_defers()
        self._defer_scopes.pop()
        self.dedent()
        self._write_indent()
        self.output.write("}\n")
        self._write_indent()
        self.output.write(f"{continue_label}:\n")
        self._write_indent()
        self.output.write(f"++{idx_name};\n")
        self._write_indent()
        self.output.write(f"goto {cond_label};\n")
        self._write_indent()
        self.output.write(f"{break_label}:\n")
        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit_stmt_or_block(self, node: Optional[ASTNode]) -> None:
        if node is None:
            self.output.write("{ }\n")
            return
        if node.kind == NodeKind.BLOCK:
            self._visit_block_inline(node)
            return
        self.output.write("{\n")
        self.indent()
        self._defer_scopes.append([])
        self.visit(node)
        self._emit_current_scope_defers()
        self._defer_scopes.pop()
        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    def _emit_for_clause(self, node: Optional[ASTNode]) -> str:
        if node is None:
            return ""
        if node.kind == NodeKind.VAR:
            explicit = getattr(node, "explicit_type", None)
            if explicit and explicit.kind == NodeKind.TYPE_ARRAY:
                raise CodegenError("C backend: array declarations are not allowed in for-init", node.span)
            c_type = self._infer_decl_type(explicit, node.value, node)
            name = self._sanitize_name(node.emit_name or node.name or "i")
            if node.value:
                return f"{c_type} {name} = {self._emit_expr(node.value)}"
            return f"{c_type} {name} = {self._default_value(explicit, c_type)}"
        if node.kind == NodeKind.ASSIGNMENT:
            target = self._emit_expr(node.target) if node.target else "x"
            value = self._emit_expr(node.value) if node.value else "0"
            op = getattr(node, "operator", None) or getattr(node, "op", AssignOp.ASSIGN)
            return f"{target} {self._assign_op_to_c(op)} {value}"
        if node.kind == NodeKind.EXPRESSION_STMT and node.expression:
            return self._emit_expr(node.expression)
        if node.kind == NodeKind.CALL:
            return self._emit_expr(node)
        return ""

    def _emit_index_base_expr(self, object_node: Optional[ASTNode], object_expr: str) -> str:
        object_type = self._type_map.get(id(object_node)) if object_node is not None else None
        if isinstance(object_type, SliceType):
            return f"({object_expr}).data"
        return object_expr

    def _emit_iterable_element_expr(
        self,
        iterable_node: Optional[ASTNode],
        iterable_expr: str,
        iterable_type,
        idx_name: str,
    ) -> str:
        if isinstance(iterable_type, SliceType):
            return f"({iterable_expr}).data[{idx_name}]"
        return f"{iterable_expr}[{idx_name}]"

    def _iterable_cache_type(self, iterable_type) -> str:
        if iterable_type is not None and iterable_type.equals(STRING):
            return "const char*"
        if isinstance(iterable_type, SliceType):
            return self._semantic_type_to_c(iterable_type) or "void*"
        if isinstance(iterable_type, ArrayType):
            elem = self._semantic_type_to_c(iterable_type.element_type) or "int32_t"
            return f"{elem}*"
        raise CodegenError(
            "C backend: for-in iteration currently requires an array, slice, or string value",
            None,
        )

    def _iterable_element_type(self, iterable_type) -> str:
        if iterable_type is not None and iterable_type.equals(STRING):
            return "char"
        if isinstance(iterable_type, ArrayType):
            return self._semantic_type_to_c(iterable_type.element_type) or "int32_t"
        if isinstance(iterable_type, SliceType):
            return self._semantic_type_to_c(iterable_type.element_type) or "int32_t"
        # Fallback for semantic unknowns.
        return "int32_t"

    def _iterable_length_expr(self, iterable_node: Optional[ASTNode], iterable_expr: str, iterable_type) -> str:
        if isinstance(iterable_type, ArrayType):
            return str(iterable_type.size)
        if isinstance(iterable_type, SliceType):
            return f"({iterable_expr}).len"
        if iterable_type is not None and iterable_type.equals(STRING):
            return f"strlen({iterable_expr})"
        if iterable_node and iterable_node.kind == NodeKind.IDENTIFIER:
            return f"A7_ARRAY_LEN({iterable_expr})"
        raise CodegenError(
            "C backend: for-in iteration currently requires an array, slice, or string value",
            iterable_node.span if iterable_node else None,
        )

    def _emit_slice_expr(self, node: ASTNode) -> str:
        source_type = self._type_map.get(id(node.object)) if node.object else None
        is_string_source = source_type is not None and source_type.equals(STRING)
        if not isinstance(source_type, (ArrayType, SliceType)) and not is_string_source:
            raise CodegenError(
                "C backend: slice expressions currently require an array, slice, or string value",
                node.span,
            )

        result_type = self._type_map.get(id(node))
        if not isinstance(result_type, SliceType):
            element_type = CHAR if is_string_source else source_type.element_type
            result_type = SliceType(element_type)

        slice_c_type = self._semantic_type_to_c(result_type) or "void*"
        object_expr = self._emit_expr(node.object)
        start_expr = self._emit_expr(node.start) if node.start else "0"

        if isinstance(source_type, ArrayType):
            end_expr = self._emit_expr(node.end) if node.end else str(source_type.size)
            data_expr = f"&({object_expr})[(size_t)({start_expr})]"
        elif isinstance(source_type, SliceType):
            end_expr = self._emit_expr(node.end) if node.end else f"({object_expr}).len"
            data_expr = f"({object_expr}).data + (size_t)({start_expr})"
        else:
            end_expr = self._emit_expr(node.end) if node.end else f"strlen({object_expr})"
            elem_c_type = self._semantic_type_to_c(result_type.element_type) or "char"
            data_expr = f"({elem_c_type}*)&({object_expr})[(size_t)({start_expr})]"

        len_expr = f"((size_t)({end_expr}) - (size_t)({start_expr}))"
        return f"(({slice_c_type}){{ .data = {data_expr}, .len = {len_expr} }})"

    def _emit_match_expr(self, node: ASTNode) -> str:
        scrutinee = node.expression
        if not self._is_side_effect_free_match_scrutinee(scrutinee):
            raise CodegenError(
                "C backend: match expressions with side-effectful scrutinees are only supported in variable initializers",
                node.span,
            )

        scrutinee_expr = self._emit_expr(scrutinee) if scrutinee else "0"
        return self._emit_match_expr_with_scrutinee(node, scrutinee_expr)

    def _emit_side_effectful_match_var_init(self, name: str, c_type: str, node: ASTNode) -> None:
        scrutinee = node.expression
        scrutinee_type = self._semantic_type_to_c(self._type_map.get(id(scrutinee))) or "int32_t"
        if scrutinee_type == "int32_t":
            self._needs_stdint = True

        temp_name = self._unique_name("__a7_match")
        self._write_indent()
        self.output.write(f"{c_type} {name};\n")
        self._write_indent()
        self.output.write("{\n")
        self.indent()
        self._write_indent()
        self.output.write(f"{scrutinee_type} {temp_name} = {self._emit_expr(scrutinee)};\n")
        result = self._emit_match_expr_with_scrutinee(node, temp_name)
        self._write_indent()
        self.output.write(f"{name} = {result};\n")
        self.dedent()
        self._write_indent()
        self.output.write("}\n")

    def _emit_match_expr_with_scrutinee(self, node: ASTNode, scrutinee_expr: str) -> str:
        default_expr = self._emit_expr(node.else_case) if isinstance(node.else_case, ASTNode) else "0"
        result = f"({default_expr})"

        for case in reversed(node.cases or []):
            case_expr_node = getattr(case, "expression", None)
            if case_expr_node is None:
                continue
            case_expr = self._emit_expr(case_expr_node)
            condition = self._emit_match_expr_condition(scrutinee_expr, case.patterns or [])
            if condition is None:
                result = f"({case_expr})"
            else:
                result = f"(({condition}) ? ({case_expr}) : {result})"

        return result

    def _emit_match_expr_condition(self, scrutinee_expr: str, patterns: list[ASTNode]) -> Optional[str]:
        conditions: list[str] = []
        for pattern in patterns:
            condition = self._emit_match_pattern_condition(scrutinee_expr, pattern)
            if condition is None:
                return None
            conditions.append(condition)
        if not conditions:
            return "0"
        return " || ".join(f"({condition})" for condition in conditions)

    def _emit_match_pattern_condition(self, scrutinee_expr: str, pattern: ASTNode) -> Optional[str]:
        if pattern.kind == NodeKind.PATTERN_WILDCARD:
            return None
        if pattern.kind == NodeKind.PATTERN_LITERAL:
            value = self._emit_expr(pattern.literal) if pattern.literal else "0"
            return f"({scrutinee_expr}) == ({value})"
        if pattern.kind == NodeKind.PATTERN_ENUM:
            if pattern.enum_type and pattern.variant:
                value = f"{self._sanitize_name(pattern.enum_type)}_{self._sanitize_name(pattern.variant)}"
                return f"({scrutinee_expr}) == ({value})"
            raise CodegenError("C backend: malformed enum pattern in match expression", pattern.span)
        if pattern.kind == NodeKind.PATTERN_IDENTIFIER:
            name = pattern.name or ""
            if name == "_":
                return None
            value = self._sanitize_name(getattr(pattern, "emit_name", None) or name)
            return f"({scrutinee_expr}) == ({value})"
        if pattern.kind == NodeKind.PATTERN_RANGE:
            start = self._emit_pattern(pattern.start) if pattern.start else "0"
            end = self._emit_pattern(pattern.end) if pattern.end else "0"
            return f"({scrutinee_expr}) >= ({start}) && ({scrutinee_expr}) <= ({end})"
        value = self._emit_expr(pattern)
        return f"({scrutinee_expr}) == ({value})"

    def _is_side_effect_free_match_scrutinee(self, node: Optional[ASTNode]) -> bool:
        if node is None:
            return True
        if node.kind in {
            NodeKind.LITERAL,
            NodeKind.IDENTIFIER,
            NodeKind.FIELD_ACCESS,
            NodeKind.INDEX,
            NodeKind.SLICE,
            NodeKind.DEREF,
        }:
            children = [
                getattr(node, "object", None),
                getattr(node, "index", None),
                getattr(node, "start", None),
                getattr(node, "end", None),
                getattr(node, "pointer", None),
            ]
            return all(self._is_side_effect_free_match_scrutinee(child) for child in children if child is not None)
        if node.kind == NodeKind.UNARY:
            return self._is_side_effect_free_match_scrutinee(node.operand)
        if node.kind == NodeKind.BINARY:
            return (
                self._is_side_effect_free_match_scrutinee(node.left)
                and self._is_side_effect_free_match_scrutinee(node.right)
            )
        if node.kind == NodeKind.CAST:
            return self._is_side_effect_free_match_scrutinee(node.expression)
        return False

    def _emit_pattern(self, node: ASTNode) -> str:
        if node is None:
            return "default"
        if node.kind == NodeKind.PATTERN_LITERAL:
            return self._emit_expr(node.literal) if node.literal else "0"
        if node.kind == NodeKind.PATTERN_ENUM:
            if node.enum_type and node.variant:
                return f"{self._sanitize_name(node.enum_type)}_{self._sanitize_name(node.variant)}"
            raise CodegenError("C backend: malformed enum pattern in match", node.span)
        if node.kind == NodeKind.PATTERN_WILDCARD:
            return "default"
        if node.kind == NodeKind.PATTERN_IDENTIFIER:
            return self._sanitize_name(getattr(node, "emit_name", None) or node.name or "value")
        if node.kind == NodeKind.PATTERN_RANGE:
            raise CodegenError(
                "C backend: range patterns are not supported in C match lowering",
                node.span,
            )
        return "default"

    def _binary_op_to_c(self, op: BinaryOp) -> str:
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
            BinaryOp.AND: "&&",
            BinaryOp.OR: "||",
            BinaryOp.BIT_AND: "&",
            BinaryOp.BIT_OR: "|",
            BinaryOp.BIT_XOR: "^",
            BinaryOp.BIT_SHL: "<<",
            BinaryOp.BIT_SHR: ">>",
        }
        return mapping.get(op, "/*op*/")

    def _assign_op_to_c(self, op: AssignOp) -> str:
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

    def _sanitize_name(self, name: str) -> str:
        if not name:
            return "unnamed"
        safe = name.replace("$", "_").replace(".", "_").replace("-", "_")
        if safe in self._C_GLOBAL_CONFLICTS:
            safe = f"a7_{safe}"
        if safe in self._C_RESERVED:
            safe += "_"
        if safe and safe[0].isdigit():
            safe = f"n_{safe}"
        return safe

    def _unique_name(self, prefix: str) -> str:
        self._name_counter += 1
        return f"{prefix}_{self._name_counter}"

    def _is_null_literal(self, node: ASTNode) -> bool:
        return (
            node is not None
            and node.kind == NodeKind.LITERAL
            and node.literal_kind == LiteralKind.NIL
        )

    def _quote_c_string(self, text: str) -> str:
        out: list[str] = ['"']
        for ch in text:
            if ch == "\\":
                out.append("\\\\")
            elif ch == "\"":
                out.append("\\\"")
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\t":
                out.append("\\t")
            elif ch == "\r":
                out.append("\\r")
            else:
                out.append(ch)
        out.append('"')
        return "".join(out)

    def _quote_c_char(self, c: str) -> str:
        if c == "\n":
            return "'\\n'"
        if c == "\t":
            return "'\\t'"
        if c == "\r":
            return "'\\r'"
        if c == "\\":
            return "'\\\\'"
        if c == "'":
            return "'\\''"
        if c == "\0":
            return "'\\0'"
        return f"'{c}'"

    def _write_indent(self) -> None:
        self.output.write("    " * self.indent_level)
