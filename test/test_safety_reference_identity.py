"""Deletion follows allocation identity; field guards follow the current place value."""

import pytest

from conftest import expect_exit, expect_ok, run_all_profiles

UNSAFE = {
    'saf2_nil_ptr': """
io :: import "std/io"
Box :: struct { value: i32 }
Holder :: struct { ptr: ref Box }
main :: fn() {
 h := Holder{ptr: nil}
 h.ptr.value = 7
}
""",
    'saf8_double_del': """
io :: import "std/io"
Box :: struct { value: i32 }
Holder :: struct { child: ref Box }
main :: fn() {
 h := Holder{child: new Box}
 del h.child
 del h.child
}
""",
    'alias_uaf': """
io :: import "std/io"
Box :: struct { value: i32 }
Holder :: struct { child: ref Box }
main :: fn() {
 b := new Box
 if b != nil {
  c := b
  del b
  io.println("{}", c.value)
 }
}
""",
    'alias_double_del': """
io :: import "std/io"
Box :: struct { value: i32 }
Holder :: struct { child: ref Box }
main :: fn() {
 b := new Box
 c := b
 del b
 del c
}
""",
}

CONTROLS = {
    'saf2_guarded_ptr': """
io :: import "std/io"
Box :: struct { value: i32 }
Holder :: struct { ptr: ref Box }
main :: fn() {
 allocated := new Box
 if allocated != nil {
  allocated.value = 7
  h := Holder{ptr: allocated}
  if h.ptr != nil { io.println("{}", h.ptr.value) }
  del allocated
 }
}
""",
    'saf8_single_del': """
io :: import "std/io"
Box :: struct { value: i32 }
Holder :: struct { child: ref Box }
main :: fn() {
 h := Holder{child: new Box}
 del h.child
}
""",
    'saf8_reassign_del': """
io :: import "std/io"
Box :: struct { value: i32 }
Holder :: struct { child: ref Box }
main :: fn() {
 h := Holder{child: new Box}
 del h.child
 h.child = new Box
 del h.child
}
""",
    'alias_before_del_control': """
io :: import "std/io"
Box :: struct { value: i32 }
Holder :: struct { child: ref Box }
main :: fn() {
 b := new Box
 if b != nil {
  c := b
  c.value = 7
  io.println("{}", b.value)
  del b
 }
}
""",
    'independent_allocations_control': """
io :: import "std/io"
Box :: struct { value: i32 }
Holder :: struct { child: ref Box }
main :: fn() {
 b := new Box
 c := new Box
 del b
 if c != nil { io.println("{}", c.value) }
 del c
}
""",
    'separate_fields_control': """
io :: import "std/io"
Box :: struct { value: i32 }
Holder :: struct { child: ref Box }
Pair :: struct { left: ref Box; right: ref Box }
main :: fn() {
 p := Pair{left: new Box, right: new Box}
 del p.left
 del p.right
}
""",
    'alias_reassigned_control': """
io :: import "std/io"
Box :: struct { value: i32 }
Holder :: struct { child: ref Box }
main :: fn() {
 b := new Box
 c := b
 del b
 c = new Box
 if c != nil { io.println("{}", c.value) }
 del c
}
""",
}

@pytest.mark.parametrize("name", UNSAFE)
def test_invalid_reference_use_is_a_semantic_error(tmp_path, name):
    message = "Reference not proven non-nil" if name == "saf2_nil_ptr" else "deleted"
    expect_exit(UNSAFE[name], tmp_path, 6, message)

@pytest.mark.parametrize("name", CONTROLS)
def test_reference_controls_run_in_every_profile(tmp_path, zig, name):
    expected = {"saf2_guarded_ptr": "7\n", "alias_before_del_control": "7\n",
                "independent_allocations_control": "0\n", "alias_reassigned_control": "0\n"}.get(name, "")
    assert run_all_profiles(CONTROLS[name], tmp_path, zig) == expected

BOX = 'io :: import "std/io"\nBox :: struct { value: i32 }\nHolder :: struct { ptr: ref Box }\n'

