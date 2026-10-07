"""Inferred types must not consume one Python frame per nested container."""

import sys

from a7.backends.zig import ZigCodeGenerator
from a7.types import ArrayType, FunctionType, GenericInstanceType, I32, ReferenceType, SliceType, U8


def test_deep_inferred_array_emission_has_constant_python_stack():
    type_ = I32
    for _ in range(2000):
        type_ = ArrayType(type_, 1)
    generator = ZigCodeGenerator()
    previous = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(100)
        result = generator._emit_semantic_type(type_)
    finally:
        sys.setrecursionlimit(previous)
    assert result == "[1]" * 2000 + "i32"


def test_function_and_generic_arguments_keep_their_order_and_return_type():
    type_ = FunctionType(
        [ReferenceType(GenericInstanceType("Box", [I32])), SliceType(U8)],
        ArrayType(I32, 4),
    )
    assert ZigCodeGenerator()._emit_semantic_type(type_) == "*const fn (?*Box(i32), []u8) [4]i32"


def test_function_without_a_result_emits_void():
    assert ZigCodeGenerator()._emit_semantic_type(FunctionType([])) == "*const fn () void"
