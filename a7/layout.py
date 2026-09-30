"""Struct layout reporting for `a7 check --layout`.

Computes the memory layout the Zig backend produces for each named struct:
field offsets, size, alignment, 64B cache lines touched, and line utilization.
Zig lays out auto structs by sorting fields by alignment, largest first, with
ties keeping declaration order (verified against @offsetOf on Zig 0.16.0),
then packing sequentially with natural alignment and padding the total to
the struct alignment. The numbers here match the emitted binary. Field
offsets are therefore not source order; the view exists to show where fields
really land. Field-access counts come from the typed AST and serve as a
hot/cold hint: a field touched zero times is cold cargo in every walked line.

All walks are iterative; nothing in this module recurses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .ast_nodes import ASTNode, NodeKind
from .types import (
    ArrayType,
    EnumType,
    GenericParamType,
    PointerType,
    PrimitiveType,
    ReferenceType,
    SliceType,
    StructType,
    Type,
    UnionType,
)

LINE_BYTES = 64

# name -> (size, align). char lowers to u8 and string to []const u8 in the
# backend, so both carry the Zig sizes, not source-level ones.
PRIMITIVE_LAYOUTS = {
    "i8": (1, 1), "u8": (1, 1), "bool": (1, 1), "char": (1, 1),
    "i16": (2, 2), "u16": (2, 2),
    "i32": (4, 4), "u32": (4, 4), "f32": (4, 4),
    "i64": (8, 8), "u64": (8, 8), "usize": (8, 8), "isize": (8, 8), "f64": (8, 8),
    "string": (16, 8),
}


@dataclass
class FieldLayout:
    name: str
    type_name: str
    offset: Optional[int]
    size: Optional[int]
    align: int
    touched: int = 0


@dataclass
class StructLayout:
    name: str
    fields: list = field(default_factory=list)
    size: Optional[int] = None
    align: int = 1
    note: str = ""

    @property
    def lines(self) -> Optional[int]:
        if self.size is None:
            return None
        return max(1, (self.size + LINE_BYTES - 1) // LINE_BYTES)

    @property
    def line_use_percent(self) -> Optional[float]:
        if self.size is None or not self.lines:
            return None
        return 100.0 * self.size / (self.lines * LINE_BYTES)


def _type_display(ty: Optional[Type]) -> str:
    if ty is None:
        return "?"
    return str(ty)


def _enum_tag_layout(ty: EnumType) -> (int, int):
    """Zig auto enums use the smallest tag that fits the variant count."""
    count = len(ty.variants)
    if count <= 1:
        return (1, 1)
    bits = max(1, (count - 1).bit_length())
    size = 1
    while size * 8 < bits:
        size *= 2
    return (size, size)


def _leaf_layout(ty: Optional[Type], struct_sizes: dict) -> Optional[(int, int)]:
    """Layout of a non-composite type. Returns None for generic parameters,
    unresolved or anonymous structs, and anything unknown."""
    if isinstance(ty, PrimitiveType):
        return PRIMITIVE_LAYOUTS.get(ty.name)
    if isinstance(ty, (PointerType, ReferenceType)):
        return (8, 8)
    if isinstance(ty, SliceType):
        return (16, 8)
    if isinstance(ty, EnumType):
        return _enum_tag_layout(ty)
    if isinstance(ty, StructType):
        if ty.generic_params or ty.name is None:
            return None
        return struct_sizes.get(ty.name)
    return None


def _linear_layout(ty: Optional[Type], struct_sizes: dict) -> Optional[(int, int)]:
    """Arrays wrapped around a leaf type. Unions are not handled here and
    return None; call _base_layout for those."""
    mult = 1
    current = ty
    while isinstance(current, ArrayType):
        if not isinstance(current.size, int) or current.size < 0:
            return None
        mult *= current.size
        current = current.element_type
    if isinstance(current, UnionType):
        return None
    leaf = _leaf_layout(current, struct_sizes)
    if leaf is None:
        return None
    return (leaf[0] * mult, leaf[1])


def _base_layout(ty: Optional[Type], struct_sizes: dict) -> Optional[(int, int)]:
    """Size and alignment of a type, resolving nested structs through
    struct_sizes (name -> (size, align) or None). Returns None when the size
    is not computable: generic parameters, unresolved or anonymous structs.
    Unions flatten their members onto an explicit worklist and take the
    largest member size; arrays of unions stay unresolved."""
    if ty is None:
        return None
    if not isinstance(ty, UnionType):
        return _linear_layout(ty, struct_sizes)
    size = 0
    align = 1
    stack = list(ty.fields)
    while stack:
        member = stack.pop()
        inner = member.field_type
        if isinstance(inner, UnionType):
            stack.extend(inner.fields)
            continue
        layout = _linear_layout(inner, struct_sizes)
        if layout is None:
            return None
        size = max(size, layout[0])
        align = max(align, layout[1])
    return (size if size else 1, align)


def _field_dependencies(ty: Optional[Type]) -> list:
    """Named struct types this type contains by value (arrays included).
    Pointers, refs and slices never embed their target."""
    deps: list = []
    stack = [ty]
    while stack:
        current = stack.pop()
        if current is None:
            continue
        if isinstance(current, ArrayType):
            stack.append(current.element_type)
        elif isinstance(current, StructType):
            if current.name is not None and not current.generic_params:
                deps.append(current.name)
    return deps


def compute_struct_layouts(symbol_table) -> list:
    """Layout every named non-generic struct known to the symbol table.

    Structs are resolved in dependency order (Kahn's algorithm over by-value
    containment), so a struct field of struct type is always computed after
    its dependency. A struct left unresolved by a cycle, or containing a
    generic parameter, reports size None.
    """
    structs: dict = {}
    all_symbols = {}
    if symbol_table is not None:
        global_scope = getattr(symbol_table, "get_global_scope", None)
        scope_symbols = global_scope() if callable(global_scope) else None
        if scope_symbols is None:
            getter = getattr(symbol_table, "get_all_symbols", None)
            scope_symbols = getter() if callable(getter) else None
        if scope_symbols is not None:
            all_symbols = getattr(scope_symbols, "symbols", {}) or {}
    for name, symbol in all_symbols.items():
        ty = getattr(symbol, "type", None)
        if isinstance(ty, StructType) and ty.name:
            structs[ty.name] = ty

    dependents: dict = {name: set() for name in structs}
    pending: dict = {name: set() for name in structs}
    for name, ty in structs.items():
        for struct_field in ty.fields:
            for dep in _field_dependencies(struct_field.field_type):
                if dep in structs and dep != name:
                    pending[name].add(dep)
                    dependents[dep].add(name)
                elif dep == name:
                    pending[name].add(name)

    ready = [name for name, deps in pending.items() if not deps]
    order: list = []
    while ready:
        name = ready.pop()
        order.append(name)
        for dependent in dependents.get(name, ()):
            pending[dependent].discard(name)
            if not pending[dependent] and dependent not in order:
                ready.append(dependent)

    sizes: dict = {}
    resolved_layouts: dict = {}
    for name in order:
        layout = _layout_struct_instance(structs[name], sizes)
        resolved_layouts[name] = layout
        sizes[name] = (layout.size, layout.align) if layout.size is not None else None

    layouts: list = []
    for name in sorted(structs):
        if name in resolved_layouts and resolved_layouts[name].size is not None:
            layouts.append(resolved_layouts[name])
        else:
            unresolved = StructLayout(name=name)
            unresolved.note = "size unresolved (cycle, generic or anonymous field)"
            layouts.append(unresolved)
    return layouts


def _layout_struct_instance(ty: StructType, struct_sizes: dict) -> StructLayout:
    """Lay out one struct given already-resolved dependency sizes.

    Fields are packed in alignment order, largest alignment first, ties in
    declaration order — the rule Zig's auto layout follows. The struct layout
    reports each field at its real offset in the binary, which can differ
    from source order.
    """
    layout = StructLayout(name=ty.name or "<anonymous>")
    resolved_fields: list = []
    resolved = True
    for index, struct_field in enumerate(ty.fields):
        field_layout = _base_layout(struct_field.field_type, struct_sizes)
        display = _type_display(struct_field.field_type)
        if field_layout is None:
            resolved = False
            resolved_fields.append(
                (0, index, FieldLayout(name=struct_field.name, type_name=display,
                                       offset=None, size=None, align=1))
            )
            continue
        size, align = field_layout
        resolved_fields.append(
            (align, index, FieldLayout(name=struct_field.name, type_name=display,
                                       offset=0, size=size, align=align))
        )
        layout.align = max(layout.align, align)
    resolved_fields.sort(key=lambda item: (-item[0], item[1]))
    offset = 0
    for _, _, field_layout in resolved_fields:
        if field_layout.size is None:
            continue
        offset = (offset + field_layout.align - 1) // field_layout.align * field_layout.align
        field_layout.offset = offset
        offset += field_layout.size
    layout.fields = [item[2] for item in resolved_fields]
    if resolved:
        layout.size = (offset + layout.align - 1) // layout.align * layout.align
    else:
        layout.note = "size unresolved (generic or anonymous field type)"
    return layout


def count_field_touches(ast: Optional[ASTNode], type_map: Optional[dict]) -> dict:
    """Count FIELD_ACCESS nodes per (struct name, field name).

    The base expression's type resolves the struct; ref and pointer bases are
    unwrapped to their referent. Unresolvable bases are skipped.
    """
    touches: dict = {}
    if ast is None or not type_map:
        return touches
    stack = [ast]
    while stack:
        node = stack.pop()
        if not isinstance(node, ASTNode):
            continue
        if node.kind == NodeKind.FIELD_ACCESS:
            base_type = type_map.get(id(getattr(node, "object", None)))
            while isinstance(base_type, (PointerType, ReferenceType)):
                base_type = base_type.pointee_type if isinstance(base_type, PointerType) else base_type.referent_type
            if isinstance(base_type, StructType):
                struct_name = base_type.name or "<anonymous>"
                key = (struct_name, getattr(node, "field", "?"))
                touches[key] = touches.get(key, 0) + 1
        for value in vars(node).values():
            if isinstance(value, ASTNode):
                stack.append(value)
            elif isinstance(value, list):
                stack.extend(item for item in value if isinstance(item, ASTNode))
    return touches


def apply_touches(layouts: list, touches: dict) -> None:
    """Attach touch counts to matching field layouts."""
    for layout in layouts:
        for struct_field in layout.fields:
            struct_field.touched = touches.get((layout.name, struct_field.name), 0)


def format_report(layouts: list) -> str:
    """Human-readable layout table for `a7 check --layout`."""
    if not layouts:
        return "layout: no named structs in this file"
    lines = [f"layout: {len(layouts)} structs, line = {LINE_BYTES}B"]
    for layout in layouts:
        if layout.size is None:
            note = f"  ({layout.note})" if layout.note else ""
            lines.append(f"{layout.name}: {note}")
            continue
        use = layout.line_use_percent
        use_text = f"{use:.1f}%" if use is not None else "?"
        lines.append(
            f"{layout.name}: size {layout.size}B align {layout.align} "
            f"lines {layout.lines} line-use {use_text}"
        )
        for struct_field in layout.fields:
            if struct_field.size is None or struct_field.offset is None:
                lines.append(
                    f"  {struct_field.name:<12} {struct_field.type_name:<16} "
                    f"offset ? size ? touched {struct_field.touched}"
                )
            else:
                lines.append(
                    f"  {struct_field.name:<12} {struct_field.type_name:<16} "
                    f"offset {struct_field.offset:<4} size {struct_field.size:<4} "
                    f"touched {struct_field.touched}"
                )
    return "\n".join(lines)
