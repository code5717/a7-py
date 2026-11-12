"""Deterministic timing/process boundaries; no performance or native evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/bench_perf.py'
OUTPUT = b'result: 7\n'
MEMORY_OUTPUTS = {
    'mem_cache': b'result: 6616666665 49999999 50000001\n',
    'mem_copy': b'result: 942376503\n',
    'mem_text': b'result: 98811553\n',
    'mem_cyclic': b'result: 757942091\n',
}


@pytest.fixture
def harness(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('measurement_contract', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = tmp_path
    module.BUILD_DIR = tmp_path / 'build'
    module.PINS_DIR = tmp_path / 'pins'
    monkeypatch.setattr(module, 'host_name', lambda: 'fixture-host')
    monkeypatch.setattr(module.os, 'sched_getaffinity', lambda pid: {12, 14})
    monkeypatch.setattr(module.shutil, 'which', lambda name: '/usr/bin/taskset')
    return module


def observations(harness, monkeypatch, durations):
    ticks = []
    elapsed = 0
    for _ in harness.BENCHES:
        for duration in durations:
            ticks.extend([elapsed, elapsed + duration])
            elapsed += duration
    iterator = iter(ticks)
    monkeypatch.setattr(harness.time, 'perf_counter', lambda: next(iterator))
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        name = Path(argv[-1]).name.removesuffix('_fast')
        if name in MEMORY_OUTPUTS:
            assert kwargs['input'] == b'A\n'
        else:
            assert 'input' not in kwargs
        return SimpleNamespace(returncode=0, stdout=MEMORY_OUTPUTS.get(Path(argv[-1]).name.removesuffix('_fast'), OUTPUT), stderr=b'')
    monkeypatch.setattr(harness.subprocess, 'run', run)
    monkeypatch.setattr(harness, 'zig_version', lambda: 'fixture-zig')
    monkeypatch.setattr(harness, 'emit_zig', lambda name: (True, ''))
    monkeypatch.setattr(harness, 'build_binary', lambda name: (True, ''))
    return calls


def pin(harness):
    harness.PINS_DIR.mkdir()
    payload = {n: {'release': 10, 'output_sha256': hashlib.sha256(MEMORY_OUTPUTS.get(n, OUTPUT)).hexdigest()} for n in harness.BENCHES}
    harness.pin_path().write_text(json.dumps(payload))
    return harness.pin_path().read_bytes()


@pytest.mark.parametrize('mode', ['--pin', '--gate'])
@pytest.mark.parametrize('durations,expected', [([10]*7, 0), ([9, 11]*3, 0), ([8, 10, 10, 10, 12], 1)])
def test_actual_measurements_reject_noise_and_preserve_pin(harness, monkeypatch, capsys, mode, durations, expected):
    original = pin(harness)
    calls = observations(harness, monkeypatch, durations)
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT), mode, '--runs', str(len(durations))])
    assert harness.main() == expected
    assert len(calls) == 17 * len(durations)
    assert all(c[:3] == ['taskset', '-c', '12'] for c in calls)
    assert {Path(c[-1]).name for c in calls} == {n+'_fast' for n in harness.BENCHES}
    assert 'cpu=12' in capsys.readouterr().out
    if expected or mode == '--gate':
        assert harness.pin_path().read_bytes() == original
    else:
        rows = json.loads(harness.pin_path().read_text())
        assert len(rows) == 17
        assert all(r['release'] == 10 and r['runs'] == len(durations) and r['cpu'] == 12 and r['cv'] == harness.variation(durations) and r['output_sha256'] == hashlib.sha256(MEMORY_OUTPUTS.get(n, OUTPUT)).hexdigest() for n, r in rows.items())


@pytest.mark.parametrize('args,missing_tool', [(['--pin', '--runs', '4'], False), (['--gate', '--runs', '1'], False), (['--taskset', '13'], False), (['--taskset', '12,14'], False), (['--taskset', '-1'], False), (['--taskset', '12'], True), (['--pin'], True)])
def test_invalid_measurement_configuration_reaches_no_native_boundary(harness, monkeypatch, args, missing_tool):
    original = pin(harness)
    if missing_tool:
        monkeypatch.setattr(harness.shutil, 'which', lambda name: None)
    def forbidden(*args, **kwargs):
        pytest.fail('native boundary reached for invalid measurement configuration')
    for name in ['zig_version', 'emit_zig', 'build_binary', 'time_binary']:
        monkeypatch.setattr(harness, name, forbidden)
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT), *args])
    assert harness.main() == 2
    assert not harness.BUILD_DIR.exists()
    assert harness.pin_path().read_bytes() == original


def test_default_seven_samples_and_requested_allowed_cpu(harness, monkeypatch):
    calls = observations(harness, monkeypatch, [10]*7)
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT), '--pin', '--taskset', '14'])
    assert harness.main() == 0
    assert len(calls) == 119
    assert all(c[:3] == ['taskset', '-c', '14'] for c in calls)


def test_raw_sample_statistics_have_independent_expected_values(harness):
    assert harness.robust_center([1, 8, 9, 10, 100]) == 9
    assert harness.robust_center([1, 8, 9, 10]) == 8.5
    assert harness.variation([9, 11]*3) == 0.10
    assert harness.variation([10]*7) == 0
    assert harness.variation([8, 10, 10, 10, 12]) > 0.10


def test_output_instability_still_invalidates_actual_timing(harness, monkeypatch):
    observations(harness, monkeypatch, [10]*7)
    outputs = iter([OUTPUT, b'result: 8\n'])
    monkeypatch.setattr(harness.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0, stdout=next(outputs), stderr=b''))
    center, digest, error, cv = harness.time_binary('arith_loop', 7, '12')
    assert center is None and digest is None
    assert error == 'output differs across runs'


@pytest.mark.parametrize('capability', ['missing', 'os_error'])
def test_unavailable_affinity_inspection_preserves_pin(harness, monkeypatch, capsys, capability):
    original = pin(harness)
    if capability == 'missing':
        monkeypatch.delattr(harness.os, 'sched_getaffinity')
    else:
        def unavailable(pid):
            raise OSError('affinity inspection denied')
        monkeypatch.setattr(harness.os, 'sched_getaffinity', unavailable)
    def forbidden(*args, **kwargs):
        pytest.fail('native boundary reached without affinity inspection')
    for name in ['zig_version', 'emit_zig', 'build_binary', 'time_binary']:
        monkeypatch.setattr(harness, name, forbidden)
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT), '--pin'])
    assert harness.main() == 2
    assert 'cannot inspect inherited CPU affinity' in capsys.readouterr().err
    assert not harness.BUILD_DIR.exists()
    assert harness.pin_path().read_bytes() == original
