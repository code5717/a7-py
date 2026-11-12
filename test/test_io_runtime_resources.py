"""Packaged I/O helpers preserve dependencies and appear only when used."""

from pathlib import Path

import pytest

from conftest import expect_ok


@pytest.mark.parametrize('body, present, absent', [
    ('', (), ('__a7_stdout_print', '__a7_stderr_print', '__a7_stdin_read_line', '__a7_IoResult')),
    ('io.print("x")', ('__a7_stdout_print',), ('__a7_stderr_print', '__a7_stdin_read_line', '__a7_IoResult')),
    ('io.println("x")', ('__a7_stdout_print',), ('__a7_stderr_print', '__a7_stdin_read_line', '__a7_IoResult')),
    ('io.eprintln("x")', ('__a7_stderr_print',), ('__a7_stdout_print', '__a7_stdout_flush', '__a7_stdin_read_line', '__a7_IoResult')),
    ('io.println_ok("x")', ('__a7_stdout_print_ok', '__a7_IoResult'), ('__a7_stderr_print', '__a7_stdin_read_line')),
    ('buf: [4]u8; io.read_line(buf[0..])', ('__a7_stdin_read_line', '__a7_IoResult'), ('__a7_stdout_print', '__a7_stdout_flush', '__a7_stderr_print')),
])
def test_io_runtime_inclusion(tmp_path, body, present, absent):
    result = expect_ok('io :: import "std/io"\nmain :: fn() { ' + body + ' }', tmp_path)
    emitted = Path(result.output_path).read_text()
    for name in present:
        assert name in emitted
    for name in absent:
        assert name not in emitted
    if '__a7_IoResult' in present:
        alias = emitted.index('const __a7_IoResult = ')
        helper = emitted.index('fn __a7_stdout_print_ok' if 'println_ok' in body else 'fn __a7_stdin_read_line')
        assert alias < helper


def test_combined_io_flushes_before_stderr_and_stdin(tmp_path):
    result = expect_ok('''io :: import "std/io"
main :: fn() {
    io.print("prompt")
    io.eprintln("error")
    buf: [4]u8
    io.read_line(buf[0..])
    io.println_ok("done")
}
''', tmp_path)
    emitted = Path(result.output_path).read_text()
    assert emitted.count('fn __a7_stdout_flush()') == 1
    assert emitted.index('fn __a7_stdout_flush()') < emitted.index('fn __a7_stderr_print(')
    stderr = emitted.split('fn __a7_stderr_print(', 1)[1].split('\n}', 1)[0]
    assert stderr.index('__a7_stdout_flush();') < stderr.index('std.Io.File.stderr()')
    stdin = emitted.split('fn __a7_stdin_read_line(', 1)[1].split('\n}', 1)[0]
    assert stdin.index('__a7_stdout_flush();') < stdin.index('takeByte()')
    assert emitted.count('var __a7_stdin_reader:') == 1
    assert 'error.EndOfStream => if (n == 0) return .{ .err = .EndOfStream } else break,' in stdin
    assert 'buf[n] = b;' in stdin
    checked_print = emitted.split('fn __a7_stdout_print_ok(', 1)[1].split('\n}', 1)[0]
    assert checked_print.index('interface.print(') < checked_print.index('interface.flush()')
    assert 'return .{ .err = .WriteFailed }' in checked_print
    assert 'return .{ .err = .FlushFailed }' in checked_print


def test_runtime_resources_resolve_from_package_with_unrelated_cwd(tmp_path, monkeypatch):
    # A same-shaped directory in the caller's cwd cannot replace package data.
    impostor = tmp_path / 'a7/stdlib/rt'
    impostor.mkdir(parents=True)
    (impostor / 'stdout.zig').write_text('wrong_runtime_resource\n')
    monkeypatch.chdir(tmp_path)
    result = expect_ok('io :: import "std/io"\nmain :: fn() { io.println("x") }', tmp_path)
    emitted = Path(result.output_path).read_text()
    assert 'wrong_runtime_resource' not in emitted
    assert 'fn __a7_stdout_print(comptime fmt: []const u8, args: anytype) void {' in emitted
    assert 'out.print(fmt, args) catch __a7_stdout_failed("write");' in emitted
    assert 'pub const panic = std.debug.FullPanic(__a7_panic);' in emitted
