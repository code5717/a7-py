"""User-facing CLI workflows and native process boundary contracts."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent


def cli(tmp_path, *args, env=None):
    return subprocess.run([sys.executable, str(ROOT / 'main.py'), *map(str, args)],
                          cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)


def program(tmp_path):
    source = tmp_path / 'hello world.a7'
    source.write_text('io :: import "std/io"\nhelper :: import "helper"\nmain :: fn() {\n io.println("{}", helper.answer())\n}\n')
    (tmp_path / 'helper.a7').write_text('pub answer :: fn() i32 {\n ret 42\n}\n')
    return source


def test_check_full_pipeline_and_legacy_json_without_zig(tmp_path):
    source = program(tmp_path)
    env = {**os.environ, 'PATH': str(tmp_path)}
    result = cli(tmp_path, 'check', source, '--format', 'json', env=env)
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(result.stdout)['status'] == 'ok'
    assert sorted(p.name for p in tmp_path.iterdir()) == ['hello world.a7', 'helper.a7']
    legacy = cli(tmp_path, '--mode', 'pipeline', '--format', 'json', source, env=env)
    assert legacy.returncode == 0
    assert json.loads(legacy.stdout)['status'] == 'ok'
    source.write_text('main :: fn() {\n missing_function()\n}\n')
    invalid = cli(tmp_path, 'check', source, '--format', 'json', env=env)
    assert invalid.returncode == 6
    assert json.loads(invalid.stdout)['status'] == 'error'
    human = cli(tmp_path, 'check', source, env=env)
    assert human.returncode == 6 and 'missing_function' in human.stderr


@pytest.mark.parametrize('profile', ['debug', 'release', 'fast'])
def test_native_build_run_spaces_and_output_protection(tmp_path, profile):
    assert shutil.which('zig'), 'Zig required for CLI native qualification'
    source = program(tmp_path)
    output = tmp_path / 'binary with spaces'
    built = cli(tmp_path, 'build', source, '-o', output, '--profile', profile)
    assert built.returncode == 0, built.stderr + built.stdout
    native = subprocess.run([str(output)], capture_output=True, text=True)
    assert (native.returncode, native.stdout) == (0, '42\n')
    run = cli(tmp_path, 'run', source, '--profile', profile)
    assert (run.returncode, run.stdout) == (0, '42\n'), run.stderr


def test_version_and_missing_toolchain(tmp_path):
    result = cli(tmp_path, '--version')
    assert result.returncode == 0 and result.stdout.startswith('a7 ')
    env = {**os.environ, 'PATH': str(tmp_path)}
    doctor = cli(tmp_path, 'doctor', env=env)
    assert doctor.returncode == 2
    assert 'Python ' in doctor.stdout and 'A7 ' in doctor.stdout
    assert 'not found on PATH' in doctor.stdout
    built = cli(tmp_path, 'build', program(tmp_path), env=env)
    assert built.returncode == 2
    assert 'not found on PATH' in built.stderr


@pytest.mark.parametrize('kind', ['entry', 'import', 'symlink', 'hardlink', 'directory'])
def test_build_cannot_replace_inputs_or_directories(tmp_path, kind):
    source = program(tmp_path)
    module = tmp_path / 'helper.a7'
    destination = tmp_path / 'alias'
    if kind == 'entry':
        destination = source
    elif kind == 'import':
        destination = module
    elif kind == 'symlink':
        destination.symlink_to(module)
    elif kind == 'hardlink':
        destination.hardlink_to(module)
    else:
        destination.mkdir()
    before = (source.read_bytes(), module.read_bytes())
    result = cli(tmp_path, 'build', source, '-o', destination)
    assert result.returncode == 3, result.stderr
    assert (source.read_bytes(), module.read_bytes()) == before


def fake_zig(tmp_path, body):
    executable = tmp_path / 'zig'
    executable.write_text(f'#!{sys.executable}\n' + body)
    executable.chmod(0o755)
    return {**os.environ, 'PATH': str(tmp_path)}


def test_wrong_zig_and_native_build_failure(tmp_path):
    source = program(tmp_path)
    env = fake_zig(tmp_path, 'print("0.15.0")\n')
    rejected = cli(tmp_path, 'build', source, env=env)
    assert rejected.returncode == 2 and 'found 0.15.0' in rejected.stderr
    env = fake_zig(tmp_path, 'import sys\nif sys.argv[1] == "version": print("0.16.0")\nelse:\n print("native build rejected", file=sys.stderr)\n sys.exit(1)\n')
    output = tmp_path / 'previous-binary'
    output.write_bytes(b'previous good build')
    failed = cli(tmp_path, 'build', source, '-o', output, env=env)
    assert failed.returncode == 7 and 'native build rejected' in failed.stderr
    assert output.read_bytes() == b'previous good build'


def test_run_forwards_arguments_cwd_and_exit_at_process_boundary(tmp_path):
    # Fake Zig isolates process forwarding. This does not qualify A7 argument APIs.
    source = program(tmp_path)
    env = fake_zig(tmp_path, '''import sys
from pathlib import Path
if sys.argv[1] == 'version':
 print('0.16.0')
else:
 output = Path(next(arg.split('=', 1)[1] for arg in sys.argv if arg.startswith('-femit-bin=')))
 output.write_text('#!' + sys.executable + '\\nimport json, os, sys\\nprint(json.dumps([os.getcwd(), sys.argv[1:]]))\\nsys.exit(23)\\n')
 output.chmod(0o755)
''')
    result = cli(tmp_path, 'run', source, '--', 'arg with spaces', '--profile', 'user-value', env=env)
    assert result.returncode == 23, result.stderr
    assert json.loads(result.stdout) == [str(tmp_path), ['arg with spaces', '--profile', 'user-value']]


def library(tmp_path):
    module = tmp_path / 'helper.a7'
    module.write_text('pub answer :: fn() i32 {\n ret 42\n}\n')
    return module


def test_check_rejects_file_without_main(tmp_path):
    result = cli(tmp_path, 'check', library(tmp_path))
    assert result.returncode == 6, result.stdout + result.stderr
    combined = result.stdout + result.stderr
    assert "no 'main :: fn()'" in combined
    assert '--lib' in combined


def test_check_lib_accepts_file_without_main(tmp_path):
    result = cli(tmp_path, 'check', '--lib', library(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr


def test_build_and_run_reject_file_without_main(tmp_path):
    # No Zig needed: the entry gate fails before toolchain lookup.
    module = library(tmp_path)
    built = cli(tmp_path, 'build', module)
    assert built.returncode == 6, built.stdout + built.stderr
    ran = cli(tmp_path, 'run', module)
    assert ran.returncode == 6, ran.stdout + ran.stderr


def test_lib_compile_emits_without_main(tmp_path):
    module = library(tmp_path)
    output = tmp_path / 'helper.zig'
    rejected = cli(tmp_path, '--mode', 'compile', '--output', str(output), str(module))
    assert rejected.returncode == 6, rejected.stdout + rejected.stderr
    assert not output.exists()
    accepted = cli(tmp_path, '--mode', 'compile', '--lib', '--output', str(output), str(module))
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert 'pub fn answer' in output.read_text(encoding='utf-8')


@pytest.mark.parametrize('arguments', [
    ['--version', '-v'],
    ['missing.a7', '--version'],
    ['check', 'missing.a7', '--version'],
])
def test_version_works_next_to_other_arguments(tmp_path, arguments):
    result = cli(tmp_path, *arguments)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith('a7 ') and result.stdout.count('\n') == 1


def test_help_lists_the_subcommands(tmp_path):
    result = cli(tmp_path, '-h')
    assert result.returncode == 0, result.stderr
    listed = [line.split()[0] for line in result.stdout.split('commands (see', 1)[1].splitlines()[1:5]]
    assert listed == ['check', 'build', 'run', 'doctor']
    assert '--version' in result.stdout


LAYOUT_SOURCE = (
    'io :: import "std/io"\nDot :: struct {\n x: i32\n y: i64\n}\n'
    'main :: fn() {\n d := Dot{x: 1, y: 2}\n io.println("{}", d.x)\n}\n'
)


def test_check_layout_json_carries_the_layout(tmp_path):
    source = tmp_path / 'dot.a7'
    source.write_text(LAYOUT_SOURCE)
    result = cli(tmp_path, 'check', '--layout', '--format', 'json', source)
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload['status'] == 'ok'
    assert payload['layout'] == {
        'line_bytes': 64,
        'structs': [{
            'name': 'Dot', 'size': 16, 'align': 8, 'lines': 1, 'line_use_percent': 25.0, 'note': None,
            'fields': [
                {'name': 'y', 'type': 'i64', 'offset': 0, 'size': 8, 'align': 8, 'touched': 0},
                {'name': 'x', 'type': 'i32', 'offset': 8, 'size': 4, 'align': 4, 'touched': 1},
            ],
        }],
    }
    plain = cli(tmp_path, 'check', '--format', 'json', source)
    assert 'layout' not in json.loads(plain.stdout)


def test_build_refuses_a7_output_and_names_it(tmp_path):
    # No Zig is run: the destination is rejected first. A stub passes the
    # toolchain version check.
    source = tmp_path / 'dot.a7'
    source.write_text(LAYOUT_SOURCE)
    env = fake_zig(tmp_path, 'print("0.16.0")\n')
    target = tmp_path / 'out.a7'
    result = cli(tmp_path, 'build', source, '-o', target, env=env)
    assert result.returncode == 3, result.stdout + result.stderr
    assert str(target) in result.stderr
    assert not target.exists()