@pytest.mark.parametrize("statement", [
    "if flag { del b }",
    "{ defer del b }",
    "while flag { del b; break }",
    "drop(b)",
], ids=["branch", "defer", "loop", "call"])
def test_deletion_invalidates_aliases_across_control_flow(tmp_path, statement):
    source = BOX + "drop :: fn(p: ref Box) { del p }\n" + """
f :: fn(flag: bool) {
    b := new Box
    if b == nil { ret }
    c := b
    """ + statement + """
    io.println("{}", c.value)
}
main :: fn() { f(true) }
"""
    expect_exit(source, tmp_path, 6, "deleted")

@pytest.mark.parametrize("mutation", [
    "h.ptr = nil",
    "clear(h)",
], ids=["assignment", "call"])
def test_field_guard_does_not_survive_mutation(tmp_path, mutation):
    source = BOX + "clear :: fn(h: ref Holder) { h.ptr = nil }\n" + """
main :: fn() {
    b := new Box
    if b == nil { ret }
    h := Holder{ptr: b}
    if h.ptr != nil {
        """ + mutation + """
        io.println("{}", h.ptr.value)
    }
    del b
}
"""
    expect_exit(source, tmp_path, 6, "Reference not proven non-nil")


def test_loop_replacing_struct_cannot_reuse_field_guard(tmp_path):
    source = BOX + """
main :: fn() {
    b := new Box
    if b == nil { ret }
    h := Holder{ptr: b}
    if h.ptr != nil {
        i: usize = 0
        while i < 2 {
            io.println("{}", h.ptr.value)
            h = Holder{ptr: nil}
            i += 1
        }
    }
    del b
}
"""
    expect_exit(source, tmp_path, 6, "Reference not proven non-nil")


def test_fresh_allocations_inside_loop_are_not_previous_iterations(tmp_path, zig):
    source = BOX + """
main :: fn() {
    i: usize = 0
    while i < 3 {
        b := new Box
        if b == nil { ret }
        c := b
        c.value = 7
        io.println("{}", b.value)
        del c
        i += 1
    }
}
"""
    assert run_all_profiles(source, tmp_path, zig) == "7\n7\n7\n"


def test_struct_copy_preserves_reference_identity(tmp_path):
    source = BOX + """
main :: fn() {
    b := new Box
    if b == nil { ret }
    h := Holder{ptr: b}
    other := h
    del h.ptr
    io.println("{}", other.ptr.value)
}
"""
    expect_exit(source, tmp_path, 6, "deleted")


def test_conditional_reference_preserves_possible_aliases(tmp_path):
    source = BOX + """
f :: fn(flag: bool) {
    b := new Box
    d := new Box
    if b == nil { del d; ret }
    if d == nil { del b; ret }
    c := if flag { b } else { d }
    del b
    io.println("{}", c.value)
    del d
}
main :: fn() { f(true) }
"""
    expect_exit(source, tmp_path, 6, "deleted")


def test_parameter_alias_is_invalid_after_deletion(tmp_path):
    expect_exit(BOX + """
f :: fn(b: ref Box) {
    c := b
    del b
    io.println("{}", c.value)
}
main :: fn() {}
""", tmp_path, 6, "deleted")


def test_call_deleting_global_invalidates_local_alias(tmp_path):
    expect_exit(BOX + """
global: ref Box = nil
drop :: fn() { del global }
main :: fn() {
    global = new Box
    c := global
    if c == nil { ret }
    drop()
    io.println("{}", c.value)
}
""", tmp_path, 6, "deleted")


def test_forward_nested_deleting_function_does_not_use_global_summary(tmp_path):
    expect_exit(BOX + """
drop :: fn(b: ref Box) { b.value = 1 }
main :: fn() {
    b := new Box
    if b == nil { ret }
    c := b
    drop(b)
    drop :: fn(value: ref Box) { del value }
    io.println("{}", c.value)
}
""", tmp_path, 6, "deleted")


