"""
Type checking pass for A7 semantic analysis.

Performs type inference, type checking, and type compatibility validation.
"""

from typing import Any, Optional, List, Dict, Set, Tuple

from a7.ast_nodes import ASTNode, NodeKind, BinaryOp, UnaryOp, AssignOp, LiteralKind
from a7.symbol_table import SymbolTable, Symbol, SymbolKind
from a7.semantic_context import SemanticContext
from a7.cast_classifier import classify_cast
from a7.generics import resolve_generic_constraint
from a7.types import (
    Type, TypeKind,
    PrimitiveType, ArrayType, SliceType, PointerType, ReferenceType,
    FunctionType, StructType, StructField, EnumType, EnumVariant,
    UnionType, UnionField, GenericParamType, GenericInstanceType,
    TypeSet, VoidType, UnknownType,
    BOOL, CHAR, STRING, I8, I16, I32, I64, U8, U16, U32, U64, F32, F64,
    USIZE,
    VOID, UNKNOWN, NUMERIC, INTEGER,
    get_primitive_type, get_predefined_type_set
)
from a7.errors import SemanticError, TypeCheckError, TypeErrorType, SemanticErrorType, SourceSpan
from a7.stdlib import StdlibRegistry


class TypeCheckingPass:
    """
    Second pass of semantic analysis.

    Performs:
    1. Type inference for := declarations
    2. Type checking for all expressions
    3. Function call argument/return type validation
    4. Assignment compatibility checking
    5. Generic type constraint validation
    """

    def __init__(self, symbols: SymbolTable):
        """
        Initialize type checking pass.

        Args:
            symbols: Symbol table from name resolution pass
        """
        self.symbols = symbols
        self.context = SemanticContext()
        self.errors: List[SemanticError] = []
        self.current_file: str = "<unknown>"
        self.source_lines: List[str] = []

        # Cache for type information attached to AST nodes
        self.node_types: Dict[int, Type] = {}
        # Tracks sequential reuse of child scopes by (parent_scope_id, scope_name)
        self._scope_reuse_positions: Dict[tuple[int, str], int] = {}
        self._resolving_type_aliases: Set[str] = set()
        self._resolved_type_aliases: Set[str] = set()
        self._generic_constraints: Dict[str, TypeSet] = {}
        self._nonnegative_vars: Set[str] = set()
        self.stdlib = StdlibRegistry()

    def analyze(self, program: ASTNode, filename: str = "<unknown>") -> Dict[int, Type]:
        """
        Perform type checking on a program.

        Args:
            program: Root program node
            filename: Source file name

        Returns:
            Dict mapping node IDs to their types

        Note:
            Collects ALL errors instead of stopping at the first one.
            Check self.errors after calling to see if there were any issues.
        """
        self.current_file = filename
        self.errors = []
        self._scope_reuse_positions = {}
        self._resolving_type_aliases = set()
        self._resolved_type_aliases = set()
        self._generic_constraints = {}
        self._nonnegative_vars = set()

        # Visit the program
        self.visit_program(program)

        # Return the node types map for use by later passes
        return self.node_types

    def add_error(self, message: str, span: Optional[SourceSpan] = None) -> None:
        """Add a type checking error (legacy - prefer add_type_error)."""
        error = SemanticError(message, span, self.current_file)
        self.errors.append(error)

    def add_type_error(
        self,
        error_type: TypeErrorType,
        span: Optional[SourceSpan] = None,
        expected_type: Optional[str] = None,
        got_type: Optional[str] = None,
        context: Optional[str] = None,
    ) -> None:
        """Add a type checking error with structured type."""
        error = TypeCheckError.from_type(
            error_type,
            span=span,
            filename=self.current_file,
            source_lines=self.source_lines,
            expected_type=expected_type,
            got_type=got_type,
            context=context,
        )
        self.errors.append(error)

    def add_semantic_error(
        self,
        error_type: SemanticErrorType,
        span: Optional[SourceSpan] = None,
        context: Optional[str] = None,
    ) -> None:
        """Add a semantic error from the type checker."""
        error = SemanticError.from_type(
            error_type,
            span=span,
            filename=self.current_file,
            source_lines=self.source_lines,
            context=context,
        )
        self.errors.append(error)

    def set_type(self, node: ASTNode, type_: Type) -> None:
        """Associate a type with an AST node."""
        self.node_types[id(node)] = type_

    def get_type(self, node: ASTNode) -> Optional[Type]:
        """Get the type of an AST node."""
        return self.node_types.get(id(node))

    def _enter_matching_scope(self, name: str) -> None:
        """Enter the next child scope matching name under the current scope."""
        parent = self.symbols.current_scope
        key = (id(parent), name)
        start = self._scope_reuse_positions.get(key, 0)
        matches = [child for child in parent.children if child.name == name]

        if start < len(matches):
            scope = matches[start]
            self._scope_reuse_positions[key] = start + 1
            self.symbols.current_scope = scope
            self.symbols.scope_stack.append(scope)
            return

        # Fallback for malformed/partial ASTs not seen by name resolution
        self.symbols.enter_scope(name)

    def _is_variadic_function(self, node: ASTNode) -> bool:
        if getattr(node, "is_variadic", False):
            return True
        return bool(node.parameters and getattr(node.parameters[-1], "is_variadic", False))

    # Visitor methods

    def visit_program(self, node: ASTNode) -> None:
        """Visit program root."""
        if node.kind != NodeKind.PROGRAM:
            error = SemanticError.from_type(SemanticErrorType.UNEXPECTED_NODE_KIND, span=node.span, filename=self.current_file, source_lines=self.source_lines, context=f"Expected program node, got {node.kind}")
            self.errors.append(error)
            return

        # First pass: register all type declarations
        for decl in node.declarations or []:
            if decl.kind in {NodeKind.STRUCT, NodeKind.ENUM, NodeKind.UNION, NodeKind.TYPE_ALIAS}:
                self.register_type_decl(decl)

        # Second pass: register function signatures (for mutual recursion support)
        for decl in node.declarations or []:
            if decl.kind == NodeKind.FUNCTION:
                self.register_function_signature(decl)

        # Third pass: type check all declarations (including function bodies)
        for decl in node.declarations or []:
            self.visit_declaration(decl)

    def register_type_decl(self, node: ASTNode) -> None:
        """Register a type declaration (first pass)."""
        if node.kind == NodeKind.STRUCT:
            self.register_struct_type(node)
        elif node.kind == NodeKind.ENUM:
            self.register_enum_type(node)
        elif node.kind == NodeKind.UNION:
            self.register_union_type(node)
        elif node.kind == NodeKind.TYPE_ALIAS:
            self.register_type_alias(node)

    def register_type_alias(self, node: ASTNode) -> None:
        """Resolve and register a type alias."""
        alias_name = node.name or "<anonymous>"
        if alias_name in self._resolved_type_aliases:
            return
        if alias_name in self._resolving_type_aliases:
            self.errors.append(
                SemanticError(
                    f"Circular type alias dependency involving '{alias_name}'",
                    node.span,
                    self.current_file,
                )
            )
            return

        self._resolving_type_aliases.add(alias_name)
        try:
            alias_type = self.resolve_type_node(node.value) if node.value else UNKNOWN
        finally:
            self._resolving_type_aliases.remove(alias_name)

        symbol = self.symbols.lookup(alias_name)
        if symbol:
            symbol.type = alias_type
        else:
            self.symbols.define(
                Symbol(
                    name=alias_name,
                    kind=SymbolKind.TYPE,
                    type=alias_type,
                    node=node,
                    is_mutable=False,
                )
            )
        self._resolved_type_aliases.add(alias_name)

    def register_function_signature(self, node: ASTNode) -> None:
        """Register a function's signature (type) without processing its body.

        This enables mutual recursion support - all function types are known
        before any function bodies are type-checked.
        """
        func_name = node.name or "<anonymous>"
        previous_constraints = self._generic_constraints
        self._generic_constraints = self._generic_constraints_from_params(node.generic_params or [])
        func_type: Optional[FunctionType] = None

        try:
            # Resolve return type
            return_type = self.resolve_type_node(node.return_type) if node.return_type else None

            # Resolve parameter types
            param_types = []
            if node.parameters:
                for param in node.parameters:
                    param_type = self.resolve_type_node(param.param_type) if param.param_type else UNKNOWN
                    param_types.append(param_type)

            # Check for variadic
            is_variadic = self._is_variadic_function(node)

            variadic_type = None
            if is_variadic and node.parameters:
                last_param = node.parameters[-1]
                if last_param.param_type:
                    variadic_type = self.resolve_type_node(last_param.param_type)

            # Create function type
            func_type = FunctionType(
                param_types=tuple(param_types),
                return_type=return_type,
                is_variadic=is_variadic,
                variadic_type=variadic_type,
                generic_param_order=tuple(param.name for param in (node.generic_params or []) if param.name),
            )
        finally:
            self._generic_constraints = previous_constraints

        # Update function symbol
        func_symbol = self.symbols.lookup(func_name)
        if func_symbol and func_type is not None:
            func_symbol.type = func_type

    def _generic_constraints_from_params(self, generic_params: List[ASTNode]) -> Dict[str, TypeSet]:
        """Resolve declared generic parameter constraints by parameter name."""
        constraints: Dict[str, TypeSet] = {}
        for param in generic_params:
            if param.kind != NodeKind.GENERIC_PARAM or not param.name:
                continue
            resolved = self._resolve_generic_constraint_node(param.constraint)
            if resolved is not None:
                constraints[param.name] = resolved
        return constraints

    def _resolve_generic_constraint_node(self, constraint_node: Optional[ASTNode]) -> Optional[TypeSet]:
        """Resolve inline, predefined, or locally aliased generic type-set constraints."""
        resolved = resolve_generic_constraint(constraint_node)
        if resolved is not None or constraint_node is None:
            return resolved

        if constraint_node.kind == NodeKind.TYPE_IDENTIFIER:
            name = constraint_node.name or constraint_node.type_name or ""
            symbol = self.symbols.lookup(name)
            if symbol and symbol.kind == SymbolKind.CONSTANT and symbol.node is not None:
                return resolve_generic_constraint(getattr(symbol.node, "value", None))

        return None

    def register_struct_type(self, node: ASTNode) -> None:
        """Register a struct type."""
        struct_name = node.name or "<anonymous>"

        # Create struct fields (types will be resolved lazily)
        fields = []
        if node.fields:
            for field_node in node.fields:
                if field_node.kind == NodeKind.FIELD:
                    field_name = field_node.name or "<unknown>"
                    # Resolve field type
                    field_type = self.resolve_type_node(field_node.field_type) if field_node.field_type else UNKNOWN
                    fields.append(StructField(name=field_name, field_type=field_type))

        # Create struct type
        generic_params = tuple(gp.name for gp in (node.generic_params or []))
        if not generic_params:
            discovered: List[str] = []
            for field in fields:
                self._collect_generic_type_names(field.field_type, discovered)
            # Preserve encounter order while deduplicating
            generic_params = tuple(dict.fromkeys(discovered))
        struct_type = StructType(name=struct_name, fields=tuple(fields), generic_params=generic_params)

        # Update symbol
        symbol = self.symbols.lookup(struct_name)
        if symbol:
            symbol.type = struct_type

    def register_enum_type(self, node: ASTNode) -> None:
        """Register an enum type."""
        enum_name = node.name or "<anonymous>"

        # Create enum variants
        variants = []
        if node.variants:
            for variant_node in node.variants:
                if variant_node.kind == NodeKind.ENUM_VARIANT:
                    variant_name = variant_node.name or "<unknown>"
                    # Extract value if present (will be int literal)
                    value = None
                    if variant_node.value:
                        value = self.extract_int_value(variant_node.value)
                    variants.append(EnumVariant(name=variant_name, value=value))

        # Create enum type
        enum_type = EnumType(name=enum_name, variants=tuple(variants))

        # Update symbol
        symbol = self.symbols.lookup(enum_name)
        if symbol:
            symbol.type = enum_type

    def register_union_type(self, node: ASTNode) -> None:
        """Register a union type."""
        union_name = node.name or "<anonymous>"

        # Create union fields
        fields = []
        if node.fields:
            for field_node in node.fields:
                if field_node.kind == NodeKind.FIELD:
                    field_name = field_node.name or "<unknown>"
                    field_type = self.resolve_type_node(field_node.field_type) if field_node.field_type else UNKNOWN
                    fields.append(UnionField(name=field_name, field_type=field_type))

        # Create union type
        union_type = UnionType(name=union_name, fields=tuple(fields))

        # Update symbol
        symbol = self.symbols.lookup(union_name)
        if symbol:
            symbol.type = union_type

    def extract_int_value(self, node: ASTNode) -> Optional[int]:
        """Extract integer value from a literal node."""
        if node.kind == NodeKind.LITERAL and node.literal_kind == LiteralKind.INTEGER:
            return node.literal_value
        return None

    def resolve_type_node(self, node: Optional[ASTNode]) -> Type:
        """Resolve a type expression to a Type object (iterative for wrapper chains)."""
        if node is None:
            return UNKNOWN

        # Iteratively unwrap linear type chains (array/slice/pointer)
        wrappers: list = []  # ('kind', extra_data)
        current = node

        while current is not None:
            if current.kind == NodeKind.TYPE_ARRAY:
                size = self.extract_int_value(current.size) if current.size else 0
                wrappers.append(('array', size))
                current = current.element_type
            elif current.kind == NodeKind.TYPE_SLICE:
                wrappers.append(('slice', None))
                current = current.element_type
            elif current.kind == NodeKind.TYPE_POINTER:
                wrappers.append(('ref', None))
                current = current.target_type
            else:
                break  # Leaf type node — resolve it

        # Resolve the leaf type
        result = self._resolve_type_leaf(current)

        # Reconstruct wrapper types in reverse
        for kind, data in reversed(wrappers):
            if kind == 'array':
                result = ArrayType(element_type=result, size=data)
            elif kind == 'slice':
                result = SliceType(element_type=result)
            elif kind == 'ref':
                result = ReferenceType(referent_type=result)

        return result

    def _resolve_type_leaf(self, node: Optional[ASTNode]) -> Type:
        """Resolve a leaf (non-wrapper) type node."""
        if node is None:
            return UNKNOWN

        if node.kind == NodeKind.TYPE_PRIMITIVE:
            type_name = node.type_name or ""
            prim_type = get_primitive_type(type_name)
            return prim_type if prim_type else UNKNOWN

        elif node.kind == NodeKind.TYPE_IDENTIFIER:
            type_name = node.name or node.type_name or ""
            if node.generic_params:
                type_args = [self.resolve_type_node(arg) for arg in node.generic_params]
                return GenericInstanceType(base_name=type_name, type_args=tuple(type_args))
            symbol = self.symbols.lookup(type_name)
            if symbol:
                if symbol.kind not in {
                    SymbolKind.TYPE,
                    SymbolKind.STRUCT,
                    SymbolKind.ENUM,
                    SymbolKind.UNION,
                    SymbolKind.GENERIC_PARAM,
                }:
                    self.add_type_error(TypeErrorType.UNDEFINED_TYPE, node.span, context=f"Type '{type_name}'")
                    return UNKNOWN
                if symbol.kind == SymbolKind.TYPE and symbol.node is not None and symbol.node.kind == NodeKind.TYPE_ALIAS:
                    self.register_type_alias(symbol.node)
                return symbol.type
            else:
                self.add_type_error(TypeErrorType.UNDEFINED_TYPE, node.span, context=f"Type '{type_name}'")
                return UNKNOWN

        elif node.kind in (NodeKind.TYPE_ARRAY, NodeKind.TYPE_SLICE, NodeKind.TYPE_POINTER):
            # These should have been handled by the iterative unwrapping,
            # but handle gracefully if called directly
            return self.resolve_type_node(node)

        elif node.kind == NodeKind.TYPE_FUNCTION:
            param_types = []
            if node.parameter_types:
                for pt in node.parameter_types:
                    param_types.append(self.resolve_type_node(pt))
            return_type = self.resolve_type_node(node.return_type) if node.return_type else None
            is_variadic = node.is_variadic or False
            if is_variadic:
                # Variadic function-pointer types are parsed but not lowered;
                # match the diagnostic from visit_function_decl so the error
                # surfaces uniformly across declarations and aliases.
                self.errors.append(
                    SemanticError.from_type(
                        SemanticErrorType.UNSUPPORTED_FEATURE,
                        span=node.span,
                        filename=self.current_file,
                        source_lines=self.source_lines,
                        custom_message=(
                            "Variadic function pointers are parsed for future support, "
                            "but Zig ABI/lowering is not implemented yet"
                        ),
                    )
                )
            variadic_type = self.resolve_type_node(node.param_type) if node.param_type and is_variadic else None
            return FunctionType(
                param_types=tuple(param_types), return_type=return_type,
                is_variadic=is_variadic, variadic_type=variadic_type
            )

        elif node.kind == NodeKind.TYPE_STRUCT:
            fields = []
            if node.fields:
                for field_node in node.fields:
                    if field_node.kind == NodeKind.FIELD:
                        field_name = field_node.name or "<unknown>"
                        field_type = self.resolve_type_node(field_node.field_type) if field_node.field_type else UNKNOWN
                        fields.append(StructField(name=field_name, field_type=field_type))
            return StructType(name=None, fields=tuple(fields))

        elif node.kind == NodeKind.TYPE_GENERIC:
            if node.name and not node.type_name and not node.type_args:
                return GenericParamType(
                    name=node.name,
                    constraint=self._generic_constraints.get(node.name),
                )
            else:
                base_name = node.type_name or ""
                type_args = []
                if node.type_args:
                    for arg in node.type_args:
                        type_args.append(self.resolve_type_node(arg))
                return GenericInstanceType(base_name=base_name, type_args=tuple(type_args))

        elif node.kind == NodeKind.TYPE_SET:
            types_in_set = []
            if node.types:
                for t in node.types:
                    types_in_set.append(self.resolve_type_node(t))
            return TypeSet(types=frozenset(types_in_set))

        else:
            error = SemanticError.from_type(SemanticErrorType.UNEXPECTED_NODE_KIND, span=node.span, filename=self.current_file, source_lines=self.source_lines, context=f"Unknown type node kind: {node.kind}")
            self.errors.append(error)
            return UNKNOWN

    def visit_declaration(self, node: ASTNode) -> None:
        """Visit a top-level declaration."""
        if node.kind == NodeKind.FUNCTION:
            self.visit_function_decl(node)
        elif node.kind == NodeKind.CONST:
            self.visit_const_decl(node)
        elif node.kind == NodeKind.VAR:
            self.visit_var_decl(node)
        elif node.kind == NodeKind.TYPE_ALIAS:
            self.register_type_alias(node)
        # Struct/enum/union already registered

    def visit_function_decl(self, node: ASTNode) -> None:
        """Visit and type check a function declaration."""
        func_name = node.name or "<anonymous>"
        previous_constraints = self._generic_constraints
        self._generic_constraints = self._generic_constraints_from_params(node.generic_params or [])

        try:
            # Enter function scope for parameter and body processing
            self._enter_matching_scope(f"function_{func_name}")

            # Resolve return type
            return_type = self.resolve_type_node(node.return_type) if node.return_type else None

            # Resolve parameter types and update existing parameter symbols
            param_types = []
            if node.parameters:
                for param in node.parameters:
                    param_type = self.resolve_type_node(param.param_type) if param.param_type else UNKNOWN
                    param_types.append(param_type)

                    # Update existing parameter symbol's type (symbol was defined during name resolution)
                    param_name = param.name or ""
                    existing_symbol = self.symbols.lookup(param_name)
                    if existing_symbol:
                        existing_symbol.type = param_type
                    else:
                        # Symbol wasn't defined by name resolution - define it now
                        param_symbol = Symbol(
                            name=param_name,
                            kind=SymbolKind.VARIABLE,
                            type=param_type,
                            node=param,
                            is_mutable=False
                        )
                        self.symbols.define(param_symbol)

            # Check for variadic (variadic flag may be on function node or last parameter)
            is_variadic = self._is_variadic_function(node)
            if is_variadic:
                self.errors.append(
                    SemanticError.from_type(
                        SemanticErrorType.UNSUPPORTED_FEATURE,
                        span=node.span,
                        filename=self.current_file,
                        source_lines=self.source_lines,
                        custom_message=(
                            "Variadic parameters are parsed for future support, "
                            "but Zig ABI/lowering is not implemented yet"
                        ),
                    )
                )

            variadic_type = None
            if is_variadic and node.parameters:
                last_param = node.parameters[-1]
                if last_param.param_type:
                    variadic_type = self.resolve_type_node(last_param.param_type)

            # Create function type
            func_type = FunctionType(
                param_types=tuple(param_types),
                return_type=return_type,
                is_variadic=is_variadic,
                variadic_type=variadic_type,
                generic_param_order=tuple(param.name for param in (node.generic_params or []) if param.name),
            )

            # Update function symbol (in outer scope)
            func_symbol = self.symbols.lookup(func_name)
            if func_symbol:
                func_symbol.type = func_type

            # Enter function context
            self.context.enter_function(func_name, return_type, node)

            # Type check body
            if node.body:
                self.visit_statement(node.body)

            # Check that non-void functions have return
            if return_type is not None and not self.context.function_has_return():
                # Allow functions that might not return (e.g., always infinite loop)
                # This is a warning-level issue, not an error
                pass

            # Exit function context
            self.context.exit_function()

            # Exit function scope
            self.symbols.exit_scope()
        finally:
            self._generic_constraints = previous_constraints

    def visit_const_decl(self, node: ASTNode) -> None:
        """Visit a constant declaration."""
        const_name = node.name or "<unknown>"

        # Type check the value
        value_type = UNKNOWN
        if node.value:
            value_type = self.visit_expression(node.value)

        # If explicit type given, check compatibility
        if node.explicit_type:
            explicit_type = self.resolve_type_node(node.explicit_type)
            if not value_type.is_assignable_to(explicit_type):
                self.add_type_error(
                    TypeErrorType.TYPE_MISMATCH,
                    node.span,
                    expected_type=str(explicit_type),
                    got_type=str(value_type),
                    context=f"Constant '{const_name}'"
                )
            value_type = explicit_type

        # Update symbol
        symbol = self.symbols.lookup(const_name)
        if symbol:
            symbol.type = value_type

    def visit_var_decl(self, node: ASTNode) -> None:
        """Visit a variable declaration."""
        var_name = node.name or "<unknown>"

        # Check for nil literal
        is_nil_value = (node.value and node.value.kind == NodeKind.LITERAL
                        and node.value.literal_kind == LiteralKind.NIL)

        # Type check the value if present
        value_type = UNKNOWN
        if node.value:
            value_type = self.visit_expression(node.value)

        # Determine final type
        if node.explicit_type:
            # Explicit type annotation
            explicit_type = self.resolve_type_node(node.explicit_type)

            # Check nil assignment to non-reference type
            if is_nil_value and not isinstance(explicit_type, ReferenceType):
                self.add_type_error(
                    TypeErrorType.NIL_ONLY_FOR_REFERENCES,
                    node.span,
                    got_type=str(explicit_type),
                    context=f"Variable '{var_name}'"
                )
            elif (
                node.value
                and not is_nil_value
                and not self._is_initializer_assignable_to(
                    node.value,
                    value_type,
                    explicit_type,
                    node.span,
                    context=f"Variable '{var_name}'",
                )
            ):
                # Generic locals may be initialized from literals before call-site substitution.
                is_generic_relaxed = (
                    isinstance(explicit_type, GenericParamType)
                    and (
                        isinstance(value_type, (GenericParamType, UnknownType))
                        or (
                            node.value.kind == NodeKind.LITERAL
                            and node.value.literal_kind in {
                                LiteralKind.INTEGER,
                                LiteralKind.FLOAT,
                                LiteralKind.CHAR,
                                LiteralKind.STRING,
                                LiteralKind.BOOLEAN,
                            }
                        )
                    )
                )
                if is_generic_relaxed:
                    value_type = explicit_type
                else:
                    self.add_type_error(
                        TypeErrorType.TYPE_MISMATCH,
                        node.span,
                        expected_type=str(explicit_type),
                        got_type=str(value_type),
                        context=f"Variable '{var_name}'"
                    )
            if node.value and not is_nil_value and isinstance(explicit_type, GenericParamType):
                value_type = explicit_type
            value_type = explicit_type
        elif not node.value:
            # No value and no type - error
            error = SemanticError.from_type(SemanticErrorType.MISSING_TYPE_ANNOTATION, span=node.span, filename=self.current_file, source_lines=self.source_lines, context=f"Variable '{var_name}' requires either type annotation or initializer")
            self.errors.append(error)
            value_type = UNKNOWN
        elif is_nil_value:
            error = SemanticError.from_type(
                SemanticErrorType.MISSING_TYPE_ANNOTATION,
                span=node.span,
                filename=self.current_file,
                source_lines=self.source_lines,
                context=f"Variable '{var_name}' initialized with nil requires an explicit ref type",
            )
            self.errors.append(error)
            value_type = UNKNOWN

        # Update the existing symbol's type (symbol was defined during name resolution)
        existing_symbol = self.symbols.lookup(var_name)
        if existing_symbol:
            existing_symbol.type = value_type
        else:
            # Symbol wasn't defined by name resolution - define it now
            var_symbol = Symbol(
                name=var_name,
                kind=SymbolKind.VARIABLE,
                type=value_type,
                node=node,
                is_mutable=True
            )
            self.symbols.define(var_symbol)

    def visit_statement(self, node: ASTNode) -> None:
        """Visit a statement (iterative)."""
        # Stack items: ('visit', node) or ('action', callable)
        stack: list = [('visit', node)]

        while stack:
            action, item = stack.pop()

            if action == 'action':
                item()
                continue

            nd = item  # action == 'visit'

            if nd.kind == NodeKind.BLOCK:
                self._enter_matching_scope("block")
                saved_facts = set(self._nonnegative_vars)
                try:
                    for stmt in nd.statements or []:
                        self.visit_statement(stmt)
                        self._learn_fact_after_statement(stmt)
                finally:
                    self._nonnegative_vars = saved_facts
                    self.symbols.exit_scope()

            elif nd.kind == NodeKind.VAR:
                self.visit_var_decl(nd)
            elif nd.kind == NodeKind.CONST:
                self.visit_const_decl(nd)
            elif nd.kind == NodeKind.TYPE_ALIAS:
                self.register_type_alias(nd)

            elif nd.kind == NodeKind.EXPRESSION_STMT:
                if nd.expression:
                    self.visit_expression(nd.expression)

            elif nd.kind == NodeKind.ASSIGNMENT:
                self.visit_assignment(nd)

            elif nd.kind == NodeKind.IF_STMT:
                self.visit_if_stmt(nd)

            elif nd.kind == NodeKind.WHILE:
                self.visit_while_stmt(nd)

            elif nd.kind == NodeKind.FOR:
                self.visit_for_stmt(nd)

            elif nd.kind in (NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED):
                self.visit_for_in_stmt(nd)

            elif nd.kind == NodeKind.MATCH:
                self.visit_match_stmt(nd)

            elif nd.kind == NodeKind.RETURN:
                self.visit_return_stmt(nd)

            elif nd.kind in (NodeKind.BREAK, NodeKind.CONTINUE):
                pass

            elif nd.kind == NodeKind.DEFER:
                deferred_stmt = getattr(nd, "statement", None)
                if deferred_stmt:
                    self.visit_statement(deferred_stmt)
                elif nd.expression:
                    self.visit_expression(nd.expression)

            elif nd.kind == NodeKind.DEL:
                if nd.expression:
                    self.visit_expression(nd.expression)

    def visit_assignment(self, node: ASTNode) -> None:
        """Visit an assignment statement."""
        # Type check both sides
        lhs_type = self.visit_expression(node.target) if node.target else UNKNOWN
        rhs_type = self.visit_expression(node.value) if node.value else UNKNOWN
        effective_lhs_type = lhs_type

        if (
            isinstance(lhs_type, ReferenceType)
            and not isinstance(rhs_type, ReferenceType)
            and rhs_type.is_assignable_to(lhs_type.referent_type)
        ):
            if node.target and self._is_lvalue_expression(node.target):
                setattr(node, "implicit_deref_target", True)
                effective_lhs_type = lhs_type.referent_type
            else:
                self.add_type_error(
                    TypeErrorType.CANNOT_DEREFERENCE,
                    node.span,
                    got_type=str(lhs_type),
                    context="Assignment through a reference requires a named lvalue",
                )

        # Mutability check: look up the target symbol
        if node.target and node.target.kind == NodeKind.IDENTIFIER:
            target_name = node.target.name
            sym = self.symbols.lookup(target_name)
            if sym and not sym.is_mutable and node.target.kind != NodeKind.DEREF and not getattr(node, "implicit_deref_target", False):
                self.add_semantic_error(
                    SemanticErrorType.CANNOT_ASSIGN_TO_IMMUTABLE,
                    node.span,
                    context=f"'{target_name}' is immutable"
                )

        # Compound assignment operator type checking
        op = getattr(node, 'op', None)
        if op and op != AssignOp.ASSIGN:
            arithmetic_ops = {AssignOp.ADD_ASSIGN, AssignOp.SUB_ASSIGN, AssignOp.MUL_ASSIGN, AssignOp.DIV_ASSIGN, AssignOp.MOD_ASSIGN}
            bitwise_ops = {AssignOp.AND_ASSIGN, AssignOp.OR_ASSIGN, AssignOp.XOR_ASSIGN, AssignOp.SHL_ASSIGN, AssignOp.SHR_ASSIGN}

            if op in arithmetic_ops:
                if not self._is_numeric_compatible(effective_lhs_type):
                    self.add_type_error(TypeErrorType.REQUIRES_NUMERIC_TYPE, node.span, got_type=str(effective_lhs_type), context=f"Operator {op.name} requires numeric type")
            elif op in bitwise_ops:
                if not self._is_integral_compatible(effective_lhs_type):
                    self.add_type_error(TypeErrorType.REQUIRES_INTEGER_TYPE, node.span, got_type=str(effective_lhs_type), context=f"Operator {op.name} requires integer type")

        # Check assignment compatibility
        if not self._is_initializer_assignable_to(
            node.value,
            rhs_type,
            effective_lhs_type,
            node.span,
            context="Assignment",
        ):
            self.add_type_error(
                TypeErrorType.ASSIGNMENT_TYPE_MISMATCH,
                node.span,
                expected_type=str(effective_lhs_type),
                got_type=str(rhs_type)
            )

    def visit_if_stmt(self, node: ASTNode) -> None:
        """Visit an if statement."""
        # Condition must be boolean
        if node.condition:
            cond_type = self.visit_expression(node.condition)
            if not cond_type.equals(BOOL):
                self.add_type_error(TypeErrorType.CONDITION_NOT_BOOL, node.condition.span, expected_type="bool", got_type=str(cond_type))

        # Visit branches
        if node.then_stmt:
            with self._temporary_nonnegative_facts(self._facts_from_positive_condition(node.condition)):
                self.visit_statement(node.then_stmt)
        if node.else_stmt:
            self.visit_statement(node.else_stmt)

    def visit_while_stmt(self, node: ASTNode) -> None:
        """Visit a while statement."""
        # Condition must be boolean
        if node.condition:
            cond_type = self.visit_expression(node.condition)
            if not cond_type.equals(BOOL):
                self.add_type_error(TypeErrorType.CONDITION_NOT_BOOL, node.condition.span, expected_type="bool", got_type=str(cond_type))

        # Enter loop context
        self.context.enter_loop()

        # Visit body
        if node.body:
            self.visit_statement(node.body)

        # Exit loop context
        self.context.exit_loop()

    def visit_for_stmt(self, node: ASTNode) -> None:
        """Visit a for loop."""
        # Enter the for scope created during name resolution
        self._enter_matching_scope("for")

        # Enter loop context
        self.context.enter_loop()
        try:
            # Type check init, condition, update
            if node.init:
                self.visit_statement(node.init)

            if node.condition:
                cond_type = self.visit_expression(node.condition)
                if not cond_type.equals(BOOL):
                    self.add_type_error(TypeErrorType.CONDITION_NOT_BOOL, node.condition.span, expected_type="bool", got_type=str(cond_type))

            if node.update:
                self.visit_statement(node.update)

            # Visit body
            if node.body:
                self.visit_statement(node.body)
        finally:
            # Exit loop context and for scope
            self.context.exit_loop()
            self.symbols.exit_scope()

    def visit_for_in_stmt(self, node: ASTNode) -> None:
        """Visit a for-in loop."""
        # Enter the for-in scope (must match name resolution)
        scope_name = "for_in_indexed" if node.kind == NodeKind.FOR_IN_INDEXED else "for_in"
        self._enter_matching_scope(scope_name)

        # Type check iterable (outside loop scope)
        iterable_type = UNKNOWN
        if node.iterable:
            iterable_type = self.visit_expression(node.iterable)

        # Determine element type
        element_type = UNKNOWN
        if isinstance(iterable_type, ArrayType):
            element_type = iterable_type.element_type
        elif isinstance(iterable_type, SliceType):
            element_type = iterable_type.element_type
        elif iterable_type.equals(STRING):
            element_type = CHAR
        elif not iterable_type.equals(UNKNOWN):
            self.add_type_error(
                TypeErrorType.REQUIRES_ARRAY_OR_SLICE,
                node.iterable.span if node.iterable else node.span,
                got_type=str(iterable_type),
                context="for-in requires an array, slice, or string iterable",
            )

        # Update iterator variable type
        if node.iterator:
            iter_symbol = self.symbols.lookup(node.iterator)
            if iter_symbol:
                iter_symbol.type = element_type

        # For indexed for-in, update index variable type
        if node.kind == NodeKind.FOR_IN_INDEXED and node.index_var:
            index_symbol = self.symbols.lookup(node.index_var)
            if index_symbol:
                index_symbol.type = USIZE

        # Enter loop context
        self.context.enter_loop()

        # Visit body
        if node.body:
            self.visit_statement(node.body)

        # Exit loop context and scope
        self.context.exit_loop()
        self.symbols.exit_scope()

    def visit_match_stmt(self, node: ASTNode) -> None:
        """Visit a match statement."""
        scrutinee_type = self.visit_expression(node.expression) if node.expression else UNKNOWN
        has_catch_all = bool(node.else_case)
        bool_coverage: Set[bool] = set()
        enum_coverage: Set[str] = set()
        seen_patterns: Dict[Tuple[str, Any], ASTNode] = {}
        seen_ranges: List[Tuple[str, float, float, ASTNode]] = []
        wildcard_pattern: Optional[ASTNode] = None

        # Visit all case branches
        for case in (node.cases or []):
            self._validate_match_case_capture_shape(case.patterns or [])
            for pattern in (case.patterns or []):
                pattern_kind, pattern_value = self._validate_match_pattern(pattern, scrutinee_type)
                wildcard_pattern = self._check_match_pattern_redundancy(
                    pattern,
                    pattern_kind,
                    pattern_value,
                    seen_patterns,
                    seen_ranges,
                    wildcard_pattern,
                    self._match_full_coverage_reason(scrutinee_type, bool_coverage, enum_coverage),
                )
                if pattern_kind == "wildcard":
                    has_catch_all = True
                elif pattern_kind == "bool":
                    bool_coverage.add(bool(pattern_value))
                elif pattern_kind == "enum" and isinstance(pattern_value, str):
                    enum_coverage.add(pattern_value)

            self._enter_matching_scope("match_case")
            self._define_match_capture_symbols(case.patterns or [], scrutinee_type)
            try:
                case_stmt = getattr(case, "statement", None)
                if case_stmt:
                    self.visit_statement(case_stmt)
                elif case.statements:
                    for stmt in case.statements:
                        self.visit_statement(stmt)
            finally:
                self.symbols.exit_scope()

        # Visit else case
        if node.else_case:
            if wildcard_pattern is not None:
                self.add_semantic_error(
                    SemanticErrorType.UNREACHABLE_CODE,
                    self._match_else_span(node.else_case) or node.span,
                    context="match else branch is unreachable because a previous wildcard pattern covers all values",
                )
            elif full_coverage_reason := self._match_full_coverage_reason(scrutinee_type, bool_coverage, enum_coverage):
                self.add_semantic_error(
                    SemanticErrorType.UNREACHABLE_CODE,
                    self._match_else_span(node.else_case) or node.span,
                    context=f"match else branch is unreachable because previous cases cover all {full_coverage_reason} values",
                )

            self._enter_matching_scope("match_else")
            try:
                for stmt in node.else_case:
                    self.visit_statement(stmt)
            finally:
                self.symbols.exit_scope()

        self._check_match_exhaustiveness(
            span=node.span,
            scrutinee_type=scrutinee_type,
            has_catch_all=has_catch_all,
            bool_coverage=bool_coverage,
            enum_coverage=enum_coverage,
        )

    def visit_return_stmt(self, node: ASTNode) -> None:
        """Visit a return statement."""
        # Type check return value (RETURN nodes use 'value' attribute, not 'expression')
        return_type = None
        if node.value:
            return_type = self.visit_expression(node.value)
            expected = self.context.get_function_return_type()
            if (
                self._is_nil_literal(node.value)
                and expected is not None
                and not isinstance(expected, ReferenceType)
            ):
                self.add_type_error(
                    TypeErrorType.NIL_ONLY_FOR_REFERENCES,
                    node.value.span,
                    got_type=str(expected),
                    context="Return value",
                )

        # Validate against function return type
        if not self.context.validate_return(return_type):
            expected = self.context.get_function_return_type()
            if expected:
                self.add_type_error(
                    TypeErrorType.RETURN_TYPE_MISMATCH,
                    node.span,
                    expected_type=str(expected),
                    got_type=str(return_type)
                )
            else:
                self.add_type_error(TypeErrorType.RETURN_TYPE_MISMATCH, node.span, expected_type="void", context="Cannot return value from void function")

        # Mark function as having return
        self.context.mark_function_returns()

    def visit_expression(self, node: ASTNode) -> Type:
        """
        Visit an expression and return its type.

        Args:
            node: Expression node

        Returns:
            Type of the expression
        """
        expr_type = self._visit_expression_impl(node)
        self.set_type(node, expr_type)
        return expr_type

    def _visit_expression_impl(self, node: ASTNode) -> Type:
        """Internal implementation of expression type checking."""
        if node.kind == NodeKind.LITERAL:
            return self.visit_literal(node)
        elif node.kind == NodeKind.IDENTIFIER:
            return self.visit_identifier(node)
        elif node.kind == NodeKind.BINARY:
            return self.visit_binary_expr(node)
        elif node.kind == NodeKind.UNARY:
            return self.visit_unary_expr(node)
        elif node.kind == NodeKind.CALL:
            return self.visit_call_expr(node)
        elif node.kind == NodeKind.INDEX:
            return self.visit_index_expr(node)
        elif node.kind == NodeKind.SLICE:
            return self.visit_slice_expr(node)
        elif node.kind == NodeKind.FIELD_ACCESS:
            return self.visit_field_access(node)
        elif node.kind == NodeKind.ADDRESS_OF:
            return self.visit_address_of(node)
        elif node.kind == NodeKind.DEREF:
            return self.visit_deref(node)
        elif node.kind == NodeKind.CAST:
            return self.visit_cast(node)
        elif node.kind == NodeKind.IF_EXPR:
            return self.visit_if_expr(node)
        elif node.kind == NodeKind.MATCH_EXPR:
            return self.visit_match_expr(node)
        elif node.kind == NodeKind.STRUCT_INIT:
            return self.visit_struct_init(node)
        elif node.kind == NodeKind.ARRAY_INIT:
            return self.visit_array_init(node)
        elif node.kind == NodeKind.NEW_EXPR:
            return self.visit_new_expr(node)
        elif node.kind == NodeKind.TYPE_SET:
            return self.resolve_type_node(node)
        else:
            error = SemanticError.from_type(SemanticErrorType.UNEXPECTED_NODE_KIND, span=node.span, filename=self.current_file, source_lines=self.source_lines, context=f"Unknown expression kind: {node.kind}")
            self.errors.append(error)
            return UNKNOWN

    def visit_literal(self, node: ASTNode) -> Type:
        """Visit a literal expression."""
        if node.literal_kind == LiteralKind.INTEGER:
            return I32  # Default integer type
        elif node.literal_kind == LiteralKind.FLOAT:
            return F64  # Default float type
        elif node.literal_kind == LiteralKind.CHAR:
            return CHAR
        elif node.literal_kind == LiteralKind.STRING:
            return STRING
        elif node.literal_kind == LiteralKind.BOOLEAN:
            return BOOL
        elif node.literal_kind == LiteralKind.NIL:
            return UNKNOWN  # nil type depends on context
        return UNKNOWN

    def visit_identifier(self, node: ASTNode) -> Type:
        """Visit an identifier expression."""
        ident_name = node.name or ""
        symbol = self.symbols.lookup(ident_name)

        if symbol:
            # Mark as used
            self.symbols.mark_used(ident_name)
            return symbol.type
        else:
            self.add_type_error(TypeErrorType.UNDEFINED_TYPE, node.span, context=f"Identifier '{ident_name}'")
            return UNKNOWN

    def visit_binary_expr(self, node: ASTNode) -> Type:
        """Visit a binary expression."""
        left_type = self.visit_expression(node.left) if node.left else UNKNOWN
        right_type = self.visit_expression(node.right) if node.right else UNKNOWN

        op = node.operator

        # Arithmetic operators: +, -, *, /, %
        if op in {BinaryOp.ADD, BinaryOp.SUB, BinaryOp.MUL, BinaryOp.DIV, BinaryOp.MOD}:
            if op == BinaryOp.ADD and isinstance(left_type, ArrayType) and isinstance(right_type, ArrayType):
                if (
                    left_type.size == right_type.size
                    and left_type.element_type.equals(right_type.element_type)
                    and self._is_numeric_compatible(left_type.element_type)
                ):
                    return left_type
                self.add_type_error(
                    TypeErrorType.OPERATOR_TYPE_MISMATCH,
                    node.span,
                    context=f"add between {left_type} and {right_type}",
                )
                return UNKNOWN
            if not self._is_numeric_compatible(left_type) or not self._is_numeric_compatible(right_type):
                self.add_type_error(TypeErrorType.REQUIRES_NUMERIC_TYPE, node.span)
                return UNKNOWN
            # Preserve generic parameters for body type-checking before monomorphization.
            if isinstance(left_type, GenericParamType):
                return left_type
            if isinstance(right_type, GenericParamType):
                return right_type
            # Result type is the wider of the two for concrete numeric types.
            if left_type.is_floating():
                return left_type
            if right_type.is_floating():
                return right_type
            return left_type

        # Comparison operators: ==, !=, <, <=, >, >=
        elif op in {BinaryOp.EQ, BinaryOp.NE, BinaryOp.LT, BinaryOp.LE, BinaryOp.GT, BinaryOp.GE}:
            if not self._types_are_comparable(left_type, right_type, ordering=op not in {BinaryOp.EQ, BinaryOp.NE}):
                self.add_type_error(
                    TypeErrorType.OPERATOR_TYPE_MISMATCH,
                    node.span,
                    context=f"{op.name.lower()} between {left_type} and {right_type}",
                )
                return UNKNOWN
            return BOOL

        # Logical operators: and, or
        elif op in {BinaryOp.AND, BinaryOp.OR}:
            if not left_type.equals(BOOL) or not right_type.equals(BOOL):
                self.add_type_error(TypeErrorType.REQUIRES_BOOL_TYPE, node.span)
            return BOOL

        # Bitwise operators: &, |, ^, <<, >>
        elif op in {BinaryOp.BIT_AND, BinaryOp.BIT_OR, BinaryOp.BIT_XOR, BinaryOp.BIT_SHL, BinaryOp.BIT_SHR}:
            if not self._is_integral_compatible(left_type) or not self._is_integral_compatible(right_type):
                self.add_type_error(TypeErrorType.REQUIRES_INTEGER_TYPE, node.span)
                return UNKNOWN
            return left_type

        return UNKNOWN

    def visit_unary_expr(self, node: ASTNode) -> Type:
        """Visit a unary expression."""
        operand_type = self.visit_expression(node.operand) if node.operand else UNKNOWN

        op = node.operator

        if op == UnaryOp.NEG:
            if not self._is_numeric_compatible(operand_type):
                self.add_type_error(TypeErrorType.REQUIRES_NUMERIC_TYPE, node.span)
            return operand_type

        elif op == UnaryOp.NOT:
            if not operand_type.equals(BOOL):
                self.add_type_error(TypeErrorType.REQUIRES_BOOL_TYPE, node.span)
            return BOOL

        elif op == UnaryOp.BIT_NOT:
            if not self._is_integral_compatible(operand_type):
                self.add_type_error(TypeErrorType.REQUIRES_INTEGER_TYPE, node.span)
            return operand_type

        return UNKNOWN

    def visit_call_expr(self, node: ASTNode) -> Type:
        """Visit a function call expression."""
        # Reject `@`-prefixed intrinsics (other than @type_set, which the
        # parser routes to a TYPE_SET node, not a CALL). These names parse
        # but are not implemented yet; surface a clear "unsupported"
        # diagnostic instead of the generic "undefined identifier".
        callee = node.function
        if (
            callee is not None
            and callee.kind == NodeKind.IDENTIFIER
            and isinstance(callee.name, str)
            and callee.name.startswith("@")
        ):
            self.errors.append(
                SemanticError.from_type(
                    SemanticErrorType.UNSUPPORTED_FEATURE,
                    span=callee.span or node.span,
                    filename=self.current_file,
                    source_lines=self.source_lines,
                    custom_message=(
                        f"Intrinsic '{callee.name}' is parsed for future support "
                        "but is not implemented in the Zig backend yet"
                    ),
                )
            )
            return UNKNOWN

        # Get function type
        func_type = self.visit_expression(node.function) if node.function else UNKNOWN
        if node.function:
            self.set_type(node.function, func_type)

        if not isinstance(func_type, FunctionType):
            # Check if this is a module method call (e.g., io.println) — allow it
            if isinstance(func_type, UnknownType) and node.function:
                if node.function.kind == NodeKind.FIELD_ACCESS and node.function.object:
                    obj_symbol = self.symbols.lookup(
                        getattr(node.function.object, 'name', '') or ''
                    )
                    if obj_symbol and obj_symbol.kind == SymbolKind.MODULE:
                        if getattr(node, "file_module_call", None):
                            for arg in node.arguments or []:
                                self.visit_expression(arg)
                            return UNKNOWN
                        return self._visit_stdlib_module_call(node, obj_symbol)

            # Use the span of the function being called, not the whole call expression
            error_span = node.function.span if node.function else node.span

            # Provide better context for unknown types
            if isinstance(func_type, UnknownType):
                # Try to get a meaningful name for what's being called
                if hasattr(node.function, 'kind'):
                    if node.function.kind == NodeKind.FIELD_ACCESS:
                        obj_name = node.function.object.name if hasattr(node.function.object, 'name') else "expression"
                        method_name = node.function.field or "method"
                        context = f"Cannot call '{obj_name}.{method_name}' (undefined identifier)"
                    elif node.function.kind == NodeKind.IDENTIFIER:
                        func_name = node.function.name or "expression"
                        context = f"Cannot call undefined identifier '{func_name}'"
                    else:
                        context = "Cannot call undefined expression"
                    self.add_type_error(TypeErrorType.NOT_CALLABLE, error_span, context=context)
                else:
                    self.add_type_error(TypeErrorType.NOT_CALLABLE, error_span, got_type=str(func_type))
            else:
                self.add_type_error(TypeErrorType.NOT_CALLABLE, error_span, got_type=str(func_type))
            return UNKNOWN

        # Type check arguments
        arg_types = []
        if node.arguments:
            for arg in node.arguments:
                arg_types.append(self.visit_expression(arg))

        # Check for generic type inference
        generic_mapping = self._infer_generic_types(func_type, arg_types)
        if generic_mapping or func_type.generic_param_order:
            # Backend lowering can use this semantic annotation to monomorphize
            # concrete generic calls without re-running type inference.
            if generic_mapping:
                node.generic_mapping = generic_mapping
            self._check_generic_constraints(func_type, generic_mapping, node.span)
            # Substitute generic types in param_types for type checking
            resolved_param_types = [self._substitute_generic(pt, generic_mapping) for pt in func_type.param_types]
        else:
            resolved_param_types = list(func_type.param_types)

        # Check argument count
        expected_count = len(func_type.param_types)
        actual_count = len(arg_types)

        if not func_type.is_variadic and actual_count != expected_count:
            self.add_type_error(
                TypeErrorType.WRONG_ARGUMENT_COUNT,
                node.span,
                context=f"Expected {expected_count} arguments, got {actual_count}"
            )

        # Check argument types (skip check if param type is unknown, e.g., untyped variadic)
        implicit_ref_args: Set[int] = set()
        for i, (arg_type, param_type) in enumerate(zip(arg_types, resolved_param_types)):
            if isinstance(param_type, UnknownType):
                continue  # Skip type checking for untyped variadic parameters
            if isinstance(param_type, GenericParamType):
                continue  # Skip generic params that weren't resolved
            if self._is_nil_literal(node.arguments[i]) and not isinstance(param_type, ReferenceType):
                self.add_type_error(
                    TypeErrorType.NIL_ONLY_FOR_REFERENCES,
                    node.arguments[i].span,
                    got_type=str(param_type),
                    context=f"Argument {i+1}",
                )
                continue
            if isinstance(param_type, ReferenceType) and not isinstance(arg_type, ReferenceType):
                if arg_type.is_assignable_to(param_type.referent_type) and self._is_lvalue_expression(node.arguments[i]):
                    implicit_ref_args.add(i)
                    continue
            if not arg_type.is_assignable_to(param_type):
                self.add_type_error(
                    TypeErrorType.ARGUMENT_TYPE_MISMATCH,
                    node.span,
                    expected_type=str(param_type),
                    got_type=str(arg_type),
                    context=f"Argument {i+1}"
                )
        if implicit_ref_args:
            setattr(node, "implicit_ref_args", implicit_ref_args)

        # Resolve return type with generic substitution
        return_type = func_type.return_type if func_type.return_type else VOID
        if generic_mapping:
            return_type = self._substitute_generic(return_type, generic_mapping)

        return return_type

    def _visit_stdlib_module_call(self, node: ASTNode, module_symbol: Symbol) -> Type:
        """Validate stdlib module calls that lower through backend-specific emitters."""
        arg_types = [self.visit_expression(arg) for arg in (node.arguments or [])]
        function = node.function
        module_path = getattr(module_symbol.node, "module_path", None) or module_symbol.name
        method_name = function.field if function and function.kind == NodeKind.FIELD_ACCESS else None
        canonical = self.stdlib.resolve_call(module_path, method_name or "")
        if canonical is None:
            self.add_type_error(
                TypeErrorType.NOT_CALLABLE,
                function.span if function else node.span,
                context=f"Unknown stdlib call '{module_path}.{method_name or '<unknown>'}'",
            )
            return UNKNOWN

        node.stdlib_canonical = canonical
        if canonical.startswith("std.io."):
            self._validate_io_call(node, arg_types)
            return VOID
        if canonical.startswith("std.math."):
            return self._validate_math_call(node, canonical, arg_types)
        return UNKNOWN

    def _validate_io_call(self, node: ASTNode, arg_types: List[Type]) -> None:
        args = node.arguments or []
        if not args:
            return
        format_type = arg_types[0] if arg_types else UNKNOWN
        if not format_type.equals(STRING):
            self.add_type_error(
                TypeErrorType.ARGUMENT_TYPE_MISMATCH,
                args[0].span,
                expected_type="string",
                got_type=str(format_type),
                context="io format argument",
            )
            return
        if args[0].kind != NodeKind.LITERAL or args[0].literal_kind != LiteralKind.STRING:
            self.add_semantic_error(
                SemanticErrorType.UNSUPPORTED_FEATURE,
                args[0].span,
                context="io format strings must be string literals",
            )
            return
        placeholder_count = self._count_format_placeholders(str(args[0].literal_value or ""))
        actual_count = max(0, len(args) - 1)
        if placeholder_count != actual_count:
            self.add_type_error(
                TypeErrorType.WRONG_ARGUMENT_COUNT,
                node.span,
                context=f"io format string expects {placeholder_count} values, got {actual_count}",
            )

    def _validate_math_call(self, node: ASTNode, canonical: str, arg_types: List[Type]) -> Type:
        name = canonical.rsplit(".", 1)[-1]
        expected_count = 2 if name in {"min", "max"} else 1
        if len(arg_types) != expected_count:
            self.add_type_error(
                TypeErrorType.WRONG_ARGUMENT_COUNT,
                node.span,
                context=f"math.{name} expects {expected_count} arguments, got {len(arg_types)}",
            )
            return UNKNOWN

        for index, arg_type in enumerate(arg_types, start=1):
            if not self._is_numeric_compatible(arg_type):
                self.add_type_error(
                    TypeErrorType.REQUIRES_NUMERIC_TYPE,
                    (node.arguments or [node])[index - 1].span,
                    got_type=str(arg_type),
                    context=f"math.{name} argument {index}",
                )
                return UNKNOWN
            if name in {"sqrt", "floor", "ceil", "sin", "cos", "tan", "log", "exp"} and not arg_type.is_floating():
                self.add_type_error(
                    TypeErrorType.ARGUMENT_TYPE_MISMATCH,
                    (node.arguments or [node])[index - 1].span,
                    expected_type="f32 or f64",
                    got_type=str(arg_type),
                    context=f"math.{name} argument {index}",
                )
                return UNKNOWN

        if name in {"min", "max"} and len(arg_types) == 2:
            if arg_types[0].is_assignable_to(arg_types[1]):
                return arg_types[1]
            if arg_types[1].is_assignable_to(arg_types[0]):
                return arg_types[0]
            self.add_type_error(
                TypeErrorType.ARGUMENT_TYPE_MISMATCH,
                node.span,
                expected_type=str(arg_types[0]),
                got_type=str(arg_types[1]),
                context=f"math.{name} arguments",
            )
            return UNKNOWN
        return arg_types[0] if arg_types else UNKNOWN

    def _count_format_placeholders(self, fmt: str) -> int:
        count = 0
        index = 0
        while index < len(fmt):
            ch = fmt[index]
            if ch == "{" and index + 1 < len(fmt):
                if fmt[index + 1] == "{":
                    index += 2
                    continue
                end = fmt.find("}", index + 1)
                if end != -1:
                    count += 1
                    index = end + 1
                    continue
            if ch == "}" and index + 1 < len(fmt) and fmt[index + 1] == "}":
                index += 2
                continue
            index += 1
        return count

    def _check_generic_constraints(
        self,
        func_type: FunctionType,
        generic_mapping: Dict[str, Type],
        span: Optional[SourceSpan],
    ) -> None:
        """Validate inferred generic arguments against declared constraints."""
        seen: Set[str] = set()
        stack: List[Type] = list(func_type.param_types)
        if func_type.return_type:
            stack.append(func_type.return_type)

        while stack:
            current = stack.pop()
            if isinstance(current, GenericParamType):
                if current.name in seen:
                    continue
                seen.add(current.name)
                concrete = generic_mapping.get(current.name)
                if concrete is None:
                    self.add_semantic_error(
                        SemanticErrorType.GENERIC_PARAM_MISMATCH,
                        span,
                        context=f"Could not infer generic parameter '${current.name}'",
                    )
                elif current.constraint and not current.constraint.contains(concrete):
                    self.add_semantic_error(
                        SemanticErrorType.CONSTRAINT_VIOLATION,
                        span,
                        context=(
                            f"Generic parameter '${current.name}' requires {current.constraint}, "
                            f"got {concrete}"
                        ),
                    )
            elif isinstance(current, ReferenceType):
                stack.append(current.referent_type)
            elif isinstance(current, PointerType):
                stack.append(current.pointee_type)
            elif isinstance(current, ArrayType):
                stack.append(current.element_type)
            elif isinstance(current, SliceType):
                stack.append(current.element_type)
            elif isinstance(current, FunctionType):
                stack.extend(current.param_types)
                if current.return_type:
                    stack.append(current.return_type)
            elif isinstance(current, GenericInstanceType):
                stack.extend(current.type_args)

    def _infer_generic_types(self, func_type: FunctionType, arg_types: List[Type]) -> Dict[str, Type]:
        """
        Infer generic type parameters from actual argument types.

        Returns a mapping from generic parameter names to concrete types.
        """
        mapping: Dict[str, Type] = {}

        def bind(name: str, concrete: Type) -> None:
            existing = mapping.get(name)
            if existing is None or existing.equals(concrete):
                mapping[name] = concrete

        stack: List[Tuple[Type, Type]] = list(zip(func_type.param_types, arg_types))
        while stack:
            param_type, arg_type = stack.pop()
            if isinstance(param_type, GenericParamType):
                bind(param_type.name, arg_type)
            elif isinstance(param_type, ReferenceType):
                if isinstance(arg_type, ReferenceType):
                    stack.append((param_type.referent_type, arg_type.referent_type))
                else:
                    stack.append((param_type.referent_type, arg_type))
            elif isinstance(param_type, PointerType) and isinstance(arg_type, PointerType):
                stack.append((param_type.pointee_type, arg_type.pointee_type))
            elif isinstance(param_type, ArrayType) and isinstance(arg_type, ArrayType):
                if param_type.size == arg_type.size:
                    stack.append((param_type.element_type, arg_type.element_type))
            elif isinstance(param_type, ArrayType) and isinstance(arg_type, SliceType):
                stack.append((param_type.element_type, arg_type.element_type))
            elif isinstance(param_type, SliceType) and isinstance(arg_type, (SliceType, ArrayType)):
                stack.append((param_type.element_type, arg_type.element_type))
            elif isinstance(param_type, FunctionType) and isinstance(arg_type, FunctionType):
                stack.extend(zip(param_type.param_types, arg_type.param_types))
                if param_type.return_type and arg_type.return_type:
                    stack.append((param_type.return_type, arg_type.return_type))
            elif isinstance(param_type, GenericInstanceType) and isinstance(arg_type, GenericInstanceType):
                if param_type.base_name == arg_type.base_name:
                    stack.extend(zip(param_type.type_args, arg_type.type_args))

        return mapping

    def _substitute_generic(self, type_: Type, mapping: Dict[str, Type]) -> Type:
        """Substitute generic type parameters with concrete types (iterative for wrappers)."""
        # Iteratively unwrap single-child wrapper types, then rebuild
        wrappers: list = []  # list of ('kind', extra_data) to reconstruct
        current = type_

        while True:
            if isinstance(current, GenericParamType):
                current = mapping.get(current.name, current)
                break
            elif isinstance(current, ReferenceType):
                wrappers.append(('ref', None))
                current = current.referent_type
            elif isinstance(current, ArrayType):
                wrappers.append(('array', current.size))
                current = current.element_type
            elif isinstance(current, SliceType):
                wrappers.append(('slice', None))
                current = current.element_type
            elif isinstance(current, PointerType):
                wrappers.append(('pointer', None))
                current = current.pointee_type
            elif isinstance(current, FunctionType):
                # FunctionType has multiple children — substitute each param
                new_params = tuple(self._substitute_generic(pt, mapping) for pt in current.param_types)
                new_return = self._substitute_generic(current.return_type, mapping) if current.return_type else None
                current = FunctionType(
                    param_types=new_params,
                    return_type=new_return,
                    is_variadic=current.is_variadic,
                    variadic_type=current.variadic_type,
                    generic_param_order=current.generic_param_order,
                )
                break
            elif isinstance(current, GenericInstanceType):
                new_args = tuple(self._substitute_generic(arg, mapping) for arg in current.type_args)
                current = GenericInstanceType(base_name=current.base_name, type_args=new_args)
                break
            else:
                break  # Leaf type, no substitution needed

        # Reconstruct wrappers in reverse order
        for kind, data in reversed(wrappers):
            if kind == 'ref':
                current = ReferenceType(referent_type=current)
            elif kind == 'array':
                current = ArrayType(element_type=current, size=data)
            elif kind == 'slice':
                current = SliceType(element_type=current)
            elif kind == 'pointer':
                current = PointerType(pointee_type=current)

        return current

    def visit_index_expr(self, node: ASTNode) -> Type:
        """Visit an index expression."""
        obj_type = self.visit_expression(node.object) if node.object else UNKNOWN
        index_type = self.visit_expression(node.index) if node.index else UNKNOWN

        if node.index:
            self._validate_index_bound(node.index, index_type)

        if isinstance(obj_type, ArrayType):
            return obj_type.element_type
        elif isinstance(obj_type, SliceType):
            return obj_type.element_type
        elif obj_type.equals(STRING):
            return CHAR
        else:
            self.add_type_error(TypeErrorType.CANNOT_INDEX_TYPE, node.span, got_type=str(obj_type))
            return UNKNOWN

    def visit_slice_expr(self, node: ASTNode) -> Type:
        """Visit a slice expression."""
        obj_type = self.visit_expression(node.object) if node.object else UNKNOWN

        if node.start:
            start_type = self.visit_expression(node.start)
            self._validate_index_bound(node.start, start_type)

        if node.end:
            end_type = self.visit_expression(node.end)
            self._validate_index_bound(node.end, end_type)

        if isinstance(obj_type, ArrayType):
            return SliceType(obj_type.element_type)
        if isinstance(obj_type, SliceType):
            return SliceType(obj_type.element_type)
        if obj_type.equals(STRING):
            return SliceType(CHAR)

        self.add_type_error(TypeErrorType.REQUIRES_ARRAY_OR_SLICE, node.span, got_type=str(obj_type))
        return UNKNOWN

    def _validate_index_bound(self, node: ASTNode, index_type: Type) -> None:
        """Require indexes and slice bounds to be usize or non-negative literals."""
        if isinstance(index_type, PrimitiveType) and index_type.name == "usize":
            return
        if self._is_non_negative_integer_literal(node):
            return
        self.add_type_error(
            TypeErrorType.INDEX_NOT_INTEGER,
            node.span,
            got_type=f"{index_type}; expected usize",
        )

    def _is_non_negative_integer_literal(self, node: ASTNode) -> bool:
        return (
            node.kind == NodeKind.LITERAL
            and node.literal_kind == LiteralKind.INTEGER
            and isinstance(node.literal_value, int)
            and node.literal_value >= 0
        )

    def visit_field_access(self, node: ASTNode) -> Type:
        """Visit a field access expression."""
        obj_type = self.visit_expression(node.object) if node.object else UNKNOWN
        field_name = node.field or ""

        # Check if the object is a module symbol — allow field access without error
        if node.object and hasattr(node.object, 'name'):
            obj_symbol = self.symbols.lookup(node.object.name or "")
            if obj_symbol and obj_symbol.kind == SymbolKind.MODULE:
                module_path = getattr(getattr(obj_symbol, "node", None), "module_path", None)
                canonical_module = self.stdlib.canonical_module_name(module_path or "")
                if canonical_module and self.stdlib.resolve_call(module_path or "", field_name) is None:
                    self.add_type_error(
                        TypeErrorType.NO_SUCH_FIELD,
                        node.span,
                        context=f"Stdlib module '{module_path}' has no function '{field_name}'",
                    )
                # Module field access returns UNKNOWN; calls are lowered by the stdlib preprocessor.
                return UNKNOWN

        if isinstance(obj_type, GenericInstanceType):
            concrete_struct = self._resolve_generic_instance_struct(obj_type)
            if concrete_struct is not None:
                obj_type = concrete_struct

        if isinstance(obj_type, ReferenceType):
            referent = obj_type.referent_type
            if isinstance(referent, GenericInstanceType):
                concrete_struct = self._resolve_generic_instance_struct(referent)
                if concrete_struct is not None:
                    referent = concrete_struct

            if isinstance(referent, StructType):
                field = referent.get_field(field_name)
                if field:
                    setattr(node, "implicit_deref_object", True)
                    return field.field_type
                self.add_type_error(TypeErrorType.NO_SUCH_FIELD, node.span, context=f"Struct '{referent}' has no field '{field_name}'")
                return UNKNOWN
            if isinstance(referent, UnionType):
                field = referent.get_field(field_name)
                if field:
                    setattr(node, "implicit_deref_object", True)
                    return field.field_type
                self.add_type_error(TypeErrorType.NO_SUCH_FIELD, node.span, context=f"Union '{referent}' has no field '{field_name}'")
                return UNKNOWN

            if field_name in {"adr", "val"}:
                self.add_type_error(
                    TypeErrorType.FIELD_ACCESS_ON_NON_STRUCT,
                    node.span,
                    got_type=str(obj_type),
                    context=f"'.{field_name}' is not reference syntax; pass lvalues directly to ref parameters and access ref struct fields directly",
                )
                return UNKNOWN

        if isinstance(obj_type, SliceType):
            if field_name == "ptr":
                return PointerType(obj_type.element_type)
            if field_name == "len":
                return USIZE
            self.add_type_error(
                TypeErrorType.NO_SUCH_FIELD,
                node.span,
                context=f"Slice '{obj_type}' has no field '{field_name}'",
            )
            return UNKNOWN

        if isinstance(obj_type, StructType):
            field = obj_type.get_field(field_name)
            if field:
                return field.field_type
            else:
                self.add_type_error(TypeErrorType.NO_SUCH_FIELD, node.span, context=f"Struct '{obj_type}' has no field '{field_name}'")
                return UNKNOWN
        elif isinstance(obj_type, UnionType):
            field = obj_type.get_field(field_name)
            if field:
                return field.field_type
            self.add_type_error(TypeErrorType.NO_SUCH_FIELD, node.span, context=f"Union '{obj_type}' has no field '{field_name}'")
            return UNKNOWN
        elif isinstance(obj_type, EnumType):
            # Enum variant access: EnumName.VariantName
            if obj_type.has_variant(field_name):
                return obj_type  # Enum variant has the enum type
            else:
                self.add_type_error(TypeErrorType.NO_SUCH_FIELD, node.span, context=f"Enum '{obj_type}' has no variant '{field_name}'")
                return UNKNOWN
        else:
            # Use the span of the object being accessed, not the whole field access
            error_span = node.object.span if node.object else node.span

            # Provide better context for unknown types
            if isinstance(obj_type, UnknownType):
                # Get the object name if available
                obj_name = node.object.name if hasattr(node.object, 'name') and node.object.name else "expression"
                accessed_field = node.field or "field"
                context = f"Cannot access field '{accessed_field}' on undefined identifier '{obj_name}'"
                self.add_type_error(TypeErrorType.FIELD_ACCESS_ON_NON_STRUCT, error_span, context=context)
            else:
                self.add_type_error(TypeErrorType.FIELD_ACCESS_ON_NON_STRUCT, error_span, got_type=str(obj_type))
            return UNKNOWN

    def visit_address_of(self, node: ASTNode) -> Type:
        """Visit an internal address-of expression."""
        operand_type = self.visit_expression(node.operand) if node.operand else UNKNOWN
        if node.operand and node.operand.kind not in {
            NodeKind.IDENTIFIER,
            NodeKind.FIELD_ACCESS,
            NodeKind.INDEX,
            NodeKind.DEREF,
        }:
            self.add_type_error(
                TypeErrorType.ADDRESS_OF_RVALUE,
                node.span,
                got_type=str(operand_type),
            )
        return ReferenceType(referent_type=operand_type)

    def visit_deref(self, node: ASTNode) -> Type:
        """Visit an internal dereference expression."""
        ptr_type = self.visit_expression(node.pointer) if node.pointer else UNKNOWN

        if isinstance(ptr_type, PointerType):
            return ptr_type.pointee_type
        elif isinstance(ptr_type, ReferenceType):
            return ptr_type.referent_type
        else:
            self.add_type_error(TypeErrorType.REQUIRES_POINTER_TYPE, node.span, got_type=str(ptr_type))
            return UNKNOWN

    def _is_lvalue_expression(self, node: Optional[ASTNode]) -> bool:
        return node is not None and node.kind in {
            NodeKind.IDENTIFIER,
            NodeKind.FIELD_ACCESS,
            NodeKind.INDEX,
            NodeKind.DEREF,
        }

    def visit_cast(self, node: ASTNode) -> Type:
        """Visit a cast expression and record only base type information.

        Range, non-negative, finite-float, and lowering approval checks belong
        to the safety proof pass.
        """
        source_type = self.visit_expression(node.expression) if node.expression is not None else UNKNOWN
        target_type = self.resolve_type_node(node.target_type)
        setattr(node, "cast_source_type", source_type)
        setattr(node, "cast_target_type", target_type)

        return target_type

    def _temporary_nonnegative_facts(self, facts: Set[str]):
        checker = self

        class _FactScope:
            def __enter__(self) -> None:
                self.previous = set(checker._nonnegative_vars)
                checker._nonnegative_vars.update(facts)

            def __exit__(self, exc_type, exc, tb) -> None:
                checker._nonnegative_vars = self.previous

        return _FactScope()

    def _facts_from_positive_condition(self, condition: Optional[ASTNode]) -> Set[str]:
        if condition is None or condition.kind != NodeKind.BINARY:
            return set()
        name = self._identifier_name(condition.left)
        literal = self._integer_literal_value(condition.right)
        if name is None or literal is None:
            return set()
        if condition.operator in {BinaryOp.GE, BinaryOp.GT} and literal >= 0:
            return {name}
        return set()

    def _learn_fact_after_statement(self, node: ASTNode) -> None:
        if node.kind != NodeKind.IF_STMT or node.condition is None or node.then_stmt is None:
            return
        if not self._statement_always_returns(node.then_stmt):
            return
        condition = node.condition
        if condition.kind != NodeKind.BINARY:
            return
        name = self._identifier_name(condition.left)
        literal = self._integer_literal_value(condition.right)
        if name is None or literal is None:
            return
        if condition.operator == BinaryOp.LT and literal >= 0:
            self._nonnegative_vars.add(name)
        elif condition.operator == BinaryOp.LE and literal < 0:
            self._nonnegative_vars.add(name)

    def _statement_always_returns(self, node: ASTNode) -> bool:
        if node.kind == NodeKind.RETURN:
            return True
        if node.kind == NodeKind.BLOCK:
            statements = node.statements or []
            return bool(statements) and self._statement_always_returns(statements[-1])
        return False

    def _expression_is_known_nonnegative(self, node: Optional[ASTNode]) -> bool:
        if node is None:
            return False
        literal = self._integer_literal_value(node)
        if literal is not None:
            return literal >= 0
        name = self._identifier_name(node)
        return bool(name and name in self._nonnegative_vars)

    def _identifier_name(self, node: Optional[ASTNode]) -> Optional[str]:
        if node is not None and node.kind == NodeKind.IDENTIFIER:
            return node.name
        return None

    def _integer_literal_value(self, node: Optional[ASTNode]) -> Optional[int]:
        if node is None:
            return None
        if (
            node.kind == NodeKind.LITERAL
            and node.literal_kind == LiteralKind.INTEGER
            and isinstance(node.literal_value, int)
        ):
            return node.literal_value
        if (
            node.kind == NodeKind.UNARY
            and node.operator == UnaryOp.NEG
            and node.operand
            and node.operand.kind == NodeKind.LITERAL
            and node.operand.literal_kind == LiteralKind.INTEGER
            and isinstance(node.operand.literal_value, int)
        ):
            return -node.operand.literal_value
        return None

    def visit_if_expr(self, node: ASTNode) -> Type:
        """Visit an if expression."""
        # Condition must be bool
        if node.condition:
            cond_type = self.visit_expression(node.condition)
            if not cond_type.equals(BOOL):
                self.add_type_error(TypeErrorType.CONDITION_NOT_BOOL, node.condition.span, expected_type="bool")

        # Both branches must have compatible types
        then_type = self.visit_expression(node.then_expr) if node.then_expr else VOID
        else_type = self.visit_expression(node.else_expr) if node.else_expr else VOID

        if not then_type.equals(else_type):
            self.add_type_error(
                TypeErrorType.IF_EXPR_TYPE_MISMATCH,
                node.span,
                expected_type=str(then_type),
                got_type=str(else_type)
            )

        return then_type

    def visit_match_expr(self, node: ASTNode) -> Type:
        """Visit a match expression and infer a unified result type."""
        scrutinee_type = self.visit_expression(node.expression) if node.expression else UNKNOWN
        has_catch_all = isinstance(node.else_case, ASTNode)
        bool_coverage: Set[bool] = set()
        enum_coverage: Set[str] = set()
        seen_patterns: Dict[Tuple[str, Any], ASTNode] = {}
        seen_ranges: List[Tuple[str, float, float, ASTNode]] = []
        wildcard_pattern: Optional[ASTNode] = None

        branch_types: List[Type] = []
        for case in (node.cases or []):
            self._validate_match_case_capture_shape(case.patterns or [])
            for pattern in (case.patterns or []):
                pattern_kind, pattern_value = self._validate_match_pattern(pattern, scrutinee_type)
                wildcard_pattern = self._check_match_pattern_redundancy(
                    pattern,
                    pattern_kind,
                    pattern_value,
                    seen_patterns,
                    seen_ranges,
                    wildcard_pattern,
                    self._match_full_coverage_reason(scrutinee_type, bool_coverage, enum_coverage),
                )
                if pattern_kind == "wildcard":
                    has_catch_all = True
                elif pattern_kind == "bool":
                    bool_coverage.add(bool(pattern_value))
                elif pattern_kind == "enum" and isinstance(pattern_value, str):
                    enum_coverage.add(pattern_value)

            case_expr = getattr(case, "expression", None)
            if case_expr:
                self._enter_matching_scope("match_case")
                self._define_match_capture_symbols(case.patterns or [], scrutinee_type)
                try:
                    branch_types.append(self.visit_expression(case_expr))
                finally:
                    self.symbols.exit_scope()

        if isinstance(node.else_case, ASTNode):
            if wildcard_pattern is not None:
                self.add_semantic_error(
                    SemanticErrorType.UNREACHABLE_CODE,
                    node.else_case.span,
                    context="match else branch is unreachable because a previous wildcard pattern covers all values",
                )
            elif full_coverage_reason := self._match_full_coverage_reason(scrutinee_type, bool_coverage, enum_coverage):
                self.add_semantic_error(
                    SemanticErrorType.UNREACHABLE_CODE,
                    node.else_case.span,
                    context=f"match else branch is unreachable because previous cases cover all {full_coverage_reason} values",
                )
            branch_types.append(self.visit_expression(node.else_case))

        self._check_match_exhaustiveness(
            span=node.span,
            scrutinee_type=scrutinee_type,
            has_catch_all=has_catch_all,
            bool_coverage=bool_coverage,
            enum_coverage=enum_coverage,
        )

        if not branch_types:
            return UNKNOWN

        result_type = branch_types[0]
        for branch_type in branch_types[1:]:
            if branch_type.equals(result_type):
                continue
            if branch_type.is_assignable_to(result_type):
                continue
            if result_type.is_assignable_to(branch_type):
                result_type = branch_type
                continue
            self.add_type_error(
                TypeErrorType.IF_EXPR_TYPE_MISMATCH,
                node.span,
                expected_type=str(result_type),
                got_type=str(branch_type),
                context="match expression branches",
            )
            return UNKNOWN

        return result_type

    def _check_match_pattern_redundancy(
        self,
        pattern: ASTNode,
        pattern_kind: Optional[str],
        pattern_value: Optional[object],
        seen_patterns: Dict[Tuple[str, Any], ASTNode],
        seen_ranges: List[Tuple[str, float, float, ASTNode]],
        wildcard_pattern: Optional[ASTNode],
        full_coverage_reason: Optional[str],
    ) -> Optional[ASTNode]:
        """Emit diagnostics for exact duplicate or unreachable match patterns."""
        if wildcard_pattern is not None:
            self.add_semantic_error(
                SemanticErrorType.UNREACHABLE_CODE,
                pattern.span,
                context=(
                    f"match pattern '{self._format_match_pattern(pattern)}' is unreachable "
                    "because a previous wildcard pattern covers all values"
                ),
            )
            return wildcard_pattern

        key = self._match_pattern_key(pattern, pattern_kind, pattern_value)
        if key is not None and key in seen_patterns:
            self.add_semantic_error(
                SemanticErrorType.UNREACHABLE_CODE,
                pattern.span,
                context=f"redundant match pattern '{self._format_match_pattern(pattern)}'",
            )
            return wildcard_pattern

        if full_coverage_reason is not None:
            self.add_semantic_error(
                SemanticErrorType.UNREACHABLE_CODE,
                pattern.span,
                context=(
                    f"match pattern '{self._format_match_pattern(pattern)}' is unreachable "
                    f"because previous cases cover all {full_coverage_reason} values"
                ),
            )
            return wildcard_pattern

        range_key = self._match_pattern_range(pattern)
        if range_key is None and key is not None:
            range_hit = self._literal_covered_by_seen_range(key, seen_ranges)
            if range_hit is not None:
                self.add_semantic_error(
                    SemanticErrorType.UNREACHABLE_CODE,
                    pattern.span,
                    context=(
                        f"match pattern '{self._format_match_pattern(pattern)}' is unreachable "
                        f"because it is covered by previous range pattern '{self._format_match_pattern(range_hit)}'"
                    ),
                )
                return wildcard_pattern

        if range_key is not None:
            overlap = self._find_overlapping_match_range(range_key, seen_ranges)
            if overlap is not None:
                self.add_semantic_error(
                    SemanticErrorType.UNREACHABLE_CODE,
                    pattern.span,
                    context=(
                        f"match range pattern '{self._format_match_pattern(pattern)}' overlaps "
                        f"previous range pattern '{self._format_match_pattern(overlap)}'"
                    ),
                )
                return wildcard_pattern

            literal_overlap = self._find_seen_literal_in_range(range_key, seen_patterns)
            if literal_overlap is not None:
                self.add_semantic_error(
                    SemanticErrorType.UNREACHABLE_CODE,
                    pattern.span,
                    context=(
                        f"match range pattern '{self._format_match_pattern(pattern)}' overlaps "
                        f"previous literal pattern '{self._format_match_pattern(literal_overlap)}'"
                    ),
                )
                return wildcard_pattern

        if key is None:
            if range_key is not None:
                seen_ranges.append((*range_key, pattern))
            return wildcard_pattern

        seen_patterns[key] = pattern
        if pattern_kind == "wildcard":
            return pattern

        return wildcard_pattern

    def _match_pattern_range(self, pattern: ASTNode) -> Optional[Tuple[str, float, float]]:
        """Return a comparable inclusive range for statically-known numeric/char ranges."""
        if pattern.kind != NodeKind.PATTERN_RANGE:
            return None

        start = self._range_pattern_value(pattern.start, set()) if pattern.start else None
        end = self._range_pattern_value(pattern.end, set()) if pattern.end else None
        if start is None or end is None:
            start = self._range_symbolic_value(pattern.start) if pattern.start else None
            end = self._range_symbolic_value(pattern.end) if pattern.end else None
            if start is None or end is None:
                return None

        start_kind, start_value = start
        end_kind, end_value = end
        if start_kind.startswith("symbol:") and end_kind.startswith("symbol:"):
            symbols = sorted({start_kind.removeprefix("symbol:"), end_kind.removeprefix("symbol:")})
            return (f"symbolic:{'|'.join(symbols)}", 0, 0)
        if start_kind != end_kind:
            return None

        low = min(start_value, end_value)
        high = max(start_value, end_value)
        return (start_kind, low, high)

    def _is_match_capture_pattern(self, pattern: ASTNode) -> bool:
        """Return true when an identifier pattern introduces a case-local binding."""
        if pattern.kind != NodeKind.PATTERN_IDENTIFIER:
            return False
        name = pattern.name or ""
        if not name or name == "_":
            return False
        if getattr(pattern, "is_capture_pattern", False):
            return True
        if self.symbols.lookup(name) is None:
            pattern.is_capture_pattern = True
            return True
        return False

    def _match_capture_patterns(self, patterns: List[ASTNode]) -> List[ASTNode]:
        return [pattern for pattern in patterns if self._is_match_capture_pattern(pattern)]

    def _validate_match_case_capture_shape(self, patterns: List[ASTNode]) -> None:
        captures = self._match_capture_patterns(patterns)
        if not captures:
            return
        if len(patterns) > 1:
            capture = captures[0]
            self.add_semantic_error(
                SemanticErrorType.INVALID_PATTERN,
                capture.span,
                context=(
                    f"Match capture pattern '{capture.name}' must be the only "
                    "pattern in its case"
                ),
            )

    def _define_match_capture_symbols(self, patterns: List[ASTNode], capture_type: Type) -> None:
        for pattern in self._match_capture_patterns(patterns):
            name = pattern.name or ""
            existing = self.symbols.current_scope.lookup_local(name)
            if existing:
                existing.type = capture_type
                existing.node = pattern
                existing.is_mutable = False
                continue

            capture_symbol = Symbol(
                name=name,
                kind=SymbolKind.VARIABLE,
                type=capture_type,
                node=pattern,
                is_mutable=False,
            )
            if not self.symbols.define(capture_symbol):
                self.add_semantic_error(
                    SemanticErrorType.ALREADY_DEFINED,
                    pattern.span,
                    context=f"Match capture '{name}'",
                )

    def _range_pattern_value(self, pattern: Optional[ASTNode], resolving: Set[str]) -> Optional[Tuple[str, int | float]]:
        """Resolve literals and constant identifiers to comparable range values."""
        if pattern is None:
            return None

        literal = self._match_pattern_literal(pattern)
        if literal is not None:
            return self._range_literal_value(literal)

        name = None
        if pattern.kind == NodeKind.PATTERN_IDENTIFIER:
            name = pattern.name
        elif pattern.kind == NodeKind.IDENTIFIER:
            name = pattern.name

        if name:
            if name in resolving:
                return None
            symbol = self.symbols.lookup(name)
            if symbol is None or symbol.kind != SymbolKind.CONSTANT or symbol.node is None:
                return None
            value_node = getattr(symbol.node, "value", None)
            return self._range_const_expr_value(value_node, resolving | {name})

        return self._range_const_expr_value(pattern, resolving)

    def _range_const_expr_value(self, node: Optional[ASTNode], resolving: Set[str]) -> Optional[Tuple[str, int | float]]:
        """Evaluate simple compile-time constant expressions for range diagnostics."""
        if node is None:
            return None

        literal = self._match_pattern_literal(node)
        if literal is not None:
            return self._range_literal_value(literal)

        if node.kind == NodeKind.IDENTIFIER:
            return self._range_pattern_value(node, resolving)

        if node.kind == NodeKind.UNARY:
            value = self._range_const_expr_value(node.operand, resolving)
            if value is None:
                return None
            kind, number = value
            if kind != "number":
                return None
            if node.operator == UnaryOp.NEG:
                return ("number", -number)
            return None

        if node.kind == NodeKind.BINARY:
            left = self._range_const_expr_value(node.left, resolving)
            right = self._range_const_expr_value(node.right, resolving)
            if left is None or right is None:
                return None
            left_kind, left_value = left
            right_kind, right_value = right
            if left_kind != "number" or right_kind != "number":
                return None
            if node.operator == BinaryOp.ADD:
                return ("number", left_value + right_value)
            if node.operator == BinaryOp.SUB:
                return ("number", left_value - right_value)
            if node.operator == BinaryOp.MUL:
                return ("number", left_value * right_value)
            if node.operator == BinaryOp.DIV and right_value != 0:
                if isinstance(left_value, int) and isinstance(right_value, int):
                    return ("number", left_value // right_value)
                return ("number", left_value / right_value)
            if node.operator == BinaryOp.MOD and right_value != 0:
                return ("number", left_value % right_value)

        return None

    def _range_symbolic_value(self, node: Optional[ASTNode]) -> Optional[Tuple[str, int | float]]:
        """Resolve runtime-symbolic range endpoints backed by local variables."""
        if node is None:
            return None

        if node.kind in {NodeKind.IDENTIFIER, NodeKind.PATTERN_IDENTIFIER}:
            name = node.name or ""
            if not name:
                return None
            symbol = self.symbols.lookup(name)
            if symbol is None or symbol.kind != SymbolKind.VARIABLE:
                return None
            symbol_type = symbol.type
            if symbol_type.kind != TypeKind.UNKNOWN and not self._is_numeric_compatible(symbol_type):
                return None
            return (f"symbol:{name}", 0)

        return None

    def _range_literal_value(self, literal: ASTNode) -> Optional[Tuple[str, int | float]]:
        """Normalize literal values that can participate in range overlap checks."""
        if literal.literal_kind == LiteralKind.INTEGER:
            return ("number", int(literal.literal_value))

        if literal.literal_kind == LiteralKind.FLOAT:
            return ("number", float(literal.literal_value))

        if literal.literal_kind == LiteralKind.CHAR:
            value = str(literal.literal_value or "")
            if len(value) != 1:
                return None
            return ("char", ord(value))

        return None

    def _literal_covered_by_seen_range(
        self,
        key: Tuple[str, Any],
        seen_ranges: List[Tuple[str, float, float, ASTNode]],
    ) -> Optional[ASTNode]:
        """Return a previous range that covers this literal key, if any."""
        literal = self._literal_key_range_value(key)
        if literal is None:
            return None

        literal_kind, value = literal
        for range_kind, low, high, range_pattern in seen_ranges:
            if literal_kind == range_kind and low <= value <= high:
                return range_pattern

        return None

    def _literal_key_range_value(self, key: Tuple[str, Any]) -> Optional[Tuple[str, float]]:
        """Normalize a literal pattern key for range containment checks."""
        if len(key) != 3 or key[0] != "literal":
            return None

        literal_kind = key[1]
        literal_value = key[2]
        if literal_kind in {LiteralKind.INTEGER, LiteralKind.FLOAT}:
            return ("number", float(literal_value))

        if literal_kind == LiteralKind.CHAR:
            value = str(literal_value or "")
            if len(value) != 1:
                return None
            return ("char", float(ord(value)))

        return None

    def _find_overlapping_match_range(
        self,
        range_key: Tuple[str, float, float],
        seen_ranges: List[Tuple[str, float, float, ASTNode]],
    ) -> Optional[ASTNode]:
        """Return a previous range pattern that overlaps this range, if any."""
        current_kind, current_low, current_high = range_key
        for seen_kind, seen_low, seen_high, seen_pattern in seen_ranges:
            if current_kind.startswith("symbolic:") and seen_kind.startswith("symbolic:"):
                current_symbols = set(current_kind.removeprefix("symbolic:").split("|"))
                seen_symbols = set(seen_kind.removeprefix("symbolic:").split("|"))
                if current_symbols & seen_symbols:
                    return seen_pattern
                continue
            if current_kind != seen_kind:
                continue
            if current_low <= seen_high and seen_low <= current_high:
                return seen_pattern

        return None

    def _find_seen_literal_in_range(
        self,
        range_key: Tuple[str, float, float],
        seen_patterns: Dict[Tuple[str, Any], ASTNode],
    ) -> Optional[ASTNode]:
        """Return a previous literal pattern that falls inside this range, if any."""
        range_kind, low, high = range_key
        for key, pattern in seen_patterns.items():
            literal = self._literal_key_range_value(key)
            if literal is None:
                continue
            literal_kind, value = literal
            if literal_kind == range_kind and low <= value <= high:
                return pattern

        return None

    def _match_full_coverage_reason(
        self,
        scrutinee_type: Type,
        bool_coverage: Set[bool],
        enum_coverage: Set[str],
    ) -> Optional[str]:
        """Return a coverage label when previous patterns already cover the scrutinee."""
        if scrutinee_type.equals(BOOL) and bool_coverage == {True, False}:
            return "bool"

        if isinstance(scrutinee_type, EnumType):
            declared_variants = {variant.name for variant in scrutinee_type.variants}
            if declared_variants and declared_variants <= enum_coverage:
                return f"enum '{scrutinee_type.name}'"

        return None

    def _match_pattern_key(
        self,
        pattern: ASTNode,
        pattern_kind: Optional[str],
        pattern_value: Optional[object],
    ) -> Optional[Tuple[str, Any]]:
        """Return a comparable key for patterns with exact coverage."""
        if pattern_kind == "wildcard":
            return ("wildcard", None)

        if pattern_kind == "bool":
            return ("bool", bool(pattern_value))

        if pattern_kind == "enum" and isinstance(pattern_value, str):
            return ("enum", pattern.enum_type or "", pattern_value)

        literal = self._match_pattern_literal(pattern)
        if literal is None:
            constant = self._range_pattern_value(pattern, set())
            if constant is None:
                return None
            kind, value = constant
            if kind == "char":
                return ("literal", LiteralKind.CHAR, chr(int(value)))
            if isinstance(value, float):
                return ("literal", LiteralKind.FLOAT, value)
            return ("literal", LiteralKind.INTEGER, value)

        return ("literal", literal.literal_kind, literal.literal_value)

    def _match_pattern_literal(self, pattern: ASTNode) -> Optional[ASTNode]:
        """Return the literal node embedded in a literal pattern."""
        if pattern.kind == NodeKind.PATTERN_LITERAL and pattern.literal:
            literal = pattern.literal
            return literal if literal.kind == NodeKind.LITERAL else None

        if pattern.kind == NodeKind.LITERAL:
            return pattern

        return None

    def _format_match_pattern(self, pattern: ASTNode) -> str:
        """Format a match pattern for diagnostics."""
        if pattern.kind == NodeKind.PATTERN_WILDCARD:
            return "_"

        if pattern.kind == NodeKind.PATTERN_IDENTIFIER:
            return pattern.name or "<identifier>"

        if pattern.kind == NodeKind.PATTERN_ENUM:
            return f"{pattern.enum_type}.{pattern.variant}"

        if pattern.kind == NodeKind.PATTERN_RANGE:
            start = self._format_match_pattern(pattern.start) if pattern.start else ""
            end = self._format_match_pattern(pattern.end) if pattern.end else ""
            return f"{start}..{end}"

        literal = self._match_pattern_literal(pattern)
        if literal is not None:
            value = literal.literal_value
            if literal.literal_kind == LiteralKind.STRING:
                return f'"{value}"'
            if literal.literal_kind == LiteralKind.CHAR:
                return f"'{value}'"
            if literal.literal_kind == LiteralKind.BOOLEAN:
                return "true" if value else "false"
            if literal.literal_kind == LiteralKind.NIL:
                return "nil"
            return str(value)

        return pattern.kind.name.lower()

    def _match_else_span(self, else_case: object) -> Optional[SourceSpan]:
        """Find the best available span for a match else branch."""
        if isinstance(else_case, ASTNode):
            return else_case.span

        if isinstance(else_case, list) and else_case:
            first = else_case[0]
            if isinstance(first, ASTNode):
                return first.span

        return None

    def _validate_match_pattern(self, pattern: ASTNode, scrutinee_type: Type) -> Tuple[Optional[str], Optional[object]]:
        """Type-check a match pattern against the scrutinee type.

        Returns:
            Tuple of coverage kind/value used for exhaustiveness tracking:
            - ("wildcard", None)
            - ("bool", True|False)
            - ("enum", variant_name)
            - (None, None) for patterns that do not contribute specific coverage.
        """
        if pattern.kind == NodeKind.PATTERN_WILDCARD:
            return ("wildcard", None)

        if pattern.kind == NodeKind.PATTERN_IDENTIFIER and (pattern.name or "") == "_":
            return ("wildcard", None)

        if self._is_match_capture_pattern(pattern):
            return ("wildcard", None)

        if pattern.kind == NodeKind.PATTERN_RANGE:
            if scrutinee_type.kind != TypeKind.UNKNOWN and not (
                self._is_numeric_compatible(scrutinee_type) or scrutinee_type.equals(CHAR)
            ):
                self.add_type_error(
                    TypeErrorType.TYPE_MISMATCH,
                    pattern.span,
                    expected_type="numeric or char",
                    got_type=str(scrutinee_type),
                    context="Range patterns require a numeric or char match type",
                )

            for endpoint in (pattern.start, pattern.end):
                if endpoint is None:
                    continue
                endpoint_type = self._resolve_pattern_type(endpoint, scrutinee_type)
                if (
                    endpoint_type.kind != TypeKind.UNKNOWN
                    and scrutinee_type.kind != TypeKind.UNKNOWN
                    and not self._is_initializer_assignable_to(
                        endpoint,
                        endpoint_type,
                        scrutinee_type,
                        endpoint.span,
                        context="Range pattern endpoint type mismatch",
                    )
                ):
                    self.add_type_error(
                        TypeErrorType.TYPE_MISMATCH,
                        endpoint.span,
                        expected_type=str(scrutinee_type),
                        got_type=str(endpoint_type),
                        context="Range pattern endpoint type mismatch",
                    )
            return (None, None)

        pattern_type = self._resolve_pattern_type(pattern, scrutinee_type)
        if (
            pattern_type.kind != TypeKind.UNKNOWN
            and scrutinee_type.kind != TypeKind.UNKNOWN
            and not self._is_initializer_assignable_to(
                self._pattern_value_node(pattern),
                pattern_type,
                scrutinee_type,
                pattern.span,
                context="Match pattern type mismatch",
            )
        ):
            self.add_type_error(
                TypeErrorType.TYPE_MISMATCH,
                pattern.span,
                expected_type=str(scrutinee_type),
                got_type=str(pattern_type),
                context="Match pattern type mismatch",
            )

        if pattern.kind == NodeKind.PATTERN_LITERAL and pattern.literal:
            literal = pattern.literal
            if literal.kind == NodeKind.LITERAL and literal.literal_kind == LiteralKind.BOOLEAN:
                return ("bool", bool(literal.literal_value))

        if pattern.kind == NodeKind.LITERAL and pattern.literal_kind == LiteralKind.BOOLEAN:
            return ("bool", bool(pattern.literal_value))

        if pattern.kind == NodeKind.PATTERN_ENUM and isinstance(scrutinee_type, EnumType):
            return ("enum", pattern.variant)

        return (None, None)

    def _pattern_value_node(self, pattern: ASTNode) -> ASTNode:
        if pattern.kind == NodeKind.PATTERN_LITERAL and pattern.literal:
            return pattern.literal
        return pattern

    def _resolve_pattern_type(self, pattern: ASTNode, scrutinee_type: Type) -> Type:
        """Resolve the semantic type of a pattern node."""
        if pattern.kind == NodeKind.PATTERN_LITERAL and pattern.literal:
            return self.visit_expression(pattern.literal)

        if pattern.kind == NodeKind.PATTERN_ENUM:
            enum_name = pattern.enum_type or ""
            variant_name = pattern.variant or ""

            enum_symbol = self.symbols.lookup(enum_name)
            if not enum_symbol or not isinstance(enum_symbol.type, EnumType):
                self.add_type_error(
                    TypeErrorType.UNDEFINED_TYPE,
                    pattern.span,
                    context=f"Enum '{enum_name}'",
                )
                return UNKNOWN

            enum_type = enum_symbol.type
            if not enum_type.has_variant(variant_name):
                self.add_type_error(
                    TypeErrorType.NO_SUCH_FIELD,
                    pattern.span,
                    context=f"Enum '{enum_name}' has no variant '{variant_name}'",
                )
                return UNKNOWN

            if isinstance(scrutinee_type, EnumType) and scrutinee_type.name != enum_type.name:
                self.add_type_error(
                    TypeErrorType.TYPE_MISMATCH,
                    pattern.span,
                    expected_type=str(scrutinee_type),
                    got_type=str(enum_type),
                    context="Match pattern enum type mismatch",
                )

            return enum_type

        if pattern.kind == NodeKind.PATTERN_IDENTIFIER:
            pattern_name = pattern.name or ""
            if pattern_name == "_":
                return UNKNOWN

            symbol = self.symbols.lookup(pattern_name)
            if symbol:
                self.symbols.mark_used(pattern_name)
                return symbol.type

            self.add_semantic_error(
                SemanticErrorType.UNDEFINED_IDENTIFIER,
                pattern.span,
                context=f"Pattern identifier '{pattern_name}'",
            )
            return UNKNOWN

        return self.visit_expression(pattern)

    def _check_match_exhaustiveness(
        self,
        span: Optional[SourceSpan],
        scrutinee_type: Type,
        has_catch_all: bool,
        bool_coverage: Set[bool],
        enum_coverage: Set[str],
    ) -> None:
        """Emit non-exhaustive match diagnostics for bool and enum scrutinees."""
        if has_catch_all or scrutinee_type.kind == TypeKind.UNKNOWN:
            return

        if scrutinee_type.equals(BOOL):
            missing = []
            if True not in bool_coverage:
                missing.append("true")
            if False not in bool_coverage:
                missing.append("false")
            if missing:
                self.add_semantic_error(
                    SemanticErrorType.NON_EXHAUSTIVE_MATCH,
                    span,
                    context=f"Missing bool case(s): {', '.join(missing)}",
                )
            return

        if isinstance(scrutinee_type, EnumType):
            declared_variants = {variant.name for variant in scrutinee_type.variants}
            missing = sorted(declared_variants - enum_coverage)
            if missing:
                self.add_semantic_error(
                    SemanticErrorType.NON_EXHAUSTIVE_MATCH,
                    span,
                    context=f"Enum '{scrutinee_type.name}' missing case(s): {', '.join(missing)}",
                )

    def visit_struct_init(self, node: ASTNode) -> Type:
        """Visit a struct initialization."""
        # Resolve struct type
        struct_type = None
        if node.struct_type:
            if isinstance(node.struct_type, str):
                # Look up type by name
                symbol = self.symbols.lookup(node.struct_type)
                struct_type = symbol.type if symbol else None
            else:
                struct_type = self.resolve_type_node(node.struct_type)

        if isinstance(struct_type, UnionType):
            return self._visit_union_init(node, struct_type)

        if not isinstance(struct_type, StructType):
            return UNKNOWN

        result_type: Type = struct_type

        # Generic struct instantiation: Pair(i32, string){...}
        type_arg_nodes = getattr(node, "type_arguments", None) or []
        if type_arg_nodes:
            original_struct_type = struct_type
            type_args = [self.resolve_type_node(arg) for arg in type_arg_nodes]
            struct_type = self._instantiate_struct_type(struct_type, type_args)
            if (
                original_struct_type.name
                and len(original_struct_type.generic_params or ()) == len(type_args)
            ):
                result_type = GenericInstanceType(
                    base_name=original_struct_type.name,
                    type_args=tuple(type_args),
                )
            else:
                result_type = struct_type

        # Type check field initializers
        if node.field_inits:
            for field_init in node.field_inits:
                field_name = field_init.name or ""
                # Get expected field type from struct definition
                expected_type = None
                for field in struct_type.fields:
                    if field.name == field_name:
                        expected_type = field.field_type
                        break

                # Type check the value
                if field_init.value:
                    actual_type = self.visit_expression(field_init.value)
                    if expected_type and not self._is_initializer_assignable_to(
                        field_init.value,
                        actual_type,
                        expected_type,
                        field_init.span,
                        context=f"Field '{field_name}'",
                    ):
                        self.add_type_error(
                            TypeErrorType.TYPE_MISMATCH,
                            field_init.span,
                            expected_type=str(expected_type),
                            got_type=str(actual_type),
                            context=f"Field '{field_name}'"
                        )

        return result_type

    def _visit_union_init(self, node: ASTNode, union_type: UnionType) -> Type:
        """Visit a union initialization using the existing Type{field: value} literal."""
        field_inits = node.field_inits or []
        if len(field_inits) != 1 or not field_inits[0].name:
            self.add_type_error(
                TypeErrorType.TYPE_MISMATCH,
                node.span,
                expected_type=f"one named field for union '{union_type.name}'",
                got_type=f"{len(field_inits)} initializer(s)",
            )
            return union_type

        field_init = field_inits[0]
        field_name = field_init.name or ""
        expected_field = union_type.get_field(field_name)
        if expected_field is None:
            self.add_type_error(
                TypeErrorType.NO_SUCH_FIELD,
                field_init.span,
                context=f"Union '{union_type}' has no field '{field_name}'",
            )
            return union_type

        if field_init.value:
            actual_type = self.visit_expression(field_init.value)
            if not self._is_initializer_assignable_to(
                field_init.value,
                actual_type,
                expected_field.field_type,
                field_init.span,
                context=f"Union field '{field_name}'",
            ):
                self.add_type_error(
                    TypeErrorType.TYPE_MISMATCH,
                    field_init.span,
                    expected_type=str(expected_field.field_type),
                    got_type=str(actual_type),
                    context=f"Union field '{field_name}'",
                )

        return union_type

    def visit_array_init(self, node: ASTNode) -> Type:
        """Visit an array initialization."""
        # Infer element type from first element
        if node.elements and len(node.elements) > 0:
            elem_type = self.visit_expression(node.elements[0])
            size = len(node.elements)
            for index, element in enumerate(node.elements[1:], start=1):
                actual_type = self.visit_expression(element)
                common_type = self._common_array_literal_element_type(elem_type, actual_type)
                if common_type is None:
                    self.add_type_error(
                        TypeErrorType.TYPE_MISMATCH,
                        element.span,
                        expected_type=str(elem_type),
                        got_type=str(actual_type),
                        context=f"Array element {index}",
                    )
                else:
                    elem_type = common_type
            return ArrayType(element_type=elem_type, size=size)

        return UNKNOWN

    def _common_array_literal_element_type(self, left: Type, right: Type) -> Optional[Type]:
        """Find a common literal element type without accepting unrelated shapes."""
        if right.is_assignable_to(left):
            return left
        if left.is_assignable_to(right):
            return right
        if isinstance(left, ArrayType) and isinstance(right, ArrayType) and left.size == right.size:
            element_type = self._common_array_literal_element_type(left.element_type, right.element_type)
            if element_type is not None:
                return ArrayType(element_type=element_type, size=left.size)
        return None

    def _is_initializer_assignable_to(
        self,
        value_node: Optional[ASTNode],
        actual_type: Type,
        expected_type: Type,
        span: Optional[SourceSpan],
        context: str = "Initializer",
    ) -> bool:
        """Check assignment with literal-specific validation for composite types."""
        if self._is_nil_literal(value_node):
            return isinstance(expected_type, ReferenceType)
        if (
            value_node
            and value_node.kind == NodeKind.ARRAY_INIT
            and isinstance(expected_type, ArrayType)
        ):
            return self._check_array_initializer_assignable(
                value_node,
                expected_type,
                span,
                context,
            )
        if isinstance(expected_type, PrimitiveType):
            literal_value = self._integer_literal_value(value_node)
            if literal_value is not None:
                return self._integer_literal_fits_type(literal_value, expected_type)
            if self._is_float_literal(value_node) and expected_type.name in {'f32', 'f64'}:
                return True

        return actual_type.is_assignable_to(expected_type)

    def _is_nil_literal(self, value_node: Optional[ASTNode]) -> bool:
        return (
            value_node is not None
            and value_node.kind == NodeKind.LITERAL
            and value_node.literal_kind == LiteralKind.NIL
        )

    def _integer_literal_value(self, value_node: Optional[ASTNode]) -> Optional[int]:
        if value_node is None:
            return None
        if (
            value_node.kind == NodeKind.LITERAL
            and value_node.literal_kind == LiteralKind.INTEGER
            and isinstance(value_node.literal_value, int)
        ):
            return value_node.literal_value
        if (
            value_node.kind == NodeKind.UNARY
            and value_node.operator == UnaryOp.NEG
            and value_node.operand
            and value_node.operand.kind == NodeKind.LITERAL
            and value_node.operand.literal_kind == LiteralKind.INTEGER
            and isinstance(value_node.operand.literal_value, int)
        ):
            return -value_node.operand.literal_value
        return None

    def _integer_literal_fits_type(self, value: int, target: PrimitiveType) -> bool:
        ranges = {
            'i8': (-(2**7), 2**7 - 1),
            'i16': (-(2**15), 2**15 - 1),
            'i32': (-(2**31), 2**31 - 1),
            'i64': (-(2**63), 2**63 - 1),
            'isize': (-(2**63), 2**63 - 1),
            'u8': (0, 2**8 - 1),
            'u16': (0, 2**16 - 1),
            'u32': (0, 2**32 - 1),
            'u64': (0, 2**64 - 1),
            'usize': (0, 2**64 - 1),
        }
        if target.name in ranges:
            lo, hi = ranges[target.name]
            return lo <= value <= hi
        return target.name in {'f32', 'f64'}

    def _is_float_literal(self, value_node: Optional[ASTNode]) -> bool:
        return (
            value_node is not None
            and value_node.kind == NodeKind.LITERAL
            and value_node.literal_kind == LiteralKind.FLOAT
        )

    def _check_array_initializer_assignable(
        self,
        node: ASTNode,
        expected_type: ArrayType,
        span: Optional[SourceSpan],
        context: str,
    ) -> bool:
        elements = node.elements or []
        ok = True

        if len(elements) != expected_type.size:
            self.add_type_error(
                TypeErrorType.TYPE_MISMATCH,
                span or node.span,
                expected_type=f"[{expected_type.size}]{expected_type.element_type}",
                got_type=f"[{len(elements)}]{expected_type.element_type}",
                context=f"{context} array size mismatch",
            )
            ok = False

        for index, element in enumerate(elements):
            actual_element_type = self.get_type(element)
            if actual_element_type is None:
                actual_element_type = self.visit_expression(element)

            if (
                element.kind == NodeKind.ARRAY_INIT
                and isinstance(expected_type.element_type, ArrayType)
            ):
                if not self._check_array_initializer_assignable(
                    element,
                    expected_type.element_type,
                    element.span,
                    f"{context} element {index}",
                ):
                    ok = False
                continue

            if not self._is_initializer_assignable_to(
                element,
                actual_element_type,
                expected_type.element_type,
                element.span,
                context=f"{context} element {index}",
            ):
                self.add_type_error(
                    TypeErrorType.TYPE_MISMATCH,
                    element.span,
                    expected_type=str(expected_type.element_type),
                    got_type=str(actual_element_type),
                    context=f"{context} element {index}",
                )
                ok = False

        return ok

    def visit_new_expr(self, node: ASTNode) -> Type:
        """Visit a new expression."""
        # new T returns ref T
        alloc_type = self.resolve_type_node(node.target_type) if node.target_type else UNKNOWN
        if isinstance(alloc_type, ArrayType):
            self.add_type_error(
                TypeErrorType.TYPE_MISMATCH,
                node.span,
                expected_type="scalar or struct allocation",
                got_type=str(alloc_type),
                context="new [N]T heap arrays are not implemented; use a stack array or slice an existing array",
            )
        return ReferenceType(referent_type=alloc_type)

    # Generic/type helpers

    def _is_numeric_compatible(self, type_: Type) -> bool:
        return type_.is_numeric() or isinstance(type_, (GenericParamType, UnknownType))

    def _is_integral_compatible(self, type_: Type) -> bool:
        return type_.is_integral() or isinstance(type_, (GenericParamType, UnknownType))

    def _types_are_comparable(self, left: Type, right: Type, *, ordering: bool) -> bool:
        if isinstance(left, (GenericParamType, UnknownType)) or isinstance(right, (GenericParamType, UnknownType)):
            return True
        if ordering:
            return self._is_numeric_compatible(left) and self._is_numeric_compatible(right)
        if left.equals(right):
            return True
        return self._is_numeric_compatible(left) and self._is_numeric_compatible(right)

    def _collect_generic_type_names(self, type_: Type, out: List[str]) -> None:
        """Collect GenericParamType names reachable from a semantic Type object."""
        stack: List[Type] = [type_]
        while stack:
            current = stack.pop()
            if isinstance(current, GenericParamType):
                out.append(current.name)
            elif isinstance(current, ReferenceType):
                stack.append(current.referent_type)
            elif isinstance(current, PointerType):
                stack.append(current.pointee_type)
            elif isinstance(current, ArrayType):
                stack.append(current.element_type)
            elif isinstance(current, SliceType):
                stack.append(current.element_type)
            elif isinstance(current, FunctionType):
                if current.return_type is not None:
                    stack.append(current.return_type)
                stack.extend(current.param_types)
            elif isinstance(current, GenericInstanceType):
                stack.extend(list(current.type_args))
            elif isinstance(current, StructType):
                for field in current.fields:
                    stack.append(field.field_type)

    def _instantiate_struct_type(self, struct_type: StructType, type_args: List[Type]) -> StructType:
        """Instantiate a generic struct with concrete type arguments."""
        params = list(struct_type.generic_params or ())
        if not params:
            return struct_type
        if len(params) != len(type_args):
            # Keep original type for error reporting paths.
            return struct_type

        mapping: Dict[str, Type] = {name: arg for name, arg in zip(params, type_args)}
        new_fields = tuple(
            StructField(name=field.name, field_type=self._substitute_generic(field.field_type, mapping))
            for field in struct_type.fields
        )
        return StructType(name=struct_type.name, fields=new_fields, generic_params=())

    def _resolve_generic_instance_struct(self, instance: GenericInstanceType) -> Optional[StructType]:
        """Resolve GenericInstanceType(base, args) to a concrete StructType if base is a struct."""
        symbol = self.symbols.lookup(instance.base_name)
        if not symbol or not isinstance(symbol.type, StructType):
            return None
        return self._instantiate_struct_type(symbol.type, list(instance.type_args))
