"""Type relation contracts, legacy shallow results, and deep Python operations."""

import sys

import pytest

import a7.types as t


def shallow_cases(m):
    """A fixed corpus with named, structural, signature, and constraint changes."""
    field = m.StructField('x', m.I32)
    named = m.StructType('S', [field])
    altered = m.StructType('S', [m.StructField('y', m.I64)])
    return [
        m.I32, m.I64, m.UNKNOWN, m.UnknownType(), m.VOID,
        m.ArrayType(m.I32, 2), m.ArrayType(m.I32, 3), m.SliceType(m.I32),
        m.PointerType(m.I32), m.ReferenceType(m.I32),
        m.FunctionType([m.I32], m.I64),
        m.FunctionType([m.I32], m.I64, True, m.STRING),
        m.FunctionType([m.I32], m.I64, generic_param_order=['T']),
        m.FunctionType([m.I32]), m.FunctionType([m.I32], m.VOID),
        named, altered, m.StructType(None, [field]),
        m.StructType('Other', [field]), m.StructType(None, [field], ['T']),
        m.EnumType('E', [m.EnumVariant('a', 0)]), m.EnumType('E'),
        m.UnionType('U', [m.UnionField('x', m.I32)]), m.UnionType('U'),
        m.GenericParamType('T'), m.GenericParamType('T', m.NUMERIC),
        m.GenericInstanceType('Box', [m.I32]), m.GenericInstanceType('Box', [m.I64]),
        m.TypeSet(frozenset([named])), m.TypeSet(frozenset([altered])),
        m.TypeSet(frozenset([m.I32]), 'N'), m.TypeSet(frozenset([m.I64]), 'N'),
        m.TypeSet(frozenset([m.I32])),
    ]


# Recorded from the pre-conversion module. These relation tables are fixed
# observations, not another implementation of the comparison algorithm.
LEGACY_LANGUAGE_ROWS = (
    '100000000000000000000000000000000',
    '010000000000000000000000000000000',
    '001100000000000000000000000000000',
    '001100000000000000000000000000000',
    '000010000000000000000000000000000',
    '000001000000000000000000000000000',
    '000000100000000000000000000000000',
    '000000010000000000000000000000000',
    '000000001000000000000000000000000',
    '000000000100000000000000000000000',
    '000000000011100000000000000000000',
    '000000000011100000000000000000000',
    '000000000011100000000000000000000',
    '000000000000010000000000000000000',
    '000000000000001000000000000000000',
    '000000000000000111010000000000000',
    '000000000000000110000000000000000',
    '000000000000000101110000000000000',
    '000000000000000001110000000000000',
    '000000000000000101110000000000000',
    '000000000000000000001100000000000',
    '000000000000000000001100000000000',
    '000000000000000000000011000000000',
    '000000000000000000000011000000000',
    '000000000000000000000000110000000',
    '000000000000000000000000110000000',
    '000000000000000000000000001000000',
    '000000000000000000000000000100000',
    '000000000000000000000000000010000',
    '000000000000000000000000000001000',
    '000000000000000000000000000000111',
    '000000000000000000000000000000110',
    '000000000000000000000000000000101',
)
LEGACY_PYTHON_ROWS = (
    '100000000000000000000000000000000',
    '010000000000000000000000000000000',
    '001100000000000000000000000000000',
    '001100000000000000000000000000000',
    '000010000000000000000000000000000',
    '000001000000000000000000000000000',
    '000000100000000000000000000000000',
    '000000010000000000000000000000000',
    '000000001000000000000000000000000',
    '000000000100000000000000000000000',
    '000000000010000000000000000000000',
    '000000000001000000000000000000000',
    '000000000000100000000000000000000',
    '000000000000010000000000000000000',
    '000000000000001000000000000000000',
    '000000000000000100000000000000000',
    '000000000000000010000000000000000',
    '000000000000000001000000000000000',
    '000000000000000000100000000000000',
    '000000000000000000010000000000000',
    '000000000000000000001000000000000',
    '000000000000000000000100000000000',
    '000000000000000000000010000000000',
    '000000000000000000000001000000000',
    '000000000000000000000000100000000',
    '000000000000000000000000010000000',
    '000000000000000000000000001000000',
    '000000000000000000000000000100000',
    '000000000000000000000000000010000',
    '000000000000000000000000000001000',
    '000000000000000000000000000000100',
    '000000000000000000000000000000010',
    '000000000000000000000000000000001',
)


