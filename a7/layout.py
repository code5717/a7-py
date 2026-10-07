"""Struct layout reporting for `a7 check --layout`.

Computes the memory layout the Zig backend produces for each named struct:
field offsets, size, alignment, 64B cache lines touched, and line utilization.
Zig lays out auto structs by sorting fields by alignment, largest first, with
ties keeping declaration order (verified against @offsetOf on Zig 0.16.0),
then packing sequentially with natural alignment and padding the total to
the struct alignment. The numbers are those of a debug or release build;
`test/test_layout_matches_zig.py` compares them with Zig's @sizeOf and
@offsetOf. A fast build differs in one case: a bare `union` loses its
hidden tag (see `_union_layout`). Field
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
    FunctionType,
    PointerType,
    PrimitiveType,
    ReferenceType,
    SliceType,
    StructType,
    Type,
    UnionType,
)

LINE_BYTES = 64

UNION_TAG_NOTE = (
    "union sizes include the tag of debug and release builds; "
    "a fast build drops it from an untagged union"
)

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


def _align_up(offset: int, align: int) -> int:
    return (offset + align - 1) // align * align


def _tag_layout(count: int) -> (int, int):
    """Zig's auto tag for `count` names: the smallest unsigned integer that
    holds count - 1, stored in a power-of-two byte count. One name needs no
    bits, so the tag has size 0."""
    bits = (count - 1).bit_length() if count > 1 else 0
    if bits == 0:
        return (0, 1)
    size = 1
    while size * 8 < bits:
        size *= 2
    return (size, size)


def _enum_layout(ty: EnumType) -> (int, int):
    """The backend emits `enum(i32)` when a variant has an explicit value
    and an auto-tagged `enum` otherwise."""
    if any(variant.value is not None for variant in ty.variants):
        return (4, 4)
    return _tag_layout(len(ty.variants))


def _union_layout(members: list) -> Optional[(int, int)]:
    """Layout of a union from its member layouts.

    Zig stores the largest member, then a tag naming the active member,
    then pads to the alignment. `union(enum)` always has the tag. A bare
    `union` has it in Debug and ReleaseSafe (profiles debug and release)
    as a safety check, and drops it in ReleaseFast (profile fast); the
    report describes the tagged form.
    """
    if any(member is None for member in members):
        return None
    payload = max((member[0] for member in members), default=0)
    align = max((member[1] for member in members), default=1)
    tag_size, tag_align = _tag_layout(len(members))
    align = max(align, tag_align)
    return (_align_up(_align_up(payload, tag_align) + tag_size, align), align)


def _leaf_layout(ty: Optional[Type], struct_sizes: dict) -> Optional[(int, int)]:
    """Layout of a type with no by-value members. Returns None for generic
    parameters, unresolved or anonymous structs, and anything unknown."""
    if isinstance(ty, PrimitiveType):
        return PRIMITIVE_LAYOUTS.get(ty.name)
    if isinstance(ty, (PointerType, ReferenceType, FunctionType)):
        # A function-typed field is emitted as `*const fn (...) R`.
        return (8, 8)
    if isinstance(ty, SliceType):
        return (16, 8)
    if isinstance(ty, EnumType):
        return _enum_layout(ty)
    if isinstance(ty, StructType):
        if ty.generic_params or ty.name is None:
            return None
        return struct_sizes.get(ty.name)
    return None


def _base_layout(ty: Optional[Type], struct_sizes: dict) -> Optional[(int, int)]:
    """Size and alignment of a type, resolving nested structs through
    struct_sizes (name -> (size, align) or None). Returns None when the size
    is not computable: generic parameters, unresolved or anonymous structs.

    Arrays and unions are evaluated children first on an explicit stack:
    each is pushed once to schedule its members and once more to combine
    their results.
    """
    results: dict = {}
    active: set = set()
    stack = [(ty, False)]
    while stack:
        current, members_done = stack.pop()
        key = id(current)
        if members_done:
            active.discard(key)
            if isinstance(current, ArrayType):
                inner = results.get(id(current.element_type))
                sized = isinstance(current.size, int) and current.size >= 0
                results[key] = (inner[0] * current.size, inner[1]) if inner and sized else None
            else:
                results[key] = _union_layout([results.get(id(f.field_type)) for f in current.fields])
            continue
        if key in results:
            continue
        if isinstance(current, (ArrayType, UnionType)):
            if key in active or getattr(current, "generic_params", ()):
                # A type that contains itself by value has no size.
                results[key] = None
                continue
            active.add(key)
            stack.append((current, True))
            if isinstance(current, ArrayType):
                stack.append((current.element_type, False))
            else:
                stack.extend((f.field_type, False) for f in current.fields)
            continue
        results[key] = _leaf_layout(current, struct_sizes)
    return results[id(ty)]


def _by_value_members(ty: Optional[Type]) -> list:
    """Struct and union types this type embeds by value, through arrays and
    union members. Pointers, refs and slices never embed their target."""
    found: list = []
    seen: set = set()
    stack = [ty]
    while stack:
        current = stack.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, ArrayType):
            stack.append(current.element_type)
        elif isinstance(current, UnionType):
            found.append(current)
            stack.extend(f.field_type for f in current.fields)
        elif isinstance(current, StructType):
            found.append(current)
    return found


def _field_dependencies(ty: Optional[Type]) -> list:
    """Named struct types this type contains by value."""
    return [
        member.name for member in _by_value_members(ty)
        if isinstance(member, StructType) and member.name is not None and not member.generic_params
    ]


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
        if any(isinstance(member, UnionType) for member in _by_value_members(struct_field.field_type)):
            layout.note = UNION_TAG_NOTE
    resolved_fields.sort(key=lambda item: (-item[0], item[1]))
    offset = 0
    for _, _, field_layout in resolved_fields:
        if field_layout.size is None:
            continue
        offset = _align_up(offset, field_layout.align)
        field_layout.offset = offset
        offset += field_layout.size
    layout.fields = [item[2] for item in resolved_fields]
    if resolved:
        layout.size = _align_up(offset, layout.align)
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
        if layout.note:
            lines.append(f"  note: {layout.note}")
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


def layouts_to_json(layouts: list) -> dict:
    """The layout report as data, for `a7 check --layout --format json`.

    Unresolved sizes and offsets are null; `note` says why.
    """
    return {
        "line_bytes": LINE_BYTES,
        "structs": [
            {
                "name": layout.name,
                "size": layout.size,
                "align": layout.align if layout.size is not None else None,
                "lines": layout.lines,
                "line_use_percent": layout.line_use_percent,
                "note": layout.note or None,
                "fields": [
                    {
                        "name": struct_field.name,
                        "type": struct_field.type_name,
                        "offset": struct_field.offset,
                        "size": struct_field.size,
                        "align": struct_field.align if struct_field.size is not None else None,
                        "touched": struct_field.touched,
                    }
                    for struct_field in layout.fields
                ],
            }
            for layout in layouts
        ],
    }
