"""`Name :: @type_set(...)` aliases exist only at compile time (audit P3-19).

The backend used to exit 7 on the declaration ("unsupported expression node
'TYPE_SET'"). It now emits nothing for it; a parameter the alias constrains
lowers to `comptime T: type` like any other.
"""

from conftest import expect_exit, expect_ok, run_both_profiles


def test_file_scope_alias_that_nothing_uses(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
IntOnly :: @type_set(i32, i64)
main :: fn() { io.println("{}", 1) }
""", tmp_path, zig) == "1\n"


def test_alias_as_a_declared_constraint_and_in_a_where_clause(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
SmallInts :: @type_set(i8, i16)
twice($T: SmallInts) :: fn(x: $T) $T { ret x + x }
thrice :: fn(x: $T) $T where T: SmallInts { ret x + x + x }
main :: fn() {
    v: i8 = 3
    w: i16 = 100
    io.println("{} {}", twice(v), thrice(w))
}
""", tmp_path, zig) == "6 300\n"


def test_alias_constraint_rejects_a_type_outside_the_set(tmp_path):
    expect_exit("""
SmallInts :: @type_set(i8, i16)
twice($T: SmallInts) :: fn(x: $T) $T { ret x + x }
main :: fn() {
    v: i64 = 3
    y := twice(v)
}
""", tmp_path, 6, "Generic parameter '$T' requires")


def test_function_local_alias_emits_no_zig_declaration(tmp_path, zig):
    source = """
io :: import "std/io"
main :: fn() {
    Local :: @type_set(i32, i64)
    io.println("ok")
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "ok\n"
    emitted = open(expect_ok(source, tmp_path).output_path, encoding="utf-8").read()
    assert "Local" not in emitted
