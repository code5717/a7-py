"""
Type checking pass for A7 semantic analysis.

Performs type inference, type checking, and type compatibility validation.
"""

from typing import Any, Optional, List, Dict, Set, Tuple

from src.ast_nodes import ASTNode, NodeKind, BinaryOp, UnaryOp, AssignOp, LiteralKind
from src.symbol_table import SymbolTable, Symbol, SymbolKind
from src.semantic_context import SemanticContext
from src.types import (
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
from src.errors import SemanticError, TypeCheckError, TypeErrorType, SemanticErrorType, SourceSpan


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
        # TYPE_ALIAS will be resolved on-demand

    def register_function_signature(self, node: ASTNode) -> None:
        """Register a function's signature (type) without processing its body.

        This enables mutual recursion support - all function types are known
        before any function bodies are type-checked.
        """
        func_name = node.name or "<anonymous>"

        # Resolve return type
        return_type = self.resolve_type_node(node.return_type) if node.return_type else None

        # Resolve parameter types
        param_types = []
        if node.parameters:
            for param in node.parameters:
                param_type = self.resolve_type_node(param.param_type) if param.param_type else UNKNOWN
                param_types.append(param_type)

        # Check for variadic
        is_variadic = node.is_variadic or False
        if not is_variadic and node.parameters:
            last_param = node.parameters[-1]
            is_variadic = getattr(last_param, 'is_variadic', False) or False

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
            variadic_type=variadic_type
        )

        # Update function symbol
        func_symbol = self.symbols.lookup(func_name)
        if func_symbol:
            func_symbol.type = func_type

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
                return GenericParamType(name=node.name)
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
        # Struct/enum/union already registered

    def visit_function_decl(self, node: ASTNode) -> None:
        """Visit and type check a function declaration."""
        func_name = node.name or "<anonymous>"

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
        is_variadic = node.is_variadic or False
        if not is_variadic and node.parameters:
            # Check if last parameter is variadic
            last_param = node.parameters[-1]
            is_variadic = getattr(last_param, 'is_variadic', False) or False

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
            variadic_type=variadic_type
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
            elif node.value and not is_nil_value and not value_type.is_assignable_to(explicit_type):
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
                stack.append(('action', lambda: self.symbols.exit_scope()))
                for stmt in reversed(nd.statements or []):
                    stack.append(('visit', stmt))

            elif nd.kind == NodeKind.VAR:
                self.visit_var_decl(nd)
            elif nd.kind == NodeKind.CONST:
                self.visit_const_decl(nd)

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

        # Mutability check: look up the target symbol
        if node.target and node.target.kind == NodeKind.IDENTIFIER:
            target_name = node.target.name
            sym = self.symbols.lookup(target_name)
            if sym and not sym.is_mutable and node.target.kind != NodeKind.DEREF:
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
                if not self._is_numeric_compatible(lhs_type):
                    self.add_type_error(TypeErrorType.REQUIRES_NUMERIC_TYPE, node.span, got_type=str(lhs_type), context=f"Operator {op.name} requires numeric type")
            elif op in bitwise_ops:
                if not self._is_integral_compatible(lhs_type):
                    self.add_type_error(TypeErrorType.REQUIRES_INTEGER_TYPE, node.span, got_type=str(lhs_type), context=f"Operator {op.name} requires integer type")

        # Check assignment compatibility
        if not rhs_type.is_assignable_to(lhs_type):
            self.add_type_error(
                TypeErrorType.ASSIGNMENT_TYPE_MISMATCH,
                node.span,
                expected_type=str(lhs_type),
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
        # Get function type
        func_type = self.visit_expression(node.function) if node.function else UNKNOWN

        if not isinstance(func_type, FunctionType):
            # Check if this is a module method call (e.g., io.println) — allow it
            if isinstance(func_type, UnknownType) and node.function:
                if node.function.kind == NodeKind.FIELD_ACCESS and node.function.object:
                    obj_symbol = self.symbols.lookup(
                        getattr(node.function.object, 'name', '') or ''
                    )
                    if obj_symbol and obj_symbol.kind == SymbolKind.MODULE:
                        # Module method call — type check args but don't error
                        if node.arguments:
                            for arg in node.arguments:
                                self.visit_expression(arg)
                        return UNKNOWN

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
        if generic_mapping:
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
        for i, (arg_type, param_type) in enumerate(zip(arg_types, resolved_param_types)):
            if isinstance(param_type, UnknownType):
                continue  # Skip type checking for untyped variadic parameters
            if isinstance(param_type, GenericParamType):
                continue  # Skip generic params that weren't resolved
            if not arg_type.is_assignable_to(param_type):
                self.add_type_error(
                    TypeErrorType.ARGUMENT_TYPE_MISMATCH,
                    node.span,
                    expected_type=str(param_type),
                    got_type=str(arg_type),
                    context=f"Argument {i+1}"
                )

        # Resolve return type with generic substitution
        return_type = func_type.return_type if func_type.return_type else VOID
        if generic_mapping:
            return_type = self._substitute_generic(return_type, generic_mapping)

        return return_type

    def _infer_generic_types(self, func_type: FunctionType, arg_types: List[Type]) -> Dict[str, Type]:
        """
        Infer generic type parameters from actual argument types.

        Returns a mapping from generic parameter names to concrete types.
        """
        mapping: Dict[str, Type] = {}

        for param_type, arg_type in zip(func_type.param_types, arg_types):
            if isinstance(param_type, GenericParamType):
                # Direct generic parameter: $T
                if param_type.name in mapping:
                    # Already have a binding - verify consistency
                    existing = mapping[param_type.name]
                    if not arg_type.equals(existing):
                        # Type mismatch for same generic parameter
                        pass  # Will be caught by later checks
                else:
                    mapping[param_type.name] = arg_type
            elif isinstance(param_type, ReferenceType):
                # Reference to generic: ref $T
                if isinstance(param_type.referent_type, GenericParamType):
                    generic_name = param_type.referent_type.name
                    # Extract the referent type from the argument
                    if isinstance(arg_type, ReferenceType):
                        mapping[generic_name] = arg_type.referent_type
                    else:
                        # Try to use the argument type directly
                        mapping[generic_name] = arg_type
            elif isinstance(param_type, ArrayType):
                # Array of generic: []$T
                if isinstance(param_type.element_type, GenericParamType):
                    generic_name = param_type.element_type.name
                    if isinstance(arg_type, ArrayType):
                        mapping[generic_name] = arg_type.element_type
                    elif isinstance(arg_type, SliceType):
                        mapping[generic_name] = arg_type.element_type
            elif isinstance(param_type, SliceType):
                # Slice of generic: []$T
                if isinstance(param_type.element_type, GenericParamType):
                    generic_name = param_type.element_type.name
                    if isinstance(arg_type, SliceType):
                        mapping[generic_name] = arg_type.element_type
                    elif isinstance(arg_type, ArrayType):
                        mapping[generic_name] = arg_type.element_type

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
                current = FunctionType(param_types=new_params, return_type=new_return, is_variadic=current.is_variadic, variadic_type=current.variadic_type)
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

        if node.index and not index_type.is_integral():
            self.add_type_error(TypeErrorType.INDEX_NOT_INTEGER, node.index.span, got_type=str(index_type))

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
            if not start_type.is_integral():
                self.add_type_error(TypeErrorType.INDEX_NOT_INTEGER, node.start.span, got_type=str(start_type))

        if node.end:
            end_type = self.visit_expression(node.end)
            if not end_type.is_integral():
                self.add_type_error(TypeErrorType.INDEX_NOT_INTEGER, node.end.span, got_type=str(end_type))

        if isinstance(obj_type, ArrayType):
            return SliceType(obj_type.element_type)
        if isinstance(obj_type, SliceType):
            return SliceType(obj_type.element_type)
        if obj_type.equals(STRING):
            return SliceType(CHAR)

        self.add_type_error(TypeErrorType.REQUIRES_ARRAY_OR_SLICE, node.span, got_type=str(obj_type))
        return UNKNOWN

    def visit_field_access(self, node: ASTNode) -> Type:
        """Visit a field access expression."""
        obj_type = self.visit_expression(node.object) if node.object else UNKNOWN
        field_name = node.field or ""

        # Check if the object is a module symbol — allow field access without error
        if node.object and hasattr(node.object, 'name'):
            obj_symbol = self.symbols.lookup(node.object.name or "")
            if obj_symbol and obj_symbol.kind == SymbolKind.MODULE:
                # Module field access — return UNKNOWN since module isn't loaded
                return UNKNOWN

        if isinstance(obj_type, GenericInstanceType):
            concrete_struct = self._resolve_generic_instance_struct(obj_type)
            if concrete_struct is not None:
                obj_type = concrete_struct

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
        """Visit an address-of expression (.adr)."""
        operand_type = self.visit_expression(node.operand) if node.operand else UNKNOWN
        return ReferenceType(referent_type=operand_type)

    def visit_deref(self, node: ASTNode) -> Type:
        """Visit a dereference expression (.val)."""
        ptr_type = self.visit_expression(node.pointer) if node.pointer else UNKNOWN

        if isinstance(ptr_type, PointerType):
            return ptr_type.pointee_type
        elif isinstance(ptr_type, ReferenceType):
            return ptr_type.referent_type
        else:
            self.add_type_error(TypeErrorType.REQUIRES_POINTER_TYPE, node.span, got_type=str(ptr_type))
            return UNKNOWN

    def visit_cast(self, node: ASTNode) -> Type:
        """Visit a cast expression."""
        # Just return target type (actual cast validation would be more complex)
        return self.resolve_type_node(node.target_type)

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
                branch_types.append(self.visit_expression(case_expr))

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
        """Return a comparable inclusive range for literal numeric/char ranges."""
        if pattern.kind != NodeKind.PATTERN_RANGE:
            return None

        start_literal = self._match_pattern_literal(pattern.start) if pattern.start else None
        end_literal = self._match_pattern_literal(pattern.end) if pattern.end else None
        if start_literal is None or end_literal is None:
            return None

        start = self._range_literal_value(start_literal)
        end = self._range_literal_value(end_literal)
        if start is None or end is None:
            return None

        start_kind, start_value = start
        end_kind, end_value = end
        if start_kind != end_kind:
            return None

        low = min(start_value, end_value)
        high = max(start_value, end_value)
        return (start_kind, low, high)

    def _range_literal_value(self, literal: ASTNode) -> Optional[Tuple[str, float]]:
        """Normalize literal values that can participate in range overlap checks."""
        if literal.literal_kind in {LiteralKind.INTEGER, LiteralKind.FLOAT}:
            return ("number", float(literal.literal_value))

        if literal.literal_kind == LiteralKind.CHAR:
            value = str(literal.literal_value or "")
            if len(value) != 1:
                return None
            return ("char", float(ord(value)))

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
            return None

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
                    and not endpoint_type.is_assignable_to(scrutinee_type)
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
            and not pattern_type.is_assignable_to(scrutinee_type)
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

        if not isinstance(struct_type, StructType):
            return UNKNOWN

        # Generic struct instantiation: Pair(i32, string){...}
        type_arg_nodes = getattr(node, "type_arguments", None) or []
        if type_arg_nodes:
            type_args = [self.resolve_type_node(arg) for arg in type_arg_nodes]
            struct_type = self._instantiate_struct_type(struct_type, type_args)

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
                    if expected_type and not actual_type.is_assignable_to(expected_type):
                        self.add_type_error(
                            TypeErrorType.TYPE_MISMATCH,
                            field_init.span,
                            expected_type=str(expected_type),
                            got_type=str(actual_type),
                            context=f"Field '{field_name}'"
                        )

        return struct_type

    def visit_array_init(self, node: ASTNode) -> Type:
        """Visit an array initialization."""
        # Infer element type from first element
        if node.elements and len(node.elements) > 0:
            elem_type = self.visit_expression(node.elements[0])
            size = len(node.elements)
            return ArrayType(element_type=elem_type, size=size)

        return UNKNOWN

    def visit_new_expr(self, node: ASTNode) -> Type:
        """Visit a new expression."""
        # new T returns ref T
        alloc_type = self.resolve_type_node(node.target_type) if node.target_type else UNKNOWN
        return ReferenceType(referent_type=alloc_type)

    # Generic/type helpers

    def _is_numeric_compatible(self, type_: Type) -> bool:
        return type_.is_numeric() or isinstance(type_, (GenericParamType, UnknownType))

    def _is_integral_compatible(self, type_: Type) -> bool:
        return type_.is_integral() or isinstance(type_, (GenericParamType, UnknownType))

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