def test_controlled_shallow_baseline_relations():
    cases = shallow_cases(t)
    language = tuple(''.join('1' if a.equals(b) else '0' for b in cases) for a in cases)
    python = tuple(''.join('1' if a == b else '0' for b in cases) for a in cases)
    assert language == LEGACY_LANGUAGE_ROWS
    assert python == LEGACY_PYTHON_ROWS


def test_original_hash_payloads_and_equal_object_contract():
    scalar_hash = hash(('primitive', 'i32'))
    array_hash = hash(('array', scalar_hash, 3))
    array = t.ArrayType(t.I32, 3)
    assert hash(array) == array_hash
    assert hash(t.SliceType(array)) == hash(('slice', array_hash))
    assert hash(t.PointerType(array)) == hash(('pointer', array_hash))
    assert hash(t.ReferenceType(array)) == hash(('reference', array_hash))
    field = t.StructField('x', array)
    assert hash(field) == hash(('x', array_hash))
    assert hash(t.UnionField('x', array)) == hash(field)
    assert hash(t.StructType(fields=[field])) == hash(('struct', (field,)))
    assert hash(t.FunctionType([array], t.I32, generic_param_order=['T'])) == hash(
        ('function', (array,), scalar_hash, ('T',)))
    assert hash(t.GenericInstanceType('G', [array])) == hash(('generic_instance', 'G', (array,)))
    assert hash(t.TypeSet(frozenset([array]))) == hash(('type_set', frozenset([array])))
    for a, b in zip(shallow_cases(t), shallow_cases(t)):
        assert a == b
        assert hash(a) == hash(b)


def test_language_matching_does_not_replace_python_equality():
    a = t.StructType('Node', [t.StructField('value', t.I32)])
    b = t.StructType('Node', [t.StructField('other', t.STRING)])
    assert a.equals(b) and a != b
    assert hash(a) == hash(b)
    assert not t.TypeSet(frozenset([a])).equals(t.TypeSet(frozenset([b])))
    assert a.equals(t.StructType(fields=a.fields))
    assert t.StructField('x', t.I32) != t.UnionField('x', t.I32)
    assert not t.UNKNOWN.equals(t.I32)
    assert t.UNKNOWN.is_assignable_to(t.I32)
    assert t.FunctionType([t.I32], t.I64).equals(t.FunctionType([t.I32], t.I64, True, t.STRING))
    assert not t.FunctionType([t.I32], t.I64).equals(t.FunctionType([t.I64], t.I32))
    assert not t.StructType(fields=[t.StructField('a', t.I32), t.StructField('b', t.I64)]).equals(
        t.StructType(fields=[t.StructField('b', t.I64), t.StructField('a', t.I32)]))


WRAPPERS = [
    lambda x: t.ArrayType(x, 3), lambda x: t.SliceType(x),
    lambda x: t.PointerType(x), lambda x: t.ReferenceType(x),
    lambda x: t.FunctionType([x, x], x),
    lambda x: t.StructType(fields=[t.StructField('item', x)]),
    lambda x: t.GenericInstanceType('Box', [x]),
    lambda x: t.TypeSet(frozenset([x])),
    lambda x: t.UnionType('U', [t.UnionField('item', x)]),
    lambda x: t.GenericParamType('T', t.TypeSet(frozenset([x]))),
]


