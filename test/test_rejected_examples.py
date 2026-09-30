"""Programs that must NOT compile, pinned by their diagnostic.

The compiler's best errors are the ones that stop a program before it produces
a wrong answer, and nothing exercised them: every file under `examples/` has to
compile, build, run and match its golden. `examples/rejected/` holds the other
side of that contract, and `manifest.json` pairs each file with the exit code
and the message fragment it must produce.

This is the same "one located cause" contract `test_untyped_constants_acceptance.py`
asserts, applied to the cases the language refuses outright.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REJECTED = ROOT / "examples" / "rejected"
MANIFEST = REJECTED / "manifest.json"

# Exit codes are the compiler's own vocabulary, not pytest's.
EXIT_SEMANTIC = 6


def load_cases():
    data = json.loads(MANIFEST.read_text())
    cases = data["cases"]
    listed = {case["file"] for case in cases}
    on_disk = {path.name for path in REJECTED.glob("*.a7")}
    assert listed == on_disk, (
        f"manifest and directory disagree: only in manifest {sorted(listed - on_disk)}, "
        f"only on disk {sorted(on_disk - listed)}"
    )
    return cases


CASES = load_cases()


def compile_result(source: Path, output: Path):
    return subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(source), "--output", str(output),
         "--format", "json"],
        cwd=ROOT, capture_output=True, text=True,
    )


@pytest.mark.parametrize("case", CASES, ids=[case["file"] for case in CASES])
def test_rejected_program_fails_with_its_diagnostic(case, tmp_path):
    source = REJECTED / case["file"]
    output = tmp_path / "main.zig"
    result = compile_result(source, output)

    assert result.returncode == case["exit_code"], (
        f"expected exit {case['exit_code']}, got {result.returncode}\n"
        f"{result.stdout}{result.stderr}"
    )
    payload = json.loads(result.stdout)
    details = payload["error"]["details"]
    assert details, payload["error"]
    assert any(
        case["message"].lower() in entry["message"].lower() for entry in details
    ), [entry["message"] for entry in details]
    # A rejected program must not leave a usable artifact behind.
    assert not output.exists(), "rejected source still produced an output file"


@pytest.mark.parametrize("case", CASES, ids=[case["file"] for case in CASES])
def test_rejected_program_has_one_located_cause(case, tmp_path):
    """One located cause, with a real span, as the acceptance suite requires."""
    source = REJECTED / case["file"]
    result = compile_result(source, tmp_path / "main.zig")
    payload = json.loads(result.stdout)
    details = payload["error"]["details"]
    assert len(details) == 1, [entry["message"] for entry in details]
    span = details[0].get("span")
    assert span and span.get("start_line", 0) > 0, details[0]


def test_rejected_directory_is_excluded_from_the_e2e_glob():
    """A file that must fail cannot live where the e2e gates demand success.

    `scripts/verify_examples_common.py` and `scripts/build_examples.py` glob
    `examples/*.a7` without recursing, and `test_examples_e2e.py` requires the
    count of passing examples to equal the number of files the glob returns. If
    that ever changes to a recursive glob, these files start failing the gate
    and this test explains why that is not a regression to fix.
    """
    verifier = (ROOT / "scripts" / "verify_examples_common.py").read_text()
    assert 'glob("*.a7")' in verifier
    assert "rglob" not in verifier, (
        "verify_examples_common.py now recurses; examples/rejected/ would be "
        "compiled and built as if it were a working example"
    )
