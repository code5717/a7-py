"""Type declarations resolve in any order (findings P2-30).

Every struct, enum and union name is registered before any field resolves,
so a field may name a type declared later in the file or, through `ref`,
the type that holds it. A type that stores itself by value has no finite
size and is rejected with the cycle spelled out.
"""

from __future__ import annotations

import pytest

from conftest import expect_exit, expect_ok, run_both_profiles


def test_fields_may_name_types_declared_later(tmp_path, zig):
    source = """\
io :: import "std/io"

Shape :: struct { origin: Point, color: Color, label: Label }
Point :: struct { x: i32, y: i32 }
Color :: enum { Red, Blue }
Label :: union { code: i32, ratio: f64 }

main :: fn() {
    s := Shape{origin: Point{x: 3, y: 4}, color: Color.Blue, label: Label{code: 9}}
    if s.color == Color.Blue {
        io.println("{} {} {}", s.origin.x, s.origin.y, s.label.code)
    }
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "3 4 9\n"


def test_a_struct_may_refer_to_itself_through_ref(tmp_path, zig):
    source = """\
io :: import "std/io"

Node :: struct {
    value: i32
    next: ref Node
}

main :: fn() {
    tail := new Node
    if tail == nil { ret }
    tail.value = 2
    tail.next = nil
    head := Node{value: 1, next: tail}
    total := head.value
    link := head.next
    if link != nil {
        total += link.value
    }
    io.println("{}", total)
    del tail
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "3\n"


def test_two_structs_may_refer_to_each_other_through_ref(tmp_path, zig):
    source = """\
io :: import "std/io"

Owner :: struct { pet: ref Pet, age: i32 }
Pet :: struct { owner: ref Owner, legs: i32 }

main :: fn() {
    owner := Owner{pet: nil, age: 30}
    pet := Pet{owner: nil, legs: 4}
    io.println("{} {}", owner.age, pet.legs)
}
"""
    assert run_both_profiles(source, tmp_path, zig) == "30 4\n"


@pytest.mark.parametrize(
    ("declarations", "cycle"),
    [
        pytest.param("Node :: struct { next: Node, v: i32 }", "Node -> Node", id="direct"),
        pytest.param(
            "A :: struct { b: B }\nB :: struct { a: A }", "A -> B -> A", id="two-structs",
        ),
        pytest.param(
            "A :: struct { rows: [2]B }\nB :: struct { a: A }", "A -> B -> A", id="through-array",
        ),
        pytest.param(
            "A :: struct { u: U }\nU :: union { a: A, n: i32 }", "A -> U -> A", id="through-union",
        ),
        pytest.param(
            "Box($T) :: struct { item: $T }\nN :: struct { box: Box(N) }",
            "N -> Box(N) -> N",
            id="through-generic-instance",
        ),
    ],
)
def test_a_type_that_stores_itself_by_value_is_rejected(tmp_path, declarations, cycle):
    source = f"{declarations}\n\nmain :: fn() {{\n}}\n"
    result = expect_exit(source, tmp_path, 6, f"contains itself by value ({cycle})")
    # One cycle, one error: every member of the cycle would repeat it.
    assert len(result.failure.details) == 1, result.failure.details


def test_a_generic_field_that_holds_only_a_slice_is_not_a_cycle(tmp_path):
    source = """\
List($T) :: struct { items: []$T, count: usize }
Tree :: struct { children: List(Tree), value: i32 }

main :: fn() {
}
"""
    expect_ok(source, tmp_path)