def test_read_only_call_preserves_field_guard(tmp_path, zig):
    source = BOX + """
read :: fn(h: ref Holder) { if h.ptr != nil { io.println("{}", h.ptr.value) } }
main :: fn() {
    b := new Box
    if b == nil { ret }
    b.value = 7
    h := Holder{ptr: b}
    if h.ptr != nil {
        read(h)
        io.println("{}", h.ptr.value)
    }
    del b
}
"""
    assert run_all_profiles(source, tmp_path, zig) == "7\n7\n"


@pytest.mark.parametrize("operation, index", [
    ("b.n += 1", "b.n - 1"),
    ("wr(b)", "b.n - 4"),
], ids=["compound-field-store", "callee-writes-through-alias"])
def test_numeric_field_writes_cannot_supply_stale_bounds_proofs(tmp_path, operation, index):
    source = """
Box :: struct { n: usize }
wr :: fn(b: ref Box) { local := b; local.n = 1 }
main :: fn() {
    b := Box{n: 5}
    """ + operation + """
    arr: [2]usize
    value := arr[""" + index + """]
}
"""
    expect_exit(source, tmp_path, 6, "Index not proven in bounds")


@pytest.mark.parametrize("body", [
    "local := h; local.ptr = nil",
    "local := h; if flag { local.ptr = nil }",
    "local := h; while flag { local.ptr = nil; break }",
    "local := h; defer local.ptr = nil",
], ids=["direct", "branch", "loop", "defer"])
def test_callee_reference_alias_write_invalidates_field_guard(tmp_path, body):
    source = BOX + "clear :: fn(h: ref Holder, flag: bool) { " + body + " }\n" + """
main :: fn() {
    b := new Box
    if b == nil { ret }
    h := Holder{ptr: b}
    if h.ptr != nil {
        clear(h, true)
        io.println("{}", h.ptr.value)
    }
    del b
}
"""
    expect_exit(source, tmp_path, 6, "Reference not proven non-nil")


def test_readonly_callee_alias_preserves_field_guard(tmp_path, zig):
    source = BOX + """
read :: fn(h: ref Holder) {
    local := h
    if local.ptr != nil { io.println("{}", local.ptr.value) }
}
main :: fn() {
    b := new Box
    if b == nil { ret }
    b.value = 7
    h := Holder{ptr: b}
    if h.ptr != nil {
        read(h)
        io.println("{}", h.ptr.value)
    }
    del b
}
"""
    assert run_all_profiles(source, tmp_path, zig) == "7\n7\n"


def test_fresh_local_reference_does_not_invalidate_parameter_fields(tmp_path):
    source = BOX + """
change :: fn(h: ref Holder) {
    local := h
    local = new Holder
    if local == nil { ret }
    local.ptr = nil
}
main :: fn() {
    b := new Box
    if b == nil { ret }
    h := Holder{ptr: b}
    if h.ptr != nil {
        change(h)
        io.println("{}", h.ptr.value)
    }
    del b
}
"""
    expect_ok(source, tmp_path)


@pytest.mark.parametrize("exit_statement", ["ret", "break", "continue"])
def test_deferred_alias_write_uses_each_exit_state(tmp_path, exit_statement):
    body = """
fresh := new Holder
if fresh == nil { ret }
local := h
defer local.ptr = nil
if flag { """ + exit_statement + """ }
local = fresh
"""
    if exit_statement != "ret":
        body = "while flag { " + body + " }"
    source = BOX + "clear :: fn(h: ref Holder, flag: bool) { " + body + " }\n" + """
main :: fn() {
    b := new Box
    if b == nil { ret }
    h := Holder{ptr: b}
    if h.ptr != nil {
        clear(h, true)
        io.println("{}", h.ptr.value)
    }
    del b
}
"""
    expect_exit(source, tmp_path, 6, "Reference not proven non-nil")


