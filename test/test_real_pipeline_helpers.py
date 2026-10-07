"""The shared helpers in conftest must fail when the program is wrong."""

import pytest

from conftest import build_and_run, expect_exit, expect_ok, run_both_profiles

HELLO = 'io :: import "std/io"\n\nmain :: fn() {\n    io.println("{}", 6 * 7)\n}\n'


def test_expect_ok_runs_the_safety_pass(tmp_path):
    # Type-correct, but the divisor is unproven: only the full pipeline rejects it.
    source = (
        'io :: import "std/io"\n\n'
        "div :: fn(a: i32, b: i32) i32 {\n    ret a / b\n}\n\n"
        'main :: fn() {\n    io.println("{}", div(6, 3))\n}\n'
    )
    with pytest.raises(AssertionError):
        expect_ok(source, tmp_path)
    expect_exit(source, tmp_path, 6, "divisor")


def test_expect_exit_requires_a_fragment(tmp_path):
    with pytest.raises(AssertionError):
        expect_exit("main :: fn() {\n    x := y\n}\n", tmp_path, 6, "")


def test_expect_exit_checks_the_stage(tmp_path):
    with pytest.raises(AssertionError):
        expect_exit("main :: fn( {\n", tmp_path, 6, "expected")
    expect_exit("main :: fn( {\n", tmp_path, 5, "expected")


def test_build_and_run_returns_program_output(tmp_path, zig):
    assert build_and_run(HELLO, tmp_path, zig).stdout == "42\n"


def test_both_profiles_agree(tmp_path, zig):
    assert run_both_profiles(HELLO, tmp_path, zig) == "42\n"
