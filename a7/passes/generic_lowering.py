"""Generic lowering helpers for backend code generation."""

from __future__ import annotations

import copy
import re
from typing import Dict, Iterable, List, Optional, Tuple

from a7.ast_nodes import ASTNode, LiteralKind, NodeKind
from a7.errors import CodegenError
from a7.types import (
    ArrayType,
    FunctionType,
    GenericInstanceType,
    GenericParamType,
    PointerType,
    PrimitiveType,
    ReferenceType,
    SliceType,
    StructType,
    Type,
    UnionType,
    VoidType,
)


class GenericLoweringPass:
    """Monomorphize simple top-level generic functions for non-generic backends."""

    def __init__(self) -> None:
        self._generic_functions: Dict[str, ASTNode] = {}
        self._generic_structs: Dict[str, ASTNode] = {}
        self._instances: Dict[Tuple[str, Tuple[Tuple[str, Type], ...]], str] = {}
        self._struct_instances: Dict[Tuple[str, Tuple[Type, ...]], str] = {}
        self._specialized_functions: List[ASTNode] = []
        self._specialized_structs: List[ASTNode] = []

    def process(self, program: ASTNode) -> ASTNode:
        """Return ``program`` with generic functions and structs specialized."""
        if program.kind != NodeKind.PROGRAM:
            return program

        declarations = program.declarations or []
        self._generic_functions = {
            decl.name: decl
            for decl in declarations
            if decl.kind == NodeKind.FUNCTION and decl.name and decl.generic_params
        }
        self._generic_structs = {
            decl.name: decl
            for decl in declarations
            if decl.kind == NodeKind.STRUCT and decl.name and self._struct_generic_param_names(decl)
        }
        if not self._generic_functions and not self._generic_structs:
            return program

        for decl in declarations:
            if (
                decl.kind == NodeKind.FUNCTION and decl.generic_params
            ) or (
                decl.kind == NodeKind.STRUCT and decl.name in self._generic_structs
            ):
                continue
            self._rewrite_generic_uses(decl)

        lowered_decls: List[ASTNode] = []
        for decl in declarations:
            if decl.kind == NodeKind.FUNCTION and decl.generic_params:
                continue
            if decl.kind == NodeKind.STRUCT and decl.name in self._generic_structs:
                continue
            lowered_decls.append(decl)

        insertion_index = self._first_function_index(lowered_decls)
        lowered_decls[insertion_index:insertion_index] = self._specialized_structs
        insertion_index += len(self._specialized_structs)
        lowered_decls[insertion_index:insertion_index] = self._specialized_functions
        program.declarations = lowered_decls
        return program

    def _rewrite_generic_uses(self, root: Optional[ASTNode]) -> None:
        if root is None:
            return

        stack = [root]
        while stack:
            node = stack.pop()
            if node is None:
                continue

            if node.kind == NodeKind.CALL:
                self._rewrite_call(node)
            elif node.kind == NodeKind.STRUCT_INIT:
                self._rewrite_struct_init(node)
            elif node.kind == NodeKind.TYPE_IDENTIFIER:
                self._rewrite_type_identifier(node)

            for child in self._iter_child_nodes(node):
                stack.append(child)

    def _rewrite_call(self, node: ASTNode) -> None:
        fn = node.function
        if fn is None or fn.kind != NodeKind.IDENTIFIER or not fn.name:
            return

        generic_fn = self._generic_functions.get(fn.name)
        if generic_fn is None:
            return

        mapping = getattr(node, "generic_mapping", None)
        if not mapping:
            raise CodegenError(
                f"C backend: cannot infer type arguments for generic function '{fn.name}'",
                node.span,
            )

        specialized_name = self._ensure_specialized_function(generic_fn, mapping)
        fn.name = specialized_name
        fn.emit_name = specialized_name

    def _ensure_specialized_function(self, func: ASTNode, mapping: Dict[str, Type]) -> str:
        func_name = func.name or "anonymous"
        ordered_names = [param.name for param in (func.generic_params or []) if param.name]
        key_items = tuple((name, mapping[name]) for name in ordered_names if name in mapping)
        if len(key_items) != len(ordered_names):
            missing = ", ".join(f"${name}" for name in ordered_names if name not in mapping)
            raise CodegenError(
                f"C backend: missing type arguments for generic function '{func_name}': {missing}",
                func.span,
            )

        cache_key = (func_name, key_items)
        cached = self._instances.get(cache_key)
        if cached:
            return cached

        suffix = "__".join(self._mangle_type(type_) for _, type_ in key_items)
        specialized_name = f"{func_name}__{suffix}"
        specialized = copy.deepcopy(func)
        specialized.name = specialized_name
        specialized.generic_params = []
        self._substitute_type_nodes(specialized, mapping)

        self._instances[cache_key] = specialized_name
        self._specialized_functions.append(specialized)
        self._rewrite_generic_uses(specialized)
        return specialized_name

    def _rewrite_struct_init(self, node: ASTNode) -> None:
        if not isinstance(node.struct_type, str) or node.struct_type not in self._generic_structs:
            return
        type_args = [self._type_from_ast(arg) for arg in (node.type_arguments or [])]
        if not type_args:
            return
        specialized_name = self._ensure_specialized_struct(
            self._generic_structs[node.struct_type],
            type_args,
            node.span,
        )
        node.struct_type = specialized_name
        node.type_arguments = []

    def _rewrite_type_identifier(self, node: ASTNode) -> None:
        if not node.name or node.name not in self._generic_structs or not node.generic_params:
            return
        type_args = [self._type_from_ast(arg) for arg in node.generic_params]
        specialized_name = self._ensure_specialized_struct(
            self._generic_structs[node.name],
            type_args,
            node.span,
        )
        node.name = specialized_name
        node.generic_params = []

    def _ensure_specialized_struct(
        self,
        struct: ASTNode,
        type_args: List[Type],
        span=None,
    ) -> str:
        struct_name = struct.name or "anonymous"
        params = self._struct_generic_param_names(struct)
        if len(params) != len(type_args):
            expected = ", ".join(f"${name}" for name in params)
            raise CodegenError(
                f"C backend: generic struct '{struct_name}' expects type arguments: {expected}",
                span or struct.span,
            )

        cache_key = (struct_name, tuple(type_args))
        cached = self._struct_instances.get(cache_key)
        if cached:
            return cached

        suffix = "__".join(self._mangle_type(type_) for type_ in type_args)
        specialized_name = f"{struct_name}__{suffix}"
        mapping = {name: type_ for name, type_ in zip(params, type_args)}
        specialized = copy.deepcopy(struct)
        specialized.name = specialized_name
        specialized.generic_params = []
        self._substitute_type_nodes(specialized, mapping)

        self._struct_instances[cache_key] = specialized_name
        self._rewrite_generic_uses(specialized)
        self._specialized_structs.append(specialized)
        return specialized_name

    def _substitute_type_nodes(self, node: Optional[ASTNode], mapping: Dict[str, Type]) -> None:
        if node is None:
            return

        stack = [node]
        while stack:
            current = stack.pop()
            if current.kind == NodeKind.TYPE_GENERIC and current.name in mapping:
                replacement = self._type_to_ast(mapping[current.name], current.span)
                current.kind = replacement.kind
                current.name = replacement.name
                current.type_name = replacement.type_name
                current.target_type = replacement.target_type
                current.element_type = replacement.element_type
                current.size = replacement.size
                current.parameter_types = replacement.parameter_types
                current.return_type = replacement.return_type
                current.type_args = replacement.type_args
                current.generic_params = replacement.generic_params

            for child in self._iter_child_nodes(current):
                stack.append(child)

    def _type_to_ast(self, type_: Type, span=None) -> ASTNode:
        if isinstance(type_, PrimitiveType):
            return ASTNode(kind=NodeKind.TYPE_PRIMITIVE, type_name=type_.name, span=span)
        if isinstance(type_, ArrayType):
            return ASTNode(
                kind=NodeKind.TYPE_ARRAY,
                element_type=self._type_to_ast(type_.element_type, span),
                size=ASTNode(
                    kind=NodeKind.LITERAL,
                    literal_kind=LiteralKind.INTEGER,
                    literal_value=type_.size,
                    span=span,
                ),
                span=span,
            )
        if isinstance(type_, SliceType):
            return ASTNode(
                kind=NodeKind.TYPE_SLICE,
                element_type=self._type_to_ast(type_.element_type, span),
                span=span,
            )
        if isinstance(type_, (PointerType, ReferenceType)):
            target = type_.pointee_type if isinstance(type_, PointerType) else type_.referent_type
            return ASTNode(
                kind=NodeKind.TYPE_POINTER,
                target_type=self._type_to_ast(target, span),
                span=span,
            )
        if isinstance(type_, FunctionType):
            return ASTNode(
                kind=NodeKind.TYPE_FUNCTION,
                parameter_types=[self._type_to_ast(t, span) for t in type_.param_types],
                return_type=self._type_to_ast(type_.return_type, span) if type_.return_type else None,
                is_variadic=type_.is_variadic,
                span=span,
            )
        if isinstance(type_, GenericInstanceType):
            return ASTNode(
                kind=NodeKind.TYPE_IDENTIFIER,
                name=type_.base_name,
                generic_params=[self._type_to_ast(t, span) for t in type_.type_args],
                span=span,
            )
        if isinstance(type_, (StructType, UnionType)) and type_.name:
            return ASTNode(kind=NodeKind.TYPE_IDENTIFIER, name=type_.name, span=span)
        if isinstance(type_, VoidType):
            return ASTNode(kind=NodeKind.TYPE_PRIMITIVE, type_name="void", span=span)
        if isinstance(type_, GenericParamType):
            return ASTNode(kind=NodeKind.TYPE_GENERIC, name=type_.name, span=span)

        raise CodegenError(f"C backend: unsupported generic specialization type '{type_}'", span)

    def _type_from_ast(self, node: ASTNode) -> Type:
        if node.kind == NodeKind.TYPE_PRIMITIVE:
            return PrimitiveType(node.type_name or "i32")
        if node.kind == NodeKind.TYPE_IDENTIFIER:
            if node.generic_params:
                return GenericInstanceType(
                    base_name=node.name or "",
                    type_args=tuple(self._type_from_ast(arg) for arg in node.generic_params),
                )
            return StructType(name=node.name or "", fields=())
        if node.kind == NodeKind.TYPE_GENERIC:
            return GenericParamType(node.name or "T")
        if node.kind == NodeKind.TYPE_ARRAY:
            size = 0
            if node.size and node.size.kind == NodeKind.LITERAL and isinstance(node.size.literal_value, int):
                size = node.size.literal_value
            return ArrayType(element_type=self._type_from_ast(node.element_type), size=size)
        if node.kind == NodeKind.TYPE_SLICE:
            return SliceType(element_type=self._type_from_ast(node.element_type))
        if node.kind == NodeKind.TYPE_POINTER:
            return ReferenceType(referent_type=self._type_from_ast(node.target_type))
        if node.kind == NodeKind.TYPE_FUNCTION:
            return FunctionType(
                param_types=tuple(self._type_from_ast(t) for t in (node.parameter_types or [])),
                return_type=self._type_from_ast(node.return_type) if node.return_type else None,
                is_variadic=node.is_variadic,
            )
        raise CodegenError(f"C backend: unsupported generic type argument AST '{node.kind.name}'", node.span)

    def _struct_generic_param_names(self, node: ASTNode) -> List[str]:
        explicit = [param.name for param in (node.generic_params or []) if param.name]
        if explicit:
            return explicit

        names: List[str] = []
        for field in (node.fields or []):
            self._collect_generic_param_names(field.field_type, names)
        return list(dict.fromkeys(names))

    def _collect_generic_param_names(self, node: Optional[ASTNode], out: List[str]) -> None:
        if node is None:
            return
        stack = [node]
        while stack:
            current = stack.pop()
            if current is None:
                continue
            if current.kind == NodeKind.TYPE_GENERIC and current.name:
                out.append(current.name)
            for child in self._iter_child_nodes(current):
                stack.append(child)

    def _mangle_type(self, type_: Type) -> str:
        text = str(type_)
        text = text.replace("[]", "slice_")
        text = text.replace("[", "arr_").replace("]", "_")
        text = text.replace("*", "ptr")
        text = text.replace(" ", "_")
        return re.sub(r"[^0-9A-Za-z_]+", "_", text).strip("_") or "type"

    def _first_function_index(self, declarations: List[ASTNode]) -> int:
        for index, decl in enumerate(declarations):
            if decl.kind == NodeKind.FUNCTION:
                return index
        return len(declarations)

    def _iter_child_nodes(self, node: ASTNode) -> Iterable[ASTNode]:
        for value in vars(node).values():
            if isinstance(value, ASTNode):
                yield value
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ASTNode):
                        yield item
