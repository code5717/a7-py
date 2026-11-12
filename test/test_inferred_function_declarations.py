"""Inferred callable bindings retain runtime pointer and generic alias behavior."""

import pytest

from conftest import build_and_run


CASES = [
    (
        "direct_reassignment",
        '''
io :: import "std/io"
first :: fn(x: i32) i32 { ret x + 1 }
second :: fn(x: i32) i32 { ret x + 2 }
main :: fn() { f := first; f = second; io.println("{}", f(40)) }
''',
        "42\n",
    ),
    (
        "reference_slot_replacement",
        '''
io :: import "std/io"
first :: fn(x: i32) i32 { ret x + 1 }
second :: fn(x: i32) i32 { ret x + 2 }
replace :: fn(slot: ref fn(i32) i32) { if slot != nil { slot = second } }
main :: fn() { f := first; replace(f); io.println("{}", f(40)) }
''',
        "42\n",
    ),
    (
        "saved_alias_keeps_original_target",
        '''
io :: import "std/io"
first :: fn(x: i32) i32 { ret x + 1 }
second :: fn(x: i32) i32 { ret x + 2 }
main :: fn() {
    f := first
    saved := f
    f = second
    io.println("{} {}", saved(40), f(40))
}
''',
        "41 42\n",
    ),
    (
        "generic_alias_stays_comptime",
        '''
io :: import "std/io"
identity :: fn(x: $T) $T { ret x }
main :: fn() {
    alias := identity
    small: i8 = 42
    io.println("{} {}", alias(small), alias("ok"))
}
''',
        "42 ok\n",
    ),
    (
        "concrete_reference_signature",
        '''
io :: import "std/io"
increment :: fn(x: ref i32) { if x != nil { x += 1 } }
main :: fn() { f := increment; n: i32 = 41; f(n); io.println("{}", n) }
''',
        "42\n",
    ),
]


@pytest.mark.parametrize("profile", ["debug", "release", "fast"])
@pytest.mark.parametrize("name,source,stdout", CASES, ids=[case[0] for case in CASES])
def test_inferred_function_declaration_native(name, source, stdout, profile, tmp_path, zig):
    result = build_and_run(source, tmp_path, zig, profile=profile)
    assert result.returncode == 0, result.stderr
    assert result.stdout == stdout
    assert result.stderr == ""
