"""
Type system for A7 semantic analysis.

Provides type representation, type checking, and type compatibility analysis.
"""

from dataclasses import dataclass, fields
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum, auto

from a7.ast_nodes import ASTNode, NodeKind


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
        return _compare_types(self, other, semantic=True)

    def __str__(self) -> str:
        return _format_type(self)

    def __hash__(self) -> int:
        return _hash_type(self)

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented
        return _compare_types(self, other, semantic=False)


@dataclass(frozen=True)
class SliceType(Type):
    """Dynamic slice type: []T."""
    element_type: Type

    def __init__(self, element_type: Type):
        object.__setattr__(self, 'kind', TypeKind.SLICE)
        object.__setattr__(self, 'element_type', element_type)

    def equals(self, other: Type) -> bool:
        return _compare_types(self, other, semantic=True)

    def __str__(self) -> str:
        return _format_type(self)

    def __hash__(self) -> int:
        return _hash_type(self)

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented
        return _compare_types(self, other, semantic=False)


@dataclass(frozen=True)
class PointerType(Type):
    """Pointer type: ptr T."""
    pointee_type: Type

    def __init__(self, pointee_type: Type):
        object.__setattr__(self, 'kind', TypeKind.POINTER)
        object.__setattr__(self, 'pointee_type', pointee_type)

    def equals(self, other: Type) -> bool:
        return _compare_types(self, other, semantic=True)

    def __str__(self) -> str:
        return _format_type(self)

    def __hash__(self) -> int:
        return _hash_type(self)

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented
        return _compare_types(self, other, semantic=False)


@dataclass(frozen=True)
class ReferenceType(Type):
    """Reference type: ref T (can be nil)."""
    referent_type: Type

    def __init__(self, referent_type: Type):
        object.__setattr__(self, 'kind', TypeKind.REFERENCE)
        object.__setattr__(self, 'referent_type', referent_type)

    def equals(self, other: Type) -> bool:
        return _compare_types(self, other, semantic=True)

    def __str__(self) -> str:
        return _format_type(self)

    def __hash__(self) -> int:
        return _hash_type(self)

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented
        return _compare_types(self, other, semantic=False)


@dataclass(frozen=True)
class FunctionType(Type):
    """Function type: fn(params...) return_type."""
    param_types: tuple[Type, ...]
    return_type: Optional[Type]
    is_variadic: bool = False
    variadic_type: Optional[Type] = None  # For typed variadic: ..i32
    generic_param_order: Tuple[str, ...] = ()

    def __init__(self, param_types, return_type=None, is_variadic=False, variadic_type=None, generic_param_order=()):
        object.__setattr__(self, 'kind', TypeKind.FUNCTION)
        # Convert list to tuple for immutability
        if isinstance(param_types, list):
            param_types = tuple(param_types)
        object.__setattr__(self, 'param_types', param_types)
        object.__setattr__(self, 'return_type', return_type)
        object.__setattr__(self, 'is_variadic', is_variadic)
        object.__setattr__(self, 'variadic_type', variadic_type)
        object.__setattr__(self, 'generic_param_order', tuple(generic_param_order or ()))

    def equals(self, other: Type) -> bool:
        return _compare_types(self, other, semantic=True)

    def __str__(self) -> str:
        return _format_type(self)

    def __hash__(self) -> int:
        return _hash_type(self)

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented
        return _compare_types(self, other, semantic=False)


@dataclass(frozen=True)
class StructField:
    """A field in a struct type."""
    name: str
    field_type: Type

    def __hash__(self) -> int:
        return _hash_type(self)

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented
        return _compare_types(self, other, semantic=False)


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
        return _compare_types(self, other, semantic=True)

    def get_field(self, name: str) -> Optional[StructField]:
        """Get field by name."""
        for field in self.fields:
            if field.name == name:
                return field
        return None

    def __str__(self) -> str:
        return _format_type(self)

    def __hash__(self) -> int:
        return _hash_type(self)

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented
        return _compare_types(self, other, semantic=False)


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
        return _hash_type(self)

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented
        return _compare_types(self, other, semantic=False)


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

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented
        return _compare_types(self, other, semantic=False)


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
        return _format_type(self)

    def __hash__(self) -> int:
        return hash(('generic_param', self.name))

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented
        return _compare_types(self, other, semantic=False)


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
        return _compare_types(self, other, semantic=True)

    def __str__(self) -> str:
        return _format_type(self)

    def __hash__(self) -> int:
        return _hash_type(self)

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented
        return _compare_types(self, other, semantic=False)


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
        return _compare_types(self, other, semantic=True)

    def contains(self, type_: Type) -> bool:
        """Check if a type is in this type set."""
        return any(type_.equals(t) for t in self.types)

    def __str__(self) -> str:
        return _format_type(self)

    def __hash__(self) -> int:
        return _hash_type(self)

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented
        return _compare_types(self, other, semantic=False)


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


