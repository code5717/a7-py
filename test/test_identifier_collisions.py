"""A7 names that Zig reserves build and run (audit P2-47).

Zig rejects a declaration named like a primitive type (`u1`, `f16`, `void`)
unless it is quoted, and a local named like a file-scope declaration. The
generated preamble declares `std`, `allocator`, `panic` and `main` at file
scope and owns the `__a7_` prefix; a user name that matches is renamed.
"""

from conftest import run_both_profiles


def test_locals_named_like_zig_primitive_types(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
main :: fn() {
    u1 := 5
    i7 := 6
    void := 7
    c_int := 8
    anyerror := 9
    noreturn := 10
    f16 := 1.5
    comptime_int := 11
    type := 12
    io.println("{} {} {} {} {} {} {} {} {}", u1, i7, void, c_int, anyerror, noreturn, f16, comptime_int, type)
}
""", tmp_path, zig) == "5 6 7 8 9 10 1.5 11 12\n"


def test_declarations_fields_and_parameters_named_like_primitives(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
u8x :: struct { u1: i32, type: i32 }
i7 :: enum { u1, i9 }
f16 :: fn(void: i32, u1: i32) i32 { ret void + u1 }
c_int := 30
main :: fn() {
    p := u8x{u1: 1, type: 2}
    e := i7.i9
    match e {
        case i7.u1: { io.println("u1") }
        case i7.i9: { io.println("i9") }
    }
    for u2 in [1, 2] { io.println("{}", u2) }
    io.println("{} {} {}", p.u1 + p.type, f16(1, 2), c_int)
}
""", tmp_path, zig) == "i9\n1\n2\n3 3 30\n"


def test_locals_named_like_preamble_declarations(tmp_path, zig):
    # `new` and `del` make the preamble declare `allocator`; `io` makes it
    # declare `std`, `panic` and `main`.
    assert run_both_profiles("""
io :: import "std/io"
Box :: struct { value: i32 }
twice :: fn(std: i32) i32 { ret std * 2 }
main :: fn() {
    std := 5
    allocator := 6
    panic := 7
    main := 8
    b := new Box
    if b != nil {
        b.value = std + allocator + panic + main
        io.println("{} {}", b.value, twice(4))
        del b
    }
}
""", tmp_path, zig) == "26 8\n"


def test_top_level_declarations_named_like_preamble_declarations(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
std :: fn() i32 { ret 1 }
allocator := 40
panic :: struct { code: i32 }
main :: fn() {
    std_1 := 5
    p := panic{code: 2}
    allocator += 1
    io.println("{} {} {} {}", std(), allocator, p.code, std_1)
}
""", tmp_path, zig) == "1 41 2 5\n"


def test_user_names_with_the_generator_prefix(tmp_path, zig):
    # `__a7_match_1` is the name the backend gives the first match scrutinee.
    assert run_both_profiles("""
io :: import "std/io"
__a7_stdout_print :: fn(n: i32) i32 { ret n + 1 }
main :: fn() {
    __a7_io := 9
    __a7_match_1 := 3
    match __a7_match_1 {
        case seen: { io.println("{}", seen) }
    }
    io.println("{} {}", __a7_io, __a7_stdout_print(1))
}
""", tmp_path, zig) == "3\n9 2\n"
