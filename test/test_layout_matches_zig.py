"""`a7 check --layout` against Zig's own @sizeOf, @alignOf and @offsetOf.

The emitted Zig declares its structs without `pub`, so a second file cannot
import them. Each case appends a Zig `test` block to a copy of the emitted
source and runs it with `zig test`; the block prints the facts for every
struct, and the report must agree field by field.

The report describes debug and release builds, where Zig gives a bare
`union` a hidden tag. The fast-profile case checks the one documented
difference: that tag is gone.
"""

import re
import subprocess

import pytest

from a7.cli import _struct_layouts
from a7.compile import A7Compiler, CompileMode, OutputFormat
from conftest import ZIG_MODE

SOURCE = """
io :: import "std/io"

One :: enum { A }
Three :: enum { A, B, C }
Valued :: enum { A = 1, B = 500 }
Bytes :: union { a: [5]u8, b: u32 }
Word :: union { a: u32, b: [4]u8 }
Tagged :: union(tag) { a: [5]u8, b: u32 }
Nested :: union { inner: Word, wide: u64 }

SingleEnum :: struct { e: One, x: u8 }
SmallEnum :: struct { e: Three, x: u8 }
ValuedEnum :: struct { e: Valued, x: u8 }
BareUnion :: struct { u: Bytes, x: u8 }
WordUnion :: struct { u: Word, x: u8 }
TaggedUnion :: struct { t: Tagged, x: u8 }
NestedUnion :: struct { n: Nested, x: u8 }
UnionArray :: struct { us: [2]Bytes, x: u16 }
Callbacks :: struct { f: fn(i32) i32, g: fn(i32) i32, x: u8 }
Mixed :: struct { s: string, r: ref SmallEnum, xs: []i32, b: bool, arr: [3]SmallEnum }
Outer :: struct { inner: TaggedUnion, flag: bool, id: i64 }

main :: fn() {
    s := SmallEnum{e: Three.B, x: 1}
    io.println("{}", s.x)
}
"""
STRUCTS = [
    "SingleEnum", "SmallEnum", "ValuedEnum", "BareUnion", "WordUnion", "TaggedUnion",
    "NestedUnion", "UnionArray", "Callbacks", "Mixed", "Outer",
]
PROBE = """
test "a7 layout probe" {
    inline for (.{ %s }) |S| {
        std.debug.print("LAYOUT {s} size={d} align={d}", .{ @typeName(S), @sizeOf(S), @alignOf(S) });
        inline for (@typeInfo(S).@"struct".fields) |f| {
            std.debug.print(" {s}@{d}+{d}", .{ f.name, @offsetOf(S, f.name), @sizeOf(f.type) });
        }
        std.debug.print("\\n", .{});
    }
}
"""
LAYOUT_LINE = re.compile(r"LAYOUT \S*?(\w+) size=(\d+) align=(\d+)((?: \w+@\d+\+\d+)*)")


def zig_layouts(zig, zig_cache, tmp_path, zig_source, profile):
    """{struct: (size, align, {field: (offset, size)})} as Zig reports them."""
    probe = tmp_path / f"layout_probe_{profile}.zig"
    probe.write_text(zig_source + PROBE % ", ".join(STRUCTS), encoding="utf-8")
    result = subprocess.run(
        [zig, "test", str(probe), "-O", ZIG_MODE[profile],
         "--cache-dir", str(zig_cache / "local"), "--global-cache-dir", str(zig_cache / "global")],
        capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, result.stderr
    facts = {}
    for name, size, align, fields in LAYOUT_LINE.findall(result.stderr):
        facts[name] = (int(size), int(align), {
            field: (int(offset), int(width))
            for field, offset, width in re.findall(r"(\w+)@(\d+)\+(\d+)", fields)
        })
    assert sorted(facts) == sorted(STRUCTS), result.stderr
    return facts


@pytest.fixture(scope="module")
def compiled(tmp_path_factory):
    source = tmp_path_factory.mktemp("layout") / "layout.a7"
    source.write_text(SOURCE, encoding="utf-8")
    result = A7Compiler(
        mode=CompileMode.PIPELINE, output_format=OutputFormat.JSON,
    ).compile_file_detailed(str(source))
    assert result.ok, result.failure
    return result


def reported(compiled):
    return {
        layout.name: (layout.size, layout.align, {f.name: (f.offset, f.size) for f in layout.fields})
        for layout in _struct_layouts(compiled)
    }


@pytest.mark.parametrize("profile", ["debug", "release"])
def test_report_matches_zig(zig, zig_cache, tmp_path, compiled, profile):
    expected = zig_layouts(zig, zig_cache, tmp_path, compiled.codegen_result["output_code"], profile)
    got = reported(compiled)

    assert {name: got[name] for name in STRUCTS} == expected


def test_fast_profile_differs_only_by_the_bare_union_tag(zig, zig_cache, tmp_path, compiled):
    fast = zig_layouts(zig, zig_cache, tmp_path, compiled.codegen_result["output_code"], "fast")
    got = reported(compiled)

    differing = sorted(name for name in STRUCTS if got[name] != fast[name])
    # Word is 4 bytes of payload at alignment 4: the tag costs a whole word.
    # Nested holds Word, so it shrinks with it. Bytes (5 bytes of payload)
    # pads to 8 with or without the tag.
    assert differing == ["NestedUnion", "WordUnion"]
    assert fast["WordUnion"][2]["u"] == (0, 4)
    assert got["WordUnion"][2]["u"] == (0, 8)


def test_report_notes_the_profile_dependence_for_union_fields(compiled):
    notes = {layout.name: layout.note for layout in _struct_layouts(compiled)}

    assert "fast build drops it" in notes["WordUnion"]
    assert notes["Callbacks"] == ""
