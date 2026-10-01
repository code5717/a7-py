"""Constant folding must preserve types and exact integer results.

Programs are compiled with the real CLI (main.py) and built with the real Zig
0.16.0 toolchain in Debug and ReleaseFast. Expected outputs are written by hand
from the A7 source, not by running the compiler. Nothing is mocked.

Set A7_TEST_ZIG to a Zig 0.16.0 binary or put zig on PATH. Missing tools fail
explicitly. Programs that the compiler may not reject yet (a shift past the
width, an out-of-range sum) are only compiled, never run. Float folding,
including results that overflow f64, is in test_float_nonfinite_folding.py.
"""

from fractions import Fraction
import math
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from a7.ast_nodes import ASTNode, NodeKind
from a7.parser import Parser
from a7.passes import NameResolutionPass, TypeCheckingPass
from a7.tokens import Tokenizer

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ("Debug", "ReleaseFast")


@pytest.fixture(scope="module")
def zig():
    executable = os.environ.get("A7_TEST_ZIG") or shutil.which("zig")
    assert executable, "Zig 0.16.0 required: set A7_TEST_ZIG or PATH"
    version = subprocess.run([executable, "version"], capture_output=True, text=True)
    assert version.returncode == 0 and version.stdout.strip() == "0.16.0", version
    return executable


def cli_compile(tmp_path, source):
    src = tmp_path / "main.a7"
    out = tmp_path / "main.zig"
    src.write_text(source, encoding="utf-8")
    process = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(src), "--output", str(out)],
        cwd=ROOT, capture_output=True, text=True,
    )
    return process, out


def emit(tmp_path, source):
    process, out = cli_compile(tmp_path, source)
    assert process.returncode == 0, process.stdout + process.stderr
    return out


def zig_cache_args(tmp_path):
    return ["--cache-dir", str(tmp_path / "cache"),
            "--global-cache-dir", str(tmp_path / "global-cache")]


def run_all_profiles(zig, tmp_path, output):
    observed = {}
    for profile in PROFILES:
        binary = tmp_path / ("program-" + profile)
        build = subprocess.run(
            [zig, "build-exe", str(output), "-O", profile,
             *zig_cache_args(tmp_path), "-femit-bin=" + str(binary)],
            capture_output=True, text=True,
        )
        assert build.returncode == 0, build.stdout + build.stderr
        process = subprocess.run([str(binary)], capture_output=True, text=True)
        observed[profile] = (process.returncode, process.stdout, process.stderr)
    return observed


def expect_everywhere(stdout):
    return {profile: (0, stdout, "") for profile in PROFILES}


# ---------------------------------------------------------------------------
# ZIG-1 / SAF-7: a folded literal must not take another node's type.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("source, stdout", [
    (
        'io :: import "std/io"\n'
        'main :: fn() {\n'
        "    same := 'x' == 'y'\n"
        '    io.println("same={}", same)\n'
        '    io.println("total={}", 60 + 5)\n'
        '}\n',
        "same=false\ntotal=65\n",
    ),
    (
        'io :: import "std/io"\n'
        'main :: fn() {\n'
        "    same := 'a' == 'a'\n"
        '    io.println("{} {}", same, 60 + 5)\n'
        '}\n',
        "true 65\n",
    ),
    (
        'io :: import "std/io"\n'
        'main :: fn() {\n'
        '    same := "a" == "a"\n'
        '    io.println("{} {}", same, 60 + 5)\n'
        '}\n',
        "true 65\n",
    ),
], ids=["char-compare-then-sum", "char-compare-same-line", "string-compare-same-line"])
def test_folded_integer_after_folded_comparison_prints_decimal(tmp_path, zig, source, stdout):
    output = emit(tmp_path, source)
    assert run_all_profiles(zig, tmp_path, output) == expect_everywhere(stdout)