@pytest.mark.parametrize('wrapper', WRAPPERS)
def test_5000_deep_types_at_recursion_limit_100(wrapper):
    previous = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(100)
        a, b, different = t.I32, t.PrimitiveType('i32'), t.I64
        for _ in range(5000):
            a, b, different = wrapper(a), wrapper(b), wrapper(different)
        assert a == b
        assert a.equals(b)
        assert a != different
        assert hash(a) == hash(b)
        assert {a: 'found'}[b] == 'found'
    finally:
        sys.setrecursionlimit(previous)


def test_cycles_retain_failure_or_existing_name_and_identity_shortcuts():
    a, b = t.SliceType(t.I32), t.SliceType(t.I32)
    object.__setattr__(a, 'element_type', a)
    object.__setattr__(b, 'element_type', b)
    assert a == a
    for operation in (lambda: a.equals(a), lambda: a.equals(b), lambda: a == b, lambda: hash(a)):
        with pytest.raises(RecursionError):
            operation()
    named = t.StructType('Node')
    object.__setattr__(named, 'fields', (t.StructField('next', t.ReferenceType(named)),))
    assert named.equals(t.StructType('Node'))
    assert hash(named) == hash(t.StructType('Node'))
    assert named == named
    # A mismatch before the cycle still short circuits without visiting it.
    assert not t.FunctionType([t.I32, a]).equals(t.FunctionType([t.I64, b]))


def test_inherited_type_methods_preserve_class_rules():
    class SpecialArray(t.ArrayType):
        pass
    a, b = SpecialArray(t.I32, 2), t.ArrayType(t.I32, 2)
    assert a.equals(b) and b.equals(a)
    assert a != b
    assert hash(a) == hash(b)


def test_nested_extension_overrides_and_super_calls_are_preserved():
    class Custom(t.PrimitiveType):
        def equals(self, other):
            return isinstance(other, t.PrimitiveType)

        def __eq__(self, other):
            return isinstance(other, t.PrimitiveType)

        def __hash__(self):
            return 17

    custom = Custom('extension')
    assert t.SliceType(custom).equals(t.SliceType(t.I64))
    assert t.SliceType(custom) == t.SliceType(t.I64)
    assert t.SliceType(t.I64) == t.SliceType(custom)
    assert hash(t.SliceType(custom)) == hash(('slice', 17))

    class Inherited(t.SliceType):
        def equals(self, other):
            return super().equals(other)

        def __eq__(self, other):
            return super().__eq__(other)

        def __hash__(self):
            return super().__hash__()

    a, b = Inherited(t.I32), Inherited(t.I32)
    assert t.ArrayType(a, 2).equals(t.ArrayType(b, 2))
    assert t.ArrayType(a, 2) == t.ArrayType(b, 2)
    assert hash(t.ArrayType(a, 2)) == hash(t.ArrayType(b, 2))


def test_type_sets_ignore_order_and_resolve_equal_hash_collisions():
    def member(field):
        return t.StructType('SameName', [t.StructField(field, t.I32)])

    left = t.TypeSet(frozenset([member('a'), member('b')]))
    reordered = t.TypeSet(frozenset([member('b'), member('a')]))
    different = t.TypeSet(frozenset([member('a'), member('c')]))
    assert left == reordered
    assert left.equals(reordered)
    assert hash(left) == hash(reordered)
    assert left != different
    assert not left.equals(different)


def test_5000_mixed_layers_preserve_differing_leaf_relations():
    previous = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(100)
        a, b, different = t.I32, t.PrimitiveType('i32'), t.I64
        for depth in range(5000):
            wrapper = WRAPPERS[depth % 7]
            a, b, different = wrapper(a), wrapper(b), wrapper(different)
        assert a.equals(b)
        assert a == b
        assert not a.equals(different)
        assert a != different
        assert hash(a) == hash(b)
    finally:
        sys.setrecursionlimit(previous)
