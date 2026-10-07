"""Each lexical type-alias declaration has its own resolution state."""

import pytest
from conftest import expect_exit, expect_ok


@pytest.mark.parametrize('prefix', ['A :: i32;', 'A :: i32; { A :: u8;'])
def test_shadowed_alias_rejects_wrong_initializer(tmp_path, prefix):
    suffix = '}' if '{' in prefix else ''
    source = 'main :: fn(){' + prefix + '{ A :: i64; x:A="bad" }' + suffix + '}'
    expect_exit(source, tmp_path, 6, "expected 'i64', got 'string'")


def test_same_named_aliases_in_independent_functions_and_sibling_scopes(tmp_path):
    expect_ok('''
io :: import "std/io"
first :: fn() { A :: i32; x:A=1; io.println("{}",x) }
second :: fn() { A :: i64; x:A=2147483648; io.println("{}",x) }
main :: fn(){
    A :: i32
    { A :: i64; x:A=2147483648; io.println("{}",x) }
    { A :: string; x:A="ok"; io.println("{}",x) }
    x:A=1
    first(); second(); io.println("{}",x)
}
''', tmp_path)


def test_independent_function_alias_does_not_skip_type_error(tmp_path):
    expect_exit('''
first :: fn() { A :: i32; x:A=1 }
second :: fn() { A :: i64; x:A="bad" }
main :: fn(){ first(); second() }
''', tmp_path, 6, "expected 'i64', got 'string'")
