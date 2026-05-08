"""
Type system for A7 semantic analysis.

Provides type representation, type checking, and type compatibility analysis.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum, auto


class TypeKind(Enum):
    """Categories of types in A7."""
    PRIMITIVE = auto()
    ARRAY = auto()
    SLICE = auto()
    POINTER = auto()
    REFERENCE = auto()
    FUNCTION = auto()
    STRUCT = auto()
    ENUM = auto()
    UNION = auto()
    GENERIC_PARAM = auto()
    GENERIC_INSTANCE = auto()
    TYPE_SET = auto()
    UNKNOWN = auto()
    VOID = auto()


@dataclass(frozen=True)
class Type:
    """
    Base class for all types in A7.

    Types are immutable and hashable for efficient caching and comparison.
    """
    kind: TypeKind

    def equals(self, other: 'Type') -> bool:
        """Check if two types are exactly equal."""
        raise NotImplementedError(f"equals not implemented for {self.__class__.__name__}")

    def is_assignable_to(self, target: 'Type') -> bool:
        """Check if this type can be assigned to target type."""
        # Default: only exact matches are assignable
        return self.equals(target)

    def is_numeric(self) -> bool:
        """Check if this is a numeric type."""
        return False

    def is_integral(self) -> bool:
        """Check if this is an integral type."""
        return False

    def is_floating(self) -> bool:
        """Check if this is a floating-point type."""
        return False

    def is_boolean(self) -> bool:
        """Check if this is a boolean type."""
        return False

    def is_reference_type(self) -> bool:
        """Check if this type can be nil (only ref T)."""
        return self.kind == TypeKind.REFERENCE

    def __str__(self) -> str:
        """Human-readable type representation."""
        raise NotImplementedError(f"__str__ not implemented for {self.__class__.__name__}")

    def __hash__(self) -> int:
        """Make types hashable for use in sets/dicts."""
        raise NotImplementedError(f"__hash__ not implemented for {self.__class__.__name__}")


@dataclass(frozen=True)
class PrimitiveType(Type):
    """Primitive scalar and builtin value types."""
    name: str

    def __init__(self, name: str):
        object.__setattr__(self, 'kind', TypeKind.PRIMITIVE)
        object.__setattr__(self, 'name', name)

    def equals(self, other: Type) -> bool:
        return isinstance(other, PrimitiveType) and self.name == other.name

    def is_numeric(self) -> bool:
        return self.name in {
            'i8', 'i16', 'i32', 'i64', 'isize',
            'u8', 'u16', 'u32', 'u64', 'usize',
            'f32', 'f64',
        }

    def is_integral(self) -> bool:
        return self.name in {
            'i8', 'i16', 'i32', 'i64', 'isize',
            'u8', 'u16', 'u32', 'u64', 'usize',
        }

    def is_floating(self) -> bool:
        return self.name in {'f32', 'f64'}

    def is_boolean(self) -> bool:
        return self.name == 'bool'

    def is_assignable_to(self, target: Type) -> bool:
        if not isinstance(target, PrimitiveType):
            return False

        # Exact match
        if self.name == target.name:
            return True

        signed_ints = {'i8', 'i16', 'i32', 'i64', 'isize'}
        unsigned_ints = {'u8', 'u16', 'u32', 'u64', 'usize'}
        floats = {'f32', 'f64'}

        if self.name in signed_ints and target.name in signed_ints:
            rank = {'i8': 1, 'i16': 2, 'i32': 3, 'isize': 4, 'i64': 5}
            return rank[target.name] >= rank[self.name]

        if self.name in unsigned_ints and target.name in unsigned_ints:
            rank = {'u8': 1, 'u16': 2, 'u32': 3, 'usize': 4, 'u64': 5}
            return rank[target.name] >= rank[self.name]

        if self.name in unsigned_ints and target.name in signed_ints:
            unsigned_bits = {'u8': 8, 'u16': 16, 'u32': 32, 'usize': 64, 'u64': 64}
            signed_bits = {'i8': 8, 'i16': 16, 'i32': 32, 'isize': 64, 'i64': 64}
            return signed_bits[target.name] > unsigned_bits[self.name]

        if self.name in floats and target.name in floats:
            rank = {'f32': 1, 'f64': 2}
            return rank[target.name] >= rank[self.name]

        if (self.name in signed_ints or self.name in unsigned_ints) and target.name in floats:
            return True

        return False

    def __str__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(('primitive', self.name))


@dataclass(frozen=True)
class ArrayType(Type):
    """Fixed-size array type: [N]T."""
    element_type: Type
    size: int

    def __init__(self, element_type: Type, size: int):
        object.__setattr__(self, 'kind', TypeKind.ARRAY)
        object.__setattr__(self, 'element_type', element_type)
        object.__setattr__(self, 'size', size)

    def equals(self, other: Type) -> bool:
        return (isinstance(other, ArrayType) and
                self.size == other.size and
                self.element_type.equals(other.element_type))

    def __str__(self) -> str:
        return f"[{self.size}]{self.element_type}"

    def __hash__(self) -> int:
        return hash(('array', hash(self.element_type), self.size))


@dataclass(frozen=True)
class SliceType(Type):
    """Dynamic slice type: []T."""
    element_type: Type

    def __init__(self, element_type: Type):
        object.__setattr__(self, 'kind', TypeKind.SLICE)
        object.__setattr__(self, 'element_type', element_type)

    def equals(self, other: Type) -> bool:
        return isinstance(other, SliceType) and self.element_type.equals(other.element_type)

    def __str__(self) -> str:
        return f"[]{self.element_type}"

    def __hash__(self) -> int:
        return hash(('slice', hash(self.element_type)))


@dataclass(frozen=True)
class PointerType(Type):
    """Pointer type: ptr T."""
    pointee_type: Type

    def __init__(self, pointee_type: Type):
        object.__setattr__(self, 'kind', TypeKind.POINTER)
        object.__setattr__(self, 'pointee_type', pointee_type)

    def equals(self, other: Type) -> bool:
        return isinstance(other, PointerType) and self.pointee_type.equals(other.pointee_type)

    def __str__(self) -> str:
        return f"ptr {self.pointee_type}"

    def __hash__(self) -> int:
        return hash(('pointer', hash(self.pointee_type)))


@dataclass(frozen=True)
class ReferenceType(Type):
    """Reference type: ref T (can be nil)."""
    referent_type: Type

    def __init__(self, referent_type: Type):
        object.__setattr__(self, 'kind', TypeKind.REFERENCE)
        object.__setattr__(self, 'referent_type', referent_type)

    def equals(self, other: Type) -> bool:
        return isinstance(other, ReferenceType) and self.referent_type.equals(other.referent_type)

    def __str__(self) -> str:
        return f"ref {self.referent_type}"

    def __hash__(self) -> int:
        return hash(('reference', hash(self.referent_type)))


@dataclass(frozen=True)
class FunctionType(Type):
    """Function type: fn(params...) return_type."""
    param_types: tuple[Type, ...]
    return_type: Optional[Type]
    is_variadic: bool = False
    variadic_type: Optional[Type] = None  # For typed variadic: ..i32

    def __init__(self, param_types, return_type=None, is_variadic=False, variadic_type=None):
        object.__setattr__(self, 'kind', TypeKind.FUNCTION)
        # Convert list to tuple for immutability
        if isinstance(param_types, list):
            param_types = tuple(param_types)
        object.__setattr__(self, 'param_types', param_types)
        object.__setattr__(self, 'return_type', return_type)
        object.__setattr__(self, 'is_variadic', is_variadic)
        object.__setattr__(self, 'variadic_type', variadic_type)

    def equals(self, other: Type) -> bool:
        if not isinstance(other, FunctionType):
            return False

        if len(self.param_types) != len(other.param_types):
            return False

        if not all(p1.equals(p2) for p1, p2 in zip(self.param_types, other.param_types)):
            return False

        if self.return_type is None and other.return_type is None:
            return True

        if self.return_type is None or other.return_type is None:
            return False

        return self.return_type.equals(other.return_type)

    def __str__(self) -> str:
        params = ', '.join(str(p) for p in self.param_types)
        if self.is_variadic:
            if self.variadic_type:
                params += f', ..{self.variadic_type}' if params else f'..{self.variadic_type}'
            else:
                params += ', ..' if params else '..'
        ret = f' {self.return_type}' if self.return_type else ''
        return f"fn({params}){ret}"

    def __hash__(self) -> int:
        return hash(('function', self.param_types, hash(self.return_type) if self.return_type else None))


@dataclass(frozen=True)
class StructField:
    """A field in a struct type."""
    name: str
    field_type: Type

    def __hash__(self) -> int:
        return hash((self.name, hash(self.field_type)))


@dataclass(frozen=True)
class StructType(Type):
    """Struct type with named fields."""
    name: Optional[str]  # None for anonymous inline structs
    fields: tuple[StructField, ...]
    generic_params: tuple[str, ...] = ()

    def __init__(self, name=None, fields=(), generic_params=()):
        object.__setattr__(self, 'kind', TypeKind.STRUCT)
        object.__setattr__(self, 'name', name)
        # Convert lists to tuples for immutability
        if isinstance(fields, list):
            fields = tuple(fields)
        if isinstance(generic_params, list):
            generic_params = tuple(generic_params)
        object.__setattr__(self, 'fields', fields)
        object.__setattr__(self, 'generic_params', generic_params)

    def equals(self, other: Type) -> bool:
        if not isinstance(other, StructType):
            return False

        # Named structs: compare by name
        if self.name and other.name:
            return self.name == other.name

        # Anonymous structs: compare structurally
        if len(self.fields) != len(other.fields):
            return False

        return all(f1.name == f2.name and f1.field_type.equals(f2.field_type)
                  for f1, f2 in zip(self.fields, other.fields))

    def get_field(self, name: str) -> Optional[StructField]:
        """Get field by name."""
        for field in self.fields:
            if field.name == name:
                return field
        return None

    def __str__(self) -> str:
        if self.name:
            if self.generic_params:
                params = ', '.join(self.generic_params)
                return f"{self.name}({params})"
            return self.name
        # Anonymous struct
        field_strs = ', '.join(f"{f.name}: {f.field_type}" for f in self.fields)
        return f"struct {{ {field_strs} }}"

    def __hash__(self) -> int:
        if self.name:
            return hash(('struct', self.name))
        return hash(('struct', self.fields))


@dataclass(frozen=True)
class EnumVariant:
    """A variant in an enum type."""
    name: str
    value: Optional[int] = None

    def __hash__(self) -> int:
        return hash((self.name, self.value))


@dataclass(frozen=True)
class EnumType(Type):
    """Enum type with named variants."""
    name: str
    variants: tuple[EnumVariant, ...]

    def __init__(self, name, variants=()):
        object.__setattr__(self, 'kind', TypeKind.ENUM)
        object.__setattr__(self, 'name', name)
        if isinstance(variants, list):
            variants = tuple(variants)
        object.__setattr__(self, 'variants', variants)

    def equals(self, other: Type) -> bool:
        return isinstance(other, EnumType) and self.name == other.name

    def has_variant(self, name: str) -> bool:
        """Check if variant exists."""
        return any(v.name == name for v in self.variants)

    def __str__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(('enum', self.name))


@dataclass(frozen=True)
class UnionField:
    """A field in a union type."""
    name: str
    field_type: Type

    def __hash__(self) -> int:
        return hash((self.name, hash(self.field_type)))


@dataclass(frozen=True)
class UnionType(Type):
    """Union type (tagged union)."""
    name: str
    fields: tuple[UnionField, ...]

    def __init__(self, name, fields=()):
        object.__setattr__(self, 'kind', TypeKind.UNION)
        object.__setattr__(self, 'name', name)
        if isinstance(fields, list):
            fields = tuple(fields)
        object.__setattr__(self, 'fields', fields)

    def equals(self, other: Type) -> bool:
        return isinstance(other, UnionType) and self.name == other.name

    def get_field(self, name: str) -> Optional[UnionField]:
        """Get field by name."""
        for field in self.fields:
            if field.name == name:
                return field
        return None

    def __str__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(('union', self.name))


@dataclass(frozen=True)
class GenericParamType(Type):
    """Generic type parameter: $T."""
    name: str
    constraint: Optional['TypeSet'] = None

    def __init__(self, name, constraint=None):
        object.__setattr__(self, 'kind', TypeKind.GENERIC_PARAM)
        object.__setattr__(self, 'name', name)
        object.__setattr__(self, 'constraint', constraint)

    def equals(self, other: Type) -> bool:
        return isinstance(other, GenericParamType) and self.name == other.name

    def __str__(self) -> str:
        if self.constraint:
            return f"${self.name}: {self.constraint}"
        return f"${self.name}"

    def __hash__(self) -> int:
        return hash(('generic_param', self.name))


@dataclass(frozen=True)
class GenericInstanceType(Type):
    """Instantiated generic type: List(i32)."""
    base_name: str
    type_args: tuple[Type, ...]

    def __init__(self, base_name, type_args=()):
        object.__setattr__(self, 'kind', TypeKind.GENERIC_INSTANCE)
        object.__setattr__(self, 'base_name', base_name)
        if isinstance(type_args, list):
            type_args = tuple(type_args)
        object.__setattr__(self, 'type_args', type_args)

    def equals(self, other: Type) -> bool:
        if not isinstance(other, GenericInstanceType):
            return False

        return (self.base_name == other.base_name and
                len(self.type_args) == len(other.type_args) and
                all(t1.equals(t2) for t1, t2 in zip(self.type_args, other.type_args)))

    def __str__(self) -> str:
        args = ', '.join(str(t) for t in self.type_args)
        return f"{self.base_name}({args})"

    def __hash__(self) -> int:
        return hash(('generic_instance', self.base_name, self.type_args))


@dataclass(frozen=True)
class TypeSet(Type):
    """Type set for generic constraints: @type_set(i32, i64, f32)."""
    types: frozenset[Type]
    name: Optional[str] = None  # For predefined type sets like Numeric

    def __init__(self, types, name=None):
        object.__setattr__(self, 'kind', TypeKind.TYPE_SET)
        object.__setattr__(self, 'types', types)
        object.__setattr__(self, 'name', name)

    def equals(self, other: Type) -> bool:
        if not isinstance(other, TypeSet):
            return False
        if self.name and other.name:
            return self.name == other.name
        return self.types == other.types

    def contains(self, type_: Type) -> bool:
        """Check if a type is in this type set."""
        return any(type_.equals(t) for t in self.types)

    def __str__(self) -> str:
        if self.name:
            return self.name
        type_strs = ', '.join(str(t) for t in sorted(self.types, key=str))
        return f"@type_set({type_strs})"

    def __hash__(self) -> int:
        if self.name:
            return hash(('type_set', self.name))
        return hash(('type_set', self.types))


@dataclass(frozen=True)
class UnknownType(Type):
    """Unknown type (used during type inference or for errors)."""

    def __init__(self):
        object.__setattr__(self, 'kind', TypeKind.UNKNOWN)

    def equals(self, other: Type) -> bool:
        return isinstance(other, UnknownType)

    def is_assignable_to(self, target: Type) -> bool:
        # Unknown type is compatible with anything during inference
        return True

    def __str__(self) -> str:
        return "unknown type"

    def __hash__(self) -> int:
        return hash('unknown')


@dataclass(frozen=True)
class VoidType(Type):
    """Void type (absence of value)."""

    def __init__(self):
        object.__setattr__(self, 'kind', TypeKind.VOID)

    def equals(self, other: Type) -> bool:
        return isinstance(other, VoidType)

    def __str__(self) -> str:
        return "void"

    def __hash__(self) -> int:
        return hash('void')


# Predefined type instances (singletons)
BOOL = PrimitiveType('bool')
CHAR = PrimitiveType('char')
STRING = PrimitiveType('string')

I8 = PrimitiveType('i8')
I16 = PrimitiveType('i16')
I32 = PrimitiveType('i32')
I64 = PrimitiveType('i64')
ISIZE = PrimitiveType('isize')

U8 = PrimitiveType('u8')
U16 = PrimitiveType('u16')
U32 = PrimitiveType('u32')
U64 = PrimitiveType('u64')
USIZE = PrimitiveType('usize')

F32 = PrimitiveType('f32')
F64 = PrimitiveType('f64')

VOID = VoidType()
UNKNOWN = UnknownType()

# Predefined type sets
NUMERIC_TYPES = frozenset({I8, I16, I32, I64, ISIZE, U8, U16, U32, U64, USIZE, F32, F64})
INTEGER_TYPES = frozenset({I8, I16, I32, I64, ISIZE, U8, U16, U32, U64, USIZE})
SIGNED_INT_TYPES = frozenset({I8, I16, I32, I64, ISIZE})
UNSIGNED_INT_TYPES = frozenset({U8, U16, U32, U64, USIZE})
FLOAT_TYPES = frozenset({F32, F64})

NUMERIC = TypeSet(NUMERIC_TYPES, name='Numeric')
INTEGER = TypeSet(INTEGER_TYPES, name='Integer')
SIGNED_INT = TypeSet(SIGNED_INT_TYPES, name='SignedInt')
UNSIGNED_INT = TypeSet(UNSIGNED_INT_TYPES, name='UnsignedInt')
FLOAT = TypeSet(FLOAT_TYPES, name='Float')


# Type construction helpers
def get_primitive_type(name: str) -> Optional[PrimitiveType]:
    """Get a primitive type by name."""
    primitives = {
        'bool': BOOL,
        'char': CHAR,
        'string': STRING,
        'i8': I8, 'i16': I16, 'i32': I32, 'i64': I64, 'isize': ISIZE,
        'u8': U8, 'u16': U16, 'u32': U32, 'u64': U64, 'usize': USIZE,
        'f32': F32, 'f64': F64,
    }
    return primitives.get(name)


def get_predefined_type_set(name: str) -> Optional[TypeSet]:
    """Get a predefined type set by name."""
    type_sets = {
        'Numeric': NUMERIC,
        'Integer': INTEGER,
        'SignedInt': SIGNED_INT,
        'UnsignedInt': UNSIGNED_INT,
        'Float': FLOAT,
    }
    return type_sets.get(name)