def interleaved_program(count):
    """Many folds mixed with char, string and bool locals.

    Each round i folds a char comparison, then immediately an integer sum,
    then a string comparison and immediately an integer product, then
    truncating division and remainder on a negative dividend, a float
    product and a folded comparison. The expected lines are derived from
    the A7 semantics of each expression, not from compiler output.
    """
    lines = ['io :: import "std/io"', "main :: fn() {"]
    expected = []
    for i in range(count):
        letter = chr(ord("a") + i % 26)
        lines += [
            f"    c{i}: char = '{letter}'",
            f'    s{i}: string = "s{i}"',
            f"    b{i} := '{letter}' == 'a'",
            f'    io.println("{{}} {{}} {{}}", {i} + 60, c{i}, b{i})',
            f'    e{i} := "s{i}" == "s0"',
            f'    io.println("{{}} {{}} {{}}", {i} * 3, s{i}, e{i})',
            f'    io.println("{{}} {{}} {{}}", -{i + 7} / 3, -{i + 7} % 3, {i} - 100)',
            f"    fl{i} := 1.5 * 2.0",
            f'    io.println("{{}} {{}}", fl{i}, {i} + 1 == 1)',
        ]
        # Truncating division: the quotient rounds toward zero and the
        # remainder takes the dividend's sign. Fraction truncation is used
        # so the expectation does not share the compiler's arithmetic.
        quotient = math.trunc(Fraction(-(i + 7), 3))
        remainder = -(i + 7) - 3 * quotient
        expected += [
            f"{i + 60} {letter} {'true' if letter == 'a' else 'false'}",
            f"{i * 3} s{i} {'true' if i == 0 else 'false'}",
            f"{quotient} {remainder} {i - 100}",
            f"3 {'true' if i == 0 else 'false'}",
        ]
    lines.append("}")
    return "\n".join(lines) + "\n", "\n".join(expected) + "\n"


def test_many_interleaved_folds_print_their_own_values(tmp_path, zig):
    source, stdout = interleaved_program(60)
    output = emit(tmp_path, source)
    assert run_all_profiles(zig, tmp_path, output) == expect_everywhere(stdout)


def test_every_folded_literal_keeps_the_type_of_the_expression_it_replaced():
    # Runs the real tokenizer, parser, name resolution and type checker in
    # process (the stages compile.py runs before codegen). Folding happens
    # during type checking now, not in the preprocessor, so operator slots
    # are recorded before analysis: after analysis, a slot that holds a
    # LITERAL was folded, and the type map handed to the backend must give
    # that literal the folded expression's type. Not verified here: how the
    # backend uses the type (the Zig tests above).
    source, _ = interleaved_program(40)
    tokens = Tokenizer(source, filename="main.a7").tokenize()
    source_lines = source.splitlines()
    ast = Parser(tokens, filename="main.a7", source_lines=source_lines).parse()

    slots = []
    stack = [ast]
    while stack:
        node = stack.pop()
        for attr, value in vars(node).items():
            items = value if isinstance(value, list) else [value]
            for index, child in enumerate(items):
                if not isinstance(child, ASTNode):
                    continue
                if child.kind in (NodeKind.BINARY, NodeKind.UNARY):
                    slots.append((node, attr, index if isinstance(value, list) else None))
                stack.append(child)

    resolver = NameResolutionPass()
    resolver.source_lines = source_lines
    symbol_table = resolver.analyze(ast, "main.a7")
    assert resolver.errors == []
    checker = TypeCheckingPass(symbol_table)
    checker.source_lines = source_lines
    checker.analyze(ast, "main.a7")
    assert checker.errors == []
    type_map = checker.node_types

    checked = []
    for parent, attr, index in slots:
        value = getattr(parent, attr)
        # Folding clears child links in place (comparisons null their
        # operands), so a recorded slot can be empty now; that operand is
        # gone, not an unfolded expression.
        current = value[index] if index is not None and value is not None else value
        if current is not None and current.kind == NodeKind.LITERAL:
            checked.append((current.literal_value, str(type_map.get(id(current)))))
    # Each of the 40 rounds folds at least `i + 60`, `i * 3`, `i - 100`,
    # the division, the remainder, `1.5 * 2.0` and `i + 1 == 1`.
    assert len(checked) >= 40 * 7
    assert [c for c in checked if c[1] == 'None'] == []


