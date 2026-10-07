"""Duplicate function names conflict within one file scope."""

from __future__ import annotations

from conftest import expect_exit, expect_ok

ALREADY_DEFINED = "Already defined: Function 'f'"


def test_identical_duplicate_rejected(tmp_path):
    expect_exit("""
f :: fn() {}
f :: fn() {}
main :: fn() {}
""", tmp_path, 6, ALREADY_DEFINED)


def test_different_parameter_types_rejected(tmp_path):
    expect_exit("""
f :: fn(x: i32) i32 {
    ret x
}
f :: fn(s: string) string {
    ret s
}
main :: fn() {
    a := f(1)
    b := f("s")
}
""", tmp_path, 6, ALREADY_DEFINED)


def test_different_arity_rejected(tmp_path):
    expect_exit("""
f :: fn(x: i32) i32 {
    ret x
}
f :: fn(x: i32, y: i32) i32 {
    ret x + y
}
main :: fn() {
    a := f(1, 2)
}
""", tmp_path, 6, ALREADY_DEFINED)


def test_generic_and_concrete_same_name_rejected(tmp_path):
    expect_exit("""
f :: fn(x: $T) $T {
    ret x
}
f :: fn(x: i32) i32 {
    ret x
}
main :: fn() {
    a := f(1)
}
""", tmp_path, 6, ALREADY_DEFINED)


def test_duplicate_declared_after_a_caller_rejected(tmp_path):
    # The second `f` follows a function that already called the first one.
    expect_exit("""
f :: fn(x: i32) i32 {
    ret x
}
g :: fn() i32 {
    ret f(1)
}
f :: fn(s: string) string {
    ret s
}
main :: fn() {
    c := g()
}
""", tmp_path, 6, ALREADY_DEFINED)


def test_two_modules_exporting_one_name_keep_distinct_types(tmp_path):
    (tmp_path / "a.a7").write_text("""pub c :: fn() char {
    ret 'A'
}
""", encoding="utf-8")
    (tmp_path / "b.a7").write_text("""pub c :: fn() i32 {
    ret 7
}
""", encoding="utf-8")
    expect_ok("""io :: import "std/io"
a :: import "a"
b :: import "b"
main :: fn() {
    x: char = a.c()
    y: i32 = b.c()
    io.println("{} {}", x, y)
}
""", tmp_path)
