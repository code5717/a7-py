"""Inline `$T` generic functions (SPEC 7.1) build and run (audit P3-13, P2-40, P2-49).

`identity :: fn(value: $T) $T` declares `$T` by naming it in the signature.
The backend used to exit 7 unless the function was written with an explicit
list, `identity($T) :: fn(value: $T) $T`.
"""

from conftest import expect_exit, run_both_profiles


def test_one_inline_parameter_is_inferred_at_each_call(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
identity :: fn(value: $T) $T { ret value }
main :: fn() {
    io.println("{} {} {}", identity(7), identity(2.5), identity("s"))
}
""", tmp_path, zig) == "7 2.5 s\n"


def test_inline_function_that_is_never_called_compiles(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
identity :: fn(value: $T) $T { ret value }
main :: fn() { io.println("ok") }
""", tmp_path, zig) == "ok\n"


def test_inline_and_declared_forms_agree(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
inline_form :: fn(a: $T, b: $T) $T where T: Numeric { ret a + b }
declared_form($T: Numeric) :: fn(a: $T, b: $T) $T { ret a + b }
main :: fn() {
    io.println("{} {}", inline_form(2, 3), declared_form(2, 3))
}
""", tmp_path, zig) == "5 5\n"


def test_each_argument_reaches_its_own_parameter(tmp_path, zig):
    # The second parameter's type is named first in neither the call's
    # inference order nor the return type; a swapped pair would print 1.
    assert run_both_profiles("""
io :: import "std/io"
Box :: struct { value: $T }
second :: fn(a: $U, b: $T) $T { ret b }
unbox :: fn(b: Box($T), tag: $U) $T { ret b.value }
main :: fn() {
    io.println("{} {}", second(1, 2.5), unbox(Box(i32){value: 4}, "tag"))
}
""", tmp_path, zig) == "2.5 4\n"


def test_where_clause_on_an_inline_function(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
add :: fn(a: $T, b: $T) $T where T: Numeric { ret a + b }
first :: fn(a: $T, b: $U) $T where T: Numeric, U: Numeric { ret a }
pick :: fn(a: $T) $T where T: @type_set(i32, i64) { ret a }
main :: fn() {
    io.println("{} {} {}", add(2, 3), first(1.5, 2), pick(9))
}
""", tmp_path, zig) == "5 1.5 9\n"


def test_where_clause_still_rejects_a_type_outside_the_set(tmp_path):
    expect_exit("""
add :: fn(a: $T, b: $T) $T where T: Numeric { ret a + b }
main :: fn() { x := add(true, false) }
""", tmp_path, 6, "requires Numeric")


def test_parameter_named_only_in_the_return_type_compiles_uncalled(tmp_path, zig):
    # A call cannot infer `$R`; the checker reports that. The declaration
    # alone must still be valid Zig.
    assert run_both_profiles("""
io :: import "std/io"
make :: fn(seed: $T) $R { z: $R; ret z }
main :: fn() { io.println("ok") }
""", tmp_path, zig) == "ok\n"
    expect_exit("""
make :: fn(seed: $T) $R { z: $R; ret z }
main :: fn() { x := make(1) }
""", tmp_path, 6, "Could not infer generic parameter '$R'")


def test_local_of_the_parameter_type_in_a_generic_body(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
pick($T) :: fn(a: $T, b: $T) $T {
    tmp: $T = a
    other := b
    ret if true { other } else { tmp }
}
zero :: fn(a: $T) $T where T: Numeric {
    z: $T = 0
    ret z + a
}
main :: fn() {
    io.println("{} {}", pick(1, 2), zero(5))
}
""", tmp_path, zig) == "2 5\n"


def test_generic_struct_literal_built_from_the_function_parameters(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
Pair($A, $B) :: struct { first: $A, second: $B }
Box :: struct { value: $T }
flip :: fn(a: $A, b: $B) Pair($B, $A) {
    ret Pair($B, $A){first: b, second: a}
}
wrap :: fn(v: $T) Box($T) {
    b: Box($T) = Box($T){value: v}
    ret b
}
main :: fn() {
    p := flip(1, 2.5)
    io.println("{} {} {}", p.first, p.second, wrap(7).value)
}
""", tmp_path, zig) == "2.5 1 7\n"


def test_implicit_generic_struct_whose_field_is_a_generic_instance(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
Box :: struct { value: $T }
Wrap :: struct { inner: Box($T) }
get($T) :: fn(b: Box($T)) $T { ret b.value }
main :: fn() {
    w := Wrap(i32){inner: Box(i32){value: 3}}
    io.println("{} {}", w.inner.value, get(Box(i32){value: 4}))
}
""", tmp_path, zig) == "3 4\n"


def test_generic_array_parameter(tmp_path, zig):
    assert run_both_profiles("""
io :: import "std/io"
total :: fn(xs: [3]$T) $T where T: Numeric { ret xs[0] + xs[1] + xs[2] }
main :: fn() {
    arr: [3]i64 = [1, 2, 3]
    io.println("{}", total(arr))
}
""", tmp_path, zig) == "6\n"


def test_name_outside_an_explicit_list_is_still_a_parameter(tmp_path, zig):
    # `$U` is not in the declared list. The checker accepts and infers it,
    # so the backend declares it after the listed names.
    assert run_both_profiles("""
io :: import "std/io"
conv($T) :: fn(a: $T, b: $U) $T { ret a }
main :: fn() { io.println("{}", conv(1, 2.5)) }
""", tmp_path, zig) == "1\n"


def test_integer_literal_in_a_body_instantiated_with_a_string_is_rejected(tmp_path):
    expect_exit("""
io :: import "std/io"
zero($T) :: fn(a: $T) $T {
    z: $T = 0
    ret z
}
main :: fn() {
    s: string = "x"
    io.println("{}", zero(s))
}
""", tmp_path, 6, "$T")
