"""Type spelling contracts and deeply nested diagnostic rendering."""

import sys

import pytest

from a7.types import (
    ArrayType, SliceType, PointerType, ReferenceType, FunctionType,
    StructType, StructField, EnumType, UnionType, GenericParamType,
    GenericInstanceType, TypeSet, I32, I64, STRING, VOID, UNKNOWN, NUMERIC,
)


@pytest.mark.parametrize('type_,expected', [
    (ArrayType(I32, 3), '[3]i32'),
    (SliceType(ReferenceType(I32)), '[]ref i32'),
    (PointerType(ArrayType(I32, 0)), 'ptr [0]i32'),
    (FunctionType([], None), 'fn()'),
    (FunctionType([], VOID), 'fn() void'),
    (FunctionType([I32, STRING], I64), 'fn(i32, string) i64'),
    (FunctionType([], None, True), 'fn(..)'),
    (FunctionType([I32], None, True), 'fn(i32, ..)'),
    (FunctionType([], I64, True, STRING), 'fn(..string) i64'),
    (FunctionType([I32], I64, True, STRING), 'fn(i32, ..string) i64'),
    (FunctionType([], None, False, STRING), 'fn()'),
    (StructType('Box', (), ['T', 'U']), 'Box(T, U)'),
    (StructType(), 'struct {  }'),
    (StructType(fields=[StructField('value', SliceType(I32))]), 'struct { value: []i32 }'),
    (EnumType('Color'), 'Color'),
    (UnionType('Value'), 'Value'),
    (GenericParamType('T'), '$T'),
    (GenericParamType('T', NUMERIC), '$T: Numeric'),
    (GenericInstanceType('Box', [I32, STRING]), 'Box(i32, string)'),
    (TypeSet(frozenset([STRING, I32])), '@type_set(i32, string)'),
    (TypeSet(frozenset()), '@type_set()'),
    (ArrayType(UNKNOWN, 1), '[1]unknown type'),
])
def test_type_spelling(type_, expected):
    assert str(type_) == expected


def test_deep_composite_diagnostic_at_recursion_limit_100():
    type_ = I32
    prefix = []
    suffix = []
    for index in range(1500):
        choice = index % 6
        if choice == 0:
            type_ = ArrayType(type_, 2)
            prefix.append('[2]')
            suffix.append('')
        elif choice == 1:
            type_ = SliceType(type_)
            prefix.append('[]')
            suffix.append('')
        elif choice == 2:
            type_ = PointerType(type_)
            prefix.append('ptr ')
            suffix.append('')
        elif choice == 3:
            type_ = ReferenceType(type_)
            prefix.append('ref ')
            suffix.append('')
        elif choice == 4:
            type_ = GenericInstanceType('Box', [type_])
            prefix.append('Box(')
            suffix.append(')')
        else:
            type_ = StructType(fields=[StructField('item', type_)])
            prefix.append('struct { item: ')
            suffix.append(' }')
    function = FunctionType([type_], type_, True, type_)
    previous = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(100)
        result = str(function)
    finally:
        sys.setrecursionlimit(previous)
    expected = ''.join(reversed(prefix)) + 'i32' + ''.join(suffix)
    assert result == 'fn(' + expected + ', ..' + expected + ') ' + expected


def test_named_cycle_remains_a_name_and_structural_cycle_still_fails():
    named = StructType('Node')
    object.__setattr__(named, 'fields', (StructField('next', ReferenceType(named)),))
    assert str(ReferenceType(named)) == 'ref Node'
    structural = SliceType(I32)
    object.__setattr__(structural, 'element_type', structural)
    with pytest.raises(RecursionError):
        str(structural)


def test_shared_children_are_not_cycles_and_constraints_keep_sorted_spelling():
    shared = SliceType(I32)
    assert str(FunctionType([shared, shared], shared)) == 'fn([]i32, []i32) []i32'
    constraint = TypeSet(frozenset([shared, STRING]))
    assert str(GenericParamType('T', constraint)) == '$T: @type_set([]i32, string)'
