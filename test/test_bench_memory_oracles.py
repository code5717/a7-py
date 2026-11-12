"""Real small subprocesses verify stdin and output contracts, not A7 performance."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    'mem_cache': b'result: 6616666665 49999999 50000001\n',
    'mem_copy': b'result: 942376503\n',
    'mem_text': b'result: 98811553\n',
    'mem_cyclic': b'result: 757942091\n',
}


@pytest.fixture
def bench(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('memory_oracles', ROOT / 'scripts/bench_perf.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = tmp_path
    module.BUILD_DIR = tmp_path / 'build'
    module.BUILD_DIR.mkdir()
    module.PINS_DIR = tmp_path / 'pins'
    ticks = iter(range(1000))
    monkeypatch.setattr(module.time, 'perf_counter', lambda: next(ticks))
    return module


@pytest.mark.parametrize('name', EXPECTED)
def test_actual_child_input_and_exact_output(bench, name):
    output = EXPECTED[name]
    child = bench.BUILD_DIR / (name + '_fast')
    child.write_text(
        f'#!{sys.executable}\nimport sys\n'
        'received = sys.stdin.buffer.read()\n'
        'if received != b"A\\n": sys.exit(23)\n'
        + f'sys.stdout.buffer.write({output!r})\n'
    )
    child.chmod(0o755)
    assert bench.time_binary(name, 5) == (
        1, hashlib.sha256(output).hexdigest(), '', 0,
    )


@pytest.mark.parametrize('behavior,output,exit_code,stderr', [
    ('wrong_number', b'result: 0\n', 0, ''),
    ('input_failure', b'input failed\n', 0, ''),
    ('stderr', EXPECTED['mem_copy'], 0, 'unexpected diagnostic'),
    ('nonzero_exit', b'', 4, ''),
])
def test_invalid_output_cannot_replace_pin(
    bench, monkeypatch, capsys, behavior, output, exit_code, stderr,
):
    bench.PINS_DIR.mkdir()
    bench.pin_path().write_bytes(b'preserved original pin\n')
    child = bench.BUILD_DIR / 'mem_copy_fast'
    child.write_text(
        f'#!{sys.executable}\nimport sys\nassert sys.stdin.buffer.read()==b"A\\n"\n'
        + f'sys.stdout.buffer.write({output!r})\n'
        + f'sys.stderr.write({stderr!r})\n'
        + f'sys.exit({exit_code})\n'
    )
    child.chmod(0o755)
    monkeypatch.setattr(bench, 'BENCHES', ['mem_copy'])
    monkeypatch.setattr(bench, 'emit_zig', lambda name: (True, ''))
    monkeypatch.setattr(bench, 'build_binary', lambda name: (True, ''))
    monkeypatch.setattr(bench, 'zig_version', lambda: 'controlled child')
    monkeypatch.setattr(sys, 'argv', ['bench_perf.py', '--pin'])
    assert bench.main() == 1
    assert bench.pin_path().read_bytes() == b'preserved original pin\n'
    error = 'run exited 4:' if exit_code else 'memory workload output differs from the seed A oracle'
    assert f'FAIL mem_copy: {error}' in capsys.readouterr().out


def test_historical_ten_entry_pin_is_incomplete_for_seventeen_workloads(bench, monkeypatch, capsys):
    old = ['arith_loop', 'alloc_churn', 'print_lines', 'array_walk', 'vector_ops',
           'sort_load', 'aos_walk', 'soa_walk', 'stride_walk', 'kv_append',
           'mem_shared', 'mem_returned', 'mem_cleanup']
    assert bench.BENCHES == old + list(EXPECTED)
    bench.PINS_DIR.mkdir()
    original = (json.dumps({name: {'release': 1.0, 'output_sha256': 'fixture-hash'}
                           for name in old[:10]}) + '\n').encode()
    bench.pin_path().write_bytes(original)
    def forbidden(*args):
        pytest.fail('gate reached build boundary with incomplete pin')
    monkeypatch.setattr(bench, 'zig_version', forbidden)
    monkeypatch.setattr(sys, 'argv', ['bench_perf.py', '--gate'])
    assert bench.main() == 1
    error = capsys.readouterr().err
    assert error.endswith('mem_shared, mem_returned, mem_cleanup, mem_cache, mem_copy, mem_text, mem_cyclic\n')
    assert bench.pin_path().read_bytes() == original
