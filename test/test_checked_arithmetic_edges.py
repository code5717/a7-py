"""Integer edge cases give one defined result in debug, release and fast.

Wrapping is the language semantic (L5), so `-MIN`, `MIN / -1` and
`abs(MIN)` wrap to MIN and `MIN % -1` is 0. A runtime shift count outside
the operand width panics in every profile.
"""

import pytest

from native_profiles import PROFILES, run_profile, same_output_in_every_profile

MIN_I32 = """
    m: i32 = -2147483647
    m -= 1
    d: i32 = -1
    d += 0
"""


def test_unary_minus_and_abs_of_the_minimum_wrap(tmp_path, zig):
    source = f"""
io :: import "std/io"
math :: import "std/math"
neg :: fn(v: i32) i32 {{ ret -v }}
main :: fn() {{{MIN_I32}
    io.println("{{}} {{}} {{}}", neg(m), neg(d), math.abs(m))
    io.println("{{}} {{}}", math.abs(d), math.abs(-5))
}}
"""
    assert same_output_in_every_profile(source, tmp_path, zig) == "-2147483648 1 -2147483648\n1 5\n"


def test_signed_minimum_divided_by_minus_one_wraps(tmp_path, zig):
    source = f"""
io :: import "std/io"
Acc :: struct {{ total: i32 }}
quot($T: Integer) :: fn(a: $T, b: $T) $T {{
    if b != 0 {{ ret a / b }}
    ret a
}}
main :: fn() {{{MIN_I32}
    if d != 0 {{ io.println("{{}} {{}}", m / d, m % d) }}
    if d != 0 {{ io.println("{{}} {{}}", 7 / d, 7 % d) }}
    acc: Acc
    acc.total = m
    if d != 0 {{ acc.total /= d }}
    io.println("{{}}", acc.total)
    if d != 0 {{ acc.total %= d }}
    io.println("{{}}", acc.total)
    io.println("{{}}", quot(m, d))
}}
"""
    assert same_output_in_every_profile(source, tmp_path, zig) == (
        "-2147483648 0\n-7 0\n-2147483648\n0\n-2147483648\n"
    )


def test_runtime_shift_counts_in_range(tmp_path, zig):
    # `x <<= n` did not build (count not cast), and `1 << n` and `~5` had no
    # concrete type in the emitted Zig.
    source = """
io :: import "std/io"
Reg :: struct { bits: u32 }
main :: fn() {
    x: u32 = 1
    n: u32 = 3
    n += 1
    x <<= n
    io.println("{}", x)
    x >>= n
    io.println("{}", x)
    r: Reg
    r.bits = 3
    r.bits <<= n
    io.println("{}", r.bits)
    y: i32 = 1 << n
    w := 256 >> n
    z := ~5
    io.println("{} {} {}", y, w, z)
}
"""
    assert same_output_in_every_profile(source, tmp_path, zig) == "16\n1\n48\n16 16 -6\n"


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("expression", ["a << n", "a >> n"])
def test_shift_count_at_the_bit_width_panics(tmp_path, zig, profile, expression):
    source = f"""
io :: import "std/io"
shift :: fn(a: i32, n: i32) i32 {{ ret {expression} }}
main :: fn() {{
    io.println("{{}}", shift(64, 3))
    io.println("{{}}", shift(1, 32))
    io.println("not reached")
}}
"""
    process = run_profile(source, tmp_path, zig, profile)
    assert process.returncode == -6, process.stderr
    assert "panic: shift count out of range" in process.stderr
    assert process.stdout == ("512\n" if "<<" in expression else "8\n")
