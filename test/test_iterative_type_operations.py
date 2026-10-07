"""Dataclass type diagnostics retain their spelling without Python recursion."""

import sys
from dataclasses import dataclass, field

import pytest

from a7.types import (
    ArrayType, FunctionType, GenericInstanceType, I32, ReferenceType,
    SliceType, StructField, StructType, TypeSet, PrimitiveType,
)
from conftest import low_recursion_limit


@pytest.mark.parametrize('value, expected', [
    (ArrayType(I32, 2), "ArrayType(kind=<TypeKind.ARRAY: 2>, element_type=PrimitiveType(kind=<TypeKind.PRIMITIVE: 1>, name='i32'), size=2, size_param=None)"),
    (FunctionType([I32]), "FunctionType(kind=<TypeKind.FUNCTION: 6>, param_types=(PrimitiveType(kind=<TypeKind.PRIMITIVE: 1>, name='i32'),), return_type=None, is_variadic=False, variadic_type=None, generic_param_order=())"),
    (TypeSet(frozenset()), "TypeSet(kind=<TypeKind.TYPE_SET: 12>, types=frozenset(), name=None)"),
    (TypeSet(frozenset([I32]), 'N'), "TypeSet(kind=<TypeKind.TYPE_SET: 12>, types=frozenset({PrimitiveType(kind=<TypeKind.PRIMITIVE: 1>, name='i32')}), name='N')"),
])
def test_type_repr_preserves_dataclass_spelling(value, expected):
    assert repr(value) == expected


def test_mixed_repr_at_depth_1800_and_recursion_limit_100():
    value = I32
    for _ in range(600):
        value = ReferenceType(SliceType(ArrayType(value, 2)))
    prefix = ('ReferenceType(kind=<TypeKind.REFERENCE: 5>, referent_type='
              'SliceType(kind=<TypeKind.SLICE: 3>, element_type='
              'ArrayType(kind=<TypeKind.ARRAY: 2>, element_type=')
    expected = prefix * 600 + "PrimitiveType(kind=<TypeKind.PRIMITIVE: 1>, name='i32')" + ', size=2, size_param=None)))' * 600
    previous = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(low_recursion_limit())
        assert repr(value) == expected
    finally:
        sys.setrecursionlimit(previous)


def test_deep_records_signatures_and_instances_keep_leaf_diagnostic():
    left, right = I32, PrimitiveType('different_leaf')
    for _ in range(400):
        left = GenericInstanceType('Box', [FunctionType([StructType(fields=[StructField('item', left)])])])
        right = GenericInstanceType('Box', [FunctionType([StructType(fields=[StructField('item', right)])])])
    previous = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(low_recursion_limit())
        result = repr(left)
        assert result.count("base_name='Box'") == 400
        assert result.count("StructField(name='item'") == 400
        assert result.count('FunctionType(') == 400
        assert repr(right) == result.replace("name='i32'", "name='different_leaf'")
    finally:
        sys.setrecursionlimit(previous)


def test_named_cycle_and_shared_children_preserve_cycle_markers():
    node = StructType('Node')
    object.__setattr__(node, 'fields', (StructField('next', ReferenceType(node)),))
    assert repr(node) == "StructType(kind=<TypeKind.STRUCT: 7>, name='Node', fields=(StructField(name='next', field_type=ReferenceType(kind=<TypeKind.REFERENCE: 5>, referent_type=...)),), generic_params=())"
    shared = SliceType(I32)
    assert repr(FunctionType([shared, shared])).count('SliceType(') == 2
    assert '...' not in repr(FunctionType([shared, shared]))


def test_inherited_repr_omits_hidden_fields_and_honors_leaf_overrides():
    @dataclass(frozen=True, repr=False)
    class HiddenSlice(SliceType):
        hidden: int = field(default=7, repr=False)

    value = HiddenSlice(kind=I32.kind, element_type=I32)
    assert repr(value).startswith(value.__class__.__qualname__ + '(')
    assert 'hidden=' not in repr(value)

    class CustomPrimitive(PrimitiveType):
        def __repr__(self):
            return '<custom-leaf>'

    assert repr(SliceType(CustomPrimitive('custom'))) == 'SliceType(kind=<TypeKind.SLICE: 3>, element_type=<custom-leaf>)'


def test_repr_exception_does_not_leave_false_cycle_markers():
    class BrokenPrimitive(PrimitiveType):
        def __repr__(self):
            raise ValueError('fixture repr failed')

    value = SliceType(BrokenPrimitive('broken'))
    with pytest.raises(ValueError, match='fixture repr failed'):
        repr(value)
    object.__setattr__(value, 'element_type', I32)
    assert '...' not in repr(value)


def test_deep_union_constraints_and_type_sets_render_the_leaf():
    from a7.types import GenericParamType, UnionField, UnionType

    value = I32
    for _ in range(400):
        value = UnionType('U', [UnionField('item', GenericParamType('T', TypeSet(frozenset([value]))))])
    previous = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(low_recursion_limit())
        result = repr(value)
    finally:
        sys.setrecursionlimit(previous)
    assert result.count('UnionType(') == 400
    assert result.count('GenericParamType(') == 400
    assert result.count('types=frozenset({') == 400
    assert result.count("name='i32'") == 1
    assert '...' not in result


def test_custom_leaf_reentering_parent_uses_existing_cycle_marker():
    class ParentRepr(PrimitiveType):
        def __repr__(self):
            return 'parent=' + repr(parent)

    parent = SliceType(ParentRepr('custom'))
    assert repr(parent) == 'SliceType(kind=<TypeKind.SLICE: 3>, element_type=parent=...)'


def test_repr_false_subclass_inherits_only_declaring_class_fields():
    from a7.types import TypeKind

    @dataclass(frozen=True, repr=False)
    class Extended(SliceType):
        extra: int = 7

    value = Extended(kind=TypeKind.SLICE, element_type=I32)
    expected = value.__class__.__qualname__ + "(kind=<TypeKind.SLICE: 3>, element_type=PrimitiveType(kind=<TypeKind.PRIMITIVE: 1>, name='i32'))"
    assert repr(value) == expected
    assert repr(ReferenceType(value)) == 'ReferenceType(kind=<TypeKind.REFERENCE: 5>, referent_type=' + expected + ')'


def test_repr_reads_later_fields_after_rendering_earlier_fields():
    class Mutator(PrimitiveType):
        def __repr__(self):
            object.__setattr__(parent, 'size', 9)
            return '<changed>'

    parent = ArrayType(Mutator('x'), 2)
    assert repr(parent) == 'ArrayType(kind=<TypeKind.ARRAY: 2>, element_type=<changed>, size=9, size_param=None)'