def _format_type(root: Type) -> str:
    """Render types into fragments without retaining every nested spelling.

    Only unnamed type-set members need separate strings for sorting. Named
    records terminate at their name. Structural cycles retain the previous
    RecursionError outcome instead of inventing a recursive type spelling.
    """
    output: List[str] = []
    active: set[int] = set()
    pending = [("visit", root, output)]
    while pending:
        action, node, target = pending.pop()
        if action == "leave":
            active.remove(node)
            continue
        if action == "sort":
            target.append(", ".join(sorted("".join(member) for member in node)))
            continue
        if isinstance(node, str):
            target.append(node)
            continue

        identity = id(node)
        if identity in active:
            raise RecursionError("Cannot render a structural cycle in a type")
        active.add(identity)
        pending.append(("leave", identity, target))

        if isinstance(node, PrimitiveType):
            parts = [node.name]
        elif isinstance(node, ArrayType):
            parts = [f"[{node.size}]", node.element_type]
        elif isinstance(node, SliceType):
            parts = ["[]", node.element_type]
        elif isinstance(node, PointerType):
            parts = ["ptr ", node.pointee_type]
        elif isinstance(node, ReferenceType):
            parts = ["ref ", node.referent_type]
        elif isinstance(node, FunctionType):
            parts = ["fn("]
            for index, param in enumerate(node.param_types):
                if index:
                    parts.append(", ")
                parts.append(param)
            if node.is_variadic:
                parts.append(", .." if node.param_types else "..")
                if node.variadic_type:
                    parts.append(node.variadic_type)
            parts.append(")")
            if node.return_type:
                parts.extend([" ", node.return_type])
        elif isinstance(node, StructType):
            if node.name:
                parts = [node.name]
                if node.generic_params:
                    parts.extend(["(", ", ".join(node.generic_params), ")"])
            else:
                parts = ["struct { "]
                for index, field in enumerate(node.fields):
                    if index:
                        parts.append(", ")
                    parts.extend([field.name, ": ", field.field_type])
                parts.append(" }")
        elif isinstance(node, (EnumType, UnionType)):
            parts = [node.name]
        elif isinstance(node, GenericParamType):
            parts = ["$", node.name]
            if node.constraint:
                parts.extend([": ", node.constraint])
        elif isinstance(node, GenericInstanceType):
            parts = [node.base_name, "("]
            for index, arg in enumerate(node.type_args):
                if index:
                    parts.append(", ")
                parts.append(arg)
            parts.append(")")
        elif isinstance(node, TypeSet):
            if node.name:
                parts = [node.name]
            elif len(node.types) <= 1:
                parts = ["@type_set(", *node.types, ")"]
            else:
                # Render each member separately, then append it in spelling
                # order. Keep ordinary nested types as fragments throughout.
                members = [[] for _ in node.types]
                target.append("@type_set(")
                pending.append(("visit", ")", target))
                pending.append(("sort", members, target))
                pending.extend(("visit", member, fragments)
                               for member, fragments in zip(node.types, members))
                continue
        elif isinstance(node, UnknownType):
            parts = ["unknown type"]
        elif isinstance(node, VoidType):
            parts = ["void"]
        else:
            raise NotImplementedError(f"__str__ not implemented for {node.__class__.__name__}")
        pending.extend(("visit", part, target) for part in reversed(parts))
    return "".join(output)


