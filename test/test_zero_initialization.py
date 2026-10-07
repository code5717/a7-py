"""A declaration without an initializer and `new T` start as all zeros (L63)."""

from native_profiles import same_output_in_every_profile


def test_struct_local_and_new_memory_start_zeroed(tmp_path, zig):
    source = """
io :: import "std/io"
P :: struct { x: i32, y: i32 }
main :: fn() {
    q: P
    q.x = 1
    io.println("{} {}", q.x, q.y)
    b := new P
    if b == nil { ret }
    io.println("{} {}", b.x, b.y)
    del b
}
"""
    assert same_output_in_every_profile(source, tmp_path, zig) == "1 0\n0 0\n"


def test_slice_string_and_nested_arrays_start_empty_or_zero(tmp_path, zig):
    source = """
io :: import "std/io"
main :: fn() {
    g: [4]i32
    h: [2][2]f64
    s: string
    t: []i32
    io.println("{} {} [{}] {}", g[3], h[1][1], s, t.len)
}
"""
    assert same_output_in_every_profile(source, tmp_path, zig) == "0 0 [] 0\n"


def test_enum_starts_as_its_first_variant_not_the_value_zero(tmp_path, zig):
    source = """
io :: import "std/io"
E :: enum { A = 5, B }
P :: struct { x: i32, y: f64, ok: bool, c: char }
main :: fn() {
    p: P
    e: E
    io.println("{} {} {} {}", p.x, p.y, p.ok, p.c)
    if e == E.A { io.println("A") } else { io.println("notA") }
}
"""
    assert same_output_in_every_profile(source, tmp_path, zig) == "0 0 false \x00\nA\n"


def test_nested_struct_fields_references_unions_and_globals_start_zeroed(tmp_path, zig):
    # `Outer` has a function-pointer field. That field has no zero value and
    # stays undefined; the program assigns it before the call.
    source = """
io :: import "std/io"
E :: enum { First, Second }
U :: union { i: i32, f: f64 }
Inner :: struct { n: i64, e: E, tags: [3]E }
Outer :: struct { inner: Inner, next: ref Outer, items: []i32, name: string, cb: fn(i32) i32 }
Box($T) :: struct {
    v: $T
    next: ref Box($T)
}
global: Outer
twice :: fn(v: i32) i32 { ret v * 2 }
main :: fn() {
    o: Outer
    u: U
    b: Box(i32)
    pair: [2]Inner
    io.println("{} {} [{}]", o.inner.n, o.items.len, o.name)
    if o.next == nil { io.println("next nil") }
    if o.inner.e == E.First and o.inner.tags[2] == E.First { io.println("first") }
    io.println("{} {} {}", u.i, b.v, pair[1].n)
    if b.next == nil { io.println("box nil") }
    io.println("{} {}", global.inner.n, global.items.len)
    o.cb = twice
    io.println("{}", o.cb(4))
    heap := new Outer
    if heap == nil { ret }
    if heap.next == nil and heap.inner.e == E.First { io.println("heap zero {}", heap.inner.n) }
    del heap
}
"""
    assert same_output_in_every_profile(source, tmp_path, zig) == (
        "0 0 []\nnext nil\nfirst\n0 0 0\nbox nil\n0 0\n8\nheap zero 0\n"
    )
