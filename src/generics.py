"""
Generic type system for A7.

Handles generic type parameters, constraints, and monomorphization.
"""

import copy
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

from src.types import (
    Type, TypeKind, GenericParamType, GenericInstanceType, TypeSet,
    StructType, StructField, FunctionType, get_primitive_type, get_predefined_type_set
)
from src.ast_nodes import ASTNode, NodeKind


@dataclass
class GenericConstraint:
    """
    Represents a constraint on a generic type parameter.

    Examples:
    - $T: Numeric
    - $T: @type_set(i32, i64, f32)
    """
    param_name: str
    type_set: TypeSet

    def check_satisfies(self, concrete_type: Type) -> bool:
        """Check if a concrete type satisfies this constraint."""
        return self.type_set.contains(concrete_type)


@dataclass
class GenericContext:
    """
    Context for generic type instantiation.

    Tracks generic parameters and their concrete type mappings.
    """
    # Parameter name -> GenericParamType
    parameters: Dict[str, GenericParamType]

    # Parameter name -> Constraint
    constraints: Dict[str, GenericConstraint]

    # Parameter name -> Concrete type (during instantiation)
    bindings: Dict[str, Type]

    def __init__(self):
        self.parameters = {}
        self.constraints = {}
        self.bindings = {}

    def add_parameter(self, name: str, constraint: Optional[TypeSet] = None) -> GenericParamType:
        """
        Add a generic type parameter.

        Args:
            name: Parameter name (without $)
            constraint: Optional type constraint

        Returns:
            The created GenericParamType
        """
        param_type = GenericParamType(name=name, constraint=constraint)
        self.parameters[name] = param_type

        if constraint:
            self.constraints[name] = GenericConstraint(name, constraint)

        return param_type

    def bind(self, param_name: str, concrete_type: Type) -> bool:
        """
        Bind a generic parameter to a concrete type.

        Args:
            param_name: Parameter name
            concrete_type: Concrete type to bind

        Returns:
            True if binding succeeded and satisfies constraints
        """
        # Check if parameter exists
        if param_name not in self.parameters:
            return False

        # Check constraint if present
        if param_name in self.constraints:
            constraint = self.constraints[param_name]
            if not constraint.check_satisfies(concrete_type):
                return False

        # Bind the type
        self.bindings[param_name] = concrete_type
        return True

    def get_binding(self, param_name: str) -> Optional[Type]:
        """Get the concrete type bound to a parameter."""
        return self.bindings.get(param_name)

    def is_bound(self, param_name: str) -> bool:
        """Check if a parameter is bound to a concrete type."""
        return param_name in self.bindings

    def all_bound(self) -> bool:
        """Check if all parameters are bound."""
        return len(self.bindings) == len(self.parameters)

    def get_constraint(self, param_name: str) -> Optional[GenericConstraint]:
        """Get the constraint for a parameter."""
        return self.constraints.get(param_name)

    def clear_bindings(self) -> None:
        """Clear all type bindings."""
        self.bindings.clear()


class GenericMonomorphizer:
    """
    Handles monomorphization of generic functions and structs.

    Monomorphization generates specialized versions of generic code
    for each concrete type instantiation.
    """

    def __init__(self):
        # Cache of monomorphized instances
        # (name, type_args) -> specialized AST or symbol
        self.instances: Dict[tuple, any] = {}

    def instantiate_function(
        self,
        func_node: ASTNode,
        type_args: List[Type],
        context: GenericContext
    ) -> Optional[ASTNode]:
        """
        Create a monomorphized instance of a generic function.

        Args:
            func_node: Generic function AST node
            type_args: Concrete type arguments
            context: Generic context with parameters

        Returns:
            Specialized function node, or None if instantiation fails
        """
        func_name = func_node.name or "<anonymous>"

        # Create cache key
        type_arg_tuple = tuple(type_args)
        cache_key = (func_name, type_arg_tuple)

        # Check cache
        if cache_key in self.instances:
            return self.instances[cache_key]

        # Bind type arguments
        param_names = list(context.parameters.keys())
        if len(type_args) != len(param_names):
            return None

        for param_name, type_arg in zip(param_names, type_args):
            if not context.bind(param_name, type_arg):
                # Constraint violation
                return None

        # Generate mangled name: swap__i32, identity__f64, etc.
        type_suffix = "__".join(str(t) for t in type_args)
        mangled_name = f"{func_name}__{type_suffix}"

        # Deep clone the AST and substitute types
        specialized_node = copy.deepcopy(func_node)
        specialized_node.name = mangled_name
        _substitute_types_in_ast(specialized_node, context.bindings)

        self.instances[cache_key] = specialized_node
        return specialized_node

    def instantiate_struct(
        self,
        struct_type: StructType,
        type_args: List[Type]
    ) -> Optional[StructType]:
        """
        Create a monomorphized instance of a generic struct.

        Args:
            struct_type: Generic struct type
            type_args: Concrete type arguments

        Returns:
            Specialized struct type, or None if instantiation fails
        """
        struct_name = struct_type.name or "<anonymous>"

        # Create cache key
        type_arg_tuple = tuple(type_args)
        cache_key = (struct_name, type_arg_tuple)

        # Check cache
        if cache_key in self.instances:
            return self.instances[cache_key]

        # Check parameter count
        if len(type_args) != len(struct_type.generic_params):
            return None

        # Build bindings
        bindings = {}
        for param_name, type_arg in zip(struct_type.generic_params, type_args):
            bindings[param_name] = type_arg

        # Generate mangled name: Box__i32, Pair__i32__string
        type_suffix = "__".join(str(t) for t in type_args)
        mangled_name = f"{struct_name}__{type_suffix}"

        # Create specialized struct with substituted field types
        specialized_fields = []
        for field in struct_type.fields:
            new_field_type = _substitute_type(field.type, bindings)
            specialized_fields.append(StructField(name=field.name, type=new_field_type))

        specialized_type = StructType(
            name=mangled_name,
            fields=specialized_fields,
            generic_params=[],
        )
        self.instances[cache_key] = specialized_type
        return specialized_type

    def get_instance(self, name: str, type_args: tuple) -> Optional[any]:
        """Get a cached monomorphized instance."""
        cache_key = (name, type_args)
        return self.instances.get(cache_key)

    def has_instance(self, name: str, type_args: tuple) -> bool:
        """Check if an instance exists in the cache."""
        cache_key = (name, type_args)
        return cache_key in self.instances


