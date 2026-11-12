"""Pin user-facing docs so cut forms are not described as runnable.

Observable claim: README, SPEC, STATUS, and site coverage agree that user
variadics, multi-declaration/destructuring, and multi-return are cut. This
does not re-test compiler exits (see test_surface_cut_parsed_only.py).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_readme_names_cut_surface():
    text = _read("README.md")
    assert "cut" in text.lower()
    assert "variadic" in text.lower()
    assert "destructuring" in text.lower()
    assert "multi-return" in text.lower()
    # Must not advertise cut forms as planned runnable syntax.
    assert "variadic runtime lowering" not in text.lower()


def test_spec_preamble_and_variadic_section_say_cut():
    text = _read("docs/SPEC.md")
    assert "Sections marked cut" in text or "marked cut," in text
    assert "### 6.6 Variadic Functions" in text
    section = text.split("### 6.6 Variadic Functions", 1)[1].split("\n---", 1)[0]
    assert "Cut from the current language surface" in section
    assert "parsed and partially" not in section.lower()


def test_status_records_cut_exits():
    text = _read("docs/STATUS.md")
    assert "are cut from the runnable surface" in text
    assert "semantic exit 6" in text
    assert "parse exit 5" in text
    assert "P-STD-collections-scope" in text
    assert "P-MEM-mechanism-selection" in text
    assert "does not rewrite `a7/safety.py`" in text


def test_coverage_matrix_matches_cut_qualifications():
    text = _read("site/docs/coverage.md")
    assert "Cut: declarations parse then fail at semantic exit 6" in text
    assert "Cut: multi-return and destructuring fail at parse exit 5" in text
    assert "Cut: user variadic parameters fail at semantic exit 6" in text
    assert "user variadic runtime lowering is unavailable" not in text


def _top_level_commas(expr: str) -> bool:
    depth = 0
    for ch in expr:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            return True
    return False


def test_examples_avoid_cut_spellings():
    forbidden_snippets = (
        ": ..",
        ", :=",
    )
    for path in sorted((ROOT / "examples").glob("*.a7")):
        source = path.read_text(encoding="utf-8")
        for snippet in forbidden_snippets:
            assert snippet not in source, f"{path.name} contains cut spelling {snippet!r}"
        for line in source.splitlines():
            stripped = line.split("//", 1)[0].strip()
            if stripped.startswith("ret ") and _top_level_commas(stripped[4:]):
                raise AssertionError(f"{path.name} has multi-value ret: {stripped}")
