"""Pin cut surface for variadics, destructuring, and multi-return.

Track 5 default: these forms are not runnable. Variadics parse then exit 6.
Destructuring and multi-return spellings exit 5 with an explicit cut message.
"""

from __future__ import annotations

from pipeline_helpers import (  # noqa: F401
    expect_error,
    expect_parse_error,
    pipeline_tmp,
)


class TestVariadicCut:
    def test_typed_variadic_parameter_exits_semantic(self):
        source = """
        sum :: fn(values: ..i32) i32 {
            ret 0
        }

        main :: fn() {
            _ := sum(1, 2)
        }
        """
        assert expect_error(source, "Variadic parameters are not supported")

    def test_untyped_variadic_with_prefix_exits_semantic(self):
        source = """
        printf :: fn(format: string, args: ..) {}
        main :: fn() {
            printf("x", 1)
        }
        """
        assert expect_error(source, "Variadic parameters are not supported")


class TestDestructuringCut:
    def test_inferred_multi_decl_exits_parse(self):
        source = """
        main :: fn() {
            a, b := 1, 2
        }
        """
        assert expect_parse_error(
            source,
            "Multiple-declaration and destructuring binding are not supported",
        )

    def test_typed_multi_decl_exits_parse(self):
        source = """
        main :: fn() {
            a, b: i32 = 1, 2
        }
        """
        assert expect_parse_error(
            source,
            "Multiple-declaration and destructuring binding are not supported",
        )


class TestMultiReturnCut:
    def test_tuple_return_type_exits_parse(self):
        source = """
        pair :: fn() (i32, i32) {
            ret 1
        }
        main :: fn() {}
        """
        assert expect_parse_error(
            source,
            "Multiple return values are not supported",
        )

    def test_multi_value_ret_exits_parse(self):
        source = """
        pair :: fn() i32 {
            ret 1, 2
        }
        main :: fn() {}
        """
        assert expect_parse_error(
            source,
            "Multiple return values are not supported",
        )
