"""End-to-end pins for dot and qualified union match arms.

The validator pins live in test_match_payload.py. Every accepted program here
is compiled through the full pipeline, built with `zig build-exe` and run; a
compiler exit 0 alone does not show that the emitted switch builds. Rejected
programs pin the compiler's exit code and message.
"""

from __future__ import annotations

import pytest

from conftest import build_and_run, expect_exit, run_both_profiles

IO_IMPORT = 'io :: import "std/io"\n'

RESULT_UNION = """
Outcome :: union(tag) {
    ok: i32
    err: i32
}
"""

GENERIC_UNION = """
Outcome :: union(tag) {
    ok: $T,
    err: $E,
}
"""


def run(source: str, tmp_path, zig: str) -> str:
    process = build_and_run(source, tmp_path, zig)
    assert process.returncode == 0, process.stderr
    return process.stdout


class TestDotArms:
    def test_payload_binds_the_active_field(self, tmp_path, zig):
        out = run(IO_IMPORT + RESULT_UNION + """
        show :: fn(r: Outcome) {
            match r {
                case .ok(v): {
                    x: i32 = v + 1
                    io.println("ok {}", x)
                }
                case .err(e): {
                    io.println("err {}", e)
                }
            }
        }
        main :: fn() {
            show(Outcome{ok: 41})
            show(Outcome{err: 7})
        }
        """, tmp_path, zig)
        assert out == "ok 42\nerr 7\n"

    def test_bare_dot_tag_tests_without_binding(self, tmp_path, zig):
        out = run(IO_IMPORT + """
        Shape :: union(tag) { circle: f32, none: bool }

        is_none :: fn(s: Shape) bool {
            ret match s {
                case .none: true
                else: false
            }
        }

        main :: fn() {
            io.println("{} {}", is_none(Shape{none: true}), is_none(Shape{circle: 1.0}))
        }
        """, tmp_path, zig)
        assert out == "true false\n"

    def test_generic_union_match_expression(self, tmp_path, zig):
        out = run(IO_IMPORT + GENERIC_UNION + """
        main :: fn() {
            r := Outcome(i32, bool){ok: 7}
            out := match r {
                case .ok(v): v + 1
                case .err(e): if e { 100 } else { 0 }
            }
            io.println("{}", out)
        }
        """, tmp_path, zig)
        assert out == "8\n"


class TestFullCoverage:
    """Zig rejects an `else` prong once every tag has a prong."""

    def test_qualified_arms_cover_every_tag(self, tmp_path, zig):
        out = run_both_profiles(IO_IMPORT + RESULT_UNION + """
        show :: fn(r: Outcome) {
            match r {
                case Outcome.ok: {
                    io.println("ok")
                }
                case Outcome.err: {
                    io.println("err")
                }
            }
        }
        main :: fn() {
            show(Outcome{ok: 1})
            show(Outcome{err: 1})
        }
        """, tmp_path, zig)
        assert out == "ok\nerr\n"

    def test_explicit_else_after_full_coverage(self, tmp_path, zig):
        """The A7 `else` can never run. Its body still names `extra` and
        `fallback`, which Zig must not report as unused."""
        out = run_both_profiles(IO_IMPORT + RESULT_UNION + """
        pick :: fn(r: Outcome, fallback: i32) i32 {
            ret match r {
                case .ok(v): v
                case .err(e): e
                else: fallback
            }
        }
        main :: fn() {
            r := Outcome{err: 5}
            extra := 9
            match r {
                case .ok(v): { io.println("ok {}", v) }
                case .err(e): { io.println("err {}", e) }
                else: { io.println("never {}", extra) }
            }
            match r {
                case Outcome.ok: { io.println("ok") }
                case Outcome.err: { io.println("err") }
                else: { io.println("never") }
            }
            io.println("{}", pick(r, 0))
        }
        """, tmp_path, zig)
        assert out == "err 5\nerr\n5\n"


class TestWildcardArm:
    def test_wildcard_beside_dot_arm(self, tmp_path, zig):
        out = run_both_profiles(IO_IMPORT + RESULT_UNION + """
        show :: fn(r: Outcome) {
            match r {
                case .ok(v): { io.println("ok {}", v) }
                case _: { io.println("other") }
            }
        }
        code :: fn(r: Outcome) i32 {
            ret match r {
                case .err(e): e
                case _: 0
            }
        }
        main :: fn() {
            show(Outcome{err: 4})
            show(Outcome{ok: 2})
            io.println("{} {}", code(Outcome{err: 4}), code(Outcome{ok: 2}))
        }
        """, tmp_path, zig)
        assert out == "other\nok 2\n4 0\n"


SHADOW_LOCAL = IO_IMPORT + RESULT_UNION + """
main :: fn() {
    r := Outcome{err: 4}
    e: i32 = 100
    match r {
        case .ok(v): { io.println("ok {}", v) }
        case .err(e): { io.println("err {}", e) }
    }
    io.println("{}", e)
}
"""

