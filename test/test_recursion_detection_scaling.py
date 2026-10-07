"""Recursion ban: call-graph search cost and cycle diagnostics, through the real CLI.

The cycle messages below were captured from the CLI before the search was
replaced (path-enumerating DFS); they pin the user-visible text. The layered
program has no recursion and 2**24 distinct call paths.
"""

from collections import Counter
import json
import random
from pathlib import Path
import subprocess
import sys
import time

import pytest

from a7.compile import ExitCode


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_semantic(tmp_path: Path, source: str) -> tuple[subprocess.CompletedProcess[str], dict, float]:
    source_path = tmp_path / "main.a7"
    source_path.write_text(source, encoding="utf-8")
    start = time.perf_counter()
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "main.py"),
            "--mode",
            "semantic",
            "--format",
            "json",
            str(source_path),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=600,
    )
    elapsed = time.perf_counter() - start
    assert "Traceback" not in result.stderr, result.stderr
    return result, json.loads(result.stdout), elapsed


def layered_program(layers: int) -> str:
    # Every function in layer i calls both functions in layer i + 1.
    parts = []
    for i in range(layers):
        for side in "ab":
            parts.append(f"f{i}{side} :: fn() {{\n    f{i + 1}a()\n    f{i + 1}b()\n}}\n")
    parts.append(f"f{layers}a :: fn() {{\n}}\nf{layers}b :: fn() {{\n}}\n")
    parts.append("main :: fn() {\n    f0a()\n    f0b()\n}\n")
    return "".join(parts)


def recursion_details(payload: dict) -> list[dict]:
    return [d for d in payload["error"]["details"] if "Recursion is not allowed" in d["message"]]


def test_layered_call_graph_without_recursion_is_accepted_quickly(tmp_path):
    result, payload, elapsed = run_semantic(tmp_path, layered_program(24))

    assert result.returncode == ExitCode.SUCCESS, payload.get("error")
    # The path-enumerating search took about 50 s here; a linear search
    # finishes well under a second. The bound is loose for slow machines.
    assert elapsed < 10.0, f"semantic analysis took {elapsed:.1f}s"


@pytest.mark.parametrize(
    ("source", "expected", "line"),
    [
        pytest.param(
            "count :: fn(n: i32) i32 {\n    ret count(n)\n}\n"
            "main :: fn() {\n    x := count(1)\n}\n",
            ["Recursion is not allowed: Cycle: count -> count"],
            [1],
            id="direct",
        ),
        pytest.param(
            "ping :: fn(n: i32) i32 {\n    ret pong(n)\n}\n"
            "pong :: fn(n: i32) i32 {\n    ret ping(n)\n}\n"
            "main :: fn() {\n    x := ping(1)\n}\n",
            ["Recursion is not allowed: Cycle: ping -> pong -> ping"],
            [1],
            id="mutual",
        ),
        pytest.param(
            "alpha :: fn(n: i32) i32 {\n    ret beta(n)\n}\n"
            "gamma :: fn(n: i32) i32 {\n    ret alpha(n)\n}\n"
            "beta :: fn(n: i32) i32 {\n    ret gamma(n)\n}\n"
            "main :: fn() {\n    x := alpha(1)\n}\n",
            ["Recursion is not allowed: Cycle: alpha -> beta -> gamma -> alpha"],
            [1],
            id="three-cycle-declared-out-of-order",
        ),
        pytest.param(
            # Two independent cycles, the first reached only through a
            # non-recursive caller. One diagnostic each, in declaration order,
            # located at the function each search started from.
            "entry :: fn(n: i32) i32 {\n    ret odd(n)\n}\n"
            "odd :: fn(n: i32) i32 {\n    ret even(n)\n}\n"
            "loop :: fn(n: i32) i32 {\n    ret loop(n)\n}\n"
            "even :: fn(n: i32) i32 {\n    ret odd(n)\n}\n"
            "main :: fn() {\n    x := entry(1)\n    y := loop(1)\n}\n",
            [
                "Recursion is not allowed: Cycle: odd -> even -> odd",
                "Recursion is not allowed: Cycle: loop -> loop",
            ],
            [4, 7],
            id="two-separate-cycles",
        ),
    ],
)
def test_recursive_cycles_report_cycle_path(tmp_path, source, expected, line):
    result, payload, _ = run_semantic(tmp_path, source)

    assert result.returncode == ExitCode.SEMANTIC, result.stdout
    details = recursion_details(payload)
    assert [d["message"] for d in details] == expected
    assert [d["span"]["start_line"] for d in details] == line


