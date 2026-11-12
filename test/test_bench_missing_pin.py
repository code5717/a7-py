"""Benchmark CLI decisions with native operations replaced at named boundaries.

These controls run the real pin loading, comparison, writing and exit logic.
They do not establish benchmark output correctness or performance.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/bench_perf.py'


@pytest.fixture
def bench(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('bench_pin_contract', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = tmp_path
    module.BUILD_DIR = tmp_path / 'build'
    module.PINS_DIR = tmp_path / 'pins'
    monkeypatch.setattr(module, 'host_name', lambda: 'fixture-host')

    def forbidden(*args, **kwargs):
        pytest.fail('native/emission operation reached before pin validation')

    for name in ('run_cmd', 'zig_version', 'emit_zig', 'build_binary', 'time_binary'):
        monkeypatch.setattr(module, name, forbidden)
    return module


@pytest.mark.parametrize('shape', ['missing', 'empty', 'partial', 'malformed', 'unreadable', 'null', 'missing_release', 'missing_hash', 'negative', 'nan', 'unrepresentable_timing'])
def test_gate_requires_every_timing_before_native_work(bench, monkeypatch, capsys, shape):
    if shape != 'missing':
        bench.PINS_DIR.mkdir()
        if shape == 'unreadable':
            bench.pin_path().mkdir()
        else:
            content = {'empty': {}, 'partial': {bench.BENCHES[0]: {'release': 1}},
                       'null': None, 'missing_release': {name: {} for name in bench.BENCHES},
                       'missing_hash': {name: {'release': 1.0} for name in bench.BENCHES},
                       'negative': {name: {'release': -1.0, 'output_sha256': 'fixture'} for name in bench.BENCHES},
                       'nan': {name: {'release': float('nan'), 'output_sha256': 'fixture'} for name in bench.BENCHES},
                       'unrepresentable_timing': {name: {'release': 10 ** 400, 'output_sha256': 'fixture'} for name in bench.BENCHES}}
            bench.pin_path().write_text('{invalid' if shape == 'malformed' else json.dumps(content[shape]))
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT), '--gate'])
    assert bench.main() == 1
    captured = capsys.readouterr()
    assert '--gate requires a complete usable host pin' in captured.err
    assert 'missing or invalid timing/hash baseline' in captured.err
    assert 'benches ok' not in captured.out
    assert not bench.BUILD_DIR.exists()


def allow_fixture_observations(bench, monkeypatch, median):
    # Each operation is a named external boundary; pin/comparison logic is real.
    digest = hashlib.sha256(b'fixture-output\n').hexdigest()
    monkeypatch.setattr(bench, 'zig_version', lambda: 'fixture-toolchain')
    monkeypatch.setattr(bench, 'emit_zig', lambda name: (True, ''))
    monkeypatch.setattr(bench, 'build_binary', lambda name: (True, ''))
    monkeypatch.setattr(bench, 'time_binary', lambda name, runs, cpu: (median, digest, '', 0.0))
    return digest


@pytest.mark.parametrize('gate,median,expected', [(True, 1.0, 0), (True, 2.0, 1), (False, 2.0, 0)])
def test_existing_pin_comparison_and_report_only_exit(bench, monkeypatch, capsys, gate, median, expected):
    digest = allow_fixture_observations(bench, monkeypatch, median)
    bench.PINS_DIR.mkdir()
    bench.pin_path().write_text(json.dumps({name: {'release': 1.0, 'output_sha256': digest} for name in bench.BENCHES}))
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT)] + (['--gate'] if gate else []))
    assert bench.main() == expected
    output = capsys.readouterr().out
    if median == 1.0:
        assert 'within pins' in output
    else:
        assert 'exceeded' in output
        assert 'within pins' not in output


def test_missing_pin_default_still_reports_times(bench, monkeypatch, capsys):
    allow_fixture_observations(bench, monkeypatch, 1.0)
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT)])
    assert bench.main() == 0
    assert 'reporting times only' in capsys.readouterr().out
    assert not bench.pin_path().exists()


def test_explicit_pin_update_still_writes_observations(bench, monkeypatch, capsys):
    digest = allow_fixture_observations(bench, monkeypatch, 1.25)
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT), '--pin'])
    assert bench.main() == 0
    pin = json.loads(bench.pin_path().read_text())
    assert set(pin) == set(bench.BENCHES)
    assert all(row['release'] == 1.25 and row['output_sha256'] == digest for row in pin.values())
    assert 'pin written' in capsys.readouterr().out


def test_pin_and_gate_conflict_preserves_existing_pin_without_native_work(bench, monkeypatch, capsys):
    bench.PINS_DIR.mkdir()
    original = b'{"keep": "original bytes"}\n'
    bench.pin_path().write_bytes(original)
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT), '--pin', '--gate'])
    with pytest.raises(SystemExit) as raised:
        bench.main()
    assert raised.value.code == 2
    assert '--pin and --gate cannot be combined' in capsys.readouterr().err
    assert bench.pin_path().read_bytes() == original
    assert not bench.BUILD_DIR.exists()


def test_complete_pin_still_rejects_output_hash_mismatch(bench, monkeypatch, capsys):
    allow_fixture_observations(bench, monkeypatch, 1.0)
    bench.PINS_DIR.mkdir()
    bench.pin_path().write_text(json.dumps({name: {'release': 1.0, 'output_sha256': 'different'} for name in bench.BENCHES}))
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT), '--gate'])
    assert bench.main() == 1
    assert 'output hash differs from pin' in capsys.readouterr().out
