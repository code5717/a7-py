"""Pins for the codegen emission rules E1-E4 (delivery roadmap §E, ledger L60).

String snapshots state which lowering the backend picks. Every snapshot has a
test beside it that builds the program with `zig build-exe` and runs it,
because `zig ast-check` accepts Zig that the build rejects.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from conftest import build_and_run, expect_ok, run_both_profiles  # noqa: E402
from test_codegen_zig import compile_a7_to_zig  # noqa: E402


# --------------------------------------------------------------------------
# E1: cosmetic emission (zero behavior change)
# --------------------------------------------------------------------------

E1_SOURCE = """
main :: fn() {
    x: i32 = 3
    if x == 1 {
        x = 2
    } else {
        x = 4
    }
    while x < 10 {
        x = x + 1
    }
    y: i32 = (x + 1) + 2
    z: i32 = (x + 1) * (x + 2)
}
"""


def test_e1_parens_and_blank_lines():
    zig = compile_a7_to_zig(E1_SOURCE)
    # A condition keeps one pair of parentheses.
    assert "if (x == 1)" in zig
    assert "while (x < 10)" in zig
    # A same-operator left chain drops the inner pair.
    assert "(x +% 1 +% 2)" in zig
    # `(x + 1) * (x + 2)`: the ADD groups differ from MUL, so they stay.
    assert "((x +% 1) *% (x +% 2))" in zig
    # No blank line where a used declaration's discard was removed.
    assert "var x: i32 = 3;\n    if (x == 1)" in zig


def test_e1_return_value_keeps_parens():
    zig = compile_a7_to_zig("double :: fn(x: i32) i32 {\n    ret x * 2\n}\n")
    assert "return (x *% 2)" in zig


E1_PARENS = """io :: import "std/io"
main :: fn() {
    a: i32 = 6
    b: i32 = 3
    c: i32 = 1
    f: bool = false
    u: u32 = 5
    if (a & b) == 2 { io.println("B1") } else { io.println("B0") }
    if (a | b ^ c & 4) == 7 { io.println("C1") } else { io.println("C0") }
    if (a & b & 2 | 1 | 4 ^ 1 ^ 2) == 5 { io.println("C2 1") } else { io.println("C2 0") }
    if !f and a - b - c == 2 or f == true { io.println("D1") } else { io.println("D0") }
    if a - (b - c) == 4 { io.println("E1") } else { io.println("E0") }
    if u << 2 >> 1 == 10 { io.println("F1") } else { io.println("F0") }
    if -a + b * c * 2 + a == 6 { io.println("G1") } else { io.println("G0") }
    if a + (b + c) + a == 16 and (a == 6) == true { io.println("H1") } else { io.println("H0") }
    if a / b / c == 2 and a % 4 % 3 == 2 { io.println("I1") } else { io.println("I0") }
    x := if (a < b) == f { 1 } else { 2 }
    y := 1.5 + 2.5 + (3.0 + 4.0)
    while a > b and b > c or f == true { a -= 1 }
    io.println("{} {} {}", x, y, a)
    if cast(i32, u) + a + b == 11 { io.println("J1") } else { io.println("J0") }
    if (~a & 7) == 1 { io.println("K1") } else { io.println("K0") }
    if (a + b) * (c + a) == 24 { io.println("L1") } else { io.println("L0") }
    if !(a == b) { io.println("M1") } else { io.println("M0") }
    if (a < b) != (b < c) { io.println("N1") } else { io.println("N0") }
    if (a + b) > 1 and (b + c) > (a + c) { io.println("O1") } else { io.println("O0") }
}
"""


def test_e1_paren_removal_keeps_evaluation_order(tmp_path, zig):
    """16 mixed-operator conditions; the expected lines are what HEAD printed
    before any parentheses were removed."""
    out = run_both_profiles(E1_PARENS, tmp_path, zig)
    assert out.splitlines() == [
        "B1", "C1", "C2 0", "D1", "E1", "F1", "G1", "H1", "I1",
        "1 11 3",
        "J1", "K0", "L1", "M0", "N0", "O0",
    ]


# --------------------------------------------------------------------------
# E2: io boilerplate elision (verified pre-existing; pins only)
# --------------------------------------------------------------------------

E2_QUIET = """
main :: fn() {
    x: i32 = 40
    y: i32 = x + 2
}
"""

E2_LOUD = """io :: import "std/io"
main :: fn() {
    io.println("hi")
}
"""

E2_STDERR_ONLY = """io :: import "std/io"
main :: fn() {
    io.eprintln("oops")
}
"""


def test_e2_quiet_program_has_no_io_header():
    zig = compile_a7_to_zig(E2_QUIET)
    assert "__a7_io" not in zig
    assert "__a7_stdout_writer" not in zig
    assert "const std = " not in zig
    assert "pub fn main() void" in zig


def test_e2_print_program_keeps_io_header():
    zig = compile_a7_to_zig(E2_LOUD)
    assert "var __a7_io: ?std.Io = null;" in zig
    assert "var __a7_stdout_writer: ?std.Io.File.Writer = null;" in zig
    assert "fn __a7_user_main() void" in zig


def test_e2_stderr_only_skips_stdout_state():
    zig = compile_a7_to_zig(E2_STDERR_ONLY)
    assert "fn __a7_stderr_print(" in zig
    assert "__a7_stdout_buf" not in zig


def test_e2_quiet_program_builds_and_prints_nothing(tmp_path, zig):
    process = build_and_run(E2_QUIET, tmp_path, zig)
    assert (process.returncode, process.stdout) == (0, "")


# --------------------------------------------------------------------------
# E3: `ref` parameters lower to `?*T` (ledger L60 reverted the `*T` lowering)
# --------------------------------------------------------------------------

E3_PARAM = """Counter :: struct { n: i32 }
inc :: fn(c: ref Counter) {
    c.n = c.n + 1
}
touch :: fn(p: ref i32) {
    p += 1
}
wrap :: fn(r: ref i32) {
    touch(r)
}
"""

E3_HEAP = """Box :: struct { value: i32 }
setv :: fn(b: ref Box, v: i32) {
    b.value = v
}
main :: fn() {
    value_box := new Box
    if value_box == nil {
        ret
    }
    setv(value_box, 42)
}
"""


def test_e3_ref_param_is_optional_pointer_unwrapped_per_use():
    zig = compile_a7_to_zig(E3_PARAM)
    assert "fn inc(c: ?*Counter) void" in zig
    assert "fn touch(p: ?*i32) void" in zig
    assert "c.?.n = (c.?.n +% 1);" in zig
    assert "p.?.* +%= 1;" in zig
    # A `ref` value passes through a call unchanged: no boundary unwrap.
    assert "touch(r);" in zig
    assert "setv(value_box, 42);" in compile_a7_to_zig(E3_HEAP)


def test_e3_ref_params_mutate_the_caller_value(tmp_path, zig):
    out = run_both_profiles(
        E3_PARAM + 'io :: import "std/io"\nmain :: fn() {\n'
        "    c: Counter = Counter{ n: 40 }\n    inc(c)\n"
        "    x: i32 = 20\n    touch(x)\n    wrap(x)\n"
        '    io.println("n={} x={}", c.n, x)\n}\n',
        tmp_path, zig,
    )
    assert out == "n=41 x=22\n"


E3_NIL_CHECK = """io :: import "std/io"
Node :: struct {
    v: i32
}
show :: fn(p: ref Node) {
    if p != nil {
        io.println("v={}", p.v)
    } else {
        io.println("nil")
    }
}
main :: fn() {
    n := Node{v: 3}
    show(n)
    show(nil)
}
"""

E3_FN_POINTER = """io :: import "std/io"
inc :: fn(p: ref i32) {
    p += 1
}
main :: fn() {
    f: fn(ref i32) = inc
    x: i32 = 1
    f(x)
    io.println("{}", x)
}
"""

E3_DEFER_DEL = """io :: import "std/io"
Box :: struct { value: i32 }
free_it :: fn(b: ref Box) {
    defer del b
    io.println("{}", b.value)
}
main :: fn() {
    q := new Box
    if q == nil { ret }
    q.value = 4
    free_it(q)
}
"""


@pytest.mark.parametrize("source, expected", [
    # `if p != nil` on a `ref` parameter, reached with a value and with `nil`.
    (E3_NIL_CHECK, "v=3\nnil\n"),
    # A function-pointer type with a `ref` parameter accepts the function.
    (E3_FN_POINTER, "2\n"),
    # `defer del` on a `ref` parameter.
    (E3_DEFER_DEL, "4\n"),
], ids=["nil-check-and-nil-argument", "fn-pointer", "defer-del"])
def test_e3_ref_param_shapes_run(tmp_path, zig, source, expected):
    """Each shape failed `zig build-exe` under the `*T` lowering."""
    assert run_both_profiles(source, tmp_path, zig) == expected


# --------------------------------------------------------------------------
# E4: native Zig `switch` only for an integer, char, bool or enum scrutinee
# whose arm values are all comptime-known (ledger L60). Every other match
# keeps the if-chain.
# --------------------------------------------------------------------------

E4_NOELSE = """ONE :: 4
main :: fn() {
    day: i32 = 3
    match day {
        case 1: {
        }
        case 2, 3: {
        }
        case ONE: {
        }
    }
}
"""


def test_e4_integer_equality_without_else_uses_switch():
    zig = compile_a7_to_zig(E4_NOELSE)
    assert "switch (day)" in zig
    assert "__a7_match" not in zig
    assert "2, 3 =>" in zig
    # `ONE :: 4` is folded before codegen.
    assert "4 =>" in zig
    # A statement match may handle no arm; Zig needs the switch exhaustive.
    assert "else => {}," in zig


E4_MATCH_HEAD = """
main :: fn() {
    x: i32 = 1
    match x {
"""

E4_IF_CHAIN_ARMS = {
    "ranges-without-else": "case 1..5: {\n}\ncase 6..10: {\n}",
    "capture": "case 1: {\n}\ncase v: {\n}",
}


@pytest.mark.parametrize("arms", E4_IF_CHAIN_ARMS.values(), ids=E4_IF_CHAIN_ARMS.keys())
def test_e4_integer_match_shapes_that_stay_on_if_chain(arms):
    zig = compile_a7_to_zig(E4_MATCH_HEAD + arms + "\n    }\n}\n")
    assert "switch" not in zig
    assert "const __a7_match_1 = x;" in zig


def test_e4_fallthrough_keeps_flag_machine():
    zig = compile_a7_to_zig(E4_MATCH_HEAD + "case 1: {\nfall\n}\ncase 2: {\n}\n    }\n}\n")
    assert "switch" not in zig
    assert "__a7_match_done" in zig


E4_FLOAT = """io :: import "std/io"
main :: fn() {
    x: f64 = 1.5
    match x {
        case 1.5: { io.println("one-half") }
        case 2.5: { io.println("two-half") }
    }
    match x {
        case 2.5: { io.println("two-half") }
        else: { io.println("other") }
    }
    n := match x {
        case 1.5: 15
        else: 0
    }
    io.println("{}", n)
}
"""

E4_RUNTIME_ARM = """io :: import "std/io"
LIMIT :: 9
check :: fn(x: i32, want: i32) {
    match x {
        case want: { io.println("hit") }
        case 0: { io.println("zero") }
    }
}
classify :: fn(x: i32, want: i32) i32 {
    ret match x {
        case want: 1
        case LIMIT: 2
        else: 0
    }
}
in_range :: fn(x: i32, lo: i32, hi: i32) bool {
    match x {
        case lo..hi: { ret true }
        else: { ret false }
    }
}
main :: fn() {
    check(5, 5)
    check(0, 5)
    io.println("{} {} {}", classify(5, 5), classify(9, 5), classify(3, 5))
    io.println("{} {}", in_range(5, 1, 9), in_range(50, 1, 9))
}
"""


@pytest.mark.parametrize("source, expected", [
    # Zig has no switch on a float.
    (E4_FLOAT, "one-half\nother\n15\n"),
    # `case want:` and `case lo..hi:` name parameters; a Zig prong needs a
    # comptime value. `want`, `lo` and `hi` are read by the pattern alone.
    (E4_RUNTIME_ARM, "hit\nzero\n1 2 0\ntrue false\n"),
], ids=["float-scrutinee", "runtime-arm"])
def test_e4_match_outside_the_switch_rule_runs_as_if_chain(tmp_path, zig, source, expected):
    """Statement and expression matches, with and without `else`."""
    result = expect_ok(source, tmp_path)
    assert "switch" not in Path(result.output_path).read_text()
    assert run_both_profiles(source, tmp_path, zig) == expected


def test_e4_string_scrutinee_stays_on_if_chain():
    """The if-chain compares strings with `==`, which Zig rejects, so this
    program does not build yet (it did not build before the switch lowering
    either). The pin is only that a string match never selects `switch`."""
    zig = compile_a7_to_zig(
        'main :: fn() {\n    s := "b"\n    match s {\n'
        '        case "a": {\n        }\n        case "b": {\n        }\n    }\n}\n'
    )
    assert "switch" not in zig
    assert "__a7_match" in zig


E4_COLOR = "Color :: enum { Red, Green, Blue }\n"

E4_CLOSED = {
    # name: (declaration, scrutinee, arms)
    "enum": (E4_COLOR, "Color.Green", ["Color.Red", "Color.Green", "Color.Blue"]),
    "bool": ("", "true", ["true", "false"]),
}


@pytest.mark.parametrize("decl, scrutinee, arms", E4_CLOSED.values(), ids=E4_CLOSED.keys())
def test_e4_full_coverage_switch_has_no_else_prong(decl, scrutinee, arms):
    """Zig rejects an `else` prong once every enum or bool value has a prong.

    A match that misses a value never reaches codegen: the validator rejects
    it as non-exhaustive.
    """
    cases = "".join(f"        case {arm}: {{\n        }}\n" for arm in arms)
    zig = compile_a7_to_zig(
        f"{decl}main :: fn() {{\n    v := {scrutinee}\n    match v {{\n{cases}    }}\n}}\n"
    )
    assert "switch (v)" in zig
    assert "else =>" not in zig


E4_SWITCH_TYPES = """io :: import "std/io"
Color :: enum { Red, Green, Blue }
G :: Color.Green
pick :: fn(n: i32) i32 {
    match n {
        case 1: { ret 10 }
        case 2: { ret 20 }
    }
    ret 0
}
main :: fn() {
    x: u8 = 200
    y: i64 = 5000000000
    b := true
    c := Color.Green
    ch: char = 'q'
    match x {
        case 200: { io.println("u8 ok") }
        case 7: { io.println("never") }
    }
    match y {
        case 5000000000: { io.println("i64 ok") }
    }
    match b {
        case true: { io.println("t") }
        case false: { io.println("f") }
    }
    match c {
        case Color.Red: { io.println("red") }
        case Color.Green: { io.println("green") }
        case Color.Blue: { io.println("blue") }
    }
    match c {
        case G: { io.println("const green") }
        else: { io.println("other") }
    }
    match ch {
        case 'q': { io.println("q") }
    }
    match x + 1 {
        case 201: io.println("201")
    }
    match y {
        case 1..5: { io.println("low") }
        else: { io.println("high") }
    }
    io.println("{} {}", pick(2), pick(5))
}
"""


def test_e4_switch_runs_for_every_qualifying_scrutinee_type(tmp_path, zig):
    """u8, i64, bool, enum, char, an expression scrutinee, a top-level `::`
    constant arm, and a range beside `else`: all take the switch."""
    result = expect_ok(E4_SWITCH_TYPES, tmp_path)
    emitted = Path(result.output_path).read_text()
    assert emitted.count("switch (") == 9
    assert "__a7_match" not in emitted
    out = run_both_profiles(E4_SWITCH_TYPES, tmp_path, zig)
    assert out.splitlines() == [
        "u8 ok", "i64 ok", "t", "green", "const green", "q", "201", "high", "20 0",
    ]