def _substitute_type(type_: Type, bindings: Dict[str, Type]) -> Type:
    """Substitute generic parameters in a type with concrete bindings."""
    if isinstance(type_, GenericParamType):
        return bindings.get(type_.name, type_)
    # Could recurse into ArrayType, FunctionType, etc. for complex generics
    return type_


def _substitute_types_in_ast(node: ASTNode, bindings: Dict[str, Type]) -> None:
    """Walk an AST tree and substitute generic type references with concrete types (iterative)."""
    from src.ast_nodes import NodeKind
    if node is None:
        return

    stack = [node]
    while stack:
        current = stack.pop()
        if current is None:
            continue

        # Substitute TYPE_GENERIC nodes
        if current.kind == NodeKind.TYPE_GENERIC:
            name = getattr(current, 'name', None)
            if name and name in bindings:
                concrete = bindings[name]
                current.kind = NodeKind.TYPE_IDENTIFIER
                current.name = str(concrete)

        # Push children onto stack
        for attr_name in vars(current):
            val = getattr(current, attr_name)
            if isinstance(val, ASTNode):
                stack.append(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, ASTNode):
                        stack.append(item)


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


def check_constraint_satisfaction(type_: Type, constraint: GenericConstraint) -> bool:
    """
    Check if a type satisfies a generic constraint.

    Args:
        type_: Type to check
        constraint: Constraint to satisfy

    Returns:
        True if type satisfies constraint
    """
    return constraint.check_satisfies(type_)


def infer_type_arguments(
    generic_params: List[str],
    param_types: List[Type],
    arg_types: List[Type]
) -> Optional[Dict[str, Type]]:
    """
    Infer generic type arguments from function call.

    Args:
        generic_params: Generic parameter names
        param_types: Function parameter types (may contain generic types)
        arg_types: Actual argument types

    Returns:
        Mapping of generic param names to inferred types, or None if inference fails
    """
    # Simple unification-based type inference
    bindings: Dict[str, Type] = {}

    for param_type, arg_type in zip(param_types, arg_types):
        if not unify_types(param_type, arg_type, bindings):
            return None

    # Check that all generic parameters were inferred
    for param_name in generic_params:
        if param_name not in bindings:
            return None

    return bindings


def unify_types(pattern: Type, concrete: Type, bindings: Dict[str, Type]) -> bool:
    """
    Unify a type pattern (possibly containing generics) with a concrete type (iterative).

    Args:
        pattern: Type pattern (may contain GenericParamType)
        concrete: Concrete type
        bindings: Current type bindings (modified in-place)

    Returns:
        True if unification succeeded
    """
    # Use a worklist of (pattern, concrete) pairs to unify
    worklist = [(pattern, concrete)]

    while worklist:
        pat, conc = worklist.pop()

        if isinstance(pat, GenericParamType):
            param_name = pat.name
            if param_name in bindings:
                if not bindings[param_name].equals(conc):
                    return False
            else:
                if pat.constraint and not pat.constraint.contains(conc):
                    return False
                bindings[param_name] = conc

        elif isinstance(pat, GenericInstanceType) and isinstance(conc, GenericInstanceType):
            if pat.base_name != conc.base_name:
                return False
            if len(pat.type_args) != len(conc.type_args):
                return False
            for p_arg, c_arg in zip(pat.type_args, conc.type_args):
                worklist.append((p_arg, c_arg))
        else:
            if not pat.equals(conc):
                return False

    return True
