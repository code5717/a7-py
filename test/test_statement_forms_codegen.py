"""Statement and expression forms the backend rejected or mis-emitted (audit P2-41, P2-49, P2-40)."""

from conftest import expect_exit, expect_ok, run_both_profiles


def test_array_sum_as_a_declaration_initializer_and_as_an_assignment(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
main :: fn() {
    arr: [3]i32 = [1, 2, 3]
    brr: [3]i32 = [10, 20, 30]
    crr := arr + brr
    arr = arr + brr
    io.println("{} {} {}", crr[0], crr[2], arr[2])
}
""", tmp_path, zig) == "11 33 33\n"


def test_print_call_as_a_for_update_clause(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
main :: fn() {
    for i := 0; i < 2; io.println("step") {
        i += 1
    }
}
""", tmp_path, zig) == "step\nstep\n"


def test_print_call_has_no_value(tmp_path):
    result = expect_exit("""
io :: import "std/io"
main :: fn() {
    x := io.println("a")
}
""", tmp_path, 7, "io.println is a void call and has no value")
    assert result.failure.details[0]["span"]["start_line"] == 4


def test_field_access_and_index_on_a_literal(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
P :: struct { x: i32, y: i32 }
main :: fn() {
    a := [1, 2][0]
    b := "abc"[0]
    c := P{x: 1, y: 7}.y
    io.println("{} {} {}", a, b, c)
}
""", tmp_path, zig) == "1 a 7\n"


def test_global_variable_initialised_from_other_globals(tmp_path, zig):
    # Each initializer reads the other variable's initial value, whatever
    # the declaration order; later writes do not change it.
    assert run_both_profiles("""
io :: import "std/io"
a := b + 1
b := c * 2
c := 3
main :: fn() {
    c = 100
    a = a + 1
    io.println("{} {} {}", a, b, c)
}
""", tmp_path, zig) == "8 6 100\n"


def test_global_initializer_cycle_is_rejected(tmp_path):
    expect_exit("""
a := b
b := a
main :: fn() {}
""", tmp_path, 6, "Global value dependency cycle")


def test_write_through_a_scalar_reference_builds(tmp_path, zig):
    # `p = 4` writes the referent. The backend declared `p` with `var` and
    # Zig rejected the build: "local variable is never mutated". A7 cannot
    # read a scalar back through a `ref`, so only the build is checked.
    assert run_both_profiles("""
io :: import "std/io"
set :: fn(value: ref i64) { value = 9 }
main :: fn() {
    p := new i64
    if p != nil {
        p = 4
        set(p)
        io.println("built")
        del p
    }
}
""", tmp_path, zig) == "built\n"


def test_char_above_ascii_is_one_byte(tmp_path, zig):
    source = """
io :: import "std/io"
main :: fn() {
    c: char = 'é'
    d: char = 'ÿ'
    z: char = 'z'
    io.println("{} {}", c > z, d > c)
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "true true\n"
    # Raw `'é'` in the Zig source would be two UTF-8 bytes for one A7 byte.
    emitted = open(expect_ok(source, tmp_path).output_path, encoding="utf-8").read()
    assert "'\\xe9'" in emitted and "'\\xff'" in emitted