def test_deferred_write_after_fresh_rebinding_keeps_caller_field_guard(tmp_path):
    source = BOX + """
change :: fn(h: ref Holder) {
    fresh := new Holder
    if fresh == nil { ret }
    local := h
    defer local.ptr = nil
    local = fresh
}
main :: fn() {
    b := new Box
    if b == nil { ret }
    h := Holder{ptr: b}
    if h.ptr != nil {
        change(h)
        io.println("{}", h.ptr.value)
    }
    del b
}
"""
    expect_ok(source, tmp_path)


NESTED_RECORD = """
io :: import "std/io"
Box :: struct { value: i32 }
Holder :: struct { child: ref Box }
Outer :: struct { inner: Holder }
"""


@pytest.mark.parametrize("copy_steps", [
    "o := Outer{inner: h}",
    "o := Outer{inner: Holder{child: nil}}; o = Outer{inner: h}",
    "original := Outer{inner: h}; o := original",
    "o := Outer{inner: Holder{child: nil}}; o.inner = h",
])
def test_nested_record_copies_preserve_deleted_child_identity(tmp_path, copy_steps):
    source = NESTED_RECORD + """
main :: fn() {
    b := new Box
    if b == nil { ret }
    h := Holder{child: b}
""" + copy_steps + """
    del b
    if o.inner.child != nil { io.println("{}", o.inner.child.value) }
}
"""
    expect_exit(source, tmp_path, 6, "deleted")


def test_nested_record_distinct_fields_remain_independent(tmp_path, zig):
    source = NESTED_RECORD + """
Pair :: struct { left: Holder; right: Holder }
main :: fn() {
    a := new Box
    if a == nil { ret }
    b := new Box
    if b == nil { del a; ret }
    b.value = 17
    left := Holder{child: a}
    right := Holder{child: b}
    pair := Pair{left: left, right: right}
    del pair.left.child
    if pair.right.child != nil { io.println("{}", pair.right.child.value) }
    del pair.right.child
}
"""
    assert run_all_profiles(source, tmp_path, zig) == "17\n"


def test_nested_record_fresh_assignment_replaces_deleted_identity(tmp_path, zig):
    source = NESTED_RECORD + """
main :: fn() {
    a := new Box
    if a == nil { ret }
    h := Holder{child: a}
    o := Outer{inner: h}
    del o.inner.child
    b := new Box
    if b == nil { ret }
    b.value = 23
    fresh := Holder{child: b}
    o = Outer{inner: fresh}
    copy := o
    if copy.inner.child != nil { io.println("{}", copy.inner.child.value) }
    del copy.inner.child
}
"""
    assert run_all_profiles(source, tmp_path, zig) == "23\n"


@pytest.mark.parametrize("mutates", [False, True])
def test_wrapper_composes_known_callee_field_effects(tmp_path, mutates):
    body = "h.ptr = nil" if mutates else 'if h.ptr != nil { io.println("{}", h.ptr.value) }'
    source = BOX + "change :: fn(h: ref Holder) { read(h) }\nread :: fn(h: ref Holder) { " + body + " }\n" + """
main :: fn() {
    b := new Box
    if b == nil { ret }
    h := Holder{ptr: b}
    if h.ptr != nil {
        change(h)
        io.println("{}", h.ptr.value)
    }
    del b
}
"""
    if mutates:
        expect_exit(source, tmp_path, 6, "Reference not proven non-nil")
    else:
        expect_ok(source, tmp_path)


@pytest.mark.parametrize("falls", [False, True])
def test_match_field_write_tracks_fallthrough_alias(tmp_path, falls):
    source = BOX + """
change :: fn(h: ref Holder, n: i32) {
    fresh := new Holder
    if fresh == nil { ret }
    local := fresh
    match n {
        case 1: { local = h; """ + ("fall" if falls else "") + """ }
        case 2: { local.ptr = nil }
        else: {}
    }
}
main :: fn() {
    b := new Box
    if b == nil { ret }
    h := Holder{ptr: b}
    if h.ptr != nil {
        change(h, 1)
        io.println("{}", h.ptr.value)
    }
    del b
}
"""
    if falls:
        expect_exit(source, tmp_path, 6, "Reference not proven non-nil")
    else:
        expect_ok(source, tmp_path)
