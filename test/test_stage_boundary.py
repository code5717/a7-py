"""Stage boundary: what the semantic stage accepts must compile and build.

`--mode semantic` runs every check the compiler has (names, types, validator,
safety proof). A program it accepts and codegen or Zig then rejects is a
compiler defect: the user was told the program is valid. Each row is compiled
in semantic mode, then through the full pipeline, built with Zig and run.

Rows with a `defect` are known violations. They are strict xfails, so the row
fails as soon as the defect is fixed and the mark must then be removed.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from conftest import build_and_run, failure_text


@dataclass(frozen=True)
class Program:
    source: str
    stdout: str
    defect: str = ""


PROGRAMS = {
    "function_call": Program(
        stdout="7\n",
        source="""\
io :: import "std/io"

add :: fn(a: i32, b: i32) i32 {
    ret a + b
}

main :: fn() {
    io.println("{}", add(3, 4))
}
""",
    ),
    "guarded_division": Program(
        stdout="3 0\n",
        source="""\
io :: import "std/io"

div :: fn(a: i32, b: i32) i32 {
    if b == 0 {
        ret 0
    }
    ret a / b
}

main :: fn() {
    io.println("{} {}", div(9, 3), div(1, 0))
}
""",
    ),
    "struct_fields": Program(
        stdout="7\n",
        source="""\
io :: import "std/io"

Point :: struct {
    x: i32
    y: i32
}

main :: fn() {
    p := Point{x: 3, y: 4}
    io.println("{}", p.x + p.y)
}
""",
    ),
    "struct_passed_by_value": Program(
        stdout="15\n",
        source="""\
io :: import "std/io"

Point :: struct {
    x: i32
    y: i32
}

sum :: fn(p: Point) i32 {
    ret p.x + p.y
}

main :: fn() {
    io.println("{}", sum(Point{x: 10, y: 5}))
}
""",
    ),
    "enum_match": Program(
        stdout="green\n",
        source="""\
io :: import "std/io"

Color :: enum {
    Red
    Green
    Blue
}

name :: fn(c: Color) string {
    match c {
        case Color.Red: ret "red"
        case Color.Green: ret "green"
        case Color.Blue: ret "blue"
    }
}

main :: fn() {
    io.println("{}", name(Color.Green))
}
""",
    ),
    "declared_generic_function": Program(
        stdout="42 hi\n",
        source="""\
io :: import "std/io"

identity($T) :: fn(x: $T) $T {
    ret x
}

main :: fn() {
    io.println("{} {}", identity(42), identity("hi"))
}
""",
    ),
    "declared_generic_with_constraint": Program(
        stdout="8\n",
        source="""\
io :: import "std/io"

larger($T: Numeric) :: fn(a: $T, b: $T) $T {
    ret if a < b { b } else { a }
}

main :: fn() {
    io.println("{}", larger(3, 8))
}
""",
    ),
    "generic_struct": Program(
        stdout="42\n",
        source="""\
io :: import "std/io"

Box :: struct {
    value: $T
}

main :: fn() {
    b := Box(i32){value: 42}
    io.println("{}", b.value)
}
""",
    ),
    "tagged_union_dot_arms": Program(
        stdout="ok 41\nerr 7\n",
        source="""\
io :: import "std/io"

Result :: union(tag) {
    ok: i32
    err: i32
}

show :: fn(r: Result) {
    match r {
        case .ok(v): {
            io.println("ok {}", v)
        }
        case .err(e): {
            io.println("err {}", e)
        }
    }
}

main :: fn() {
    show(Result{ok: 41})
    show(Result{err: 7})
}
""",
    ),
    "ref_param": Program(
        stdout="8\n",
        source="""\
io :: import "std/io"

bump :: fn(p: ref i32) {
    p += 1
}

main :: fn() {
    x: i32 = 7
    bump(x)
    io.println("{}", x)
}
""",
    ),
    "heap_struct_and_defer_del": Program(
        stdout="5\n",
        source="""\
io :: import "std/io"

Box :: struct {
    value: i32
}

main :: fn() {
    b := new Box
    if b == nil {
        ret
    }
    defer del b
    b.value = 5
    io.println("{}", b.value)
}
""",
    ),
    "defer_order": Program(
        stdout="first\nmiddle\nlast\n",
        source="""\
io :: import "std/io"