def _comparison_plan(left, right, semantic):
    """Describe one comparison without invoking child equality methods."""
    def pair(a, b, language=False):
        return ('pair', a, b, language)

    if not semantic:
        # Python containers skip equality for identical elements. Dataclass
        # equality compares tuples of fields, so it has the same shortcut.
        if left is right:
            return True
        if isinstance(left, (Type, StructField, UnionField, EnumVariant)):
            if left.__class__ is not right.__class__:
                return False
            return ('all', [pair(getattr(left, f.name), getattr(right, f.name))
                            for f in fields(left) if f.compare])
        if isinstance(left, (tuple, list)):
            if not isinstance(right, type(left)) or len(left) != len(right):
                return False
            return ('all', [pair(a, b) for a, b in zip(left, right)])
        if isinstance(left, (set, frozenset)):
            if not isinstance(right, (set, frozenset)) or len(left) != len(right):
                return False
            # Set membership uses hashes and Python equality, not .equals().
            buckets = {}
            for member in right:
                buckets.setdefault(_hash_type(member, honor_override=True), []).append(member)
            return ('all', [('any', [pair(a, b) for b in buckets.get(_hash_type(a, honor_override=True), ())])
                            for a in left])
        return left == right

    category = next((cls for cls in (PrimitiveType, EnumType, UnionType, GenericParamType,
                                    UnknownType, VoidType, ArrayType, SliceType, PointerType,
                                    ReferenceType, FunctionType, StructType, GenericInstanceType,
                                    TypeSet) if isinstance(left, cls)), Type)
    if isinstance(left, (PrimitiveType, EnumType, UnionType, GenericParamType)):
        return isinstance(right, category) and left.name == right.name
    if isinstance(left, (UnknownType, VoidType)):
        return isinstance(right, category)
    if not isinstance(right, category):
        return False
    if isinstance(left, ArrayType):
        return ('all', [pair(left.size, right.size), pair(left.element_type, right.element_type, True)])
    if isinstance(left, SliceType):
        return pair(left.element_type, right.element_type, True)
    if isinstance(left, PointerType):
        return pair(left.pointee_type, right.pointee_type, True)
    if isinstance(left, ReferenceType):
        return pair(left.referent_type, right.referent_type, True)
    if isinstance(left, FunctionType):
        if len(left.param_types) != len(right.param_types):
            return False
        children = [pair(a, b, True) for a, b in zip(left.param_types, right.param_types)]
        children.append(pair(left.return_type, right.return_type,
                             left.return_type is not None and right.return_type is not None))
        return ('all', children)
    if isinstance(left, StructType):
        if left.name and right.name:
            return left.name == right.name
        if len(left.fields) != len(right.fields):
            return False
        children = []
        for a, b in zip(left.fields, right.fields):
            children.extend([pair(a.name, b.name), pair(a.field_type, b.field_type, True)])
        return ('all', children)
    if isinstance(left, GenericInstanceType):
        if left.base_name != right.base_name or len(left.type_args) != len(right.type_args):
            return False
        return ('all', [pair(a, b, True) for a, b in zip(left.type_args, right.type_args)])
    if isinstance(left, TypeSet):
        if left.name and right.name:
            return left.name == right.name
        return pair(left.types, right.types)
    raise NotImplementedError(f"equals not implemented for {left.__class__.__name__}")


def _compare_types(left, right, semantic):
    """Evaluate ordered pairs with short circuiting and an explicit work stack.

    Actual structural cycles retain RecursionError. Named language comparisons
    terminate at names; Python equality retains container identity shortcuts.
    No coinductive equality for recursive structural types is introduced.
    """
    work = [('pair', left, right, semantic)]
    active = set()
    completed = {}
    result = True
    first_pair = True
    while work:
        task = work.pop()
        action = task[0]
        if action == 'done':
            active.remove(task[1])
            completed[task[1]] = result
        elif action == 'next':
            _, iterator, conjunction = task
            if result != conjunction:
                continue
            child = next(iterator, None)
            if child is not None:
                work.append(task)
                work.append(child)
        elif action in ('all', 'any'):
            result = action == 'all'
            work.append(('next', iter(task[1]), result))
        else:
            _, a, b, language = task
            # Preserve extension methods on nested types. A root call may be
            # super().__eq__/equals from such a method, so do not redispatch it.
            method = getattr(type(a), 'equals' if language else '__eq__', None)
            custom_left = (isinstance(a, (Type, StructField, UnionField, EnumVariant))
                           and method not in _TYPE_COMPARISON_METHODS)
            custom_right = (not language and isinstance(b, (Type, StructField, UnionField, EnumVariant))
                            and type(b).__eq__ not in _TYPE_COMPARISON_METHODS)
            if not first_pair and (custom_left or custom_right):
                result = method(a, b) if language else (a is b or a == b)
                continue
            first_pair = False
            key = (id(a), id(b), language)
            if key in completed:
                result = completed[key]
                continue
            if key in active:
                raise RecursionError('Cannot compare a structural cycle in a type')
            plan = _comparison_plan(a, b, language)
            if isinstance(plan, bool):
                result = plan
                continue
            active.add(key)
            work.append(('done', key))
            work.append(plan)
    return result


