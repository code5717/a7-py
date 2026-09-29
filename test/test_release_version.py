"""Release identity must agree before artifacts can be published."""

from pathlib import Path
import importlib.util

import pytest

_spec = importlib.util.spec_from_file_location(
    "verify_release_version", Path(__file__).resolve().parents[1] / "scripts/verify_release_version.py"
)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
verify_version = _module.verify_version


def project(tmp_path: Path, changelog: str) -> Path:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n')
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "CHANGELOG.md").write_text(changelog)
    return tmp_path


def test_tag_requires_matching_package_and_changelog(tmp_path: Path) -> None:
    root = project(tmp_path, "# Changes\n\n## 1.2.3\n\n- Fixed a bug.\n")
    assert verify_version(root, "v1.2.3") == "1.2.3"
    with pytest.raises(ValueError, match="does not match package"):
        verify_version(root, "v1.2.4")


def test_tag_requires_actual_release_heading(tmp_path: Path) -> None:
    root = project(tmp_path, "## Unreleased\n\nThe planned version is 1.2.3.\n")
    with pytest.raises(ValueError, match="no release heading"):
        verify_version(root, "v1.2.3")
    assert verify_version(root, None) == "1.2.3"
