"""Track 1 alias holes: exact array elements, selected-holder sync, joined nil-write."""

import pytest

from conftest import expect_exit, expect_ok
from native_profiles import same_output_in_every_profile

IO = 'io :: import "std/io"\n'
BOX = "Box :: struct { value: i32 }\n"
HOLDER = "Holder :: struct { child: ref Box }\n"


def test_array_element_alias_after_delete_exits_6(tmp_path):
    source = IO + BOX + """
main :: fn() {
    p := new Box
    if p == nil { ret }
    refs: [1]ref Box = [p]
    del p
    q := refs[0]
    if q != nil { io.println("{}", q.value) }
}
"""
    expect_exit(source, tmp_path, 6, "Use after move or delete")


def test_array_element_alias_before_delete_is_ok(tmp_path, zig):
    source = IO + BOX + """
main :: fn() {
    p := new Box
    if p == nil { ret }
    p.value = 7
    refs: [1]ref Box = [p]
    q := refs[0]
    if q != nil { io.println("{}", q.value) }
    del p
}
"""
    assert same_output_in_every_profile(source, tmp_path, zig) == "7\n"


def test_distinct_array_element_survives_sibling_delete(tmp_path, zig):
    source = IO + BOX + """
main :: fn() {
    p := new Box
    if p == nil { ret }
    r := new Box
    if r == nil { del p; ret }
    p.value = 1
    r.value = 2
    refs: [2]ref Box = [p, r]
    del p
    q := refs[1]
    if q != nil { io.println("{}", q.value) }
    del r
}
"""
    assert same_output_in_every_profile(source, tmp_path, zig) == "2\n"


def test_exact_index_store_replaces_element_without_reviving_old_alias(tmp_path):
    source = IO + BOX + """
main :: fn() {
    p := new Box
    if p == nil { ret }
    refs: [1]ref Box = [p]
    old := refs[0]
    refs[0] = new Box
    fresh := refs[0]
    del p
    if old != nil { io.println("{}", old.value) }
    if fresh != nil { del fresh }
}
"""
    expect_exit(source, tmp_path, 6, "Use after move or delete")


def test_selected_holder_store_joins_candidate_field_facts(tmp_path):
    # Uncertain p may be a or b. Storing y through p must leave a.child as
    # join(x, y), so del x still rejects a guarded a.child read.
    source = IO + BOX + HOLDER + """
main :: fn() {
    a := new Holder
    if a == nil { ret }
    b := new Holder
    if b == nil { del a; ret }
    x := new Box
    if x == nil { del a; del b; ret }
    y := new Box
    if y == nil { del x; del a; del b; ret }
    a.child = x
    b.child = x
    flag := false
    p := if flag { a } else { b }
    p.child = y
    del x
    if a.child != nil { io.println("{}", a.child.value) }
    del y
    del a
    del b
}
"""
    expect_exit(source, tmp_path, 6, "Use after move or delete")


def test_independent_struct_copy_does_not_sync_field_store(tmp_path):
    source = IO + BOX + HOLDER + """
main :: fn() {
    p := new Box
    if p == nil { ret }
    h := Holder{child: p}
    saved := h
    h.child = new Box
    del p
    if saved.child != nil { io.println("{}", saved.child.value) }
    if h.child != nil { del h.child }
}
"""
    expect_exit(source, tmp_path, 6, "Use after move or delete")


def test_dynamic_index_store_invalidates_exact_element_facts(tmp_path):
    source = IO + BOX + """
run :: fn(i: usize) {
    p := new Box
    if p == nil { ret }
    p.value = 1
    refs: [2]ref Box = [p, p]
    if i < 2 {
        refs[i] = nil
        io.println("{}", refs[0].value)
    }
    del p
}
main :: fn() { run(0) }
"""
    expect_exit(source, tmp_path, 6, "Reference not proven non-nil")


def test_indexed_overwrite_after_delete_does_not_uaf_target(tmp_path, zig):
    source = IO + BOX + """
main :: fn() {
    p := new Box
    if p == nil { ret }
    refs: [1]ref Box = [p]
    del p
    refs[0] = new Box
    q := refs[0]
    if q != nil {
        q.value = 3
        io.println("{}", q.value)
        del q
    }
}
"""
    assert same_output_in_every_profile(source, tmp_path, zig) == "3\n"


def test_joined_holder_nil_write_invalidates_selected_child(tmp_path):
    source = IO + BOX + HOLDER + """
clear :: fn(h: ref Holder) { h.child = nil }
main :: fn() {
    x := new Box
    if x == nil { ret }
    a := new Holder
    if a == nil { del x; ret }
    b := new Holder
    if b == nil { del a; del x; ret }
    a.child = x
    b.child = x
    selected := a
    flag := false
    if flag { selected = b }
    if selected.child != nil {
        clear(a)
        io.println("{}", selected.child.value)
    }
    del a
    del b
}
"""
    expect_exit(source, tmp_path, 6, "Reference not proven non-nil")
