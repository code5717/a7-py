"""Stdout contract of generated programs (L48 "C-like buffered").

Text printed before a panic is not lost, a terminal sees each finished line
at once, and a reader that closes the pipe ends the program quietly.
"""

import os
import pty
import select
import subprocess
import time
from pathlib import Path

import pytest

from native_profiles import PROFILES, build_binary, no_core_dump, run_profile
from conftest import expect_ok


def read_line(fd, timeout=60):
    deadline = time.monotonic() + timeout
    os.set_blocking(fd, False)
    line = b""
    while not line.endswith(b"\n"):
        remaining = deadline - time.monotonic()
        assert remaining > 0, f"line timed out after {timeout} s: {line!r}"
        readable, _, _ = select.select([fd], [], [], remaining)
        assert readable, f"line timed out after {timeout} s: {line!r}"
        chunk = os.read(fd, 1)
        assert chunk, f"EOF before newline: {line!r}"
        line += chunk
    return line


def test_partial_pipe_line_has_a_read_deadline():
    reader, writer = os.pipe()
    try:
        os.write(writer, b"unfinished")
        with pytest.raises(AssertionError, match="line timed out"):
            read_line(reader, timeout=0.05)
    finally:
        os.close(reader)
        os.close(writer)


@pytest.mark.parametrize("profile", PROFILES)
def test_text_printed_before_a_panic_reaches_stdout(tmp_path, zig, profile):
    # The overshift panic is the one runtime panic a checked program can
    # still reach in all three profiles.
    source = """
io :: import "std/io"
shift :: fn(a: i32, n: i32) i32 { ret a << n }
main :: fn() {
    io.println("first line")
    io.print("no newline yet")
    io.println("{}", shift(1, 40))
}
"""
    process = run_profile(source, tmp_path, zig, profile)
    assert process.returncode == -6, process.stderr
    assert process.stdout == "first line\nno newline yet"
    assert "panic: shift count out of range" in process.stderr


def test_terminal_shows_a_line_before_the_program_continues(tmp_path, zig, zig_cache):
    # The test replaces only the empty input barrier with a raw Zig read.
    # It cannot flush stdout, so observing ready before sending input proves
    # the generated println flushes the terminal at the newline.
    source = """
io :: import "std/io"
wait_for_input :: fn() {}
main :: fn() {
    io.println("ready")
    wait_for_input()
    io.println("done")
}
"""
    result = expect_ok(source, tmp_path)
    generated = Path(result.output_path)
    code = generated.read_text()
    barrier = "fn wait_for_input() void {}"
    assert code.count(barrier) == 1
    generated.write_text(code.replace(barrier, """
fn wait_for_input() void {
    var byte: [1]u8 = undefined;
    if (std.os.linux.read(0, &byte, 1) != 1) @panic("input barrier failed");
}
"""))
    binary = tmp_path / "terminal-handshake"
    built = subprocess.run(
        [zig, "build-exe", str(generated), "-ODebug", "-femit-bin=" + str(binary),
         "--cache-dir", str(zig_cache / "local"),
         "--global-cache-dir", str(zig_cache / "global")],
        capture_output=True, text=True, timeout=120,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    master, slave = pty.openpty()
    child = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=slave,
                             stderr=subprocess.PIPE)
    os.close(slave)
    try:
        # A pty turns "\n" into "\r\n".
        assert read_line(master) == b"ready\r\n"
        assert child.poll() is None, "the line arrived only when the program exited"
        _, stderr = child.communicate(input=b"x", timeout=60)
        assert child.returncode == 0, stderr
        assert stderr == b""
        assert read_line(master) == b"done\r\n"
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)
        child.stdin.close()
        child.stderr.close()
        os.close(master)


@pytest.mark.parametrize("profile", PROFILES)
def test_reader_closing_the_pipe_ends_the_program_quietly(tmp_path, zig, profile):
    # 200000 lines is about 2.5 MB, far more than a pipe holds, so the
    # program must hit the closed pipe.
    source = """
io :: import "std/io"
main :: fn() {
    for i := 0; i < 200000; i += 1 {
        io.println("line {}", i)
    }
}
"""
    binary = build_binary(source, tmp_path, zig, profile)
    child = subprocess.Popen([str(binary)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             preexec_fn=no_core_dump)
    try:
        assert read_line(child.stdout.fileno()) == b"line 0\n"
        child.stdout.close()
        child.stdout = None
        _, stderr = child.communicate(timeout=60)
        assert child.returncode == 0
        assert stderr == b""
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)
        if child.stdout is not None:
            child.stdout.close()
        child.stderr.close()


def test_pipe_reader_gets_every_line_and_stderr_stays_ordered(tmp_path, zig):
    # Regression guard, passed before the stdout changes too: with both
    # streams on one pipe, stdout text precedes the stderr text written
    # after it (L48).
    source = """
io :: import "std/io"
main :: fn() {
    io.println("out 1")
    io.eprintln("err 1")
    io.print("out 2 ")
    io.eprintln("err 2")
    io.println("out 3")
}
"""
    binary = build_binary(source, tmp_path, zig, "release")
    process = subprocess.run([str(binary)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, timeout=60)
    assert process.returncode == 0
    assert process.stdout == "out 1\nerr 1\nout 2 err 2\nout 3\n"