def test_cycles_sharing_a_function_are_each_reported(tmp_path):
    # hub <-> left and hub <-> right share hub. The search from right is not
    # skipped because only hub and left were on the first reported cycle.
    source = (
        "hub :: fn(n: i32) i32 {\n    a := left(n)\n    ret right(n)\n}\n"
        "left :: fn(n: i32) i32 {\n    ret hub(n)\n}\n"
        "right :: fn(n: i32) i32 {\n    ret hub(n)\n}\n"
        "main :: fn() {\n    x := hub(1)\n}\n"
    )
    result, payload, _ = run_semantic(tmp_path, source)

    assert result.returncode == ExitCode.SEMANTIC, result.stdout
    details = recursion_details(payload)
    assert [(d["message"], d["span"]["start_line"]) for d in details] == [
        ("Recursion is not allowed: Cycle: hub -> left -> hub", 1),
        ("Recursion is not allowed: Cycle: right -> hub -> right", 8),
    ]


def test_disjoint_cycles_in_one_component_are_each_reported(tmp_path):
    # fa <-> fb and fc <-> fd are disjoint cycles joined into one strongly
    # connected component by fb -> fc and fd -> fa. Each cycle gets its own
    # diagnostic at the function the search started from.
    source = (
        "fa :: fn(n: i32) i32 {\n    ret fb(n)\n}\n"
        "fb :: fn(n: i32) i32 {\n    x := fa(n)\n    ret fc(n)\n}\n"
        "fc :: fn(n: i32) i32 {\n    ret fd(n)\n}\n"
        "fd :: fn(n: i32) i32 {\n    x := fc(n)\n    ret fa(n)\n}\n"
        "main :: fn() {\n    x := fa(1)\n}\n"
    )
    result, payload, _ = run_semantic(tmp_path, source)

    assert result.returncode == ExitCode.SEMANTIC, result.stdout
    details = recursion_details(payload)
    assert [
        (d["message"], d["span"]["start_line"], d["span"]["start_column"])
        for d in details
    ] == [
        ("Recursion is not allowed: Cycle: fa -> fb -> fa", 1, 1),
        ("Recursion is not allowed: Cycle: fc -> fd -> fc", 8, 1),
    ]


def reference_cycle_reports(order: list[str], graph: dict[str, set[str]]) -> list[tuple[str, str]]:
    """The cycle search the compiler used before the polynomial rewrite.

    It enumerates simple paths, so it is exponential; the differential test
    below only feeds it components of at most seven functions. Returns
    (starting function, "Cycle: ...") in report order.
    """
    reports = []
    reported: set[str] = set()
    for name in order:
        if name in reported:
            continue
        found = None
        stack = [(name, [name])]
        while stack and found is None:
            current, path = stack.pop()
            for callee in sorted(graph[current], reverse=True):
                if callee == name:
                    found = path + [callee]
                    break
                if callee in path:
                    continue
                stack.append((callee, path + [callee]))
        if found:
            reported.update(found)
            reports.append((name, "Cycle: " + " -> ".join(found)))
    return reports


def test_cycle_diagnostics_match_the_path_enumerating_search(tmp_path):
    # Invariant: the reported cycles (set, order, text, location) are the ones
    # the exhaustive search above reports. Many small random call graphs with
    # disjoint names are declared interleaved in one program, so each graph's
    # reports are independent and the global declaration order is exercised.
    rng = random.Random(20260917)
    letters = list("abcdefg")
    order: list[str] = []
    graph: dict[str, set[str]] = {}
    for g in range(120):
        size = rng.randint(1, 7)
        names = [f"k{g:03d}{letter}" for letter in rng.sample(letters, size)]
        density = rng.choice([0.15, 0.3, 0.5])
        for name in names:
            graph[name] = {callee for callee in names if rng.random() < density}
        order.extend(names)
    rng.shuffle(order)

    lines = []
    start_line = {}
    for name in order:
        start_line[name] = len(lines) + 1
        lines.append(f"{name} :: fn(n: i32) i32 {{")
        for i, callee in enumerate(sorted(graph[name])):
            lines.append(f"    v{i} := {callee}(n)")
        lines.append("    ret n")
        lines.append("}")
    lines.append("main :: fn() {")
    for i, name in enumerate(order):
        lines.append(f"    m{i} := {name}(1)")
    lines.append("}")

    reports = reference_cycle_reports(order, graph)
    expected = [(f"Recursion is not allowed: {text}", start_line[name]) for name, text in reports]
    # The seed must produce the case that matters: graphs with more than one report.
    graphs_with_reports = Counter(name[:4] for name, _ in reports)
    assert sum(1 for count in graphs_with_reports.values() if count > 1) >= 10

    result, payload, _ = run_semantic(tmp_path, "\n".join(lines) + "\n")

    assert result.returncode == ExitCode.SEMANTIC, result.stdout
    details = recursion_details(payload)
    assert [(d["message"], d["span"]["start_line"]) for d in details] == expected