def test_replaced_nodes_stay_alive_while_the_preprocessed_tree_is_alive():
    # type_map is keyed by id(node). In-place exact folding preserves node
    # identity, so a materialized literal keeps its own id and type entry by
    # construction. Requirement: every literal the checker materialized is
    # still reachable in the analyzed tree with its type entry intact, so the
    # backend cannot look up one node's id and get another node's type.
    source, _ = interleaved_program(20)
    tokens = Tokenizer(source, filename="main.a7").tokenize()
    source_lines = source.splitlines()
    ast = Parser(tokens, filename="main.a7", source_lines=source_lines).parse()
    resolver = NameResolutionPass()
    resolver.source_lines = source_lines
    symbol_table = resolver.analyze(ast, "main.a7")
    checker = TypeCheckingPass(symbol_table)
    checker.source_lines = source_lines
    checker.analyze(ast, "main.a7")
    assert resolver.errors == [] and checker.errors == []

    materialized = []
    stack = [ast]
    while stack:
        node = stack.pop()
        if node.kind == NodeKind.LITERAL and getattr(node, 'exact_materialized', False):
            materialized.append(node)
        for value in vars(node).values():
            items = value if isinstance(value, list) else [value]
            stack.extend(item for item in items if isinstance(item, ASTNode))

    assert len(materialized) >= 20 * 7
    type_map = checker.node_types
    assert [n for n in materialized if id(n) not in type_map] == []


# ---------------------------------------------------------------------------
# SAF-10: integer folding is exact and truncates toward zero.
# ---------------------------------------------------------------------------

def test_large_integer_quotient_and_remainder_match_run_time(tmp_path, zig):
    # 9007199254740993 and 18014398509481983 are not exact in binary64.
    output = emit(tmp_path, '''io :: import "std/io"
show :: fn(value: i64) {
    io.println("{} {} {} {}", value / 1, value % 1, value / 2, value % 2)
}
main :: fn() {
    exact_value_0: i64 = 9007199254740993 / 1
    exact_value_1: i64 = 9007199254740993 % 1
    exact_value_2: i64 = 9007199254740993 / 2
    exact_value_3: i64 = 9007199254740993 % 2
    io.println("{} {} {} {}", exact_value_0, exact_value_1, exact_value_2, exact_value_3)
    exact_value_4: i64 = 18014398509481983 / 1
    exact_value_5: i64 = 18014398509481983 % 1
    exact_value_6: i64 = 18014398509481983 / 2
    exact_value_7: i64 = 18014398509481983 % 2
    io.println("{} {} {} {}", exact_value_4, exact_value_5, exact_value_6, exact_value_7)
    show(9007199254740993)
    show(18014398509481983)
}
''')
    stdout = (
        "9007199254740993 0 4503599627370496 1\n"
        "18014398509481983 0 9007199254740991 1\n"
        "9007199254740993 0 4503599627370496 1\n"
        "18014398509481983 0 9007199254740991 1\n"
    )
    assert run_all_profiles(zig, tmp_path, output) == expect_everywhere(stdout)


