"""Long expression chains cost the type checker no Python stack (P2-29, P2-78).

`x + x + ...` and postfix chains (`p.next.next...`, `a[0][0]...`,
`f()()...`) nest through their first operand. The checker used one Python
frame group per link and exited 8 near 330 terms. It now walks the chain
with a list. Each test runs under a recursion limit a few frames above
the test itself, so one frame per link would fail at once.
"""

from __future__ import annotations

import sys

import pytest

from conftest import expect_exit, expect_ok, low_recursion_limit, parse_program, run_all_profiles, run_both_profiles

LINKS = 5000


def check(source: str):
    """Run name resolution and the type checker; return the checker's errors."""
    from a7.passes.name_resolution import NameResolutionPass
    from a7.passes.type_checker import TypeCheckingPass

    program = parse_program(source)
    resolver = NameResolutionPass()
    symbols = resolver.analyze(program, "chain.a7")
    assert resolver.errors == []
    checker = TypeCheckingPass(symbols)
    previous = sys.getrecursionlimit()
    sys.setrecursionlimit(low_recursion_limit())
    try:
        checker.analyze(program, "chain.a7")
    finally:
        sys.setrecursionlimit(previous)
    return [str(error) for error in checker.errors]


@pytest.mark.parametrize(
    "chain",
    [
        pytest.param(" + ".join(["x"] * LINKS), id="addition"),
        pytest.param(" and ".join(["b"] * LINKS), id="logical-and"),
        pytest.param("x" + " * x - x" * (LINKS // 2), id="mixed-arithmetic"),
        pytest.param("7 + " + " + ".join(["x"] * LINKS), id="constant-prefix"),
    ],
)
def test_a_flat_binary_chain_type_checks(chain):
    source = f"main :: fn() {{\n    x: i64 = 1\n    b := true\n    y := {chain}\n}}\n"
    assert check(source) == []


def test_a_field_chain_through_references_type_checks():
    source = (
        "Node :: struct { value: i32, next: ref Node }\n\n"
        "f :: fn(p: ref Node) i32 {\n"
        f"    ret p{'.next' * LINKS}.value\n"
        "}\n\nmain :: fn() {\n}\n"
    )
    assert check(source) == []


@pytest.mark.parametrize(
    ("chain", "fragment"),
    [
        pytest.param("a" + "[0]" * LINKS, "Cannot index this type: got 'i32'", id="index"),
        pytest.param("f" + "()" * LINKS, "Type is not callable: got 'i32'", id="call"),
        pytest.param("p" + ".x" * LINKS, "Cannot access field on non-struct type: got 'i32'", id="field"),
        pytest.param("a[0]" + ".x()[0]" * (LINKS // 3), "Cannot access field on non-struct type: got 'i32'", id="mixed"),
    ],
)
def test_a_postfix_chain_reports_its_first_bad_link_once(chain, fragment):
    source = (
        "P :: struct { x: i32 }\n"
        "f :: fn() i32 { ret 1 }\n\n"
        "main :: fn() {\n    a: [2]i32 = [1, 2]\n    p := P{x: 1}\n"
        f"    y := {chain}\n}}\n"
    )
    errors = check(source)
    assert len(errors) == 1, errors[:3]
    assert fragment in errors[0]


def test_a_constant_chain_folds_to_one_value_and_runs(tmp_path, zig):
    source = (
        'io :: import "std/io"\n\nmain :: fn() {\n'
        f"    y: i32 = {' + '.join(['1'] * LINKS)}\n"
        '    io.println("{}", y)\n}\n'
    )
    assert run_both_profiles(source, tmp_path, zig) == f"{LINKS}\n"


def test_a_2000_term_chain_compiles_builds_and_runs(tmp_path, zig):
    source = (
        'io :: import "std/io"\n\nmain :: fn() {\n    x: i64 = 1\n'
        f"    y := {' + '.join(['x'] * 2000)}\n"
        '    io.println("{}", y)\n}\n'
    )
    assert run_all_profiles(source, tmp_path, zig) == "2000\n"


def test_deep_expression_still_requires_a_nonzero_divisor(tmp_path):
    source = (
        "main :: fn() {\n    x: i64 = 1\n    divisor: i64 = 0\n"
        f"    y := ({' + '.join(['x'] * 2000)}) / divisor\n}}\n"
    )
    expect_exit(source, tmp_path, 6, "Divisor not proven non-zero")


def test_runtime_chain_passes_full_pipeline_with_low_recursion_limit(tmp_path):
    source = (
        'io :: import "std/io"\nmain :: fn() {\n    x: i64 = 1\n'
        f"    y := {' + '.join(['x'] * 2000)}\n"
        '    io.println("{}", y)\n}\n'
    )
    previous = sys.getrecursionlimit()
    sys.setrecursionlimit(low_recursion_limit())
    try:
        expect_ok(source, tmp_path)
    finally:
        sys.setrecursionlimit(previous)