SHADOW_PARAMETER = IO_IMPORT + RESULT_UNION + """
show :: fn(r: Outcome, v: i32) {
    match r {
        case .ok(v): { io.println("ok {}", v) }
        case .err(e): { io.println("err {}", e) }
    }
    io.println("{}", v)
}
main :: fn() {
    show(Outcome{ok: 4}, 7)
}
"""

SHADOW_FUNCTION = IO_IMPORT + RESULT_UNION + """
v :: fn() i32 {
    ret 9
}
main :: fn() {
    r := Outcome{ok: 4}
    match r {
        case .ok(v): { io.println("ok {}", v) }
        case .err(e): { io.println("err {}", e) }
    }
    io.println("{}", v())
}
"""

SHADOW_IN_EXPRESSION = IO_IMPORT + RESULT_UNION + """
main :: fn() {
    r := Outcome{ok: 4}
    v: i32 = 100
    n := match r {
        case .ok(v): v + 1
        case .err(e): e
    }
    io.println("{} {}", n, v)
}
"""


class TestPayloadCapture:
    @pytest.mark.parametrize("source, expected", [
        (SHADOW_LOCAL, "err 4\n100\n"),
        (SHADOW_PARAMETER, "ok 4\n7\n"),
        (SHADOW_FUNCTION, "ok 4\n9\n"),
        (SHADOW_IN_EXPRESSION, "5 100\n"),
    ], ids=["local", "parameter", "function", "local-in-expression"])
    def test_capture_named_like_an_outer_binding(self, tmp_path, zig, source, expected):
        """Zig rejects a capture that shadows a local, a parameter or a
        declaration. The arm reads the payload; the outer name is unchanged
        after the match."""
        assert run_both_profiles(source, tmp_path, zig) == expected

    def test_unused_capture_in_match_expression(self, tmp_path, zig):
        """Zig rejects an unused capture."""
        out = run_both_profiles(IO_IMPORT + RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 4}
            n := match r {
                case .ok(v): 1
                case .err(e): 0
            }
            io.println("{}", n)
        }
        """, tmp_path, zig)
        assert out == "1\n"


class TestKeywordNames:
    """`error` and `type` are Zig keywords; patterns quote them as
    declarations do."""

    def test_union_tags(self, tmp_path, zig):
        out = run_both_profiles(IO_IMPORT + """
        Shape :: union(tag) {
            type: f64
            error: i32
        }
        show :: fn(s: Shape) {
            match s {
                case .type(t): { io.println("t {}", t) }
                case .error(e): { io.println("e {}", e) }
            }
        }
        main :: fn() {
            show(Shape{error: 3})
            show(Shape{type: 1.5})
        }
        """, tmp_path, zig)
        assert out == "e 3\nt 1.5\n"

    def test_enum_variants(self, tmp_path, zig):
        """Full coverage takes the switch; the second match has a capture
        arm, so it takes the if-chain comparison."""
        out = run_both_profiles(IO_IMPORT + """
        Kind :: enum { error, type, Plain }
        name :: fn(k: Kind) {
            match k {
                case Kind.error: { io.println("error") }
                case Kind.type: { io.println("type") }
                case Kind.Plain: { io.println("plain") }
            }
            match k {
                case Kind.error: { io.println("is error") }
                case other: { io.println("not error") }
            }
        }
        main :: fn() {
            name(Kind.error)
            name(Kind.type)
        }
        """, tmp_path, zig)
        assert out == "error\nis error\ntype\nnot error\n"


class TestRejected:
    def test_partial_dot_coverage_lists_missing(self, tmp_path):
        expect_exit(IO_IMPORT + RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case .ok(v): {
                    io.println("ok {}", v)
                }
            }
        }
        """, tmp_path, 6, "misses tag(s): err")

    def test_payload_binding_mistyped_use(self, tmp_path):
        expect_exit(IO_IMPORT + RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case .ok(v): {
                    s: string = v
                    io.println(s)
                }
                case .err(e): {
                    io.println("{}", e)
                }
            }
        }
        """, tmp_path, 6, "expected 'string', got 'i32'")

    def test_unknown_tag(self, tmp_path):
        expect_exit(IO_IMPORT + RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case .bogus: {
                    io.println("no")
                }
                else: {
                    io.println("other")
                }
            }
        }
        """, tmp_path, 6, "no tag 'bogus'")

    def test_bare_arm_reports_tag_failure(self, tmp_path):
        expect_exit(IO_IMPORT + RESULT_UNION + """
        main :: fn() {
            r := Outcome{ok: 1}
            match r {
                case ok: {
                    io.println("ok")
                }
                else: {
                    io.println("other")
                }
            }
        }
        """, tmp_path, 6, "never tests the tag")
