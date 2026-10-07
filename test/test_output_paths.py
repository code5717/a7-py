"""Where `a7 FILE` writes its output, and which destinations it refuses."""

import json
import os
import subprocess
import sys
from pathlib import Path

from a7.compile import ExitCode

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HELLO = 'io :: import "std/io"\n\nmain :: fn() {\n    io.println("hi")\n}\n'


def run_cli(args, cwd=PROJECT_ROOT):
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT), "NO_COLOR": "1", "COLUMNS": "200"}
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "main.py"), *map(str, args)],
        cwd=cwd, capture_output=True, text=True, env=env,
    )


def test_default_output_replaces_only_the_file_suffix(tmp_path):
    # `.a7` also appears in the directory name; only the suffix may change.
    project = tmp_path / "my.a7proj"
    project.mkdir()
    source = project / "foo.a7"
    source.write_text(HELLO, encoding="utf-8")

    result = run_cli([source])

    assert result.returncode == ExitCode.SUCCESS, result.stdout + result.stderr
    assert (project / "foo.zig").is_file()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["my.a7proj"]


def test_output_onto_another_a7_source_is_refused(tmp_path):
    source = tmp_path / "main.a7"
    source.write_text(HELLO, encoding="utf-8")
    other = tmp_path / "other.a7"
    other.write_text("// keep me\n", encoding="utf-8")

    result = run_cli([source, "-o", other])

    assert result.returncode == ExitCode.IO, result.stdout + result.stderr
    assert str(other) in result.stderr
    assert other.read_text(encoding="utf-8") == "// keep me\n"


def test_output_path_ending_in_a7_is_refused_before_it_exists(tmp_path):
    source = tmp_path / "main.a7"
    source.write_text(HELLO, encoding="utf-8")
    target = tmp_path / "generated.a7"

    result = run_cli([source, "-o", target, "--format", "json"])

    assert result.returncode == ExitCode.IO, result.stdout + result.stderr
    error = json.loads(result.stdout)["error"]
    assert error["category"] == "io"
    assert str(target) in error["message"]
    assert not target.exists()