main :: fn() {
    defer io.println("last")
    defer io.println("middle")
    io.println("first")
}
""",
    ),
    "labeled_loops": Program(
        stdout="2\n",
        source="""\
io :: import "std/io"

main :: fn() {
    hits := 0
    @outer for i := 0; i < 3; i += 1 {
        for j := 0; j < 3; j += 1 {
            if j == 1 {
                continue outer
            }
            if i == 2 {
                break outer
            }
            hits += 1
        }
    }
    io.println("{}", hits)
}
""",
    ),
    "while_loop": Program(
        stdout="10\n",
        source="""\
io :: import "std/io"

main :: fn() {
    i := 0
    while i < 10 {
        i += 1
    }
    io.println("{}", i)
}
""",
    ),
    "array_for_in": Program(
        stdout="10\n",
        source="""\
io :: import "std/io"

main :: fn() {
    arr: [4]i32 = [1, 2, 3, 4]
    total := 0
    for x in arr {
        total += x
    }
    io.println("{}", total)
}
""",
    ),
    "slice_of_array": Program(
        stdout="50 3\n",
        source="""\
io :: import "std/io"

total :: fn(xs: []i32) i32 {
    sum := 0
    for x in xs {
        sum += x
    }
    ret sum
}

main :: fn() {
    arr: [4]i32 = [10, 20, 30, 40]
    io.println("{} {}", total(arr[1..3]), arr[1..4].len)
}
""",
    ),
    "slice_guarded_index": Program(
        stdout="8 -1\n",
        source="""\
io :: import "std/io"

at :: fn(xs: []i32, i: usize, fallback: i32) i32 {
    if i < xs.len {
        ret xs[i]
    }
    ret fallback
}

main :: fn() {
    arr: [3]i32 = [7, 8, 9]
    io.println("{} {}", at(arr[0..3], 1, -1), at(arr[0..3], 5, -1))
}
""",
    ),
    # Known violations of the boundary.
    "inline_generic": Program(
        stdout="42\n",
        source="""\
io :: import "std/io"

identity :: fn(x: $T) $T {
    ret x
}

main :: fn() {
    io.println("{}", identity(42))
}
""",
    ),
    "type_set_alias": Program(
        stdout="1\n",
        source="""\
io :: import "std/io"

IntOnly :: @type_set(i32, i64)

main :: fn() {
    io.println("{}", 1)
}
""",
    ),
    "string_equality": Program(
        stdout="same\n",
        source="""\
io :: import "std/io"

main :: fn() {
    s := "hi"
    if s == "hi" {
        io.println("same")
    }
}
""",
    ),
    "shift_by_runtime_amount": Program(
        stdout="8\n",
        source="""\
io :: import "std/io"

shifted :: fn(n: i32) i32 {
    x := 1 << n
    ret x
}

main :: fn() {
    io.println("{}", shifted(3))
}
""",
    ),
    "heap_scalar_write_through": Program(
        stdout="5\n",
        source="""\
io :: import "std/io"

main :: fn() {
    p := new i32
    if p == nil {
        ret
    }
    p = 5
    io.println("{}", p)
    del p
}
""",
        defect=(
            "no findings row: `p := new i32` then `p = 5` builds, but "
            "`io.println(\"{}\", p)` prints the address (`i32@...`), not 5; "
            "A7 has no way to read a scalar through a `ref`"
        ),
    ),
}


def semantic_stage(source: str, tmp_path):
    from a7.compile import A7Compiler

    path = tmp_path / "main.a7"
    path.write_text(source, encoding="utf-8")
    return A7Compiler(mode="semantic").compile_file_detailed(str(path))


@pytest.mark.parametrize("name", PROGRAMS)
def test_semantic_stage_accepts_the_program(name, tmp_path):
    # Without this a row could be rejected early and prove nothing about the
    # boundary; for a defect row the strict xfail below would hide that.
    result = semantic_stage(PROGRAMS[name].source, tmp_path)
    assert result.ok, f"exit {result.exit_code}: {failure_text(result)}"


@pytest.mark.parametrize("name", [
    pytest.param(name, marks=pytest.mark.xfail(strict=True, reason=program.defect))
    if program.defect else name
    for name, program in PROGRAMS.items()
])
def test_accepted_program_compiles_builds_and_runs(name, tmp_path, zig):
    program = PROGRAMS[name]
    process = build_and_run(program.source, tmp_path, zig)
    assert process.returncode == 0, process.stderr
    assert process.stdout == program.stdout
