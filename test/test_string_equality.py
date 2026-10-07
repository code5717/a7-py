"""String `==`, `!=` and `match` compare contents (audit P2-47).

The A7 cases exercise literal comparisons. A Zig probe calls emitted A7
functions with separate mutable buffers to distinguish contents from pointers.
"""

import subprocess
from pathlib import Path

import pytest

from conftest import ZIG_MODE, expect_ok, run_both_profiles


@pytest.mark.parametrize("profile", ["debug", "fast"])
def test_equal_contents_in_distinct_buffers(tmp_path, zig, zig_cache, profile):
    # Only the input storage comes from Zig. All four comparisons come from
    # A7 through the full compiler, including its safety pass and codegen.
    result = expect_ok("""
equal :: fn(a: string, b: string) bool { ret a == b }
different :: fn(a: string, b: string) bool { ret a != b }
statement :: fn(s: string) i32 {
    match s {
        case "abc": { ret 1 }
        else: { ret 2 }
    }
}
expression :: fn(s: string) i32 {
    ret match s { case "abc": 1 else: 2 }
}
""", tmp_path, profile=profile, is_library=True)
    generated = Path(result.output_path)
    generated.write_text(generated.read_text() + """
test "distinct storage preserves string content comparisons" {
    var left = [_]u8{ 'a', 'b', 'c' };
    var right = [_]u8{ 'a', 'b', 'c' };
    const a: []u8 = &left;
    const b: []u8 = &right;
    try std.testing.expect(a.ptr != b.ptr);
    try std.testing.expect(equal(a, b));
    try std.testing.expect(!different(a, b));
    try std.testing.expectEqual(@as(i32, 1), statement(a));
    try std.testing.expectEqual(@as(i32, 1), expression(a));
    // Same pointer, different lengths must differ too.
    try std.testing.expect(!equal(a, a[0..2]));
    try std.testing.expect(different(a, a[0..2]));
    right[2] = 'd';
    try std.testing.expect(!equal(a, b));
    try std.testing.expect(different(a, b));
    try std.testing.expectEqual(@as(i32, 2), statement(b));
    try std.testing.expectEqual(@as(i32, 2), expression(b));
}
""")
    process = subprocess.run(
        [zig, "test", str(generated), "-O", ZIG_MODE[profile],
         "--cache-dir", str(zig_cache / "local"),
         "--global-cache-dir", str(zig_cache / "global")],
        capture_output=True, text=True, timeout=120,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert "All 1 tests passed." in process.stderr


def test_equal_and_unequal_strings(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
name :: fn(k: i32) string {
    if k == 1 { ret "one" }
    ret "other"
}
main :: fn() {
    s := name(1)
    t := name(2)
    if s == "one" { io.println("eq literal") }
    if s != t { io.println("ne variable") }
    if s == t { io.println("wrong") }
    if name(2) != "other" { io.println("wrong") }
    same := s == name(1)
    io.println("{}", same)
}
""", tmp_path, zig) == "eq literal\nne variable\ntrue\n"


def test_strings_of_equal_length_and_different_bytes_differ(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
main :: fn() {
    a := "abc"
    b := "abd"
    io.println("{} {}", a == b, a != b)
}
""", tmp_path, zig) == "false true\n"


def test_match_statement_on_a_string(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
name :: fn(k: i32) string {
    if k == 1 { ret "one" }
    if k == 2 { ret "two" }
    ret "other"
}
main :: fn() {
    for k := 1; k <= 3; k += 1 {
        match name(k) {
            case "one": { io.println("m one") }
            case "two", "deux": { io.println("m two") }
            else: { io.println("m other") }
        }
    }
}
""", tmp_path, zig) == "m one\nm two\nm other\n"


def test_match_expression_on_a_string(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
score :: fn(s: string) i32 {
    ret match s { case "abc": 1 case "x": 2 else: 3 }
}
main :: fn() {
    io.println("{} {} {}", score("abc"), score("x"), score("abd"))
}
""", tmp_path, zig) == "1 2 3\n"