def test_boundary_values_match_the_run_time_result(tmp_path, zig):
    # Exact constant results need a concrete destination before formatting
    # when they exceed default i32. Pair these with typed runtime operations.
    output = emit(tmp_path, '''io :: import "std/io"
show_i8 :: fn(a: i8) {
    io.println("{} {} {} {}", a / 3, a % 3, a / -4, a % -4)
}
show_u8 :: fn(a: u8) {
    io.println("{} {}", a / 7, a % 7)
}
show_i64 :: fn(a: i64) {
    io.println("{} {} {} {}", a / 10, a % 10, a / -10, a % -10)
}
show_u64 :: fn(a: u64) {
    io.println("{} {}", a / 10, a % 10)
}
main :: fn() {
    i8_max: i8 = 127
    i8_min: i8 = -128
    u8_max: u8 = 255
    i64_max: i64 = 9223372036854775807
    i64_min: i64 = -9223372036854775808
    u64_max: u64 = 18446744073709551615
    io.println("{} {} {} {}", 127 / 3, 127 % 3, 127 / -4, 127 % -4)
    show_i8(i8_max)
    io.println("{} {} {} {}", -128 / 3, -128 % 3, -128 / -4, -128 % -4)
    show_i8(i8_min)
    io.println("{} {}", 255 / 7, 255 % 7)
    show_u8(u8_max)
    exact_value_8: i64 = 9223372036854775807 / 10
    exact_value_9: i64 = 9223372036854775807 % 10
    exact_value_10: i64 = 9223372036854775807 / -10
    exact_value_11: i64 = 9223372036854775807 % -10
    io.println("{} {} {} {}", exact_value_8, exact_value_9, exact_value_10, exact_value_11)
    show_i64(i64_max)
    exact_value_12: i64 = -9223372036854775808 / 10
    exact_value_13: i64 = -9223372036854775808 % 10
    exact_value_14: i64 = -9223372036854775808 / -10
    exact_value_15: i64 = -9223372036854775808 % -10
    io.println("{} {} {} {}", exact_value_12, exact_value_13, exact_value_14, exact_value_15)
    show_i64(i64_min)
    exact_value_16: i64 = 18446744073709551615 / 10
    exact_value_17: i64 = 18446744073709551615 % 10
    io.println("{} {}", exact_value_16, exact_value_17)
    show_u64(u64_max)
    io.println("{} {} {}", 2147483647 + 0, -2147483647 - 1, 2147483647 * 1)
}
''')
    stdout = (
        "42 1 -31 3\n" * 2
        + "-42 -2 32 0\n" * 2
        + "36 3\n" * 2
        + "922337203685477580 7 -922337203685477580 7\n" * 2
        + "-922337203685477580 -8 922337203685477580 -8\n" * 2
        + "1844674407370955161 5\n" * 2
        + "2147483647 -2147483648 2147483647\n"
    )
    assert run_all_profiles(zig, tmp_path, output) == expect_everywhere(stdout)



# ---------------------------------------------------------------------------
# SAF-13 and SAF-14: an integer fold whose result the node's type cannot
# represent is left to the rest of the pipeline. Compile only, because the
# compiler does not reject these yet and the emitted Zig may not build.
#
# SAF-12 (a float that overflows f64) is not here: infinity is a value the
# backend can emit, so the requirement is that the program builds and prints
# the IEEE f64 answer. test/test_float_nonfinite_folding.py checks that.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("statement, forbidden", [
    ("x: i64 = 1 << 20000", None),
    # The fold wraps to -2147483648 the way the runtime operator does, so a
    # successful compile must never name the unwrapped value.
    ("x: i32 = 2147483647 + 1", None),
], ids=["shift-past-width", "sum-past-i32"])
def test_unrepresentable_fold_is_not_emitted(tmp_path, statement, forbidden):
    process, out = cli_compile(
        tmp_path,
        'io :: import "std/io"\nmain :: fn() {\n    ' + statement + '\n    io.println("{}", x)\n}\n',
    )
    # Exit 8 is an internal compiler error; a located rejection (exit 6) or
    # a successful compile are both acceptable here.
    assert process.returncode != 8, process.stdout + process.stderr
    if process.returncode == 0 and forbidden is not None:
        assert re.search(forbidden, out.read_text(encoding="utf-8")) is None


@pytest.mark.parametrize("expression, printed", [
    ("9007199254740993 / 1", "9007199254740993"),
    ("9223372036854775807 / 10", "922337203685477580"),
])
def test_exact_quotient_formatting_widens_default(expression, printed, tmp_path):
    # An exact quotient beyond i32 widens the formatting default to i64
    # instead of rejecting: the value is exact and representable.
    process, out = cli_compile(tmp_path, 'io :: import "std/io"\nmain :: fn() { io.println("{}", ' + expression + ') }\n')
    assert process.returncode == 0, process.stdout + process.stderr
    assert printed in out.read_text(encoding="utf-8")