class _TypeHashValue:
    """A child object's hash for Python's native tuple hash algorithm."""
    __slots__ = ('value',)

    def __init__(self, value):
        self.value = value

    def __hash__(self):
        return self.value


def _hash_type(root, honor_override=False):
    """Hash children bottom up, preserving the original tuple payloads.

    Some payloads contain hash(child) integers, others contain child objects.
    Keep that distinction: hash(an_integer_hash) need not equal that integer.
    Frozen sets already cache member hashes, so their native hash is safe.
    """
    pending = [('visit', root)]
    active = set()
    computed = {}
    first_node = True
    while pending:
        action, node, *rest = pending.pop()
        identity = id(node)
        if action == 'finish':
            parts, children = rest
            for index, child, as_integer in children:
                value = computed[id(child)]
                parts[index] = value if as_integer else _TypeHashValue(value)
            computed[identity] = hash(tuple(parts))
            active.remove(identity)
            continue
        if identity in computed:
            continue
        if honor_override or not first_node:
            method = getattr(type(node), '__hash__', None)
            if isinstance(node, (Type, StructField, UnionField, EnumVariant)) and method not in _TYPE_HASH_METHODS:
                if method is None:
                    raise TypeError(f"unhashable type: '{type(node).__name__}'")
                computed[identity] = hash(_TypeHashValue(method(node)))
                continue
        first_node = False
        if identity in active:
            raise RecursionError('Cannot hash a structural cycle in a type')
        children = []
        if isinstance(node, ArrayType):
            parts = ['array', None, node.size]
            children = [(1, node.element_type, True)]
        elif isinstance(node, (SliceType, PointerType, ReferenceType)):
            if isinstance(node, SliceType):
                tag, child = 'slice', node.element_type
            elif isinstance(node, PointerType):
                tag, child = 'pointer', node.pointee_type
            else:
                tag, child = 'reference', node.referent_type
            parts = [tag, None]
            children = [(1, child, True)]
        elif isinstance(node, FunctionType):
            parts = ['function', None, None, node.generic_param_order]
            children = [(1, node.param_types, False)]
            if node.return_type:
                children.append((2, node.return_type, True))
        elif isinstance(node, (StructField, UnionField)):
            parts = [node.name, None]
            children = [(1, node.field_type, True)]
        elif isinstance(node, StructType):
            parts = ['struct', node.name if node.name else None]
            if not node.name:
                children = [(1, node.fields, False)]
        elif isinstance(node, GenericInstanceType):
            parts = ['generic_instance', node.base_name, None]
            children = [(2, node.type_args, False)]
        elif isinstance(node, TypeSet):
            parts = ['type_set', node.name if node.name else node.types]
        elif isinstance(node, (PrimitiveType, EnumType, UnionType, GenericParamType)):
            tag = next(label for cls, label in ((PrimitiveType, 'primitive'),
                       (EnumType, 'enum'), (UnionType, 'union'),
                       (GenericParamType, 'generic_param')) if isinstance(node, cls))
            parts = [tag, node.name]
        elif isinstance(node, EnumVariant):
            parts = [node.name, node.value]
        elif isinstance(node, (UnknownType, VoidType)):
            computed[identity] = hash('unknown' if isinstance(node, UnknownType) else 'void')
            continue
        elif isinstance(node, tuple):
            parts = [None] * len(node)
            children = [(i, child, False) for i, child in enumerate(node)]
        elif isinstance(node, Type):
            raise NotImplementedError(f"__hash__ not implemented for {node.__class__.__name__}")
        else:
            computed[identity] = hash(node)
            continue
        active.add(identity)
        pending.append(('finish', node, parts, children))
        pending.extend(('visit', child) for _, child, _ in reversed(children))
    return computed[id(root)]


