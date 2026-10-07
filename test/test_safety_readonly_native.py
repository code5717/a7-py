"""Valid readonly call paths preserve observable values across native profiles."""
import pytest
from native_profiles import PROFILES, run_profile

SOURCE = '''
io :: import "std/io"
Box :: struct { x: i32 }
guarded :: fn(r: ref Box) i32 {
    i: usize = 0
    for i = 0; i < 1; i += 1 {}
    if r == nil { ret 11 }
    ret r.x
}
counter :: fn(r: ref Box) usize {
    i: usize = 0
    for i = 0; i < 1; i += 1 {}
    if i == 0 { value := r.x }
    ret i
}
selected :: fn(r: ref Box, flag: bool) i32 {
    i: usize = 0
    for i = 0; i < 1; i += 1 {}
    if flag { ret r.x }
    ret 17
}
forward :: fn(r: ref Box, flag: bool) i32 { ret selected(r, flag) }
read :: fn(r: ref Box) i32 {
    i: usize = 0
    for i = 0; i < 2; i += 1 { value := r.x }
    ret r.x
}
main :: fn() {
    io.println("{}", guarded(nil))
    io.println("{}", counter(nil))
    io.println("{}", forward(nil, false))
    stack := Box { x: 23 }
    io.println("{}", read(stack))
    fresh := new Box
    if fresh == nil { ret }
    fresh.x = 29
    io.println("{}", read(fresh))
    del fresh
}
'''


@pytest.mark.zig
@pytest.mark.parametrize('profile', PROFILES)
def test_valid_readonly_paths_native(tmp_path, zig, profile):
    result = run_profile(SOURCE, tmp_path, zig, profile)
    assert (result.returncode, result.stdout, result.stderr) == (0, '11\n1\n17\n23\n29\n', '')
