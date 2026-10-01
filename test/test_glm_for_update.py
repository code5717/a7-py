"""A7 loop update statements discard results without changing control flow."""
import sys
from pathlib import Path

import pytest

# test/ is not a package, so import the shared runtime helper by path,
# matching test_untyped_constants_acceptance.py:16-19.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_zig_backend_runtime import build, compile_with_cli, run_piped, zig, zig_cache  # noqa: E402,F401

@pytest.mark.parametrize("profile", ["Debug", "ReleaseFast"])
@pytest.mark.parametrize("step", [
    'step :: fn() i32 { io.println("step"); ret 1 }',
    'step :: fn() { io.println("step") }',
])
def test_for_update_call_result_and_control_flow(tmp_path, zig, zig_cache, profile, step):
    source = '''io :: import "std/io"
''' + step + '''
main :: fn() {
    i: i32 = 0
    for i = 0; i < 4; step() {
        io.println("body {}", i)
        i += 1
        if i == 1 { continue }
        if i == 3 { break }
    }
    io.println("done")
}
'''
    output = compile_with_cli(tmp_path, source)
    binary = build(zig, zig_cache, tmp_path, output, profile)
    assert run_piped(binary) == ("body 0\nstep\nbody 1\nstep\nbody 2\ndone\n", "")
