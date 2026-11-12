"""Inferred slice slots retain slice representation through native mutation."""

import pytest

from conftest import build_and_run

CASES = [
    (
        "reference_replacement_preserves_elements",
        '''
io :: import "std/io"
replace :: fn(slot: ref []i32, next: []i32) { if slot != nil { slot = next } }
main :: fn() {
    first: [2]i32 = [11, 12]
    next: [3]i32 = [21, 22, 23]
    state := first[0..2]
    io.println("{} {}", state.len, state[0])
    replace(state, next[0..3])
    if state.len != 3 { io.println("unexpected length"); ret }
    zero: usize = 0
    last: usize = 2
    if zero < state.len {
        if last < state.len { io.println("{} {} {}", state.len, state[zero], state[last]) } else { io.println("unexpected bounds") }
    } else { io.println("unexpected bounds") }
}
''',
        "2 11\n3 21 23\n",
    ),
    (
        "direct_different_length_reassignment",
        '''
io :: import "std/io"
main :: fn() {
    backing: [3]i32 = [7, 8, 9]
    state := backing[0..3]
    state = backing[1..2]
    io.println("{} {}", state.len, state[0])
}
''',
        "1 8\n",
    ),
    (
        "immutable_slice",
        '''
io :: import "std/io"
main :: fn() {
    backing: [2]i32 = [31, 32]
    state :: backing[0..2]
    io.println("{} {} {}", state.len, state[0], state[1])
}
''',
        "2 31 32\n",
    ),
    (
        "instantiated_generic_elements",
        '''
io :: import "std/io"
show :: fn(seed: $T) {
    backing: [2]$T = [seed, seed]
    state := backing[0..2]
    saved :: backing[0..2]
    state = backing[0..1]
    io.println("{} {} {} {}", state.len, state[0], saved.len, saved[1])
}
main :: fn() { n: i8 = 42; show(n) }
''',
        "1 42 2 42\n",
    ),
    (
        "inferred_string_view_keeps_const_backing",
        '''
io :: import "std/io"
main :: fn() {
    text: string = "abcd"
    state := text[1..3]
    io.println("{} {} {}", state.len, state[0], state[1])
}
''',
        "2 b c\n",
    ),
    (
        "explicit_slice_annotation",
        '''
io :: import "std/io"
main :: fn() {
    backing: [2]i32 = [51, 52]
    state: []i32 = backing[0..2]
    state = backing[1..2]
    io.println("{} {}", state.len, state[0])
}
''',
        "1 52\n",
    ),
    (
        "immutable_alias_to_reference_slot",
        '''
io :: import "std/io"
replace :: fn(slot: ref []i32, next: []i32) { if slot != nil { slot = next } }
main :: fn() {
    backing: [3]i32 = [11, 12, 13]
    view :: backing[0..3]
    state := view
    replace(state, backing[1..2])
    if state.len != 1 { io.println("unexpected length"); ret }
    zero: usize = 0
    if zero < state.len { io.println("{} {} {}", view.len, state.len, state[zero]) } else { io.println("unexpected bounds") }
}
''',
        "3 1 12\n",
    ),
    (
        "slice_of_slice_to_reference_slot",
        '''
io :: import "std/io"
replace :: fn(slot: ref []i32, next: []i32) { if slot != nil { slot = next } }
main :: fn() {
    backing: [3]i32 = [21, 22, 23]
    view := backing[0..3]
    state := view[1..3]
    replace(state, backing[0..1])
    if state.len != 1 { io.println("unexpected length"); ret }
    zero: usize = 0
    if zero < state.len { io.println("{} {}", state.len, state[zero]) } else { io.println("unexpected bounds") }
}
''',
        "1 21\n",
    ),
    (
        "string_alias_preserves_const_backing",
        '''
io :: import "std/io"
main :: fn() {
    text: string = "abcd"
    view :: text[1..4]
    state := view
    state = text[0..2]
    io.println("{} {} {}", view.len, state.len, state[1])
}
''',
        "3 2 b\n",
    ),
    (
        "effectful_slice_initializer_runs_once",
        '''
io :: import "std/io"
view :: fn(items: []i32, calls: ref i32) []i32 {
    if calls != nil { calls += 1 }
    ret items
}
main :: fn() {
    backing: [2]i32 = [41, 42]
    calls: i32 = 0
    state := view(backing[0..2], calls)
    saved :: view(backing[0..1], calls)
    if saved.len != 1 { io.println("unexpected length"); ret }
    zero: usize = 0
    if zero < saved.len { io.println("{} {} {} {}", calls, state.len, saved.len, saved[zero]) } else { io.println("unexpected bounds") }
}
''',
        "2 2 1 41\n",
    ),
    (
        "conditional_slice_join",
        '''
io :: import "std/io"
show :: fn(flag: bool, expected: usize) {
    backing: [3]i32 = [51, 52, 53]
    state := if flag { backing[0..1] } else { backing[1..3] }
    if state.len != expected { io.println("unexpected length"); ret }
    zero: usize = 0
    if zero < state.len { io.println("{} {}", state.len, state[zero]) } else { io.println("unexpected bounds") }
}
main :: fn() { show(true, 1); show(false, 2) }
''',
        "1 51\n2 52\n",
    ),
    (
        "empty_returned_slice",
        '''
io :: import "std/io"
empty :: fn() []i32 { result: []i32; ret result }
main :: fn() { state := empty(); io.println("{}", state.len) }
''',
        "0\n",
    ),
]


