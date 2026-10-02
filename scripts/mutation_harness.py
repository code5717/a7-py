"""Mutation harness: proof that the suite would notice a broken compiler.

A large green suite proves nothing on its own. An earlier audit of this project
ran two mutants and found that replacing `classify_cast` with a constant left
2508 of 2587 tests passing, and making `get_binary_precedence` a constant — so
that `1 + 2 * 3` parses as `(1 + 2) * 3` — left 2571 of 2594 passing. Only
four tests noticed the second one.

This module defines the check that closes that gap. Each mutant is a real,
named defect with a known correct answer. For each one the harness asks a
narrow question: is there a test that fails when the defect is present?

A mutant is CATCHED when the full suite reports at least one failure with the
mutant applied. It is SURVIVED when the suite is still green, which is the
finding that matters: a surviving mutant means the suite does not test that
part of the compiler, whatever its test count.

Run it directly to see the current standing:

    uv run python scripts/mutation_harness.py --list
    uv run python scripts/mutation_harness.py --check

The default is `--list`, which only reports. `--check` mutates the working tree
and therefore refuses to run unless the tree is clean or `--allow-dirty` is
passed; it always restores what it changed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Mutant:
    """One named defect, injected by a textual substitution."""

    name: str
    file: str
    original: str
    replacement: str
    defect: str
    caught_by: str

    def apply(self) -> None:
        path = ROOT / self.file
        text = path.read_text()
        if self.original not in text:
            raise SystemExit(
                f"mutant {self.name!r} is stale: {self.file} no longer contains\n"
                f"  {self.original!r}\n"
                "Update the mutant in scripts/mutation_harness.py to match the tree."
            )
        path.write_text(text.replace(self.original, self.replacement, 1))

    def revert(self) -> None:
        (ROOT / self.file).write_text((ROOT / self.file).read_text().replace(
            self.replacement, self.original, 1
        ))


MUTANTS: list[Mutant] = [
    Mutant(
        name="classify-constant",
        file="a7/cast_classifier.py",
        original='if source.kind is TypeKind.UNKNOWN or target.kind is TypeKind.UNKNOWN:\n        return CastDecision(CastClass.FORBIDDEN, "unknown source or target type")',
        replacement='if True:\n        return CastDecision(CastClass.FORBIDDEN, "MUTANT: every cast forbidden")',
        defect=(
            "classify_cast ignores its inputs and always returns FORBIDDEN, so no cast "
            "is ever approved. The prior audit measured 2508 of 2587 tests still passing."
        ),
        caught_by="the cast matrix and the narrowing-cast pipeline tests",
    ),
    Mutant(
        name="precedence-constant",
        file="a7/ast_nodes.py",
        original="    return precedence.get(op, 0)",
        replacement="    return 7  # MUTANT: every operator at one level",
        defect=(
            "get_binary_precedence collapses the operator table, so 1 + 2 * 3 parses as "
            "(1 + 2) * 3. The prior audit measured 2571 of 2594 tests still passing."
        ),
        caught_by="test_parser_basic.py's precedence shape assertion and the golden runs",
    ),
    Mutant(
        name="exact-div-always-truncates",
        file="a7/const_eval.py",
        original="        result = truncating_divmod(left, right)[0]",
        replacement="        result = left // right  # MUTANT: floor, not truncate toward zero",
        defect=(
            "the exact-constant folder floors an integer division instead of "
            "truncating toward zero, so -7 / 2 becomes -4. It is the same shape as the "
            "truncation audit, and it survived because no test pins the emitted value."
        ),
        caught_by="any test that compiles an integer division in a float context",
    ),
    Mutant(
        name="safety-never-invalidates",
        file="a7/passes/safety.py",
        original="    def _visit_stmt(self, node: ASTNode) -> None:",
        replacement="    def _visit_stmt(self, node: ASTNode) -> None:  # MUTANT: control",
        defect=(
            "A marker mutant. If this alone causes failures the safety pass is coupled "
            "to something it should not be, which is itself worth knowing. It is "
            "expected NOT to change behaviour, and is listed so the harness has a "
            "control: a mutant that changes nothing and is reported as caught is a bug "
            "in the harness."
        ),
        caught_by="nothing; this is the control",
    ),
]


def run_suite() -> tuple[bool, str]:
    """Run the full suite once. Returns (failed, tail of output).

    The environment is inherited rather than replaced, because the suite shells
    out to `uv` and to a real Zig toolchain. `FORCE_COLOR` is cleared so the
    diagnostic assertions in test_tokenizer_errors.py behave the same way they
    do under the gate.
    """
    env = dict(os.environ)
    env.pop("FORCE_COLOR", None)
    process = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:randomly", "--tb=line"],
        cwd=ROOT, capture_output=True, text=True, env=env,
    )
    return process.returncode != 0, (process.stdout + process.stderr)[-4000:]


def describe(mutant: Mutant) -> str:
    return (
        f"{mutant.name}\n"
        f"  file      {mutant.file}\n"
        f"  defect    {mutant.defect}\n"
        f"  caught by {mutant.caught_by}\n"
    )


def list_mutants() -> int:
    print(f"{len(MUTANTS)} named mutants.\n")
    for mutant in MUTANTS:
        print(describe(mutant))
    print(
        "Run with --check to apply each one and confirm the suite notices.\n"
        "The control mutant (safety-never-invalidates) changes no behaviour and\n"
        "is expected to survive; a suite that reports it as caught is misreporting."
    )
    return 0


def check_mutants(allow_dirty: bool) -> int:
    if not allow_dirty:
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True
        ).stdout.strip()
        if status:
            print("Working tree is not clean. The harness edits files in place.")
            print("Commit or stash first, or pass --allow-dirty.")
            return 2

    survivors: list[str] = []
    for mutant in MUTANTS:
        print(f"--- {mutant.name}")
        backup = ROOT / mutant.file
        shutil.copy2(backup, backup.with_suffix(backup.suffix + ".mutantbak"))
        try:
            mutant.apply()
            failed, _tail = run_suite()
        finally:
            shutil.move(str(backup.with_suffix(backup.suffix + ".mutantbak")), str(backup))
        if failed:
            print("    CAUGHT - the suite failed with the mutant applied")
        else:
            print("    SURVIVED - the suite was still green")
            survivors.append(mutant.name)

    print()
    if survivors:
        print("Survivors (the suite does not test this):")
        for name in survivors:
            print(f"  - {name}")
    return 1 if survivors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="describe the mutants and exit")
    parser.add_argument("--check", action="store_true", help="apply each mutant and confirm detection")
    parser.add_argument("--allow-dirty", action="store_true", help="run --check with uncommitted changes")
    args = parser.parse_args()
    if args.check:
        return check_mutants(args.allow_dirty)
    return list_mutants()


if __name__ == "__main__":
    raise SystemExit(main())
