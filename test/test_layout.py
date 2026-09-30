"""Tests for the struct layout view (`a7 check --layout`).

Expected sizes and offsets in these tests are pinned to Zig 0.16.0's own
@sizeOf/@offsetOf output for the same shapes, not derived from the layout
module, so a layout regression cannot silently move them.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from a7.compile import A7Compiler, CompileMode, OutputFormat
from a7.layout import (
    apply_touches,
    compute_struct_layouts,
    count_field_touches,
    format_report,
)


def compile_pipeline(tmp_path, source):
    source_path = tmp_path / "layout_probe.a7"
    source_path.write_text(source, encoding="utf-8")
    result = A7Compiler(
        mode=CompileMode.PIPELINE,
        output_format=OutputFormat.JSON,
    ).compile_file_detailed(str(source_path))
    assert result.ok, result.failure.message if result.failure else result
    return result


def layouts_for(tmp_path, source):
    result = compile_pipeline(tmp_path, source)
    semantic = result.semantic_results or {}
    layouts = compute_struct_layouts(semantic.get("symbol_table"))
    touches = count_field_touches(result.ast, semantic.get("type_map"))
    apply_touches(layouts, touches)
    return {layout.name: layout for layout in layouts}


def by_name(fields, name):
    matches = [f for f in fields if f.name == name]
    assert len(matches) == 1, f"field {name} not found once"
    return matches[0]


def test_offsets_match_zig_ground_truth(tmp_path):
    source = """
io :: import "std/io"

Person :: struct {
    name: string
    age: i32
}

Employee :: struct {
    person: Person
    id: i64
}

Blob :: struct {
    a: i8
    b: i64
    c: i8
    d: [3]i32
}

main :: fn() {
    p := Person{name: "x", age: 1}
    e := Employee{person: p, id: 2}
    b := Blob{a: 1, b: 3, c: 4, d: [1, 2, 3]}
    io.println("{}", e.id + b.b + p.age)
}
"""
    got = layouts_for(tmp_path, source)
    # Zig 0.16.0 @sizeOf/@offsetOf: Person 24 (age@16), Employee 32
    # (person@0, id@24), Blob 24 (b@0, d@8, a@20, c@21).
    person = got["Person"]
    assert person.size == 24 and person.align == 8
    assert by_name(person.fields, "age").offset == 16
    assert by_name(person.fields, "name").size == 16
    employee = got["Employee"]
    assert employee.size == 32 and employee.align == 8
    assert by_name(employee.fields, "person").offset == 0
    assert by_name(employee.fields, "id").offset == 24
    blob = got["Blob"]
    assert blob.size == 24 and blob.align == 8
    assert by_name(blob.fields, "b").offset == 0
    assert by_name(blob.fields, "d").offset == 8
    assert by_name(blob.fields, "d").size == 12
    assert by_name(blob.fields, "a").offset == 20
    assert by_name(blob.fields, "c").offset == 21


def test_line_use_percent_rounds_to_line_count(tmp_path):
    source = """
io :: import "std/io"

Wide :: struct {
    a: [64]i32
}

main :: fn() {
    w := Wide{a: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}
    io.println("{}", w.a[0])
}
"""
    got = layouts_for(tmp_path, source)
    wide = got["Wide"]
    assert wide.size == 256
    assert wide.lines == 4
    assert wide.line_use_percent == 100.0


def test_field_touch_counts_hit_and_cold_fields(tmp_path):
    source = """
io :: import "std/io"

Particle :: struct {
    x: i32
    hp: i32
}

main :: fn() {
    p := Particle{x: 1, hp: 100}
    p.x = p.x + 1
    io.println("{}", p.x)
}
"""
    got = layouts_for(tmp_path, source)
    particle = got["Particle"]
    # p.x appears three times (write target, read, println argument); hp is
    # only initialized, and struct literals are not field accesses.
    assert by_name(particle.fields, "x").touched == 3
    assert by_name(particle.fields, "hp").touched == 0


def test_generic_struct_reports_unresolved_size(tmp_path):
    source = """
io :: import "std/io"

Pair($A, $B) :: struct {
    first: $A
    second: $B
}

main :: fn() {
    p: Pair(i32, i32) = Pair(i32, i32){first: 1, second: 2}
    io.println("{}", p.first)
}
"""
    got = layouts_for(tmp_path, source)
    pair = got["Pair"]
    assert pair.size is None
    assert pair.lines is None
    assert pair.line_use_percent is None


def test_report_lists_structs_and_offsets(tmp_path):
    source = """
io :: import "std/io"

Dot :: struct {
    x: i32
    y: i32
}

main :: fn() {
    d := Dot{x: 1, y: 2}
    io.println("{}", d.x + d.y)
}
"""
    result = compile_pipeline(tmp_path, source)
    semantic = result.semantic_results or {}
    layouts = compute_struct_layouts(semantic.get("symbol_table"))
    touches = count_field_touches(result.ast, semantic.get("type_map"))
    apply_touches(layouts, touches)
    report = format_report(layouts)
    assert "layout: 1 structs" in report
    assert "Dot: size 8B align 4 lines 1 line-use 12.5%" in report
    assert "offset 0" in report and "offset 4" in report
    assert "touched 1" in report


def test_file_without_structs_reports_empty(tmp_path):
    source = """
io :: import "std/io"

main :: fn() {
    x := 1
    io.println("{}", x)
}
"""
    got = layouts_for(tmp_path, source)
    assert got == {}