# Recognize inherited built-in methods while leaving extension overrides intact.
_TYPE_CLASSES = (Type, PrimitiveType, ArrayType, SliceType, PointerType,
                 ReferenceType, FunctionType, StructField, StructType,
                 EnumVariant, EnumType, UnionField, UnionType, GenericParamType,
                 GenericInstanceType, TypeSet, UnknownType, VoidType)
_TYPE_COMPARISON_METHODS = frozenset(
    method for cls in _TYPE_CLASSES for name in ('equals', '__eq__')
    if (method := getattr(cls, name, None)) is not None
)
_TYPE_HASH_METHODS = frozenset(cls.__hash__ for cls in _TYPE_CLASSES)


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


def resolve_generic_constraint(constraint_node: Optional[ASTNode]) -> Optional[TypeSet]:
    """
    Resolve a generic constraint node to a TypeSet.

    Args:
        constraint_node: Constraint AST node (TYPE_SET or TYPE_IDENTIFIER)

    Returns:
        Resolved TypeSet, or None if no constraint
    """
    if constraint_node is None:
        return None

    # Check for predefined type set by name
    type_set_name = getattr(constraint_node, 'type_name', None) or getattr(constraint_node, 'name', None)
    if type_set_name:
        predefined = get_predefined_type_set(type_set_name)
        if predefined:
            return predefined

    # Check for inline type set
    if constraint_node.kind == NodeKind.TYPE_SET:
        resolved_types = []
        for type_node in constraint_node.types or []:
            resolved = _resolve_constraint_member_type(type_node)
            if resolved is None:
                return None
            resolved_types.append(resolved)
        return TypeSet(types=frozenset(resolved_types))

    return None


def _resolve_constraint_member_type(type_node: Optional[ASTNode]) -> Optional[Type]:
    """Resolve a type node that appears inside an inline generic constraint set."""
    if type_node is None:
        return None

    if type_node.kind == NodeKind.TYPE_PRIMITIVE:
        return get_primitive_type(type_node.type_name or "")

    if type_node.kind == NodeKind.TYPE_IDENTIFIER:
        return get_primitive_type(type_node.name or type_node.type_name or "")

    return None


# Canonical integer width/range table. Single source for the duplicated
# mappings in passes/safety.py (SIGNED_RANGES/UNSIGNED_RANGES/INTEGER_RANGES),
# const_eval.py (_INTEGER_LAYOUT) and cast_classifier.py
# (_SIGNED_BITS/_UNSIGNED_BITS/_FLOAT_BITS). layout.py keeps its own
# PRIMITIVE_LAYOUTS: different shape (size, align) plus extra
# bool/char/string entries, so it is not rewired here.
SIGNED_INTEGER_WIDTHS: Dict[str, int] = {
    'i8': 8, 'i16': 16, 'i32': 32, 'isize': 64, 'i64': 64,
}
UNSIGNED_INTEGER_WIDTHS: Dict[str, int] = {
    'u8': 8, 'u16': 16, 'u32': 32, 'usize': 64, 'u64': 64,
}
INTEGER_BIT_WIDTHS: Dict[str, int] = {
    **SIGNED_INTEGER_WIDTHS, **UNSIGNED_INTEGER_WIDTHS,
}
INTEGER_RANGES: Dict[str, Tuple[int, int]] = {
    'i8': (-(2 ** 7), 2 ** 7 - 1),
    'i16': (-(2 ** 15), 2 ** 15 - 1),
    'i32': (-(2 ** 31), 2 ** 31 - 1),
    'i64': (-(2 ** 63), 2 ** 63 - 1),
    'isize': (-(2 ** 63), 2 ** 63 - 1),
    'u8': (0, 2 ** 8 - 1),
    'u16': (0, 2 ** 16 - 1),
    'u32': (0, 2 ** 32 - 1),
    'u64': (0, 2 ** 64 - 1),
    'usize': (0, 2 ** 64 - 1),
}
FLOAT_BIT_WIDTHS: Dict[str, int] = {
    'f32': 32, 'f64': 64,
}