@pytest.mark.parametrize("profile", ["debug", "release", "fast"])
@pytest.mark.parametrize("name,source,stdout", CASES, ids=[case[0] for case in CASES])
def test_inferred_slice_declaration_native(name, source, stdout, profile, tmp_path, zig):
    result = build_and_run(source, tmp_path, zig, profile=profile)
    assert result.returncode == 0, result.stderr
    assert result.stdout == stdout
    assert result.stderr == ""


REPRESENTATION_SOURCE = '''
io :: import "std/io"
main :: fn() {
    backing: [2]i32 = [61, 62]
    array_view :: backing[0..2]
    text: string = "ab"
    string_view :: text[0..2]
    io.println("{} {} {} {}", array_view.len, array_view[0], string_view.len, string_view[1])
}
'''


@pytest.mark.parametrize("profile", ["debug", "release", "fast"])
def test_immutable_slice_backend_representation(profile, tmp_path, zig):
    """A Zig-only assertion checks emitted storage type, without changing A7 syntax."""
    import re
    import subprocess
    from pathlib import Path

    from conftest import ZIG_MODE, expect_ok, shared_zig_cache

    result = expect_ok(REPRESENTATION_SOURCE, tmp_path, profile=profile)
    emitted = Path(result.output_path).read_text()
    for name, is_const, element in [("array_view", "false", "i32"), ("string_view", "true", "u8")]:
        assertion = (
            f"    comptime {{ if (@typeInfo(@TypeOf({name})).pointer.size != .slice) "
            f'@compileError("{name} must be a slice"); '
            f"if (@typeInfo(@TypeOf({name})).pointer.is_const != {is_const}) "
            f'@compileError("{name} backing constness changed"); '
            f"if (@typeInfo(@TypeOf({name})).pointer.child != {element}) "
            f'@compileError("{name} element type changed"); }}\n'
        )
        emitted, count = re.subn(
            rf"(^[ \t]*const {name}[^\n]*;\n)",
            lambda match: match.group(1) + assertion,
            emitted,
            flags=re.MULTILINE,
        )
        assert count == 1, name
    checked = tmp_path / f"representation-{profile}.zig"
    checked.write_text(emitted)
    cache = shared_zig_cache()
    binary = tmp_path / f"representation-{profile}"
    build = subprocess.run(
        [zig, "build-exe", str(checked), "-O", ZIG_MODE[profile],
         "--cache-dir", str(cache / "local"),
         "--global-cache-dir", str(cache / "global"),
         "-femit-bin=" + str(binary)],
        capture_output=True, text=True,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    assert build.stderr == ""
    run = subprocess.run([str(binary)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout == "2 61 2 b\n"
    assert run.stderr == ""
