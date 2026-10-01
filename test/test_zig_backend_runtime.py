"""Runtime behavior of Zig backend output: real CLI, real Zig builds, real runs.

Each case compiles A7 source through the repository CLI wrapper, builds the
emitted Zig in Debug and ReleaseFast, runs the binary, and compares output with
values derived by hand from the A7 source. Nothing is mocked. The programs use
no heap, references, division, indexing, or overflow-prone arithmetic.

Set A7_TEST_ZIG to a Zig 0.16.0 binary or put zig on PATH. A missing Zig fails
the tests.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ("Debug", "ReleaseFast")


@pytest.fixture(scope="module")
def zig():
    executable = os.environ.get("A7_TEST_ZIG") or shutil.which("zig")
    assert executable, "Zig 0.16.0 required: set A7_TEST_ZIG or PATH"
    version = subprocess.run([executable, "version"], capture_output=True, text=True)
    assert version.returncode == 0 and version.stdout.strip() == "0.16.0", version
    return executable


@pytest.fixture(scope="module")
def zig_cache(tmp_path_factory):
    return tmp_path_factory.mktemp("zig-cache")


def compile_with_cli(tmp_path, source):
    src = tmp_path / "main.a7"
    out = tmp_path / "main.zig"
    src.write_text(source, encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    process = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(src), "--output", str(out)],
        cwd=ROOT, capture_output=True, text=True, env=env,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    return out


def build(zig, zig_cache, tmp_path, output, profile):
    binary = tmp_path / ("program-" + profile)
    process = subprocess.run(
        [zig, "build-exe", str(output), "-O", profile,
         "--cache-dir", str(zig_cache / "local"),
         "--global-cache-dir", str(zig_cache / "global"),
         "-femit-bin=" + str(binary)],
        capture_output=True, text=True,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    return binary


def run_piped(binary):
    process = subprocess.run([str(binary)], capture_output=True, text=True)
    assert process.returncode == 0, process.stdout + process.stderr
    return process.stdout, process.stderr


IF_EXPR_OPERAND_CASES = {
    # pick: (if c {a} else {b}) + 10 -> 1+10=11, 2+10=12.
    # scale: (if c {a} else {b}) * 3 -> 1*3=3, 2*3=6.
    "add-and-mul-operand": ('''io :: import "std/io"

pick :: fn(c: bool, a: i32, b: i32) i32 {
    ret (if c { a } else { b }) + 10
}
scale :: fn(c: bool, a: i32, b: i32) i32 {
    ret (if c { a } else { b }) * 3
}
main :: fn() {
    io.println("{} {}", pick(true, 1, 2), pick(false, 1, 2))
    io.println("{} {}", scale(true, 1, 2), scale(false, 1, 2))
}
''', "11 12\n3 6\n"),
    # check selects a (c true) or b (c false), then compares with false:
    # (t,t,t) a=true -> false; (t,f,t) a=false -> true;
    # (f,t,f) b=false -> true; (f,t,t) b=true -> false.
    "bool-equality-operand": ('''io :: import "std/io"

check :: fn(c: bool, a: bool, b: bool) bool {
    ret (if c { a } else { b }) == false
}
main :: fn() {
    io.println("{} {} {} {}", check(true, true, true), check(true, false, true), check(false, true, false), check(false, true, true))
}
''', "false true true false\n"),
    # c is true, so the if-expression selects p and .x reads p.x = 1.
    "field-access-operand": ('''io :: import "std/io"
Pt :: struct {
    x: i32
    y: i32
}
main :: fn() {
    c := true
    p := Pt{x: 1, y: 2}
    q := Pt{x: 3, y: 4}
    v := (if c { p } else { q }).x
    io.println("{}", v)
}
''', "1\n"),
    # Counterexamples: forms that already produced correct output keep it.
    # u = 5; w = 6 * 2 = 12 (whole product parenthesized in source);
    # r = 10 + 6 = 16 (if-expression as right operand); s = 1 (plain
    # initializer). Branch values are typed locals so Zig sees runtime values.
    "already-parenthesized-and-plain": ('''io :: import "std/io"

pick :: fn(c: bool, a: i32, b: i32) i32 {
    ret (if c { a } else { b })
}
main :: fn() {
    one: i32 = 1
    two: i32 = 2
    six: i32 = 6
    seven: i32 = 7
    u := pick(true, 5, 6)
    w := ((if u == 4 { u } else { six }) * 2)
    r := 10 + (if u == 5 { six } else { seven })
    s := if u == 5 { one } else { two }
    io.println("{} {} {} {}", u, w, r, s)
}
''', "5 12 16 1\n"),
}


@pytest.mark.parametrize("case", sorted(IF_EXPR_OPERAND_CASES))
def test_if_expression_used_as_operand_selects_before_operator(tmp_path, zig, zig_cache, case):
    source, expected = IF_EXPR_OPERAND_CASES[case]
    output = compile_with_cli(tmp_path, source)
    for profile in PROFILES:
        stdout, stderr = run_piped(build(zig, zig_cache, tmp_path, output, profile))
        assert (profile, stdout) == (profile, expected)
        assert stderr == ""


PRINT_PROGRAM = '''io :: import "std/io"
main :: fn() {
    io.println("line one {}", 1)
    io.eprintln("err one")
    io.println("line two {}", 2)
    io.eprintln("err two")
    io.println("line three {}", 3)
}
'''
PRINT_STDOUT = "line one 1\nline two 2\nline three 3\n"
PRINT_STDERR = "err one\nerr two\n"


def test_prints_to_regular_files_keep_every_line(tmp_path, zig, zig_cache):
    # Two eprintln calls are needed: with a single call, a writer that restarts
    # at offset 0 would still leave the only stderr line intact.
    output = compile_with_cli(tmp_path, PRINT_PROGRAM)
    for profile in PROFILES:
        binary = build(zig, zig_cache, tmp_path, output, profile)
        out_path = tmp_path / (profile + ".stdout.txt")
        err_path = tmp_path / (profile + ".stderr.txt")
        with out_path.open("wb") as out_file, err_path.open("wb") as err_file:
            process = subprocess.run([str(binary)], stdout=out_file, stderr=err_file)
        assert process.returncode == 0
        assert (profile, out_path.read_text()) == (profile, PRINT_STDOUT)
        assert (profile, err_path.read_text()) == (profile, PRINT_STDERR)

        stdout, stderr = run_piped(binary)
        assert (profile, stdout, stderr) == (profile, PRINT_STDOUT, PRINT_STDERR)


STRUCT_ORDER_CASES = {
    # SPEC A.1 item 4: field initializers run in declaration order (x, y),
    # whatever order the literal names them in. Positional inits are already
    # in declaration order.
    "named-out-of-order": ('''io :: import "std/io"

Pt :: struct {
    x: i32
    y: i32
}
tag :: fn(t: i32) i32 {
    io.println("eval {}", t)
    ret t
}
main :: fn() {
    a := Pt{y: tag(2), x: tag(1)}
    io.println("a {} {}", a.x, a.y)
    b := Pt{tag(3), tag(4)}
    io.println("b {} {}", b.x, b.y)
}
''', "eval 1\neval 2\na 1 2\neval 3\neval 4\nb 3 4\n"),
    # Counterexample: a literal already in declaration order is unchanged.
    # Three fields so an accidental reversal or rotation would show.
    "named-in-declaration-order": ('''io :: import "std/io"

Tri :: struct {
    x: i32
    y: i32
    z: i32
}
tag :: fn(t: i32) i32 {
    io.println("eval {}", t)
    ret t
}
main :: fn() {
    t := Tri{x: tag(7), y: tag(8), z: tag(9)}
    io.println("t {} {} {}", t.x, t.y, t.z)
}
''', "eval 7\neval 8\neval 9\nt 7 8 9\n"),
}


@pytest.mark.parametrize("case", sorted(STRUCT_ORDER_CASES))
def test_struct_literal_fields_evaluate_in_declaration_order(tmp_path, zig, zig_cache, case):
    source, expected = STRUCT_ORDER_CASES[case]
    output = compile_with_cli(tmp_path, source)
    for profile in PROFILES:
        stdout, stderr = run_piped(build(zig, zig_cache, tmp_path, output, profile))
        assert (profile, stdout) == (profile, expected)
        assert stderr == ""


def test_isize_signed_offset_arithmetic_runs_both_profiles(tmp_path, zig, zig_cache):
    # SPEC 3.2: isize is the signed pointer-sized type. 4 - 10 goes
    # negative, which an unsigned index type would wrap; both results are
    # derived by hand: 10 - 4 + 2 = 8, 4 - 10 = -6.
    source = '''io :: import "std/io"
main :: fn() {
    off: isize = 10
    off = off - 4
    off = off + 2
    neg := 4 - 10
    same: isize = neg
    io.println("{} {}", off, same)
}
'''
    output = compile_with_cli(tmp_path, source)
    assert "isize" in output.read_text(encoding="utf-8")
    for profile in PROFILES:
        stdout, stderr = run_piped(build(zig, zig_cache, tmp_path, output, profile))
        assert (profile, stdout) == (profile, "8 -6\n")
        assert stderr == ""


def test_float_widths_lower_distinctly_and_run(tmp_path, zig, zig_cache):
    # f32 and f64 are distinct types with distinct Zig spellings; assigning
    # across widths without a cast is rejected (see test_feature_pins.py).
    source = '''io :: import "std/io"
main :: fn() {
    a: f32 = 1.5
    b: f64 = 2.5
    io.println("{} {}", a, b)
}
'''
    output = compile_with_cli(tmp_path, source)
    emitted = output.read_text(encoding="utf-8")
    assert "const a: f32 = 1.5;" in emitted
    assert "const b: f64 = 2.5;" in emitted
    for profile in PROFILES:
        stdout, stderr = run_piped(build(zig, zig_cache, tmp_path, output, profile))
        assert (profile, stdout) == (profile, "1.5 2.5\n")
        assert stderr == ""


def test_signed_divmod_assign_matches_truncating_division(tmp_path, zig, zig_cache):
    # B13: signed /= and %= lower to the same @divTrunc/@rem the / and %
    # operators already emit. Hand-derived: -7 / 2 truncates to -3,
    # -7 % 2 is -7 - (-3 * 2) = -1.
    source = '''io :: import "std/io"
main :: fn() {
    x: i32 = -7
    x /= 2
    y: i32 = -7
    y %= 2
    io.println("{} {}", x, y)
}
'''
    output = compile_with_cli(tmp_path, source)
    emitted = output.read_text(encoding="utf-8")
    assert "@divTrunc(" in emitted
    assert "@rem(" in emitted
    for profile in PROFILES:
        stdout, stderr = run_piped(build(zig, zig_cache, tmp_path, output, profile))
        assert (profile, stdout) == (profile, "-3 -1\n")
        assert stderr == ""


def test_slice_len_guard_with_nested_bounds_runs(tmp_path, zig, zig_cache):
    # An `i < xs.len` guard proves the index for nested uses: get(s, 2)
    # returns xs[2] = 3, get(s, 9) falls through to -1.
    source = '''io :: import "std/io"
get :: fn(xs: []i32, i: usize) i32 {
    if i < xs.len {
        if xs[i] > 0 {
            ret xs[i]
        }
    }
    ret -1
}
main :: fn() {
    buf: [4]i32 = [1, 2, 3, 4]
    s := buf[0..4]
    io.println("{} {}", get(s, 2), get(s, 9))
}
'''
    output = compile_with_cli(tmp_path, source)
    for profile in PROFILES:
        stdout, stderr = run_piped(build(zig, zig_cache, tmp_path, output, profile))
        assert (profile, stdout) == (profile, "3 -1\n")
        assert stderr == ""


def test_for_in_loop_runs_over_array(tmp_path, zig, zig_cache):
    # The for-in counterpart to indexed access: no bounds proof is needed
    # because no index expression appears.
    source = '''io :: import "std/io"
main :: fn() {
    xs: [3]i32 = [1, 2, 3]
    for x in xs {
        io.println("{}", x)
    }
}
'''
    output = compile_with_cli(tmp_path, source)
    for profile in PROFILES:
        stdout, stderr = run_piped(build(zig, zig_cache, tmp_path, output, profile))
        assert (profile, stdout) == (profile, "1\n2\n3\n")
        assert stderr == ""


def test_generic_struct_nesting_runs(tmp_path, zig, zig_cache):
    # Generic structs monomorphize per instantiation: Box(Box(i32))
    # unwraps twice to 5, and Pair carries the unwrapped value with "ok".
    source = '''io :: import "std/io"
Box :: struct {
    value: $T
}
Pair :: struct {
    first: $A
    second: $B
}
main :: fn() {
    nested: Box(Box(i32)) = Box(Box(i32)){value: Box(i32){value: 5}}
    p: Pair(i32, string) = Pair(i32, string){first: nested.value.value, second: "ok"}
    io.println("{} {}", nested.value.value, p.first)
    io.println("{}", p.second)
}
'''
    output = compile_with_cli(tmp_path, source)
    for profile in PROFILES:
        stdout, stderr = run_piped(build(zig, zig_cache, tmp_path, output, profile))
        assert (profile, stdout) == (profile, "5 5\nok\n")
        assert stderr == ""


def test_proven_narrowing_cast_runs(tmp_path, zig, zig_cache):
    # The 0 <= n <= 255 guard proves the cast(u8, n) narrowing; 200 fits
    # in u8 unchanged.
    source = '''io :: import "std/io"
main :: fn() {
    n: i32 = 200
    if n >= 0 {
        if n <= 255 {
            v := cast(u8, n)
            io.println("{}", v)
        }
    }
}
'''
    output = compile_with_cli(tmp_path, source)
    for profile in PROFILES:
        stdout, stderr = run_piped(build(zig, zig_cache, tmp_path, output, profile))
        assert (profile, stdout) == (profile, "200\n")
        assert stderr == ""
