"""Production A7 pipeline plus real Zig builds, with no mocked stages.

Set A7_TEST_ZIG to a Zig 0.16.0 binary or put zig on PATH. Missing tools fail
explicitly. Compile-only binding checks never execute a generated binary.
"""

import os
from pathlib import Path
import shutil
import subprocess

import pytest

from a7.compile import A7Compiler
from conftest import shared_zig_cache


@pytest.fixture(scope="module")
def zig():
    executable = os.environ.get("A7_TEST_ZIG") or shutil.which("zig")
    assert executable, "Zig 0.16.0 required: set A7_TEST_ZIG or PATH"
    version = subprocess.run([executable, "version"], capture_output=True, text=True)
    assert version.returncode == 0 and version.stdout.strip() == "0.16.0", version
    return executable


def emit(tmp_path, source):
    src = tmp_path / "main.a7"
    out = tmp_path / "main.zig"
    src.write_text(source, encoding="utf-8")
    result = A7Compiler().compile_file_detailed(str(src), str(out))
    assert result.ok, result.failure
    assert src.read_text(encoding="utf-8") == source
    return out


def build(zig, tmp_path, output, profile):
    binary = tmp_path / ("program-" + profile)
    process = subprocess.run(
        [zig, "build-exe", str(output), "-O", profile,
         "--cache-dir", str(tmp_path / "cache"),
         "--global-cache-dir", str(shared_zig_cache() / "global"),
         "-femit-bin=" + str(binary)],
        capture_output=True, text=True,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    return binary


@pytest.mark.parametrize("body", [
    'error := 1\n    io.println("{}", error)',
    'a: [3]i32\n    for x in a {}',
    'x := 9\n    a: [3]i32\n    for x in a { io.println("{}", x) }\n    io.println("{}", x)',
], ids=["zig-keyword-local", "unused-loop-capture", "shadowed-loop-capture"])
def test_valid_a7_bindings_build_with_zig(tmp_path, zig, body):
    output = emit(tmp_path, 'io :: import "std/io"\nmain :: fn() {\n    ' + body + '\n}\n')
    build(zig, tmp_path, output, "Debug")


def test_folded_and_runtime_integer_arithmetic_agree_across_profiles(tmp_path, zig):
    # Truncating division and remainder have independent answers -3 and -2.
    # A function parameter keeps the second expression out of A7 literal folding.
    output = emit(tmp_path, '''io :: import "std/io"
show :: fn(value: i32) {
    io.println("{} {}", value / 5, value % 5)
}
main :: fn() {
    io.println("{} {}", -17 / 5, -17 % 5)
    show(-17)
}
''')
    for profile in ("Debug", "ReleaseFast"):
        binary = build(zig, tmp_path, output, profile)
        process = subprocess.run([str(binary)], capture_output=True, text=True)
        assert process.returncode == 0, process.stderr
        assert process.stdout == "-3 -2\n-3 -2\n"
        assert process.stderr == ""


def test_large_integer_folding_preserves_exact_quotient_and_remainder(tmp_path, zig):
    # This fits in i64 but is not exactly representable in binary64.
    # Independently, division by one preserves n and remainder by one is zero.
    output = emit(tmp_path, '''io :: import "std/io"
show :: fn(value: i64) {
    io.println("{} {}", value / 1, value % 1)
}
main :: fn() {
    quotient: i64 = 9007199254740993 / 1
    remainder: i64 = 9007199254740993 % 1
    io.println("{} {}", quotient, remainder)
    show(9007199254740993)
}
''')
    observed = {}
    for profile in ("Debug", "ReleaseFast"):
        binary = build(zig, tmp_path, output, profile)
        process = subprocess.run([str(binary)], capture_output=True, text=True)
        observed[profile] = (process.returncode, process.stdout, process.stderr)
    expected = (0, "9007199254740993 0\n9007199254740993 0\n", "")
    assert observed == {"Debug": expected, "ReleaseFast": expected}


@pytest.mark.parametrize(('body', 'expected'), [
    ('''error := 9
    a: [2]i32 = [2, 3]
    for error in a { io.println("{}", error) }
    io.println("{}", error)''', '2\n3\n9\n'),
    ('''x := 9
    a: [1]i32 = [2]
    b: [1]i32 = [3]
    for x in a {
        for x in b { io.println("{}", x) }
        io.println("{}", x)
    }
    io.println("{}", x)''', '3\n2\n9\n'),
    ('''x := 9
    a: [1]i32 = [2]
    b: [1]i32 = [3]
    for x in a {
        for x in b { io.println("{}", x) }
    }
    io.println("{}", x)''', '3\n9\n'),
    ('''i: usize = 8
    x := 9
    a: [2]i32 = [2, 3]
    for i, x in a { io.println("{} {}", i, x) }
    for i, x in a { io.println("{}", x) }
    for i, x in a { io.println("{}", i) }
    for i, x in a {}
    io.println("{} {}", i, x)''', '0 2\n1 3\n2\n3\n0\n1\n8 9\n'),
    ('''x := 9
    a: [1]i32 = [2]
    for x in a {
        if true {
            x := 4
            io.println("{}", x)
        }
        io.println("{}", x)
    }
    io.println("{}", x)''', '4\n2\n9\n'),
], ids=['keyword-capture', 'nested-capture-restoration', 'unused-outer-capture',
        'indexed-capture-usage', 'local-shadows-capture'])
def test_native_loop_bindings_preserve_values(tmp_path, zig, body, expected):
    output = emit(tmp_path, 'io :: import "std/io"\nmain :: fn() {\n' + body + '\n}\n')
    binary = build(zig, tmp_path, output, 'Debug')
    process = subprocess.run([str(binary)], capture_output=True, text=True)
    assert (process.returncode, process.stdout, process.stderr) == (0, expected, '')
