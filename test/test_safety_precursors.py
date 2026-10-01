"""Safety-pass precursors (batch C4): SAF-25, SAF-24, SAF-20, SAF-21, SAF-22.

Every case runs the repository CLI on real A7 source. Rejected programs are
paired with an accepted twin; accepted twins are checked with
`zig build-obj -fno-emit-bin`, which type-checks the emitted Zig without
producing or running a binary. Only the file-scope constant case is run,
because its divisor is the literal constant 4.

Set A7_TEST_ZIG to a Zig 0.16.0 binary or put zig on PATH. A missing Zig fails
the Zig-dependent tests.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from a7.compile import ExitCode

ROOT = Path(__file__).resolve().parents[1]

DIVISOR_MESSAGE = "Divisor not proven non-zero"
INDEX_MESSAGE = "Index not proven in bounds"
SLICE_MESSAGE = "Slice bounds not proven"
NIL_MESSAGE = "Reference not proven non-nil"


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


def run_cli(tmp_path, source, name="main"):
    """Compile `source` with --format json; return (exit code, payload, zig path)."""
    src = tmp_path / f"{name}.a7"
    out = tmp_path / f"{name}.zig"
    src.write_text(source, encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    process = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(src), "--output", str(out), "--format", "json"],
        cwd=ROOT, capture_output=True, text=True, env=env,
    )
    payload = json.loads(process.stdout)
    return process.returncode, payload, out


def diagnostics(payload):
    return (payload.get("error") or {}).get("details") or []


def assert_rejected_at(payload, code, message, line):
    """Exactly one safety diagnostic with `message` at source line `line`."""
    assert code == ExitCode.SEMANTIC, payload
    details = diagnostics(payload)
    assert len(details) == 1, details
    assert message in details[0]["message"], details[0]
    assert "cast" not in details[0]["message"].lower(), details[0]
    assert details[0].get("span", {}).get("start_line") == line, details[0]


def zig_check(zig, zig_cache, output):
    process = subprocess.run(
        [zig, "build-obj", str(output), "-fno-emit-bin",
         "--cache-dir", str(zig_cache / "local"),
         "--global-cache-dir", str(zig_cache / "global")],
        capture_output=True, text=True,
    )
    assert process.returncode == 0, process.stdout + process.stderr


# SAF-25: a deferred statement runs at scope exit, so its assignment must not
# count as a fact at the defer site. Line 6 is the division in each program.
DEFERRED_ASSIGNMENTS = {
    "p18-defer-assign": '''io :: import "std/io"

main :: fn() {
    x := 0
    defer x = 5
    y := 10 / x
    io.println("{}", y)
}
''',
    "p32b-defer-compound-assign": '''io :: import "std/io"

main :: fn() {
    x := 0
    defer x += 5
    y := 10 / x
    io.println("{}", y)
}
''',
    "p32-defer-match-assign": '''io :: import "std/io"

main :: fn() {
    x := 0
    k := 1
    defer match k {
        case 1: x = 5
        else: x = 5
    }
    y := 10 / x
    io.println("{}", y)
}
''',
}
DEFERRED_DIVISION_LINE = {"p18-defer-assign": 6, "p32b-defer-compound-assign": 6, "p32-defer-match-assign": 10}


@pytest.mark.parametrize("name", sorted(DEFERRED_ASSIGNMENTS))
def test_deferred_assignment_does_not_prove_divisor(tmp_path, name):
    code, payload, _ = run_cli(tmp_path, DEFERRED_ASSIGNMENTS[name])
    assert_rejected_at(payload, code, DIVISOR_MESSAGE, DEFERRED_DIVISION_LINE[name])


def test_assignment_before_division_with_defer_is_accepted_and_zig_builds(tmp_path, zig, zig_cache):
    source = '''io :: import "std/io"

main :: fn() {
    x := 0
    defer {
        x = 5
    }
    x = 2
    y := 10 / x
    io.println("{}", y)
}
'''
    code, payload, output = run_cli(tmp_path, source)
    assert code == ExitCode.SUCCESS, diagnostics(payload)
    zig_check(zig, zig_cache, output)


# SAF-25, loop half: a deferred statement runs at the end of every iteration, so
# a fact it can destroy must not survive the defer site into the rest of the
# scope or into the next iteration.
def test_deferred_assignment_in_while_does_not_prove_later_divisor(tmp_path):
    source = '''io :: import "std/io"

main :: fn() {
    x := 5
    i := 0
    while i < 3 {
        defer x = 0
        y := 10 / x
        io.println("{}", y)
        i = i + 1
    }
}
'''
    code, payload, _ = run_cli(tmp_path, source)
    assert_rejected_at(payload, code, DIVISOR_MESSAGE, 8)


def test_deferred_assignment_in_for_in_does_not_prove_later_divisor(tmp_path):
    source = '''io :: import "std/io"

main :: fn() {
    x := 5
    arr: [3]i32 = [1, 2, 3]
    for v in arr {
        defer x = 0
        y := 10 / x
        io.println("{} {}", v, y)
    }
}
'''
    code, payload, _ = run_cli(tmp_path, source)
    assert_rejected_at(payload, code, DIVISOR_MESSAGE, 8)


def test_deferred_assignment_that_keeps_the_divisor_nonzero_stays_accepted(tmp_path):
    """Dropping the fact must not reject a division the guard re-proves.

    No `zig build-obj` here: an un-braced deferred assignment still lowers to
    `defer void;` (B11), which Zig rejects until batch Z4.
    """
    source = '''io :: import "std/io"

main :: fn() {
    x := 5
    i := 0
    while i < 3 {
        defer x = 5
        if x != 0 {
            y := 10 / x
            io.println("{}", y)
        }
        i = i + 1
    }
}
'''
    code, payload, _ = run_cli(tmp_path, source)
    assert code == ExitCode.SUCCESS, diagnostics(payload)


def test_assignment_after_defer_reproves_divisor_outside_a_loop(tmp_path):
    """Straight-line code: the assignment after the defer site re-proves `x`."""
    source = '''io :: import "std/io"

main :: fn() {
    x := 5
    defer x = 0
    x = 3
    y := 10 / x
    io.println("{}", y)
}
'''
    code, payload, _ = run_cli(tmp_path, source)
    assert code == ExitCode.SUCCESS, diagnostics(payload)


def test_braced_deferred_assignment_in_loop_rejects_stale_divisor(tmp_path):
    """The deferred zero runs before the next iteration; A7 must reject it."""
    source = '''io :: import "std/io"

main :: fn() {
    x := 5
    i := 0
    while i < 3 {
        defer {
            x = 0
        }
        y := 10 / x
        io.println("{}", y)
        i = i + 1
    }
}
'''
    code, payload, output = run_cli(tmp_path, source)
    assert code == ExitCode.SEMANTIC, payload
    assert DIVISOR_MESSAGE in str(diagnostics(payload))
    assert not output.exists()


# SAF-25, precision half: the drop applies to a bare identifier target only.
# Assigning through a field, index, slice or deref writes past the base and
# cannot invalidate a fact held about the base itself.
def test_deferred_field_assignment_keeps_the_base_non_nil_proof(tmp_path):
    """`defer box.value = 0` must not discard `box`'s non-nil proof.

    Compile-only: an un-braced deferred assignment still lowers to
    `defer void;` (B11), which Zig rejects until batch Z4, so there is no
    `zig build-obj` here and the program is never run.
    """
    source = '''io :: import "std/io"

Box :: struct {
    value: i32
}

main :: fn() {
    box := new Box
    if box == nil {
        ret
    }
    defer box.value = 0
    box.value = 7
    io.println("{}", box.value)
    del box
}
'''
    code, payload, _ = run_cli(tmp_path, source)
    assert code == ExitCode.SUCCESS, diagnostics(payload)


def test_deferred_identifier_assignment_still_drops_the_non_nil_proof(tmp_path):
    """Guard on the narrowing: `defer box = other` still invalidates `box`.

    The drop replaces `box`'s fact with an empty one; it does not copy the
    right-hand side's fact. So the `box.value` write on the next line of the
    loop body is no longer proven non-nil, even though `other` itself was
    proven non-nil above. Compile-only for the same `defer void;` reason.
    """
    source = '''io :: import "std/io"

Box :: struct {
    value: i32
}

main :: fn() {
    box := new Box
    other := new Box
    if box == nil {
        ret
    }
    if other == nil {
        ret
    }
    i := 0
    while i < 3 {
        defer box = other
        box.value = 7
        i = i + 1
    }
    del other
}
'''
    code, payload, _ = run_cli(tmp_path, source)
    assert_rejected_at(payload, code, NIL_MESSAGE, 19)


# SAF-24: the for-in value variable is a fresh binding; an outer variable of the
# same name must not lend it a fact.
def test_for_in_value_does_not_inherit_outer_fact(tmp_path):
    source = '''io :: import "std/io"

main :: fn() {
    v := 5
    arr: [3]i32 = [0, 0, 0]
    for v in arr {
        y := 10 / v
        io.println("{}", y)
    }
    io.println("{}", v)
}
'''
    code, payload, _ = run_cli(tmp_path, source)
    assert_rejected_at(payload, code, DIVISOR_MESSAGE, 7)


def test_for_in_value_with_guard_is_accepted_and_zig_builds(tmp_path, zig, zig_cache):
    source = '''io :: import "std/io"

main :: fn() {
    arr: [3]i32 = [0, 4, 0]
    for item in arr {
        if item != 0 {
            y := 10 / item
            io.println("{}", y)
        }
    }
}
'''
    code, payload, output = run_cli(tmp_path, source)
    assert code == ExitCode.SUCCESS, diagnostics(payload)
    zig_check(zig, zig_cache, output)


# SAF-20: nested function bodies are analyzed by the safety pass.
def test_nested_function_unproven_division_is_a_safety_error(tmp_path):
    source = '''io :: import "std/io"

main :: fn() {
    helper :: fn(a: i32, b: i32) i32 {
        ret a / b
    }
    io.println("hi")
}
'''
    code, payload, _ = run_cli(tmp_path, source)
    assert_rejected_at(payload, code, DIVISOR_MESSAGE, 5)


def test_nested_function_guarded_division_compiles_and_zig_builds(tmp_path, zig, zig_cache):
    source = '''io :: import "std/io"

main :: fn() {
    helper :: fn(a: i32, b: i32) i32 {
        if b != 0 {
            ret a / b
        }
        ret 0
    }
    io.println("hi")
}
'''
    code, payload, output = run_cli(tmp_path, source)
    assert code == ExitCode.SUCCESS, diagnostics(payload)
    assert "@divTrunc(a, b)" in output.read_text(encoding="utf-8")
    zig_check(zig, zig_cache, output)


# SAF-21: facts of file-scope `::` constants are available in every function;
# file-scope mutable variables give no fact.
def test_file_scope_constant_divisor_builds_and_prints_quotient(tmp_path, zig, zig_cache):
    source = '''io :: import "std/io"

N :: 4

main :: fn() {
    y := 10 / N
    io.println("{}", y)
}
'''
    code, payload, output = run_cli(tmp_path, source)
    assert code == ExitCode.SUCCESS, diagnostics(payload)
    for profile in ("Debug", "ReleaseFast"):
        binary = tmp_path / f"program-{profile}"
        build = subprocess.run(
            [zig, "build-exe", str(output), "-O", profile,
             "--cache-dir", str(zig_cache / "local"),
             "--global-cache-dir", str(zig_cache / "global"),
             "-femit-bin=" + str(binary)],
            capture_output=True, text=True,
        )
        assert build.returncode == 0, build.stdout + build.stderr
        run = subprocess.run([str(binary)], capture_output=True, text=True)
        assert run.returncode == 0, run.stdout + run.stderr
        assert (run.stdout + run.stderr).strip() == "2"


def test_file_scope_zero_constant_divisor_is_rejected(tmp_path):
    source = '''io :: import "std/io"

Z :: 0

main :: fn() {
    y := 10 / Z
    io.println("{}", y)
}
'''
    code, payload, _ = run_cli(tmp_path, source)
    assert_rejected_at(payload, code, DIVISOR_MESSAGE, 6)


def test_file_scope_mutable_variable_gives_no_divisor_fact(tmp_path):
    source = '''io :: import "std/io"

n := 4

main :: fn() {
    y := 10 / n
    io.println("{}", y)
}
'''
    code, payload, _ = run_cli(tmp_path, source)
    assert_rejected_at(payload, code, DIVISOR_MESSAGE, 6)


# SAF-22: each unproven obligation is reported under its own category, with a line.
OBLIGATION_DIAGNOSTICS = {
    "division": ('''io :: import "std/io"

quotient :: fn(a: i32, b: i32) i32 {
    ret a / b
}

main :: fn() {
    io.println("{}", quotient(10, 2))
}
''', DIVISOR_MESSAGE, 4),
    "index": ('''io :: import "std/io"

pick :: fn(a: [4]i32, i: usize) i32 {
    ret a[i]
}

main :: fn() {
    arr: [4]i32 = [1, 2, 3, 4]
    k: usize = 1
    io.println("{}", pick(arr, k))
}
''', INDEX_MESSAGE, 4),
    "slice": ('''io :: import "std/io"

main :: fn() {
    arr: [4]i32 = [1, 2, 3, 4]
    n: usize = 9
    part := arr[0..n]
    io.println("{}", part.len)
}
''', SLICE_MESSAGE, 6),
    "nil-dereference": ('''io :: import "std/io"

Inner :: struct {
    value: i32
}

Outer :: struct {
    link: ref Inner
}

main :: fn() {
    o := Outer{link: nil}
    x := o.link.value
    io.println("{}", x)
}
''', NIL_MESSAGE, 13),
}


@pytest.mark.parametrize("name", sorted(OBLIGATION_DIAGNOSTICS))
def test_unproven_obligation_json_diagnostic_has_category_and_line(tmp_path, name):
    source, message, line = OBLIGATION_DIAGNOSTICS[name]
    code, payload, _ = run_cli(tmp_path, source)
    assert_rejected_at(payload, code, message, line)


def test_returned_local_slice_is_accepted_and_zig_builds(tmp_path, zig, zig_cache):
    """S5: returning a slice of a local stack array is accepted (KNOWN)."""
    source = '''io :: import "std/io"
get :: fn() []i32 {
    buf: [4]i32 = [1, 2, 3, 4]
    ret buf[0..2]
}
main :: fn() {
    s := get()
    io.println("{}", s.len)
}
'''
    code, payload, output = run_cli(tmp_path, source)
    assert code == ExitCode.SUCCESS, diagnostics(payload)
    zig_check(zig, zig_cache, output)


def test_index_into_slice_parameter_is_rejected(tmp_path):
    """S5 pair: indexing a slice parameter is rejected without a guard."""
    source = '''io :: import "std/io"
first :: fn(xs: []i32) i32 {
    i: usize = 0
    ret xs[i]
}
main :: fn() {
    io.println("{}", 1)
}
'''
    code, payload, _ = run_cli(tmp_path, source)
    assert_rejected_at(payload, code, INDEX_MESSAGE, 4)


def test_index_use_inside_guard_condition_is_rejected(tmp_path):
    """Short-circuit: `i < xs.len` proves later statements, not the `and`
    right-hand side of its own condition. Both the in-condition use (line 3)
    and the unguarded body use (line 4) are rejected."""
    source = '''io :: import "std/io"
get :: fn(xs: []i32, i: usize) i32 {
    if i < xs.len and xs[i] > 0 {
        ret xs[i]
    }
    ret -1
}
main :: fn() {
    buf: [4]i32 = [1, 2, 3, 4]
    s := buf[0..4]
    io.println("{}", get(s, 2))
}
'''
    code, payload, _ = run_cli(tmp_path, source)
    assert code == ExitCode.SEMANTIC, payload
    details = diagnostics(payload)
    lines = sorted(
        d.get("span", {}).get("start_line")
        for d in details
        if INDEX_MESSAGE in d["message"]
    )
    assert lines == [3, 4], details
