"""
Type checking pass for A7 semantic analysis.

Performs type inference, type checking, and type compatibility validation.
"""

from collections import deque
from typing import Any, Optional, List, Dict, Set, Tuple

from a7.ast_nodes import ASTNode, NodeKind, BinaryOp, UnaryOp, AssignOp, LiteralKind
from a7.symbol_table import SymbolTable, Symbol, SymbolKind
from a7.semantic_context import SemanticContext
from a7.cast_classifier import classify_cast
from a7.types import (
    Type, TypeKind,
    PrimitiveType, ArrayType, SliceType, PointerType, ReferenceType,
    FunctionType, StructType, StructField, EnumType, EnumVariant,
    UnionType, UnionField, GenericParamType, GenericValueArg, GenericInstanceType,
    TypeSet, VoidType, UnknownType, NilType, NIL,
    BOOL, CHAR, STRING, I8, I16, I32, I64, U8, U16, U32, U64, F32, F64,
    USIZE,
    VOID, UNKNOWN, NUMERIC, INTEGER, INTEGER_RANGES, INTEGER_BIT_WIDTHS, NUMERIC_TYPES, INTEGER_TYPES,
    get_primitive_type, get_predefined_type_set
)
from a7.errors import SemanticError, TypeCheckError, TypeErrorType, SemanticErrorType, SourceSpan
from a7.stdlib import StdlibRegistry
from a7.exact_constants import evaluate, compare, render, materialize, ieee_bits, ExactArithmeticError, expression_span

_COMPARISON_OPS = frozenset({BinaryOp.EQ, BinaryOp.NE, BinaryOp.LT, BinaryOp.LE, BinaryOp.GT, BinaryOp.GE})
# The operators the exact evaluator folds.
_FOLDABLE_OPS = frozenset({
    BinaryOp.ADD, BinaryOp.SUB, BinaryOp.MUL, BinaryOp.DIV, BinaryOp.MOD,
    BinaryOp.BIT_AND, BinaryOp.BIT_OR, BinaryOp.BIT_XOR, BinaryOp.BIT_SHL, BinaryOp.BIT_SHR,
})
# Kinds whose first operand (left, object or callee) can nest without bound:
# `a + b + c`, `p.x.y`, `a[0][1]`, `f()()`.
_CHAIN_KINDS = frozenset({
    NodeKind.BINARY, NodeKind.FIELD_ACCESS, NodeKind.INDEX, NodeKind.SLICE, NodeKind.CALL,
})


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

    def __init__(self, symbols: SymbolTable, module_prefix_aliases: Optional[Dict[str, str]] = None):
        """
        Initialize type checking pass.

        Args:
            symbols: Symbol table from name resolution pass
            module_prefix_aliases: Maps an imported module's emit prefix
                (e.g. "module_helper__") to the alias the entry file
                imported it under (e.g. "h"). Used to name the qualified
                spelling when a bare call targets a merged module function.
        """
        self.symbols = symbols
        self.module_prefix_aliases: Dict[str, str] = dict(module_prefix_aliases or {})
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
        # Constraints declared on struct generic parameters, keyed by struct
        # name then parameter name. Registration resolves them once; struct
        # instantiation checks every type argument against them.
        self._struct_generic_constraints: Dict[str, Dict[str, TypeSet]] = {}
        # Same table for unions; union specialization monomorphizes
        # positionally exactly like structs.
        self._union_generic_constraints: Dict[str, Dict[str, TypeSet]] = {}
        # Declared $N value-parameter kinds (a VALUE_PARAM_KINDS name), keyed
        # by struct/union name then parameter name. A $X: <value kind>
        # constraint makes a value parameter; a TypeSet constraint
        # ($T: Numeric) or none keeps a type parameter.
        self._struct_value_param_types: Dict[str, Dict[str, str]] = {}
        self._union_value_param_types: Dict[str, Dict[str, str]] = {}
        # Value params in scope for array-size positions ([$N]u8) while
        # registering the declaration that owns them. Replaced, not mutated.
        self._active_value_params: Dict[str, str] = {}
        # Type nodes already reported for using a value parameter as a type.
        # Function signatures resolve twice (registration, then the visit).
        self._reported_value_param_types: Set[int] = set()
        # Count check result for each `Name(args)` type node already checked.
        self._annotation_argument_results: Dict[int, bool] = {}
        self._nonnegative_vars: Set[str] = set()
        self.stdlib = StdlibRegistry()
        self.exact_bindings = {}
        self._nested_functions = deque()
        self._generic_initializers: dict = {}
        self._generic_calls: dict = {}
        self._bound_callback_values: Set[int] = set()
        self._generic_callback_arguments: dict = {}

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
        self._active_value_params = {}
        self._reported_value_param_types = set()
        self._annotation_argument_results = {}
        self._nonnegative_vars = set()
        self._generic_initializers = {}
        self._generic_calls = {}
        self._bound_callback_values = set()
        self._generic_callback_arguments = {}

        # Visit the program
        self.visit_program(program)

        # Calls may precede declarations. Check each concrete instantiation
        # after all bodies have recorded their initializer requirements.
        pending = [(call, target, mapping, frozenset())
                   for calls in self._generic_calls.values()
                   for call, target, mapping in calls]
        checked = set()
        while pending:
            call, target, mapping, ancestors = pending.pop()
            if id(target) in ancestors:
                continue  # Source call cycles are rejected by semantic validation.
            unresolved: List[str] = []
            for concrete in mapping.values():
                self._collect_generic_type_names(concrete, unresolved)
            if unresolved or any(self._has_unknown(value) for value in mapping.values()):
                continue
            key = (id(target), tuple(sorted(mapping.items())))
            if key in checked:
                continue
            checked.add(key)
            for declaration, actual, expected in self._generic_initializers.get(id(target), ()):
                instantiated = self._substitute_generic(expected, mapping)
                value_type = self._substitute_generic(actual, mapping)
                unresolved = []
                self._collect_generic_type_names(instantiated, unresolved)
                self._collect_generic_type_names(value_type, unresolved)
                if unresolved or self._has_unknown(value_type):
                    continue
                fits = self._instantiated_value_fits(declaration.value, actual, value_type, instantiated, mapping)
                if not fits:
                    self.add_type_error(
                        TypeErrorType.TYPE_MISMATCH,
                        call.span or declaration.span,
                        expected_type=str(instantiated),
                        got_type=str(value_type),
                        context=f"Initializer of '{declaration.name}' in '{target.name}': {expected} instantiated as {instantiated}",
                    )
            for argument, actual, expected, position, exact_type in self._generic_callback_arguments.get(id(target), ()):
                value_type = self._substitute_generic(actual, mapping)
                instantiated = self._substitute_generic(expected, mapping)
                fits = value_type.equals(instantiated) if exact_type else self._instantiated_value_fits(argument, actual, value_type, instantiated, mapping)
                if not fits:
                    self.add_type_error(
                        TypeErrorType.ARGUMENT_TYPE_MISMATCH,
                        call.span or argument.span,
                        expected_type=str(instantiated),
                        got_type=str(value_type),
                        context=f"Callback argument {position} in '{target.name}'",
                    )
            lineage = ancestors | {id(target)}
            for nested_call, nested_target, nested_mapping in self._generic_calls.get(id(target), ()):
                pending.append((nested_call, nested_target,
                                {name: self._substitute_generic(value, mapping)
                                 for name, value in nested_mapping.items()}, lineage))

        # Only use sites acquire runtime representation. Exact bindings are erased.
        stack = [program]
        seen = set()
        while stack:
            node = stack.pop()
            if id(node) in seen:
                continue
            seen.add(id(node))
            if getattr(node, 'untyped_binding', False):
                continue
            exact = getattr(node, 'exact_constant', None)
            if (
                exact is not None
                and not getattr(node, 'exact_materialized', False)
                and not getattr(node, 'exact_diagnosed', False)
            ):
                target = self.get_type(node) or (F64 if exact[1] else I32)
                if isinstance(target, PrimitiveType) and target.is_numeric():
                    if not self._report_default_overflow(node):
                        self._is_initializer_assignable_to(node, target, target, expression_span(node))
            error = getattr(node, 'exact_float_error', None)
            if error:
                self.add_error(error, node.span)
            for value in vars(node).values():
                if isinstance(value, ASTNode):
                    stack.append(value)
                elif isinstance(value, list):
                    stack.extend(child for child in value if isinstance(child, ASTNode))

        # Return the node types map for use by later passes
        return self.node_types

    def _evaluate_exact(self, node, lookup, bindings):
        if node is None or getattr(node, 'exact_failed', False):
            return None
        try:
            return evaluate(node, lookup, bindings)
        except ExactArithmeticError as error:
            node.exact_failed = True
            self.add_error(str(error), expression_span(node))
            return None

    def _report_default_overflow(self, node: ASTNode) -> bool:
        """Report an integer constant with no destination that exceeds i32.

        Inferred variables, format arguments and generic inference all take
        the i32 default (SPEC 4.2.1); none of them widens to fit the value.
        """
        exact = getattr(node, 'exact_constant', None)
        if exact is None or exact[1] or self._integer_literal_fits_type(exact[0].numerator, I32):
            return False
        if not getattr(node, 'exact_diagnosed', False):
            self.add_error(
                f"Exact constant {render(exact[0])} does not fit default i32; use an explicit destination type",
                expression_span(node),
            )
            node.exact_diagnosed = True
        return True

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
            error = SemanticError.from_type(SemanticErrorType.UNEXPECTED_NODE_KIND, span=node.span, filename=self.current_file, source_lines=self.source_lines, context=f"Expected program node, got {node.kind.name}")
            self.errors.append(error)
            return

        # Build dependencies once, then resolve in postorder without recursion.
        globals_ = [d for d in node.declarations or [] if d.kind in {NodeKind.CONST, NodeKind.VAR}]
        declarations = {id(d): d for d in globals_}
        dependencies = {}
        for decl in globals_:
            edges = []
            found = set()
            stack = [decl.value] if decl.value else []
            while stack:
                expr = stack.pop()
                if expr.kind == NodeKind.IDENTIFIER:
                    symbol = self.symbols.lookup(expr.name)
                    key = id(symbol.node) if symbol else None
                    if key in declarations and key not in found:
                        edges.append(key)
                        found.add(key)
                for value in vars(expr).values():
                    if isinstance(value, ASTNode):
                        stack.append(value)
                    elif isinstance(value, list):
                        stack.extend(child for child in value if isinstance(child, ASTNode))
            dependencies[id(decl)] = edges
        state = {}
        ordered = []
        for root in globals_:
            if state.get(id(root)) == 2:
                continue
            active = []
            positions = {}
            work = [(id(root), False)]
            while work:
                key, ready = work.pop()
                if ready:
                    active.pop()
                    positions.pop(key, None)
                    state[key] = 2
                    ordered.append(declarations[key])
                    continue
                if state.get(key) == 2:
                    continue
                if state.get(key) == 1:
                    chain = active[positions[key]:] + [key]
                    links = [declarations[k].name for k in chain]
                    if len(links) > 32:
                        links = links[:16] + ['...'] + links[-16:]
                    self.add_error('Global value dependency cycle: ' + ' -> '.join(links), declarations[key].span)
                    return
                state[key] = 1
                positions[key] = len(active)
                active.append(key)
                work.append((key, True))
                work.extend((child, False) for child in reversed(dependencies[key]))
        # Exact constants can supply lengths in signatures and aggregate types.
        for decl in ordered:
            if decl.kind == NodeKind.CONST and not decl.explicit_type:
                exact = self._evaluate_exact(decl.value, self.symbols.lookup, self.exact_bindings)
                if exact is not None:
                    self.exact_bindings[id(decl)] = exact
                    decl.untyped_binding = True
        # Type names first, then fields: a field may name a type declared
        # later in the file, or the type that holds it (through `ref`).
        type_decls = [
            decl for decl in node.declarations or []
            if decl.kind in {NodeKind.STRUCT, NodeKind.ENUM, NodeKind.UNION, NodeKind.TYPE_ALIAS}
        ]
        for decl in type_decls:
            if decl.kind == NodeKind.ENUM:
                self.register_enum_type(decl)
            elif decl.kind in {NodeKind.STRUCT, NodeKind.UNION}:
                self._declare_record_shell(decl)
        for decl in type_decls:
            if decl.kind != NodeKind.ENUM:
                self.register_type_decl(decl)
        self._report_by_value_type_cycles(type_decls)

        # Second pass: register function signatures (for mutual recursion support)
        for decl in node.declarations or []:
            if decl.kind == NodeKind.FUNCTION:
                self.register_function_signature(decl)

        for decl in ordered:
            self.visit_declaration(decl)
        for decl in node.declarations or []:
            if decl.kind not in {NodeKind.CONST, NodeKind.VAR}:
                self.visit_declaration(decl)
        root_stack = self.symbols.scope_stack
        while self._nested_functions:
            function, scope_stack = self._nested_functions.popleft()
            self.symbols.scope_stack = list(scope_stack)
            self.symbols.current_scope = scope_stack[-1]
            self.visit_function_decl(function)
        self.symbols.scope_stack = root_stack
        self.symbols.current_scope = root_stack[-1]

    def _declare_record_shell(self, node: ASTNode) -> None:
        """Give a struct or union symbol its type object before any field resolves.

        Field resolution later fills this same object, so every reference
        taken in between (a forward or self reference) sees the fields.
        """
        symbol = self.symbols.lookup(node.name or "")
        if symbol is None or symbol.node is not node:
            return
        generic_params = tuple(gp.name for gp in (node.generic_params or []) if gp.name)
        if node.kind == NodeKind.STRUCT:
            symbol.type = StructType(name=node.name, fields=(), generic_params=generic_params)
        else:
            symbol.type = UnionType(name=node.name, fields=(), generic_params=generic_params)

    def _fill_record_shell(self, node: ASTNode, record: Type) -> Type:
        """Move a resolved record's fields into its shell and return the shell."""
        symbol = self.symbols.lookup(node.name or "")
        if symbol is None:
            return record
        shell = symbol.type
        if symbol.node is node and type(shell) is type(record) and shell is not record:
            object.__setattr__(shell, 'fields', record.fields)
            object.__setattr__(shell, 'generic_params', record.generic_params)
            return shell
        symbol.type = record
        return record

    def _by_value_members(self, type_: Type) -> List[Type]:
        """Named record types stored inline in type_, without following ref or slice."""
        found: List[Type] = []
        stack = [type_]
        while stack:
            current = stack.pop()
            if isinstance(current, ArrayType):
                stack.append(current.element_type)
            elif isinstance(current, StructType) and not current.name:
                stack.extend(field.field_type for field in current.fields)
            elif isinstance(current, (StructType, UnionType, GenericInstanceType)):
                found.append(current)
        return found

    def _report_by_value_type_cycles(self, type_decls: List[ASTNode]) -> None:
        """Reject a struct or union that stores itself inline: it has no finite size."""
        reported: Set[frozenset] = set()
        finished: Set[str] = set()
        for decl in type_decls:
            if decl.kind not in {NodeKind.STRUCT, NodeKind.UNION}:
                continue
            symbol = self.symbols.lookup(decl.name or "")
            if symbol is None or symbol.node is not decl or not isinstance(symbol.type, (StructType, UnionType)):
                continue
            path: List[str] = []
            on_path: Dict[str, int] = {}
            work: List[Tuple[Optional[Type], str]] = [(symbol.type, str(symbol.type.name))]
            expanded = 0
            while work:
                current, key = work.pop()
                if current is None:
                    on_path.pop(path.pop(), None)
                    finished.add(key)
                    continue
                if key in on_path:
                    cycle = path[on_path[key]:] + [key]
                    members = frozenset(cycle)
                    if members not in reported:
                        reported.add(members)
                        self.add_type_error(
                            TypeErrorType.INFINITE_SIZE_TYPE,
                            decl.span,
                            context=(
                                f"'{cycle[0]}' contains itself by value ({' -> '.join(cycle)}); "
                                f"store 'ref {cycle[0]}' instead"
                            ),
                        )
                    continue
                if key in finished:
                    continue
                expanded += 1
                if expanded > 1000:
                    self.add_type_error(
                        TypeErrorType.INFINITE_SIZE_TYPE,
                        decl.span,
                        context=f"'{decl.name}' expands to more than 1000 generic instances",
                    )
                    break
                concrete = current
                if isinstance(current, GenericInstanceType):
                    concrete = (self._resolve_generic_instance_struct(current)
                                or self._resolve_generic_instance_union(current))
                    if concrete is None:
                        finished.add(key)
                        continue
                on_path[key] = len(path)
                path.append(key)
                work.append((None, key))
                for field in concrete.fields:
                    for member in self._by_value_members(field.field_type):
                        work.append((member, str(member) if isinstance(member, GenericInstanceType) else str(member.name)))

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
        value_param_names = set(self._value_param_types_from_params(node.generic_params or []))
        self._generic_constraints = self._merge_where_constraints(node, None, value_param_names, f"function {func_name}", report=False)
        previous_value_params = self._active_value_params
        self._active_value_params = self._value_param_types_from_params(node.generic_params or [])
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
                    if isinstance(param_type, FunctionType):
                        self._bound_callback_values.add(id(param))

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
            self._active_value_params = previous_value_params

        # Update function symbol
        func_symbol = self.symbols.lookup(func_name)
        if func_symbol and func_type is not None:
            func_symbol.type = func_type

    # Constraint names that make $N a value parameter: usize for sizes, bool
    # for flags, and the fixed-width ints. Any other constraint (floats,
    # strings, aggregates, type sets) keeps the parameter a type parameter.
    VALUE_PARAM_KINDS = frozenset({
        'usize', 'bool',
        'u8', 'u16', 'u32', 'u64', 'i8', 'i16', 'i32', 'i64', 'isize',
    })

    def _value_param_types_from_params(self, generic_params: List[ASTNode]) -> Dict[str, str]:
        """Map declared $N names to their value kind.

        Only a declared primitive-kind constraint ($N: usize) makes a value
        parameter. A TypeSet constraint ($T: Numeric), another type, or no
        constraint keeps existing type-parameter behavior. Each value
        parameter's GENERIC_PARAM node gets `value_kind` (the kind name) for
        the backend.
        """
        value_kinds: Dict[str, str] = {}
        for param in generic_params or []:
            if param.kind != NodeKind.GENERIC_PARAM or not param.name:
                continue
            if param.name in value_kinds:
                continue
            kind_name = self._primitive_constraint_name(param.constraint)
            if kind_name is not None and kind_name in self.VALUE_PARAM_KINDS:
                value_kinds[param.name] = kind_name
                param.value_kind = kind_name
        return value_kinds

    def _primitive_constraint_name(self, constraint_node: Optional[ASTNode]) -> Optional[str]:
        """Name the primitive a generic constraint spells, if it spells one."""
        if constraint_node is None:
            return None
        if constraint_node.kind == NodeKind.TYPE_PRIMITIVE:
            return constraint_node.type_name or None
        if constraint_node.kind == NodeKind.TYPE_IDENTIFIER and not constraint_node.generic_params:
            name = constraint_node.name or constraint_node.type_name or ""
            if get_primitive_type(name) is not None:
                return name
        return None

    def _symbolic_array_size(self, size_node: Optional[ASTNode]) -> Optional[str]:
        """Name the in-scope value parameter sizing an array, if any.

        [$N]u8 with $N declared resolves to a symbolic length that the
        instantiation site substitutes. A bool $B cannot size an array;
        literals, constants, and type params keep the constant path below.
        """
        if size_node is None or size_node.kind != NodeKind.IDENTIFIER:
            return None
        name = size_node.name or ""
        kind = self._active_value_params.get(name)
        if kind is None:
            return None
        if kind == "bool":
            self.add_semantic_error(
                SemanticErrorType.CONSTRAINT_VIOLATION,
                size_node.span,
                context=f"Value parameter '${name}' is bool and cannot size an array",
            )
            return None
        return name

    def _value_arg_for_node(self, node: Optional[ASTNode]) -> Optional[Type]:
        """Fold a bare constant identifier to a GenericValueArg, if possible.

        Never calls resolve_type_node, so _resolve_type_leaf can call it
        without forming a call cycle.
        """
        if node is None or node.kind != NodeKind.TYPE_IDENTIFIER or node.generic_params:
            return None
        symbol = self.symbols.lookup(node.name or node.type_name or "")
        if symbol is None or symbol.kind != SymbolKind.CONSTANT or symbol.node is None:
            return None
        return self._extract_value_arg(symbol.node.value)

    def _resolve_type_or_value_arg(self, node: Optional[ASTNode]) -> Type:
        """Resolve one generic argument that may be a comptime value.

        Buf(SIZE) with SIZE :: 4 passes a value where Pair(i32) passes a
        type. Integer and bool constants become GenericValueArg; anything
        else keeps the type path, which still rejects non-types. Called
        only from struct/union instantiation sites, outside the
        resolve_type_node cluster, so the fallback adds no cycle.
        """
        value_arg = self._value_arg_for_node(node)
        if value_arg is not None:
            return value_arg
        return self.resolve_type_node(node)

    def _extract_value_arg(self, value_node: Optional[ASTNode]) -> Optional[Type]:
        """Fold a constant initializer to a GenericValueArg, if it is int or bool.

        Integers come from the exact evaluator, so `-1`, `2 + 2` and aliases
        fold the same way array lengths do. The exact evaluator has no bool
        values, so a bool literal is found by following constant aliases.
        """
        exact = self._evaluate_exact(value_node, self.symbols.lookup, self.exact_bindings)
        if exact is not None:
            value, floating = exact
            if floating or value.denominator != 1:
                return None
            return GenericValueArg(value=value.numerator)
        current = value_node
        seen: Set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            if current.kind == NodeKind.LITERAL:
                if current.literal_kind == LiteralKind.BOOLEAN:
                    return GenericValueArg(value=1 if current.literal_value else 0, is_bool=True)
                return None
            if current.kind != NodeKind.IDENTIFIER:
                return None
            symbol = self.symbols.lookup(current.name or "")
            if symbol is None or symbol.kind != SymbolKind.CONSTANT or symbol.node is None:
                return None
            current = symbol.node.value
        return None

    def _report_value_param_as_type(self, node: ASTNode, context: str) -> None:
        """Report one value-parameter-as-type misuse per type node."""
        if id(node) in self._reported_value_param_types:
            return
        self._reported_value_param_types.add(id(node))
        self.add_semantic_error(SemanticErrorType.CONSTRAINT_VIOLATION, node.span, context=context)

    def _check_generic_argument_kinds(
        self,
        owner_name: str,
        params: Tuple[str, ...],
        value_kinds: Dict[str, str],
        type_args: List[Type],
        span: Optional[SourceSpan],
    ) -> None:
        """Reject a value where $T takes a type and a wrong argument for $N.

        Parameters pair positionally with arguments. An unresolved argument
        was reported when it failed to resolve and is skipped here.
        """
        for param_name, concrete in zip(params, type_args):
            if isinstance(concrete, UnknownType):
                continue
            expected_kind = value_kinds.get(param_name)
            if expected_kind is not None:
                self._check_value_arg(param_name, owner_name, expected_kind, concrete, span)
            elif isinstance(concrete, GenericValueArg):
                self.add_semantic_error(
                    SemanticErrorType.CONSTRAINT_VIOLATION,
                    span,
                    context=(
                        f"Generic parameter '${param_name}' of {owner_name} takes a type, "
                        f"got value {concrete}"
                    ),
                )

    def _annotation_arguments_ok(self, node: ASTNode, type_name: str, type_args: List[Type]) -> bool:
        """Check `Name(args)` written as a type: argument count, then kinds.

        Returns False on a count mismatch, so the caller does not pair
        arguments with the wrong parameters. The result is kept per type
        node: a function signature resolves twice and reports once.
        """
        known = self._annotation_argument_results.get(id(node))
        if known is not None:
            return known
        symbol = self.symbols.lookup(type_name)
        if symbol is None:
            self.add_type_error(TypeErrorType.UNDEFINED_TYPE, node.span, context=f"Type '{type_name}'")
            self._annotation_argument_results[id(node)] = False
            return False
        if symbol.node is None or symbol.node.kind not in (NodeKind.STRUCT, NodeKind.UNION):
            return True
        # A declaration registered later in the file has no resolved type
        # yet; its declared parameter list gives the same order.
        if isinstance(symbol.type, (StructType, UnionType)):
            params = tuple(symbol.type.generic_params or ())
        else:
            params = tuple(gp.name for gp in (symbol.node.generic_params or []) if gp.name)
        ok = self._generic_argument_count_matches(type_name, params, type_args, node.span)
        if ok:
            value_kinds = self._value_param_types_from_params(symbol.node.generic_params or [])
            self._check_generic_argument_kinds(type_name, params, value_kinds, type_args, node.span)
        self._annotation_argument_results[id(node)] = ok
        return ok

    def _check_value_arg(
        self,
        param_name: str,
        owner_name: str,
        expected_kind: str,
        concrete: Type,
        span: Optional[SourceSpan],
    ) -> None:
        """Reject value arguments that miss the declared $N kind."""
        if not isinstance(concrete, GenericValueArg):
            self.add_semantic_error(
                SemanticErrorType.CONSTRAINT_VIOLATION,
                span,
                context=(
                    f"Value parameter '${param_name}' of {owner_name} requires "
                    f"a comptime {expected_kind}, got type {concrete}"
                ),
            )
            return
        if expected_kind == "bool":
            if not concrete.is_bool:
                self.add_semantic_error(
                    SemanticErrorType.CONSTRAINT_VIOLATION,
                    span,
                    context=(
                        f"Value parameter '${param_name}' of {owner_name} requires "
                        f"a comptime bool, got {concrete}"
                    ),
                )
            return
        if concrete.is_bool:
            self.add_semantic_error(
                SemanticErrorType.CONSTRAINT_VIOLATION,
                span,
                context=(
                    f"Value parameter '${param_name}' of {owner_name} requires "
                    f"a comptime {expected_kind}, got bool"
                ),
            )
            return
        low, high = INTEGER_RANGES[expected_kind]
        if not low <= concrete.value <= high:
            self.add_semantic_error(
                SemanticErrorType.CONSTRAINT_VIOLATION,
                span,
                context=(
                    f"Value parameter '${param_name}' of {owner_name} requires "
                    f"a comptime {expected_kind}, got {concrete} out of range"
                ),
            )

    def _generic_constraints_from_params(
        self,
        generic_params: List[ASTNode],
        problems: Optional[List[Tuple[Optional[SourceSpan], str]]] = None,
    ) -> Dict[str, TypeSet]:
        """Resolve declared generic parameter constraints by parameter name.

        A constraint that names no type set is added to `problems`; it is
        never dropped, which would let the parameter accept any type.
        """
        constraints: Dict[str, TypeSet] = {}
        for param in generic_params:
            if param.kind != NodeKind.GENERIC_PARAM or not param.name:
                continue
            found: List[str] = []
            resolved = self._resolve_generic_constraint_node(param.constraint, found)
            if resolved is not None:
                constraints[param.name] = resolved
            if problems is not None:
                problems.extend((param.constraint.span or param.span, f"Constraint of '${param.name}': {text}") for text in found)
        return constraints

    def _resolve_generic_constraint_node(
        self,
        constraint_node: Optional[ASTNode],
        problems: Optional[List[str]] = None,
    ) -> Optional[TypeSet]:
        """Resolve an inline, aliased or predefined type-set constraint.

        A `Name :: @type_set(...)` alias in scope wins over a predefined set
        of the same name. Returns None for no constraint, for a primitive
        that makes a value parameter, and for a name that is no type set
        (described in `problems`).
        """
        if constraint_node is None:
            return None
        if constraint_node.kind == NodeKind.TYPE_SET:
            return self._resolve_type_set_members(constraint_node, problems)
        name = getattr(constraint_node, 'type_name', None) or getattr(constraint_node, 'name', None) or ""
        if constraint_node.kind == NodeKind.TYPE_IDENTIFIER:
            symbol = self.symbols.lookup(name)
            if symbol and symbol.kind == SymbolKind.CONSTANT and symbol.node is not None:
                value = getattr(symbol.node, "value", None)
                if value is not None and value.kind == NodeKind.TYPE_SET:
                    # The alias declaration reports its own bad members.
                    return self._resolve_type_set_members(value, None)
        predefined = get_predefined_type_set(name) if name else None
        if predefined is not None:
            return predefined
        if self._primitive_constraint_name(constraint_node) is None and problems is not None:
            problems.append(
                f"'{name or constraint_node.kind.name.lower()}' is not a type set; use Numeric, Integer, "
                f"Float, Signed, Unsigned, an inline @type_set(...) or an alias of one"
            )
        return None

    def _resolve_type_set_members(self, node: ASTNode, problems: Optional[List[str]]) -> TypeSet:
        """Resolve the members of an `@type_set(...)` written as a constraint."""
        members: List[Type] = []
        for member in node.types or []:
            resolved: Optional[Type] = None
            name = getattr(member, 'type_name', None) or getattr(member, 'name', None) or ""
            if member.kind in (NodeKind.TYPE_PRIMITIVE, NodeKind.TYPE_IDENTIFIER) and not getattr(member, 'generic_params', None):
                resolved = get_primitive_type(name)
                if resolved is None:
                    symbol = self.symbols.lookup(name)
                    if (
                        symbol is not None
                        and symbol.kind in {SymbolKind.STRUCT, SymbolKind.ENUM, SymbolKind.UNION, SymbolKind.TYPE}
                        and not isinstance(symbol.type, UnknownType)
                    ):
                        resolved = symbol.type
            if resolved is not None:
                members.append(resolved)
            elif problems is not None:
                problems.append(f"@type_set member '{name or member.kind.name.lower()}' is not a known type")
        return TypeSet(types=frozenset(members))

    def _merge_where_constraints(
        self,
        node: ASTNode,
        known_names: Optional[Set[str]],
        value_names: Set[str],
        owner: str,
        report: bool = True,
    ) -> Dict[str, TypeSet]:
        """Fold a where-clause into per-param type-set constraints.

        Each bound reuses declared-constraint resolution. Malformed
        predicates arrive parser-marked; unknown, duplicate, value-param,
        and non-set bounds are rejected. Failures report only when report
        is set, so signature preregistration stays silent and visit
        reports once.
        """
        pending: List[Tuple[Optional[SourceSpan], str]] = []
        merged = self._generic_constraints_from_params(node.generic_params or [], pending)
        for entry in getattr(node, "where_clause", None) or []:
            name = entry.name or ""
            if not getattr(entry, "where_valid", True) or not name:
                pending.append((entry.span, "Unsupported where-clause bound; use 'Name: TypeSet' conjunctions only"))
                continue
            if name in merged:
                pending.append((entry.span, f"Duplicate constraint for generic parameter '${name}' of {owner}"))
                continue
            if name in value_names:
                pending.append((entry.span, f"Where-clause cannot constrain value parameter '${name}' of {owner}"))
                continue
            if known_names is not None and name not in known_names:
                pending.append((entry.span, f"Where-clause names unknown generic parameter '${name}' of {owner}"))
                continue
            resolved = self._resolve_generic_constraint_node(entry.constraint)
            if resolved is None:
                pending.append((entry.span, f"Where-clause bound for '${name}' of {owner} must be a type set"))
                continue
            merged[name] = resolved
        if report:
            for span, context in pending:
                self.add_semantic_error(SemanticErrorType.CONSTRAINT_VIOLATION, span, context=context)
        return merged

    def _validate_where_names(self, node: ASTNode, known_names: Set[str], owner: str) -> None:
        """Reject where-clause names that are not generic params of owner."""
        for entry in getattr(node, "where_clause", None) or []:
            name = entry.name or ""
            if not getattr(entry, "where_valid", True) or not name:
                continue
            if name not in known_names:
                self.add_semantic_error(
                    SemanticErrorType.CONSTRAINT_VIOLATION,
                    entry.span,
                    context=f"Where-clause names unknown generic parameter '${name}' of {owner}",
                )

    def register_struct_type(self, node: ASTNode) -> None:
        """Register a struct type."""
        struct_name = node.name or "<anonymous>"

        # Declared $N kinds are value params; record them for instantiation
        # checks and keep them in scope while resolving field sizes.
        value_param_types = self._value_param_types_from_params(node.generic_params or [])
        if value_param_types:
            self._struct_value_param_types[struct_name] = value_param_types
        previous_value_params = self._active_value_params
        self._active_value_params = value_param_types
        try:
            # Field types resolve here. A type declared later already has
            # its shell (see _declare_record_shell), so order does not matter.
            fields = []
            if node.fields:
                for field_node in node.fields:
                    if field_node.kind == NodeKind.FIELD:
                        field_name = field_node.name or "<unknown>"
                        # Resolve field type
                        field_type = self.resolve_type_node(field_node.field_type) if field_node.field_type else UNKNOWN
                        fields.append(StructField(name=field_name, field_type=field_type))
        finally:
            self._active_value_params = previous_value_params

        # Create struct type
        generic_params = tuple(gp.name for gp in (node.generic_params or []))
        if not generic_params:
            discovered: List[str] = []
            for field in fields:
                self._collect_generic_type_names(field.field_type, discovered)
            # Preserve encounter order while deduplicating
            generic_params = tuple(dict.fromkeys(discovered))
        struct_type = self._fill_record_shell(
            node, StructType(name=struct_name, fields=tuple(fields), generic_params=generic_params))

        # Struct generic parameters may declare constraints
        # ($T: Numeric). Function call sites validate theirs; struct
        # instantiation validates against this table.
        constraints = self._merge_where_constraints(node, set(generic_params), set(value_param_types), f"struct {struct_name}")
        if constraints:
            self._struct_generic_constraints[struct_name] = constraints

    def register_enum_type(self, node: ASTNode) -> None:
        """Register an enum type."""
        enum_name = node.name or "<anonymous>"

        # Create enum variants
        variants = []
        # A variant with no explicit value takes the previous value plus one,
        # so an explicit value can collide with an implicit one.
        taken: Dict[int, str] = {}
        next_value: Optional[int] = 0
        if node.variants:
            for variant_node in node.variants:
                if variant_node.kind == NodeKind.ENUM_VARIANT:
                    variant_name = variant_node.name or "<unknown>"
                    value = None
                    effective = next_value
                    if variant_node.value:
                        value = self._enum_tag_value(variant_node.value)
                        effective = value
                    variants.append(EnumVariant(name=variant_name, value=value))
                    if effective is not None:
                        if effective in taken:
                            self.add_semantic_error(
                                SemanticErrorType.DUPLICATE_ENUM_VALUE,
                                variant_node.span,
                                context=(
                                    f"'{variant_name}' and '{taken[effective]}' of enum "
                                    f"'{enum_name}' both have the value {effective}"
                                ),
                            )
                        else:
                            taken[effective] = variant_name
                    next_value = effective + 1 if effective is not None else None

        # Create enum type
        enum_type = EnumType(name=enum_name, variants=tuple(variants))

        # Update symbol
        symbol = self.symbols.lookup(enum_name)
        if symbol:
            symbol.type = enum_type

    def register_union_type(self, node: ASTNode) -> None:
        """Register a union type."""
        union_name = node.name or "<anonymous>"

        # Declared $N kinds mirror structs: value params in scope for sizes.
        value_param_types = self._value_param_types_from_params(node.generic_params or [])
        if value_param_types:
            self._union_value_param_types[union_name] = value_param_types
        previous_value_params = self._active_value_params
        self._active_value_params = value_param_types
        try:
            # Create union fields
            fields = []
            if node.fields:
                for field_node in node.fields:
                    if field_node.kind == NodeKind.FIELD:
                        field_name = field_node.name or "<unknown>"
                        field_type = self.resolve_type_node(field_node.field_type) if field_node.field_type else UNKNOWN
                        fields.append(UnionField(name=field_name, field_type=field_type))
        finally:
            self._active_value_params = previous_value_params

        # Generic parameters mirror structs: declared params first, else
        # $T names discovered in field encounter order.
        generic_params = tuple(gp.name for gp in (node.generic_params or []) if gp.name)
        if not generic_params:
            discovered: List[str] = []
            for field in fields:
                self._collect_generic_type_names(field.field_type, discovered)
            generic_params = tuple(dict.fromkeys(discovered))
        union_type = self._fill_record_shell(
            node, UnionType(name=union_name, fields=tuple(fields), generic_params=generic_params))

        constraints = self._merge_where_constraints(node, set(generic_params), set(value_param_types), f"union {union_name}")
        if constraints:
            self._union_generic_constraints[union_name] = constraints

    def _enum_tag_value(self, node: ASTNode) -> Optional[int]:
        """Fit an explicit enum value to a supported integer tag width."""
        exact = self._evaluate_exact(node, self.symbols.lookup, self.exact_bindings)
        if exact is None:
            return self.extract_int_value(node)
        node.exact_constant = exact
        target = next((kind for kind in (I32, U32, I64, U64)
                       if self._integer_literal_fits_type(exact[0].numerator, kind)),
                      I64 if exact[0] < 0 else U64)
        if not self._is_initializer_assignable_to(node, target, target, expression_span(node)):
            return None
        return exact[0].numerator

    def extract_int_value(self, node: ASTNode) -> Optional[int]:
        """Exact integer value of an expression, following typed constant aliases."""
        current = node
        seen: Set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            exact = self._evaluate_exact(current, self.symbols.lookup, self.exact_bindings)
            if exact is not None:
                return exact[0].numerator if exact[0].denominator == 1 else None
            if current.kind != NodeKind.IDENTIFIER:
                break
            symbol = self.symbols.lookup(current.name or "")
            if symbol is None or symbol.kind != SymbolKind.CONSTANT or symbol.node is None:
                break
            current = symbol.node.value
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
                size = 0
                if current.size is not None:
                    symbolic = self._symbolic_array_size(current.size)
                    if symbolic is not None:
                        wrappers.append(('array_param', symbolic))
                        current = current.element_type
                        continue
                    exact = self._evaluate_exact(current.size, self.symbols.lookup, self.exact_bindings)
                    if exact is not None:
                        current.size.exact_constant = exact
                        if self._fit_exact_usize(current.size, "Array length"):
                            size = exact[0].numerator
                        else:
                            size = None
                    else:
                        size = self.extract_int_value(current.size)
                        if size is None or not self._integer_literal_fits_type(size, USIZE):
                            self.add_error("Array length must be a compile-time integral value fitting usize", current.size.span)
                            size = None
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
            elif kind == 'array_param':
                result = ArrayType(element_type=result, size=None, size_param=data)
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
                type_args = []
                for arg in node.generic_params:
                    if (arg.kind == NodeKind.TYPE_GENERIC and not arg.type_name and not arg.type_args
                            and arg.name in self._active_value_params):
                        self._report_value_param_as_type(
                            arg,
                            f"Value parameter '${arg.name}' cannot be passed on as a generic "
                            f"argument of {type_name}; pass a named constant instead",
                        )
                        type_args.append(UNKNOWN)
                        continue
                    value_arg = self._value_arg_for_node(arg)
                    type_args.append(value_arg if value_arg is not None else self.resolve_type_node(arg))
                if not self._annotation_arguments_ok(node, type_name, type_args):
                    return UNKNOWN
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
                if node.name in self._active_value_params:
                    self._report_value_param_as_type(
                        node,
                        f"Value parameter '${node.name}' holds a comptime value, "
                        "not a type; value parameters may only size arrays",
                    )
                    return UNKNOWN
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
            error = SemanticError.from_type(SemanticErrorType.UNEXPECTED_NODE_KIND, span=node.span, filename=self.current_file, source_lines=self.source_lines, context=f"Unknown type node kind: {node.kind.name}")
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
        value_param_names = set(self._value_param_types_from_params(node.generic_params or []))
        self._generic_constraints = self._merge_where_constraints(node, None, value_param_names, f"function {func_name}")
        previous_value_params = self._active_value_params
        self._active_value_params = self._value_param_types_from_params(node.generic_params or [])

        # The signature registered before any body was checked already holds
        # the resolved types. Resolving them again would report each
        # signature error a second time.
        registered = self.symbols.lookup(func_name)
        signature: Optional[FunctionType] = None
        if (
            registered is not None
            and registered.node is node
            and isinstance(registered.type, FunctionType)
            and len(registered.type.param_types) == len(node.parameters or [])
        ):
            signature = registered.type

        try:
            # Enter function scope for parameter and body processing
            self._enter_matching_scope(f"function_{func_name}")

            # Resolve return type
            if signature is not None:
                return_type = signature.return_type
            else:
                return_type = self.resolve_type_node(node.return_type) if node.return_type else None

            # Resolve parameter types and update existing parameter symbols
            param_types = []
            if node.parameters:
                for position, param in enumerate(node.parameters):
                    if signature is not None:
                        param_type = signature.param_types[position]
                    else:
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
            if signature is not None:
                variadic_type = signature.variadic_type
            elif is_variadic and node.parameters:
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

            # Where-clause names must be generic params of this signature.
            known_names = [param.name for param in (node.generic_params or []) if param.name]
            for resolved in list(param_types) + ([return_type] if return_type is not None else []):
                self._collect_generic_type_names(resolved, known_names)
            self._validate_where_names(node, set(known_names), f"function {func_name}")

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
            self._active_value_params = previous_value_params

    def _without_own_symbol(self, decl_node: ASTNode, action):
        """Run action with the declaration's own symbol hidden.

        A declaration's initializer sees the outer binding: `y :: y + 1`
        inside a block reads the outer `y`, not the unfinished declaration.
        Hiding keeps exact evaluation from resolving the name to a symbol
        with no value yet, which used to leave a dangling bare name behind
        for an erased outer constant.
        """
        name = decl_node.name or ""
        target = None
        probe = self.symbols.current_scope
        while probe is not None:
            candidate = probe.symbols.get(name) if name else None
            if candidate is None:
                probe = probe.parent
                continue
            if getattr(candidate, "node", None) is decl_node:
                target = probe
            break
        if target is None:
            return action()
        hidden = target.symbols.pop(name)
        try:
            return action()
        finally:
            target.symbols[name] = hidden

    def visit_const_decl(self, node: ASTNode) -> None:
        """Visit a constant declaration."""
        const_name = node.name or "<unknown>"
        if getattr(node, 'untyped_binding', False):
            self.set_type(node, UNKNOWN)
            return
        # Name resolution walks statements but never match-expression arms,
        # so a const declared there has no symbol yet. Define it here the
        # way var declarations do.
        if node.name and self.symbols.current_scope.lookup_local(const_name) is None:
            self.symbols.define(Symbol(
                name=const_name,
                kind=SymbolKind.CONSTANT,
                type=UNKNOWN,
                node=node,
                is_mutable=False,
            ))
        if not node.explicit_type:
            exact = self._without_own_symbol(
                node,
                lambda: self._evaluate_exact(node.value, self.symbols.lookup, self.exact_bindings),
            )
            if exact is not None:
                self.exact_bindings[id(node)] = exact
                node.untyped_binding = True
                self.set_type(node, UNKNOWN)
                return

        # Type check the value
        value_type = UNKNOWN
        if node.value:
            value_type = self._without_own_symbol(
                node,
                lambda: self.visit_expression(node.value),
            )

        # If explicit type given, check compatibility
        if node.explicit_type:
            explicit_type = self.resolve_type_node(node.explicit_type)
            if not self._is_initializer_assignable_to(node.value, value_type, explicit_type, node.span):
                self._report_mismatch(
                    TypeErrorType.TYPE_MISMATCH, node.span, node.value, value_type, explicit_type,
                    context=f"Constant '{const_name}'",
                )
            value_type = explicit_type

        if node.value is not None and id(node.value) in self._bound_callback_values:
            self._bound_callback_values.add(id(node))
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

        # Type check the value if present. The initializer sees the outer
        # binding: `y := y + 2` reads the outer `y`, not the unfinished
        # declaration (same rule as const declarations).
        value_type = UNKNOWN
        if node.value:
            value_type = self._without_own_symbol(
                node,
                lambda: self.visit_expression(node.value),
            )

        # Determine final type
        if node.explicit_type:
            # Explicit type annotation
            explicit_type = self.resolve_type_node(node.explicit_type)

            generic_names: List[str] = []
            self._collect_generic_type_names(explicit_type, generic_names)
            if node.value is not None and generic_names and self.context.current_function is not None:
                self._generic_initializers.setdefault(id(self.context.current_function.node), []).append(
                    (node, value_type, explicit_type))

            # Check nil assignment to non-reference type
            if is_nil_value and self._has_unknown(explicit_type):
                pass  # The annotation already has its error.
            elif is_nil_value and not isinstance(explicit_type, ReferenceType):
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
                and not self._already_reported(node.value)
            ):
                # Generic locals may be initialized from literals before call-site substitution.
                is_generic_relaxed = (
                    isinstance(explicit_type, GenericParamType)
                    and (
                        isinstance(value_type, (GenericParamType, UnknownType))
                        or node.value.kind in {NodeKind.ARRAY_INIT, NodeKind.IF_EXPR, NodeKind.MATCH_EXPR}
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
                    self._report_mismatch(
                        TypeErrorType.TYPE_MISMATCH, node.span, node.value, value_type, explicit_type,
                        context=f"Variable '{var_name}'",
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
        elif node.value.kind == NodeKind.ARRAY_INIT and not node.value.elements:
            self.add_type_error(
                TypeErrorType.CANNOT_INFER_TYPE,
                node.span,
                context=(
                    f"Variable '{var_name}': an empty array literal has no element type; "
                    f"write one, as in '{var_name}: [0]i32 = []'"
                ),
            )
            value_type = UNKNOWN
        elif self._holds_nil(value_type):
            self.add_type_error(
                TypeErrorType.CANNOT_INFER_TYPE,
                node.span,
                context=(
                    f"Variable '{var_name}': nil has no type of its own; "
                    f"write the element type, as in '{var_name}: [2]ref T = [nil, nil]'"
                ),
            )
            value_type = UNKNOWN

        if not node.explicit_type and node.value:
            self._report_default_overflow(node.value)
        self.set_type(node, value_type)
        if node.value is not None and id(node.value) in self._bound_callback_values:
            self._bound_callback_values.add(id(node))
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

    def _finish_statement_region(self, region) -> None:
        kind, saved_facts = region
        if kind in ('block', 'facts'):
            self._nonnegative_vars = saved_facts
        if kind == 'for':
            self.context.exit_loop()
        if kind in ('block', 'for', 'scope'):
            self.symbols.exit_scope()

    def visit_statement(self, node: ASTNode) -> None:
        # Protected regions mirror the original finally/context-manager boundaries.
        # Ordinary continuations must not execute when a leaf raises.
        pending = [('visit', node)]
        protected = []
        try:
            while pending:
                action, nd = pending.pop()
                if action == 'finish':
                    protected.pop()
                    self._finish_statement_region(nd)
                    continue
                if action == 'sequence':
                    statements, learn = nd
                    stmt = next(statements, None)
                    if stmt is not None:
                        pending.append(('sequence', nd))
                        if learn:
                            pending.append(('learn', stmt))
                        pending.append(('visit', stmt))
                    continue
                if action == 'learn':
                    self._learn_fact_after_statement(nd)
                    continue
                if action == 'condition':
                    cond_type = self.visit_expression(nd)
                    if not cond_type.equals(BOOL) and not isinstance(cond_type, UnknownType):
                        self.add_type_error(TypeErrorType.CONDITION_NOT_BOOL, nd.span, expected_type="bool", got_type=str(cond_type))
                    continue
                if action == 'loop_exit':
                    self.context.exit_loop()
                    continue
                if action == 'for_in_exit':
                    self.context.exit_loop()
                    self.symbols.exit_scope()
                    continue
                if action == 'if_then':
                    if nd.else_stmt:
                        pending.append(('visit', nd.else_stmt))
                    if nd.then_stmt:
                        region = ('facts', set(self._nonnegative_vars))
                        self._nonnegative_vars.update(self._facts_from_positive_condition(nd.condition))
                        protected.append(region)
                        pending.extend([('finish', region), ('visit', nd.then_stmt)])
                    continue
                if action == 'while_body':
                    self.context.enter_loop()
                    pending.append(('loop_exit', None))
                    if nd.body:
                        pending.append(('visit', nd.body))
                    continue
                if action == 'match_next':
                    match, cases, state = nd
                    scrutinee_type = state["type"]
                    bool_coverage = state["bools"]
                    enum_coverage = state["enums"]
                    case = next(cases, None)
                    if case is not None:
                        self._validate_match_case_capture_shape(case.patterns or [], scrutinee_type)
                        for pattern in case.patterns or []:
                            pattern_kind, pattern_value = self._validate_match_pattern(pattern, scrutinee_type)
                            state["wildcard"] = self._check_match_pattern_redundancy(
                                pattern, pattern_kind, pattern_value, state["patterns"], state["ranges"],
                                state["wildcard"], self._match_full_coverage_reason(scrutinee_type, bool_coverage, enum_coverage),
                            )
                            if pattern_kind == "wildcard":
                                state["catch_all"] = True
                            elif pattern_kind == "bool":
                                bool_coverage.add(bool(pattern_value))
                            elif pattern_kind == "enum" and isinstance(pattern_value, str):
                                enum_coverage.add(pattern_value)
                        self._enter_matching_scope("match_case")
                        self._define_match_capture_symbols(case.patterns or [], scrutinee_type)
                        region = ('scope', None)
                        protected.append(region)
                        pending.extend([('match_next', nd), ('finish', region)])
                        case_stmt = getattr(case, "statement", None)
                        if case_stmt:
                            pending.append(('visit', case_stmt))
                        elif case.statements:
                            pending.append(('sequence', (iter(case.statements), False)))
                    else:
                        pending.append(('match_finish', (match, state)))
                        if match.else_case:
                            if state["wildcard"] is not None:
                                self.add_semantic_error(
                                    SemanticErrorType.UNREACHABLE_CODE,
                                    self._match_else_span(match.else_case) or match.span,
                                    context="match else branch is unreachable because a previous wildcard pattern covers all values",
                                )
                            elif full_coverage_reason := self._match_full_coverage_reason(scrutinee_type, bool_coverage, enum_coverage):
                                self.add_semantic_error(
                                    SemanticErrorType.UNREACHABLE_CODE,
                                    self._match_else_span(match.else_case) or match.span,
                                    context=f"match else branch is unreachable because previous cases cover all {full_coverage_reason} values",
                                )
                            self._enter_matching_scope("match_else")
                            region = ('scope', None)
                            protected.append(region)
                            pending.extend([('finish', region), ('sequence', (iter(match.else_case), False))])
                    continue
                if action == 'match_finish':
                    match, state = nd
                    self._check_match_exhaustiveness(
                        span=match.span, scrutinee_type=state["type"], has_catch_all=state["catch_all"],
                        bool_coverage=state["bools"], enum_coverage=state["enums"],
                    )
                    continue

                if nd.kind == NodeKind.BLOCK:
                    self._enter_matching_scope("block")
                    saved_facts = set(self._nonnegative_vars)
                    for stmt in nd.statements or []:
                        if stmt.kind == NodeKind.FUNCTION:
                            self.register_function_signature(stmt)
                    region = ('block', saved_facts)
                    protected.append(region)
                    pending.extend([('finish', region), ('sequence', (iter(nd.statements or []), True))])
                elif nd.kind == NodeKind.FUNCTION:
                    self._nested_functions.append((nd, tuple(self.symbols.scope_stack)))
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
                    pending.append(('if_then', nd))
                    if nd.condition:
                        pending.append(('condition', nd.condition))
                elif nd.kind == NodeKind.WHILE:
                    pending.append(('while_body', nd))
                    if nd.condition:
                        pending.append(('condition', nd.condition))
                elif nd.kind == NodeKind.FOR:
                    self._enter_matching_scope("for")
                    self.context.enter_loop()
                    region = ('for', None)
                    protected.append(region)
                    pending.append(('finish', region))
                    if nd.body:
                        pending.append(('visit', nd.body))
                    # The checker has always checked update before body.
                    if nd.update:
                        pending.append(('visit', nd.update))
                    if nd.condition:
                        pending.append(('condition', nd.condition))
                    if nd.init:
                        pending.append(('visit', nd.init))
                elif nd.kind in (NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED):
                    scope_name = "for_in_indexed" if nd.kind == NodeKind.FOR_IN_INDEXED else "for_in"
                    self._enter_matching_scope(scope_name)
                    iterable_type = self.visit_expression(nd.iterable) if nd.iterable else UNKNOWN
                    element_type = UNKNOWN
                    if isinstance(iterable_type, (ArrayType, SliceType)):
                        element_type = iterable_type.element_type
                    elif iterable_type.equals(STRING):
                        element_type = CHAR
                    elif not iterable_type.equals(UNKNOWN):
                        self.add_type_error(
                            TypeErrorType.REQUIRES_ARRAY_OR_SLICE,
                            nd.iterable.span if nd.iterable else nd.span,
                            got_type=str(iterable_type),
                            context="for-in requires an array, slice, or string iterable",
                        )
                    if nd.iterator:
                        iter_symbol = self.symbols.lookup(nd.iterator)
                        if iter_symbol:
                            iter_symbol.type = element_type
                    if nd.kind == NodeKind.FOR_IN_INDEXED and nd.index_var:
                        index_symbol = self.symbols.lookup(nd.index_var)
                        if index_symbol:
                            index_symbol.type = USIZE
                    self.context.enter_loop()
                    pending.append(('for_in_exit', None))
                    if nd.body:
                        pending.append(('visit', nd.body))
                elif nd.kind == NodeKind.MATCH:
                    scrutinee_type = self.visit_expression(nd.expression) if nd.expression else UNKNOWN
                    # Coverage and redundancy belong to this match's continuation.
                    state = {"type": scrutinee_type, "bools": set(), "enums": set(),
                             "patterns": {}, "ranges": [], "wildcard": None,
                             "catch_all": bool(nd.else_case)}
                    pending.append(('match_next', (nd, iter(nd.cases or []), state)))
                elif nd.kind == NodeKind.RETURN:
                    self.visit_return_stmt(nd)
                elif nd.kind == NodeKind.DEFER:
                    deferred_stmt = getattr(nd, "statement", None)
                    if deferred_stmt:
                        pending.append(('visit', deferred_stmt))
                    elif nd.expression:
                        self.visit_expression(nd.expression)
                elif nd.kind == NodeKind.DEL:
                    if nd.expression:
                        self.visit_expression(nd.expression)
        finally:
            while protected:
                self._finish_statement_region(protected.pop())

    def visit_assignment(self, node: ASTNode) -> None:
        """Visit an assignment statement."""
        # Type check both sides
        lhs_type = self.visit_expression(node.target) if node.target else UNKNOWN
        rhs_type = self.visit_expression(node.value) if node.value else UNKNOWN
        effective_lhs_type = lhs_type

        if (
            isinstance(lhs_type, ReferenceType)
            and not isinstance(rhs_type, (ReferenceType, NilType, UnknownType))
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

        # Mutability: the binding that stores the target must be writable.
        # A write through a reference lands in other storage and is exempt.
        if (
            node.target is not None
            and not isinstance(lhs_type, UnknownType)
            and not getattr(node, "implicit_deref_target", False)
        ):
            problem = self._immutable_root(node.target)
            if problem is not None:
                self.add_semantic_error(
                    SemanticErrorType.CANNOT_ASSIGN_TO_IMMUTABLE,
                    node.span,
                    context=problem,
                )
                return

        # Compound assignment operator type checking
        # Assignment nodes store the operator in `operator`, not `op`.
        op = getattr(node, "operator", None)
        if op and op != AssignOp.ASSIGN:
            arithmetic_ops = {AssignOp.ADD_ASSIGN, AssignOp.SUB_ASSIGN, AssignOp.MUL_ASSIGN, AssignOp.DIV_ASSIGN, AssignOp.MOD_ASSIGN}
            bool_bitwise_ops = {AssignOp.AND_ASSIGN, AssignOp.OR_ASSIGN, AssignOp.XOR_ASSIGN}
            shift_ops = {AssignOp.SHL_ASSIGN, AssignOp.SHR_ASSIGN}
            bitwise_ops = bool_bitwise_ops | shift_ops

            if op in arithmetic_ops or op in bitwise_ops:
                if op in arithmetic_ops:
                    error_type = TypeErrorType.REQUIRES_NUMERIC_TYPE
                    requirement = "numeric"
                else:
                    error_type = TypeErrorType.REQUIRES_INTEGER_TYPE
                    requirement = "integer"
                operands_ok = True
                for operand_type in (effective_lhs_type, rhs_type):
                    if isinstance(operand_type, UnknownType):
                        operands_ok = False
                        break
                    # Zig applies &, |, ^ to bool; those compound forms build
                    # today and stay accepted. `char` has no arithmetic: it
                    # takes cast(u8, c) first, the same as the binary operators.
                    if op in bool_bitwise_ops and operand_type.equals(BOOL):
                        continue
                    if op in arithmetic_ops:
                        operand_ok = self._is_numeric_compatible(operand_type)
                    else:
                        operand_ok = self._is_integral_compatible(operand_type)
                    if not operand_ok:
                        hint = self._operand_hint(operand_type, "Numeric" if op in arithmetic_ops else "Integer")
                        context = f"Operator {op.name} requires {requirement} type"
                        self.add_type_error(
                            error_type,
                            node.span,
                            got_type=str(operand_type),
                            context=f"{context}: {hint}" if hint else context,
                        )
                        operands_ok = False
                        break
                if not operands_ok:
                    return
                if op in shift_ops:
                    self._check_shift_count(node.value, effective_lhs_type, node.span)

        # Check assignment compatibility
        if not self._is_initializer_assignable_to(
            node.value,
            rhs_type,
            effective_lhs_type,
            node.span,
            context="Assignment",
        ):
            self._report_mismatch(
                TypeErrorType.ASSIGNMENT_TYPE_MISMATCH,
                node.span,
                node.value,
                rhs_type,
                effective_lhs_type,
            )
        elif (isinstance(lhs_type, FunctionType) and node.target is not None
              and node.target.kind == NodeKind.IDENTIFIER
              and id(node.value) in self._bound_callback_values):
            target = self.symbols.lookup(node.target.name or "")
            if target is not None:
                self._bound_callback_values.add(id(target.node))

    def visit_return_stmt(self, node: ASTNode) -> None:
        """Visit a return statement."""
        expected = self.context.get_function_return_type()
        # RETURN nodes use 'value' attribute, not 'expression'
        if node.value is None:
            if expected is not None:
                self.add_type_error(
                    TypeErrorType.RETURN_TYPE_MISMATCH,
                    node.span,
                    expected_type=str(expected),
                    context="'ret' has no value",
                )
        else:
            return_type = self.visit_expression(node.value)
            if expected is None:
                self.add_type_error(TypeErrorType.RETURN_TYPE_MISMATCH, node.span, expected_type="void", context="Cannot return value from void function")
            elif self._is_nil_literal(node.value) and not isinstance(expected, ReferenceType):
                if not self._has_unknown(expected):
                    self.add_type_error(
                        TypeErrorType.NIL_ONLY_FOR_REFERENCES,
                        node.value.span,
                        got_type=str(expected),
                        context="Return value",
                    )
            elif not self._is_initializer_assignable_to(node.value, return_type, expected, node.span, context="Return value"):
                self._report_mismatch(TypeErrorType.RETURN_TYPE_MISMATCH, node.span, node.value, return_type, expected)

        # Mark function as having return
        self.context.mark_function_returns()

    def visit_expression(self, node: ASTNode) -> Type:
        """
        Visit an expression and return its type.

        A chain through first operands (`a + b + c`, `p.x.y`, `a[0][1]`,
        `f()()`) is collected into a list and typed from its innermost link
        outward, so its length costs no Python stack. Every other operand is
        visited by its handler.

        Args:
            node: Expression node

        Returns:
            Type of the expression
        """
        chain = [node]
        current = node
        while not getattr(current, 'exact_failed', False) and getattr(current, 'exact_constant', None) is None:
            kind = current.kind
            if kind == NodeKind.BINARY:
                first = current.left
            elif kind in (NodeKind.FIELD_ACCESS, NodeKind.INDEX, NodeKind.SLICE):
                first = current.object
            elif kind == NodeKind.CALL and not getattr(current, "file_module_call", None):
                first = current.function
                # Module operations have backend lowering only at direct call
                # sites; the callee is typed before its call, so mark it here.
                if first is not None and first.kind == NodeKind.FIELD_ACCESS:
                    setattr(first, "direct_call_target", True)
            else:
                break
            if (
                first is None
                or first.kind not in _CHAIN_KINDS
                or getattr(first, 'exact_failed', False)
                or getattr(first, 'exact_constant', None) is not None
            ):
                break
            chain.append(first)
            current = first

        # `pending` is the exact value of the link below, not yet written to
        # its node: the link above absorbs it when the two fold together, the
        # way one evaluation of the whole constant would.
        pending = None
        first_type: Optional[Type] = None
        index = len(chain) - 1
        while index >= 0:
            current = chain[index]
            first = chain[index + 1] if index + 1 < len(chain) else None
            index -= 1
            if getattr(current, 'exact_failed', False):
                self.set_type(current, UNKNOWN)
                first_type, pending = UNKNOWN, None
                continue
            if current.kind == NodeKind.BINARY and current.operator in _COMPARISON_OPS:
                left = pending if first is not None else self._evaluate_exact(current.left, self.symbols.lookup, self.exact_bindings)
                right = self._evaluate_exact(current.right, self.symbols.lookup, self.exact_bindings)
                if left is not None and right is not None:
                    current.literal_value = compare(current.operator, left, right)
                    current.kind = NodeKind.LITERAL
                    current.literal_kind = LiteralKind.BOOLEAN
                    current.raw_text = 'true' if current.literal_value else 'false'
                    current.exact_materialized = True
                    current.left = current.right = None
                    first, pending = None, None
            exact = None
            if current.kind == NodeKind.BINARY and current.operator in _FOLDABLE_OPS:
                # A link below that is not constant makes this one not constant.
                if first is None or pending is not None:
                    lent = pending is not None
                    if lent:
                        # Lend the link below its value for this one evaluation.
                        first.exact_constant = pending
                    try:
                        exact = evaluate(current, self.symbols.lookup, self.exact_bindings)
                    except ExactArithmeticError as error:
                        # Report at the outermost link this constant reaches.
                        while index >= 0 and chain[index].kind == NodeKind.BINARY and chain[index].operator in _FOLDABLE_OPS:
                            index -= 1
                        outermost = chain[index + 1]
                        outermost.exact_failed = True
                        self.add_error(str(error), expression_span(outermost))
                        self.set_type(outermost, UNKNOWN)
                        first_type, pending = UNKNOWN, None
                        continue
                    finally:
                        if lent:
                            first.exact_constant = None
            elif first is None:
                exact = self._evaluate_exact(current, self.symbols.lookup, self.exact_bindings)
            if exact is not None:
                pending = exact
                continue
            if getattr(current, 'exact_failed', False):
                # The evaluator already reported this constant.
                self.set_type(current, UNKNOWN)
                first_type, pending = UNKNOWN, None
                continue
            if pending is not None:
                first.exact_constant = pending
                first.span = expression_span(first)
                first_type = F64 if pending[1] else I32
                self.set_type(first, first_type)
                pending = None
            first_type = self._visit_expression_impl(current, first_type if first is not None else None)
            self.set_type(current, first_type)
        if pending is not None:
            node.exact_constant = pending
            node.span = expression_span(node)
            first_type = F64 if pending[1] else I32
            self.set_type(node, first_type)
        return first_type

    def _visit_expression_impl(self, node: ASTNode, first_type: Optional[Type] = None) -> Type:
        """Type one expression node. `first_type` is its first operand's type when already known."""
        if node.kind == NodeKind.LITERAL:
            return self.visit_literal(node)
        elif node.kind == NodeKind.IDENTIFIER:
            return self.visit_identifier(node)
        elif node.kind == NodeKind.BINARY:
            return self.visit_binary_expr(node, first_type)
        elif node.kind == NodeKind.UNARY:
            return self.visit_unary_expr(node)
        elif node.kind == NodeKind.CALL:
            return self.visit_call_expr(node, first_type)
        elif node.kind == NodeKind.INDEX:
            return self.visit_index_expr(node, first_type)
        elif node.kind == NodeKind.SLICE:
            return self.visit_slice_expr(node, first_type)
        elif node.kind == NodeKind.FIELD_ACCESS:
            return self.visit_field_access(node, first_type)
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
            error = SemanticError.from_type(SemanticErrorType.UNEXPECTED_NODE_KIND, span=node.span, filename=self.current_file, source_lines=self.source_lines, context=f"Unknown expression kind: {node.kind.name}")
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
            return NIL
        return UNKNOWN

    def visit_identifier(self, node: ASTNode) -> Type:
        """Visit an identifier expression."""
        ident_name = node.name or ""
        symbol = self.symbols.lookup(ident_name)

        if symbol is None:
            self.add_semantic_error(SemanticErrorType.UNDEFINED_IDENTIFIER, node.span, context=f"'{ident_name}'")
            return UNKNOWN
        self.symbols.mark_used(ident_name)
        # A module alias or a type name is no value. `io.println` and
        # `Color.Red` reach it as the object of a member access, which
        # marks the node first.
        if not getattr(node, "member_object", False):
            if symbol.kind == SymbolKind.MODULE:
                self.add_type_error(
                    TypeErrorType.TYPE_USED_AS_VALUE,
                    node.span,
                    context=f"'{ident_name}' is a module alias; call one of its functions, as in '{ident_name}.name(...)'",
                )
                return UNKNOWN
            if symbol.kind in {SymbolKind.STRUCT, SymbolKind.ENUM, SymbolKind.UNION}:
                self.add_type_error(
                    TypeErrorType.TYPE_USED_AS_VALUE,
                    node.span,
                    context=f"'{ident_name}' is a type",
                )
                return UNKNOWN
        if id(symbol.node) in self._bound_callback_values:
            self._bound_callback_values.add(id(node))
        return symbol.type

    def visit_binary_expr(self, node: ASTNode, left_type: Optional[Type] = None) -> Type:
        """Visit a binary expression."""
        if left_type is None:
            left_type = self.visit_expression(node.left) if node.left else UNKNOWN
        right_type = self.visit_expression(node.right) if node.right else UNKNOWN

        op = node.operator
        if isinstance(left_type, UnknownType) or isinstance(right_type, UnknownType):
            # An operand already has its error; this operator adds none, and
            # a constant beside it is not held to the i32 default.
            self._silence_constants(node.left)
            self._silence_constants(node.right)
            return BOOL if op in _COMPARISON_OPS or op in {BinaryOp.AND, BinaryOp.OR} else UNKNOWN
        left_exact = getattr(node.left, 'exact_constant', None)
        right_exact = getattr(node.right, 'exact_constant', None)
        numeric_ops = {BinaryOp.ADD, BinaryOp.SUB, BinaryOp.MUL, BinaryOp.DIV, BinaryOp.MOD,
                       BinaryOp.EQ, BinaryOp.NE, BinaryOp.LT, BinaryOp.LE, BinaryOp.GT, BinaryOp.GE,
                       BinaryOp.BIT_AND, BinaryOp.BIT_OR, BinaryOp.BIT_XOR}
        if op in numeric_ops and (left_exact is None) != (right_exact is None):
            constant = node.left if left_exact is not None else node.right
            concrete = right_type if left_exact is not None else left_type
            if isinstance(concrete, PrimitiveType) and concrete.is_numeric():
                self._is_initializer_assignable_to(constant, self.get_type(constant), concrete, constant.span)
                if left_exact is not None:
                    left_type = concrete
                else:
                    right_type = concrete
        if op in {BinaryOp.BIT_SHL, BinaryOp.BIT_SHR}:
            if left_exact is not None:
                self._is_initializer_assignable_to(node.left, left_type, left_type, node.left.span)
            if right_exact is not None:
                self._is_initializer_assignable_to(node.right, right_type, right_type, node.right.span)

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
            for operand_type in (left_type, right_type):
                if not self._is_numeric_compatible(operand_type):
                    self.add_type_error(
                        TypeErrorType.REQUIRES_NUMERIC_TYPE,
                        node.span,
                        got_type=str(operand_type),
                        context=self._operand_hint(operand_type, "Numeric"),
                    )
                    return UNKNOWN
            # Preserve generic parameters for body type-checking before monomorphization.
            if isinstance(left_type, GenericParamType):
                return left_type
            if isinstance(right_type, GenericParamType):
                return right_type
            # A literal takes its peer's type when representable. Otherwise use
            # existing safe widening rules so recorded types match native values.
            if isinstance(right_type, PrimitiveType) and self._integer_literal_value(node.left) is not None:
                if self._integer_literal_fits_type(self._integer_literal_value(node.left), right_type):
                    return right_type
            if isinstance(left_type, PrimitiveType) and self._integer_literal_value(node.right) is not None:
                if self._integer_literal_fits_type(self._integer_literal_value(node.right), left_type):
                    return left_type
            if self._is_float_literal(node.left) and right_type.is_floating():
                return right_type
            if self._is_float_literal(node.right) and left_type.is_floating():
                return left_type
            if left_type.is_assignable_to(right_type):
                return right_type
            if right_type.is_assignable_to(left_type):
                return left_type
            self.add_type_error(
                TypeErrorType.OPERATOR_TYPE_MISMATCH, node.span,
                context=f"{op.name.lower()} between {left_type} and {right_type}; use an explicit cast",
            )
            return UNKNOWN

        # Comparison operators: ==, !=, <, <=, >, >=
        elif op in _COMPARISON_OPS:
            problem = self._comparison_problem(left_type, right_type, ordering=op not in {BinaryOp.EQ, BinaryOp.NE})
            if problem is not None:
                self.add_type_error(
                    TypeErrorType.OPERATOR_TYPE_MISMATCH,
                    node.span,
                    context=f"{op.name.lower()} between {left_type} and {right_type}: {problem}",
                )
            return BOOL

        # Logical operators: and, or
        elif op in {BinaryOp.AND, BinaryOp.OR}:
            if not left_type.equals(BOOL) or not right_type.equals(BOOL):
                self.add_type_error(TypeErrorType.REQUIRES_BOOL_TYPE, node.span)
            return BOOL

        # Bitwise operators: &, |, ^, <<, >>
        elif op in {BinaryOp.BIT_AND, BinaryOp.BIT_OR, BinaryOp.BIT_XOR, BinaryOp.BIT_SHL, BinaryOp.BIT_SHR}:
            for operand_type in (left_type, right_type):
                if not self._is_integral_compatible(operand_type):
                    self.add_type_error(
                        TypeErrorType.REQUIRES_INTEGER_TYPE,
                        self._node_span(node),
                        got_type=str(operand_type),
                        context=self._operand_hint(operand_type, "Integer"),
                    )
                    return UNKNOWN
            if op in {BinaryOp.BIT_SHL, BinaryOp.BIT_SHR}:
                self._check_shift_count(node.right, left_type, self._node_span(node))
            elif isinstance(left_type, GenericParamType) and right_exact is not None:
                return left_type  # The constant takes the instantiated type.
            elif isinstance(right_type, GenericParamType) and left_exact is not None:
                return right_type
            elif self._is_complemented_constant(node.right):
                return left_type  # `flags & ~1`: the mask takes the type of `flags`.
            elif self._is_complemented_constant(node.left):
                return right_type
            elif not left_type.equals(right_type):
                # A constant operand was fitted to its peer above, so two
                # different types here are two typed operands.
                self.add_type_error(
                    TypeErrorType.OPERATOR_TYPE_MISMATCH,
                    self._node_span(node),
                    context=(
                        f"{op.name.lower()} between {left_type} and {right_type}: both operands "
                        f"need the same integer type; use an explicit cast"
                    ),
                )
                return UNKNOWN
            return left_type

        return UNKNOWN

    def _is_complemented_constant(self, node: Optional[ASTNode]) -> bool:
        """True for `~c` (any number of `~`) over an untyped integer constant."""
        complemented = False
        while node is not None and node.kind == NodeKind.UNARY and node.operator == UnaryOp.BIT_NOT:
            complemented = True
            node = node.operand
        return complemented and getattr(node, 'exact_constant', None) is not None

    def _check_shift_count(self, count_node: Optional[ASTNode], shifted_type: Type, span: Optional[SourceSpan]) -> None:
        """Reject a constant shift count outside the shifted operand's width.

        A shift of two constants folds exactly before this point, so the
        shifted operand here always has a declared width.
        """
        exact = getattr(count_node, 'exact_constant', None)
        amount = self._integer_literal_value(count_node)
        if amount is None and exact is not None and exact[0].denominator == 1:
            amount = exact[0].numerator
        if amount is None:
            return
        width = INTEGER_BIT_WIDTHS.get(getattr(shifted_type, 'name', ''))
        if amount < 0 or (width is not None and amount >= width):
            self.add_type_error(TypeErrorType.OPERATOR_TYPE_MISMATCH, span,
                                context=f"Shift count must be non-negative and less than {width}")

    def _operand_hint(self, operand_type: Type, type_set: str) -> Optional[str]:
        """Name the fix for an operand an operator cannot take."""
        if isinstance(operand_type, GenericParamType):
            if operand_type.constraint is None:
                return (
                    f"'${operand_type.name}' has no constraint, so it may be any type; "
                    f"declare it as '${operand_type.name}: {type_set}'"
                )
            return f"the constraint of '${operand_type.name}' admits types this operator cannot take"
        if operand_type.equals(CHAR):
            return "char is not a number; convert with cast(u8, c)"
        return None

    def _comparison_problem(self, left: Type, right: Type, *, ordering: bool) -> Optional[str]:
        """Say why two operand types cannot be compared, or None when they can.

        The backend compares numbers, bool, char, strings, enums, references
        and nil. Records, arrays, slices and functions have no comparison.
        """
        if isinstance(left, NilType) or isinstance(right, NilType):
            other = right if isinstance(left, NilType) else left
            if ordering:
                return "nil has no order"
            if isinstance(other, (ReferenceType, NilType)):
                return None
            return f"only a 'ref' value can be nil, and '{other}' is not a reference"
        for side in (left, right):
            if isinstance(side, GenericParamType) and not self._is_numeric_compatible(side):
                if side.constraint is None:
                    return (
                        f"'${side.name}' has no constraint, so it may be a type with no comparison; "
                        f"declare it as '${side.name}: Numeric'"
                    )
                return f"the constraint of '${side.name}' admits types with no comparison"
        if self._is_numeric_compatible(left) and self._is_numeric_compatible(right):
            return None
        if not left.equals(right):
            return "the operands have different types"
        if left.equals(CHAR):
            return None
        if ordering:
            return f"'{left}' has no order; only numbers and char compare with <, <=, > and >="
        if left.equals(BOOL) or left.equals(STRING) or isinstance(left, (EnumType, ReferenceType, PointerType)):
            return None
        return f"'{left}' values have no == or !=; compare their fields or elements"

    def _node_span(self, node: ASTNode) -> Optional[SourceSpan]:
        """A node's own span, or the first source operand when it has none.

        Operator nodes synthesised by the preprocessor carry no parser span, and
        `add_type_error` stores None in the JSON payload when that happens. A
        diagnostic with no location is unusable in a compiler whose whole
        contract is a located cause, so fall back to the nearest real span.
        """
        span = getattr(node, 'span', None)
        if span is not None:
            return span
        return expression_span(node)

    def visit_unary_expr(self, node: ASTNode) -> Type:
        """Visit a unary expression."""
        operand_type = self.visit_expression(node.operand) if node.operand else UNKNOWN

        op = node.operator
        if isinstance(operand_type, UnknownType):
            # The operand already has its error.
            return BOOL if op == UnaryOp.NOT else UNKNOWN

        if op == UnaryOp.NEG:
            if isinstance(operand_type, PrimitiveType) and operand_type.name in {'u8', 'u16', 'u32', 'u64', 'usize'}:
                self.add_type_error(TypeErrorType.OPERATOR_TYPE_MISMATCH, node.span,
                                    context=f"Cannot negate unsigned type '{operand_type}'; cast to a signed type first")
                return UNKNOWN
            if not self._is_numeric_compatible(operand_type):
                self.add_type_error(TypeErrorType.REQUIRES_NUMERIC_TYPE, node.span, got_type=str(operand_type),
                                    context=self._operand_hint(operand_type, "Numeric"))
                return UNKNOWN
            return operand_type

        elif op == UnaryOp.NOT:
            if not operand_type.equals(BOOL):
                self.add_type_error(TypeErrorType.REQUIRES_BOOL_TYPE, node.span)
            return BOOL

        elif op == UnaryOp.BIT_NOT:
            if not self._is_integral_compatible(operand_type):
                self.add_type_error(TypeErrorType.REQUIRES_INTEGER_TYPE, node.span, got_type=str(operand_type),
                                    context=self._operand_hint(operand_type, "Integer"))
                return UNKNOWN
            return operand_type

        return UNKNOWN

    def visit_call_expr(self, node: ASTNode, callee_type: Optional[Type] = None) -> Type:
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

        # A bare call that resolves to a function merged in from an imported
        # module is missing its alias: the declaration is emitted with the
        # module prefix while the call site would emit the plain name, which
        # Zig rejects. Reject here with the qualified spelling. Scoped lookup
        # keeps this quiet when a local shadows the name, and pre-marked
        # sibling calls inside modules never reach this branch.
        if (
            callee is not None
            and callee.kind == NodeKind.IDENTIFIER
            and not getattr(node, "file_module_call", None)
            and not getattr(node, "locally_bound_call", None)
            and callee.name
            and not callee.name.startswith("@")
        ):
            scoped = self.symbols.lookup(callee.name)
            if (
                scoped is not None
                and isinstance(scoped.type, FunctionType)
                and getattr(getattr(scoped, "node", None), "module_emit_prefix", "")
            ):
                prefix = getattr(scoped.node, "module_emit_prefix", "")
                alias = (self.module_prefix_aliases or {}).get(prefix)
                if alias:
                    context = (
                        f"'{callee.name}' is defined in the module imported "
                        f"as '{alias}'; write '{alias}.{callee.name}()'"
                    )
                else:
                    context = (
                        f"'{callee.name}' is defined in an imported module; "
                        f"call it through the module alias"
                    )
                self.add_semantic_error(
                    SemanticErrorType.UNDEFINED_IDENTIFIER,
                    callee.span or node.span,
                    context=context,
                )
                return UNKNOWN

        # Module operations have backend lowering only at direct call sites.
        if node.function and node.function.kind == NodeKind.FIELD_ACCESS:
            setattr(node.function, "direct_call_target", True)
        # File-module alias calls (h.f() and bare sibling calls inside the
        # module) resolve against the merged program's global scope, so a
        # missing callee is rejected here, generic inference runs like any
        # direct call, and a local sharing the callee's plain name cannot
        # capture the lookup.
        alias_func_type = None
        if getattr(node, "file_module_call", None) and node.function:
            if node.function.kind == NodeKind.IDENTIFIER:
                callee_name = node.function.name
            else:
                callee_name = node.function.field or ""
            callee_symbol = self.symbols.get_global_scope().lookup_local(callee_name)
            if callee_symbol and isinstance(callee_symbol.type, FunctionType):
                alias_func_type = callee_symbol.type
        func_type = alias_func_type or callee_type or (self.visit_expression(node.function) if node.function else UNKNOWN)
        callee_declaration = None
        if alias_func_type is not None:
            callee_declaration = callee_symbol.node
        elif node.function is not None and node.function.kind == NodeKind.IDENTIFIER:
            resolved = self.symbols.lookup(node.function.name or "")
            if resolved is not None and resolved.kind == SymbolKind.FUNCTION:
                callee_declaration = resolved.node
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
                            module_name = getattr(node.function.object, 'name', '') or ''
                            field_name = node.function.field or ''
                            self.add_type_error(
                                TypeErrorType.NOT_CALLABLE,
                                node.function.span if node.function else node.span,
                                context=(
                                    f"Cannot call '{module_name}.{field_name}' "
                                    "(not defined in the imported module)"
                                ),
                            )
                            return UNKNOWN
                        return self._visit_stdlib_module_call(node, obj_symbol)

            # Use the span of the function being called, not the whole call expression
            error_span = node.function.span if node.function else node.span

            if isinstance(func_type, UnknownType) or getattr(node.function, 'diagnosed', False):
                # The callee was already reported with a message that names the
                # problem. Reporting "not callable" as well would give one
                # mistake two located causes.
                return UNKNOWN
            self.add_type_error(TypeErrorType.NOT_CALLABLE, error_span, got_type=str(func_type))
            return UNKNOWN

        # Type check arguments
        arg_types = []
        if node.arguments:
            for arg in node.arguments:
                arg_types.append(self.visit_expression(arg))

        # Check for generic type inference
        errors_before_inference = len(self.errors)
        bound_callback = id(node.function) in self._bound_callback_values
        generic_mapping = {} if bound_callback else self._infer_generic_types(
            func_type, arg_types, node.arguments or [], node.span)
        # Backend lowering can use this semantic annotation to monomorphize
        # concrete generic calls without re-running type inference.
        if generic_mapping:
            node.generic_mapping = generic_mapping
        # A declaration needs argument evidence for each generic parameter.
        # A callback signature already uses its enclosing function's bindings.
        if not bound_callback:
            self._check_generic_constraints(func_type, generic_mapping, node.span)
        # Substitute generic types in param_types for type checking
        resolved_param_types = [self._substitute_generic(pt, generic_mapping) for pt in func_type.param_types]
        inference_failed = len(self.errors) > errors_before_inference

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
            argument = node.arguments[i]
            if isinstance(param_type, UnknownType) or isinstance(arg_type, UnknownType):
                continue  # Untyped variadic parameter, or an argument that already has its error
            bound_names: List[str] = []
            owner = self.context.current_function
            if bound_callback:
                self._collect_generic_type_names(param_type, bound_names)
                self._collect_generic_type_names(arg_type, bound_names)
            elif isinstance(param_type, GenericParamType):
                continue  # Skip generic params that weren't resolved
            defer_callback_argument = bool(bound_names) and owner is not None
            if inference_failed:
                declared_names: List[str] = []
                self._collect_generic_type_names(func_type.param_types[i], declared_names)
                if declared_names:
                    continue  # The failed inference is this argument's error.
            if not defer_callback_argument and self._is_nil_literal(argument) and not isinstance(param_type, ReferenceType):
                self.add_type_error(
                    TypeErrorType.NIL_ONLY_FOR_REFERENCES,
                    argument.span,
                    got_type=str(param_type),
                    context=f"Argument {i+1}",
                )
                continue
            if (
                isinstance(param_type, ReferenceType)
                and not isinstance(arg_type, (ReferenceType, NilType))
                and self._is_lvalue_expression(argument)
            ):
                # A variable passed to `ref T` is passed by address, so its
                # type is T itself (no widening) and it must be writable.
                referent = param_type.referent_type
                unresolved: List[str] = []
                self._collect_generic_type_names(referent, unresolved)
                if not unresolved and not self._has_unknown(referent) and not arg_type.equals(referent):
                    self.add_type_error(
                        TypeErrorType.ARGUMENT_TYPE_MISMATCH,
                        argument.span,
                        expected_type=str(param_type),
                        got_type=str(arg_type),
                        context=(
                            f"Argument {i+1}: a '{param_type}' parameter takes a variable "
                            f"of type '{referent}', not one that converts to it"
                        ),
                    )
                    continue
                problem = self._immutable_root(argument)
                if problem is not None:
                    self.add_semantic_error(
                        SemanticErrorType.CANNOT_ASSIGN_TO_IMMUTABLE,
                        argument.span,
                        context=f"{problem}; argument {i+1} is passed by reference and may be written through",
                    )
                    continue
                implicit_ref_args.add(i)
                if defer_callback_argument:
                    self._generic_callback_arguments.setdefault(id(owner.node), []).append(
                        (argument, arg_type, referent, i + 1, True))
                continue
            if defer_callback_argument:
                self._generic_callback_arguments.setdefault(id(owner.node), []).append(
                    (argument, arg_type, param_type, i + 1, False))
                continue
            if not self._is_initializer_assignable_to(
                argument, arg_type, param_type, node.span, context=f"Argument {i+1}"
            ) and not (
                # Generic inference already reported an untyped argument
                # that exceeds its default type.
                isinstance(func_type.param_types[i], GenericParamType)
                and getattr(argument, 'exact_diagnosed', False)
            ):
                self._report_mismatch(
                    TypeErrorType.ARGUMENT_TYPE_MISMATCH,
                    node.span,
                    argument,
                    arg_type,
                    param_type,
                    context=f"Argument {i+1}",
                )
        if implicit_ref_args:
            setattr(node, "implicit_ref_args", implicit_ref_args)

        # Resolve return type with generic substitution
        return_type = func_type.return_type if func_type.return_type else VOID
        if generic_mapping:
            return_type = self._substitute_generic(return_type, generic_mapping)
        if inference_failed:
            unbound: List[str] = []
            self._collect_generic_type_names(return_type, unbound)
            if any(name not in generic_mapping for name in unbound) or self._has_unknown(return_type):
                return UNKNOWN  # The failed inference is the error.

        if generic_mapping and callee_declaration is not None and len(self.errors) == errors_before_inference:
            owner = self.context.current_function
            self._generic_calls.setdefault(id(owner.node) if owner else None, []).append(
                (node, callee_declaration, dict(generic_mapping)))
        return return_type

    def _visit_stdlib_module_call(self, node: ASTNode, module_symbol: Symbol) -> Type:
        """Validate stdlib module calls that lower through backend-specific emitters."""
        arg_types = [self.visit_expression(arg) for arg in (node.arguments or [])]
        function = node.function
        module_path = getattr(module_symbol.node, "module_path", None) or "<unknown>"
        method_name = function.field if function and function.kind == NodeKind.FIELD_ACCESS else None
        canonical = self.stdlib.resolve_call(module_path, method_name or "")
        if canonical is None:
            if function is not None and getattr(function, 'diagnosed', False):
                # The field-access pass already named the missing function.
                return UNKNOWN
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
        for arg in args[1:]:
            self._report_default_overflow(arg)
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
                if fmt[index + 1] == "}":
                    count += 1
                    index += 2
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
                elif self._has_unknown(concrete):
                    pass  # The argument that binds this parameter already has its error.
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
                # A $N sizing an array is bound only by explicit instantiation.
                # An unbound one at a call site is an error; the length must
                # not stay symbolic.
                if current.size_param is not None and current.size_param not in generic_mapping:
                    self.add_semantic_error(
                        SemanticErrorType.GENERIC_PARAM_MISMATCH,
                        span,
                        context=f"Could not infer generic value parameter '${current.size_param}'",
                    )
                    generic_mapping[current.size_param] = UNKNOWN
                stack.append(current.element_type)
            elif isinstance(current, SliceType):
                stack.append(current.element_type)
            elif isinstance(current, FunctionType):
                stack.extend(current.param_types)
                if current.return_type:
                    stack.append(current.return_type)
            elif isinstance(current, GenericInstanceType):
                stack.extend(current.type_args)

    def _infer_generic_types(self, func_type: FunctionType, arg_types: List[Type], arguments: Optional[List[ASTNode]] = None, span: Optional[SourceSpan] = None) -> Dict[str, Type]:
        """
        Infer generic type parameters from actual argument types.

        Returns a mapping from generic parameter names to concrete types.
        A second binding that disagrees with the first is a compile error,
        not silent first-wins; the first binding is kept for downstream checks.
        """
        mapping: Dict[str, Type] = {}
        conflicts: List[Tuple[str, Type, Type]] = []
        origins: Dict[str, Optional[ASTNode]] = {}

        def exact_fits(node: Optional[ASTNode], target: Type) -> bool:
            exact = getattr(node, 'exact_constant', None) if node is not None else None
            if exact is None or not isinstance(target, PrimitiveType):
                return False
            if target.name in {'f32', 'f64'}:
                return True
            if not target.is_integral():
                return False
            value, _floating = exact
            if value.denominator != 1:
                return False
            return self._integer_literal_fits_type(value.numerator, target)

        def coerce(node: Optional[ASTNode], target: Type) -> None:
            if node is None:
                return
            exact = getattr(node, 'exact_constant', None)
            if exact is None or not isinstance(target, PrimitiveType):
                return
            if target.name in {'f32', 'f64'}:
                materialize(node, exact, width=int(target.name[1:]))
                self.set_type(node, target)
            elif target.is_integral():
                materialize(node, exact, integer=True)
                self.set_type(node, target)

        def bind(name: str, concrete: Type, node: Optional[ASTNode]) -> None:
            existing = mapping.get(name)
            if isinstance(concrete, NilType) or self._holds_nil(concrete):
                # nil fits every `ref T`, so it names no T.
                if existing is None:
                    self.add_type_error(
                        TypeErrorType.CANNOT_INFER_TYPE,
                        node.span if node is not None else span,
                        context=f"nil has no type to bind '${name}'; pass a typed reference",
                    )
                    mapping[name] = UNKNOWN
                return
            if isinstance(existing, UnknownType) or isinstance(concrete, UnknownType):
                # One side already has its error.
                mapping.setdefault(name, concrete)
                return
            if existing is None:
                mapping[name] = concrete
                origins[name] = node
                if node is not None:
                    # An untyped argument binds its category default.
                    self._report_default_overflow(node)
            elif existing.equals(concrete):
                return
            elif node is not None and exact_fits(node, existing):
                coerce(node, existing)
            elif origins.get(name) is not None and exact_fits(origins[name], concrete):
                coerce(origins[name], concrete)
                mapping[name] = concrete
                origins[name] = node
            else:
                conflicts.append((name, existing, concrete))

        # Concrete arguments establish expectations before untyped arguments
        # supply their category defaults. Preserve the existing order within
        # each group; no overload or specialization ranking is introduced.
        pairs = list(zip(func_type.param_types, arg_types))
        deferred: List[Tuple[Type, Type, Optional[ASTNode]]] = []
        concrete_args: List[Tuple[Type, Type, Optional[ASTNode]]] = []
        for index, (param_type, arg_type) in enumerate(pairs):
            argument = arguments[index] if arguments and index < len(arguments) else None
            triple = (param_type, arg_type, argument)
            if argument is not None and getattr(argument, "exact_constant", None) is not None:
                deferred.append(triple)
            else:
                concrete_args.append(triple)
        stack: List[Tuple[Type, Type, Optional[ASTNode]]] = deferred + concrete_args
        while stack:
            param_type, arg_type, arg_node = stack.pop()
            if isinstance(param_type, GenericParamType):
                bind(param_type.name, arg_type, arg_node)
            elif isinstance(param_type, ReferenceType):
                if isinstance(arg_type, ReferenceType):
                    stack.append((param_type.referent_type, arg_type.referent_type, None))
                else:
                    stack.append((param_type.referent_type, arg_type, None))
            elif isinstance(param_type, PointerType) and isinstance(arg_type, PointerType):
                stack.append((param_type.pointee_type, arg_type.pointee_type, None))
            elif isinstance(param_type, ArrayType) and isinstance(arg_type, ArrayType):
                if param_type.size == arg_type.size:
                    stack.append((param_type.element_type, arg_type.element_type, None))
            elif isinstance(param_type, ArrayType) and isinstance(arg_type, SliceType):
                stack.append((param_type.element_type, arg_type.element_type, None))
            elif isinstance(param_type, SliceType) and isinstance(arg_type, (SliceType, ArrayType)):
                stack.append((param_type.element_type, arg_type.element_type, None))
            elif isinstance(param_type, FunctionType) and isinstance(arg_type, FunctionType):
                stack.extend((p, a, None) for p, a in zip(param_type.param_types, arg_type.param_types))
                if param_type.return_type and arg_type.return_type:
                    stack.append((param_type.return_type, arg_type.return_type, None))
            elif isinstance(param_type, GenericInstanceType) and isinstance(arg_type, GenericInstanceType):
                if param_type.base_name == arg_type.base_name:
                    stack.extend((p, a, None) for p, a in zip(param_type.type_args, arg_type.type_args))

        for name, first, second in conflicts:
            self.add_semantic_error(
                SemanticErrorType.GENERIC_BINDING_CONFLICT,
                span,
                context=f"Conflicting types for ${name}: {first} vs {second}",
            )
        return mapping

    def _substitute_generic(self, type_: Type, mapping: Dict[str, Type]) -> Type:
        """Substitute parameters in wrapper, function and generic-instance types."""
        results: Dict[int, Type] = {}
        work = [(type_, False)]
        while work:
            current, ready = work.pop()
            if id(current) in results:
                continue
            if isinstance(current, GenericParamType):
                results[id(current)] = mapping.get(current.name, current)
                continue
            if isinstance(current, ReferenceType):
                children = [current.referent_type]
            elif isinstance(current, (ArrayType, SliceType)):
                children = [current.element_type]
            elif isinstance(current, PointerType):
                children = [current.pointee_type]
            elif isinstance(current, FunctionType):
                children = list(current.param_types)
                if current.return_type is not None:
                    children.append(current.return_type)
            elif isinstance(current, GenericInstanceType):
                children = list(current.type_args)
            else:
                # Named records may contain cycles; their identity is unchanged.
                results[id(current)] = current
                continue
            if not ready:
                work.append((current, True))
                work.extend((child, False) for child in reversed(children))
                continue
            if isinstance(current, ReferenceType):
                result = ReferenceType(results[id(current.referent_type)])
            elif isinstance(current, ArrayType):
                size, size_param = current.size, current.size_param
                if size_param is not None:
                    bound = mapping.get(size_param)
                    if (isinstance(bound, GenericValueArg) and not bound.is_bool
                            and self._integer_literal_fits_type(bound.value, USIZE)):
                        size, size_param = bound.value, None
                result = ArrayType(results[id(current.element_type)], size, size_param)
            elif isinstance(current, SliceType):
                result = SliceType(results[id(current.element_type)])
            elif isinstance(current, PointerType):
                result = PointerType(results[id(current.pointee_type)])
            elif isinstance(current, FunctionType):
                result = FunctionType(
                    param_types=tuple(results[id(param)] for param in current.param_types),
                    return_type=results[id(current.return_type)] if current.return_type is not None else None,
                    is_variadic=current.is_variadic,
                    variadic_type=current.variadic_type,
                    generic_param_order=current.generic_param_order,
                )
            else:
                result = GenericInstanceType(current.base_name, tuple(results[id(arg)] for arg in current.type_args))
            results[id(current)] = result
        return results[id(type_)]

    def visit_index_expr(self, node: ASTNode, obj_type: Optional[Type] = None) -> Type:
        """Visit an index expression."""
        if obj_type is None:
            obj_type = self.visit_expression(node.object) if node.object else UNKNOWN
        index_type = self.visit_expression(node.index) if node.index else UNKNOWN

        if node.index and not isinstance(index_type, UnknownType):
            self._validate_index_bound(node.index, index_type)

        if isinstance(obj_type, UnknownType):
            # The object already has its error.
            return UNKNOWN
        if isinstance(obj_type, ReferenceType) and isinstance(obj_type.referent_type, (ArrayType, SliceType)):
            # `a[0]` on `a: ref [N]T` reads through the reference, like `p.x`.
            setattr(node, "implicit_deref_object", True)
            obj_type = obj_type.referent_type

        if isinstance(obj_type, ArrayType):
            return obj_type.element_type
        elif isinstance(obj_type, SliceType):
            return obj_type.element_type
        elif obj_type.equals(STRING):
            return CHAR
        else:
            self.add_type_error(TypeErrorType.CANNOT_INDEX_TYPE, node.span, got_type=str(obj_type))
            return UNKNOWN

    def visit_slice_expr(self, node: ASTNode, obj_type: Optional[Type] = None) -> Type:
        """Visit a slice expression."""
        if obj_type is None:
            obj_type = self.visit_expression(node.object) if node.object else UNKNOWN

        if node.start:
            start_type = self.visit_expression(node.start)
            if not isinstance(start_type, UnknownType):
                self._validate_index_bound(node.start, start_type)

        if node.end:
            end_type = self.visit_expression(node.end)
            if not isinstance(end_type, UnknownType):
                self._validate_index_bound(node.end, end_type)

        if isinstance(obj_type, UnknownType):
            # The object already has its error.
            return UNKNOWN
        if isinstance(obj_type, ArrayType):
            return SliceType(obj_type.element_type)
        if isinstance(obj_type, SliceType):
            return SliceType(obj_type.element_type)
        if obj_type.equals(STRING):
            return SliceType(CHAR)

        self.add_type_error(TypeErrorType.REQUIRES_ARRAY_OR_SLICE, node.span, got_type=str(obj_type))
        return UNKNOWN

    def _fit_exact_usize(self, node: ASTNode, context: str) -> bool:
        """Fit a size use without re-entering expression or type traversal."""
        exact = node.exact_constant
        value = exact[0]
        if value.denominator != 1:
            self.add_error(f"{context} is fractional and cannot fit usize", node.span)
            return False
        if not self._integer_literal_fits_type(value.numerator, USIZE):
            self.add_error(f"{context} is out of range for usize", node.span)
            return False
        materialize(node, exact, integer=True)
        self.set_type(node, USIZE)
        return True

    def _validate_index_bound(self, node: ASTNode, index_type: Type) -> None:
        """Require indexes and slice bounds to be usize or non-negative literals."""
        if getattr(node, "exact_constant", None) is not None:
            self._fit_exact_usize(node, "Index or slice bound")
            return
        if isinstance(index_type, PrimitiveType) and index_type.name == "usize":
            return
        if self._is_non_negative_integer_literal(node) and self._integer_literal_fits_type(node.literal_value, USIZE):
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

    def visit_field_access(self, node: ASTNode, obj_type: Optional[Type] = None) -> Type:
        """Visit a field access expression."""
        # A bare name before the dot may be a module alias or a type name.
        obj_symbol = None
        if node.object is not None and node.object.kind == NodeKind.IDENTIFIER:
            obj_symbol = self.symbols.lookup(node.object.name or "")
            node.object.member_object = True
        if obj_type is None:
            obj_type = self.visit_expression(node.object) if node.object else UNKNOWN
        field_name = node.field or ""

        # Check if the object is a module symbol — allow field access without error
        if obj_symbol is not None:
            if obj_symbol.kind == SymbolKind.MODULE:
                module_path = getattr(getattr(obj_symbol, "node", None), "module_path", None)
                canonical_module = self.stdlib.canonical_module_name(module_path or "")
                if canonical_module and self.stdlib.resolve_call(module_path or "", field_name) is None:
                    self.add_semantic_error(
                        SemanticErrorType.UNDEFINED_IDENTIFIER,
                        node.span,
                        context=f"Stdlib module '{module_path}' has no function '{field_name}'",
                    )
                    # This names the missing function. The call site would then
                    # add "Type is not callable" for the same node, which says
                    # less and leaves the user with two located causes for one
                    # mistake.
                    node.diagnosed = True
                if canonical_module and not getattr(node, "direct_call_target", False):
                    self.add_semantic_error(SemanticErrorType.UNSUPPORTED_FEATURE, node.span,
                                            context="Standard-library operations must be called directly; function values are unavailable")
                # Module field access returns UNKNOWN; calls are lowered by the stdlib preprocessor.
                return UNKNOWN

        if isinstance(obj_type, UnknownType):
            # The object already has its error.
            return UNKNOWN
        names_type = obj_symbol is not None and obj_symbol.kind in {
            SymbolKind.STRUCT, SymbolKind.ENUM, SymbolKind.UNION, SymbolKind.TYPE, SymbolKind.GENERIC_PARAM,
        }
        if names_type and isinstance(obj_type, StructType):
            self.add_type_error(
                TypeErrorType.TYPE_USED_AS_VALUE,
                node.span,
                context=(
                    f"'{node.object.name}' is a struct type; '.{field_name}' needs a value "
                    f"of type '{node.object.name}'"
                ),
            )
            return UNKNOWN

        if isinstance(obj_type, GenericInstanceType):
            concrete_struct = self._resolve_generic_instance_struct(obj_type)
            if concrete_struct is not None:
                obj_type = concrete_struct
            else:
                concrete_union = self._resolve_generic_instance_union(obj_type)
                if concrete_union is not None:
                    obj_type = concrete_union

        if isinstance(obj_type, ReferenceType):
            referent = obj_type.referent_type
            if isinstance(referent, GenericInstanceType):
                concrete_struct = self._resolve_generic_instance_struct(referent)
                if concrete_struct is not None:
                    referent = concrete_struct
                else:
                    concrete_union = self._resolve_generic_instance_union(referent)
                    if concrete_union is not None:
                        referent = concrete_union

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
                self._report_unknown_union_member(referent, field_name, node.span)
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
            self._report_unknown_union_member(obj_type, field_name, node.span)
            return UNKNOWN
        elif isinstance(obj_type, EnumType):
            # Enum variant access: EnumName.VariantName
            if not names_type:
                self.add_type_error(
                    TypeErrorType.FIELD_ACCESS_ON_NON_STRUCT,
                    node.span,
                    got_type=str(obj_type),
                    context=(
                        f"a value of enum '{obj_type}' has no fields; "
                        f"name a variant as '{obj_type}.{field_name}'"
                    ),
                )
                return UNKNOWN
            if obj_type.has_variant(field_name):
                return obj_type  # Enum variant has the enum type
            else:
                self.add_type_error(TypeErrorType.NO_SUCH_FIELD, node.span, context=f"Enum '{obj_type}' has no variant '{field_name}'")
                return UNKNOWN
        else:
            # Use the span of the object being accessed, not the whole field access
            error_span = node.object.span if node.object else node.span
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

    def _immutable_root(self, target: Optional[ASTNode]) -> Optional[str]:
        """Say why an assignment target cannot be written, or None when it can.

        Walks from the target to the binding that stores it. A step through a
        `ref` or a slice ends the walk: the write lands in other storage.
        """
        current = target
        while current is not None:
            if current.kind == NodeKind.IDENTIFIER:
                name = current.name or ""
                symbol = self.symbols.lookup(name)
                if symbol is None or symbol.is_mutable:
                    return None
                declaration = getattr(symbol, "node", None)
                if symbol.kind == SymbolKind.CONSTANT:
                    return f"'{name}' is immutable: it is a constant"
                if declaration is not None and declaration.kind == NodeKind.PARAMETER:
                    return f"'{name}' is immutable: it is a parameter"
                if symbol.kind != SymbolKind.VARIABLE:
                    return f"'{name}' is not a variable"
                return f"'{name}' is immutable"
            if current.kind == NodeKind.FIELD_ACCESS:
                object_type = self.get_type(current.object) if current.object is not None else None
                if isinstance(object_type, ReferenceType):
                    return None
                if isinstance(object_type, SliceType) or (object_type is not None and object_type.equals(STRING)):
                    return f"'.{current.field}' of '{object_type}' is read-only"
                current = current.object
            elif current.kind == NodeKind.INDEX:
                object_type = self.get_type(current.object) if current.object is not None else None
                if isinstance(object_type, (ReferenceType, SliceType)):
                    return None
                if object_type is not None and object_type.equals(STRING):
                    return "a string is immutable: its characters cannot be assigned"
                current = current.object
            elif current.kind == NodeKind.DEREF:
                return None
            else:
                return "the target is a temporary value, not a variable"
        return None

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
        for side in (source_type, target_type):
            # A cast converts numbers. A generic parameter is a number only
            # when its constraint says so.
            if isinstance(side, GenericParamType) and not self._is_numeric_compatible(side):
                self.add_type_error(
                    TypeErrorType.INVALID_CAST,
                    node.span,
                    got_type=str(side),
                    context=self._operand_hint(side, "Numeric"),
                )
                return UNKNOWN

        return target_type

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
        while node.kind == NodeKind.BLOCK:
            if not node.statements:
                return False
            node = node.statements[-1]
        return node.kind == NodeKind.RETURN

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
            if not cond_type.equals(BOOL) and not isinstance(cond_type, UnknownType):
                self.add_type_error(TypeErrorType.CONDITION_NOT_BOOL, node.condition.span, expected_type="bool", got_type=str(cond_type))

        # Both branches must have compatible types
        then_type = self.visit_expression(node.then_expr) if node.then_expr else VOID
        else_type = self.visit_expression(node.else_expr) if node.else_expr else VOID
        if (id(node.then_expr) in self._bound_callback_values
                or id(node.else_expr) in self._bound_callback_values):
            self._bound_callback_values.add(id(node))
        if isinstance(then_type, UnknownType) or isinstance(else_type, UnknownType):
            return UNKNOWN  # A branch already has its error.
        if then_type.equals(else_type) and not (then_type.is_numeric() and (
            self._is_untyped_numeric(node.then_expr) != self._is_untyped_numeric(node.else_expr)
        )):
            return then_type

        # An untyped constant branch takes the type of the typed branch. Two
        # untyped branches stay untyped, so a destination can still fit them.
        then_untyped = self._is_untyped_numeric(node.then_expr)
        else_untyped = self._is_untyped_numeric(node.else_expr)
        if then_untyped and else_untyped:
            return F64 if then_type.equals(F64) or else_type.equals(F64) else I32
        if then_untyped and isinstance(else_type, PrimitiveType) and else_type.is_numeric():
            self._fit_branch_constants(node.then_expr, else_type)
            return else_type
        if else_untyped and isinstance(then_type, PrimitiveType) and then_type.is_numeric():
            self._fit_branch_constants(node.else_expr, then_type)
            return then_type
        if else_type.is_assignable_to(then_type):
            return then_type  # for example `if c { p } else { nil }`
        if then_type.is_assignable_to(else_type):
            return else_type
        self.add_type_error(
            TypeErrorType.IF_EXPR_TYPE_MISMATCH,
            node.span,
            expected_type=str(then_type),
            got_type=str(else_type)
        )
        return UNKNOWN

    def _is_untyped_numeric(self, node: Optional[ASTNode]) -> bool:
        """True when every arm under node is an untyped numeric constant."""
        if node is None:
            return False
        stack = [node]
        while stack:
            current = stack.pop()
            if current.kind == NodeKind.IF_EXPR:
                if current.then_expr is None or current.else_expr is None:
                    return False
                stack.extend((current.then_expr, current.else_expr))
            elif current.kind == NodeKind.MATCH_EXPR:
                arms = [case.expression for case in (current.cases or []) if getattr(case, 'expression', None) is not None]
                if isinstance(current.else_case, ASTNode):
                    arms.append(current.else_case)
                if not arms:
                    return False
                stack.extend(arms)
            elif getattr(current, 'exact_constant', None) is None:
                return False
        return True

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
        branch_nodes: List[ASTNode] = []
        for case in (node.cases or []):
            self._validate_match_case_capture_shape(case.patterns or [], scrutinee_type)
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
                # Fresh scope, not a reused one: name resolution never
                # descends into match expressions, so no table scope exists
                # for these arms. Reusing one would consume a statement-arm
                # slot and push a later match statement into the wrong scope.
                self.symbols.enter_scope("match_case")
                self._define_match_capture_symbols(case.patterns or [], scrutinee_type)
                try:
                    branch_types.append(self.visit_expression(case_expr))
                    branch_nodes.append(case_expr)
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
            branch_nodes.append(node.else_case)

        self._check_match_exhaustiveness(
            span=node.span,
            scrutinee_type=scrutinee_type,
            has_catch_all=has_catch_all,
            bool_coverage=bool_coverage,
            enum_coverage=enum_coverage,
        )

        if not branch_types:
            return UNKNOWN
        if any(isinstance(branch_type, UnknownType) for branch_type in branch_types):
            return UNKNOWN  # A branch already has its error.

        if any(id(branch) in self._bound_callback_values for branch in branch_nodes):
            self._bound_callback_values.add(id(node))

        # Typed branches fix the result type; untyped constant branches then
        # take it. All-untyped branches stay untyped for a destination to fit.
        result_type: Optional[Type] = None
        untyped_nodes: List[ASTNode] = []
        floating = False
        for branch_node, branch_type in zip(branch_nodes, branch_types):
            if self._is_untyped_numeric(branch_node):
                untyped_nodes.append(branch_node)
                floating = floating or branch_type.equals(F64)
                continue
            if result_type is None or branch_type.equals(result_type) or branch_type.is_assignable_to(result_type):
                result_type = result_type if result_type is not None else branch_type
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
        if result_type is None:
            return F64 if floating else I32
        if untyped_nodes:
            if not (isinstance(result_type, PrimitiveType) and result_type.is_numeric()):
                self.add_type_error(
                    TypeErrorType.IF_EXPR_TYPE_MISMATCH,
                    node.span,
                    expected_type=str(result_type),
                    got_type="f64" if floating else "i32",
                    context="match expression branches",
                )
                return UNKNOWN
            for branch_node in untyped_nodes:
                self._fit_branch_constants(branch_node, result_type)
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

    def _scrutinee_tagged_union(self, scrutinee_type: Type) -> Optional[UnionType]:
        """Return the concrete UnionType when the scrutinee is a tagged union.

        A `ref` to a union matches like the union, the way field access
        reads through a reference. Concrete unions resolve directly; generic
        instances resolve through union specialization. Tagged-ness comes
        from the declaration (UnionType carries no tagged flag), so untagged
        unions keep whole-value capture.
        """
        concrete: Optional[UnionType] = None
        name = ""
        if isinstance(scrutinee_type, ReferenceType):
            scrutinee_type = scrutinee_type.referent_type
        if isinstance(scrutinee_type, UnionType):
            concrete, name = scrutinee_type, scrutinee_type.name or ""
        elif isinstance(scrutinee_type, GenericInstanceType):
            concrete, name = self._resolve_generic_instance_union(scrutinee_type), scrutinee_type.base_name or ""
        if concrete is None or not name:
            return None
        symbol = self.symbols.lookup(name)
        node = getattr(symbol, "node", None) if symbol is not None else None
        if node is not None and getattr(node, "is_tagged", False):
            return concrete
        return None

    def _report_unknown_union_member(
        self, union_type: UnionType, member: str, span: Optional[SourceSpan]
    ) -> None:
        """Report a name the union does not declare: a tag of `union(tag)`, else a field."""
        if self._scrutinee_tagged_union(union_type) is not None:
            self.add_type_error(
                TypeErrorType.NO_SUCH_TAG, span,
                context=f"Union '{union_type}' has no tag '{member}'",
            )
        else:
            self.add_type_error(
                TypeErrorType.NO_SUCH_FIELD, span,
                context=f"Union '{union_type}' has no field '{member}'",
            )

    def _validate_union_tag_pattern(
        self, pattern: ASTNode, union_type: UnionType
    ) -> Tuple[Optional[str], Optional[object]]:
        """Check one dot/qualified tag arm against its union's tags."""
        variant = pattern.variant or ""
        if union_type.get_field(variant) is None:
            self.add_type_error(
                TypeErrorType.NO_SUCH_TAG,
                pattern.span,
                context=f"Union '{union_type.name}' has no tag '{variant}'",
            )
            return (None, None)
        return ("union", variant)

    def _validate_match_case_capture_shape(self, patterns: List[ASTNode], scrutinee_type: Optional[Type] = None) -> None:
        if scrutinee_type is not None and self._scrutinee_tagged_union(scrutinee_type) is not None:
            return
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
        union_type = self._scrutinee_tagged_union(capture_type)
        if union_type is not None:
            for pattern in patterns:
                if pattern.kind != NodeKind.PATTERN_ENUM or not (pattern.name or ""):
                    continue
                if (pattern.enum_type or "") not in ("", union_type.name):
                    continue
                field = union_type.get_field(pattern.variant or "")
                payload = field.field_type if field is not None else UNKNOWN
                binding = pattern.name or ""
                if self._type_holds_string(payload):
                    self.add_semantic_error(
                        SemanticErrorType.INVALID_PATTERN,
                        pattern.span,
                        context=(
                            f"case '.{pattern.variant}({binding})' binds a payload of type "
                            f"'{payload}' by value, and that type holds a string; match "
                            f"'.{pattern.variant}' without a binding, or use a payload "
                            "type without strings"
                        ),
                    )
                existing = self.symbols.current_scope.lookup_local(binding)
                if existing:
                    existing.type = payload
                    existing.node = pattern
                    existing.is_mutable = False
                    continue
                payload_symbol = Symbol(
                    name=binding,
                    kind=SymbolKind.VARIABLE,
                    type=payload,
                    node=pattern,
                    is_mutable=False,
                )
                if not self.symbols.define(payload_symbol):
                    self.add_semantic_error(
                        SemanticErrorType.ALREADY_DEFINED,
                        pattern.span,
                        context=f"Match capture '{binding}'",
                    )
            return
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

    def _type_holds_string(self, type_: Type) -> bool:
        """True when a by-value copy of type_ copies a string.

        Looks through fixed arrays, struct and union fields, and generic
        instances. References, pointers and slices are not followed: copying
        one copies the handle, not the contents.
        """
        stack: List[Type] = [type_]
        seen: Set[Type] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            if current.equals(STRING):
                return True
            if isinstance(current, ArrayType):
                stack.append(current.element_type)
            elif isinstance(current, (StructType, UnionType)):
                stack.extend(field.field_type for field in current.fields)
            elif isinstance(current, GenericInstanceType):
                concrete = (self._resolve_generic_instance_struct(current)
                            or self._resolve_generic_instance_union(current))
                if concrete is not None:
                    stack.append(concrete)
        return False

    def _range_pattern_value(self, pattern: Optional[ASTNode], resolving: Set[str]) -> Optional[Tuple[str, int | float]]:
        """Resolve literal patterns, constant aliases and exact range endpoints."""
        current = pattern
        seen = set(resolving)
        pattern_position = True
        while current is not None:
            literal = self._match_pattern_literal(current)
            if literal is not None:
                return self._range_literal_value(literal)
            if current.kind == NodeKind.IDENTIFIER or (pattern_position and current.kind == NodeKind.PATTERN_IDENTIFIER):
                name = current.name
                if not name or name in seen:
                    return None
                symbol = self.symbols.lookup(name)
                if symbol is None or symbol.kind != SymbolKind.CONSTANT or symbol.node is None:
                    return None
                seen.add(name)
                current = symbol.node.value
                pattern_position = False
                continue
            exact = self._evaluate_exact(current, self.symbols.lookup, self.exact_bindings)
            if exact is None:
                return None
            # Pattern keys are Python integers or the nearest f64.
            if not exact[1] and exact[0].denominator == 1:
                return ("number", exact[0].numerator)
            try:
                return ("number", float(exact[0]))
            except OverflowError:
                return None
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

        # `.ok` and `Result.ok` name the same tag, so the key omits the prefix.
        if pattern_kind == "union" and isinstance(pattern_value, str):
            return ("union", pattern_value)

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
        pieces = []
        work = [pattern]
        while work:
            item = work.pop()
            if isinstance(item, str):
                pieces.append(item)
                continue
            if item.kind == NodeKind.PATTERN_RANGE:
                if item.end:
                    work.append(item.end)
                work.append("..")
                if item.start:
                    work.append(item.start)
                continue
            if item.kind == NodeKind.PATTERN_WILDCARD:
                pieces.append("_")
            elif item.kind == NodeKind.PATTERN_IDENTIFIER:
                pieces.append(item.name or "<identifier>")
            elif item.kind == NodeKind.PATTERN_ENUM:
                pieces.append(f"{item.enum_type}.{item.variant}")
            else:
                literal = self._match_pattern_literal(item)
                if literal is None:
                    pieces.append(item.kind.name.lower())
                    continue
                value = literal.literal_value
                if literal.literal_kind == LiteralKind.STRING:
                    pieces.append(f'"{value}"')
                elif literal.literal_kind == LiteralKind.CHAR:
                    pieces.append(f"'{value}'")
                elif literal.literal_kind == LiteralKind.BOOLEAN:
                    pieces.append("true" if value else "false")
                elif literal.literal_kind == LiteralKind.NIL:
                    pieces.append("nil")
                else:
                    pieces.append(str(value))
        return "".join(pieces)

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

        union_type = self._scrutinee_tagged_union(scrutinee_type)
        if union_type is not None:
            if pattern.kind == NodeKind.PATTERN_IDENTIFIER:
                return (None, None)
            if pattern.kind == NodeKind.PATTERN_ENUM and (pattern.enum_type or "") in ("", union_type.name):
                return self._validate_union_tag_pattern(pattern, union_type)

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
                        self._pattern_value_node(endpoint),
                        endpoint_type,
                        scrutinee_type,
                        endpoint.span,
                        context="Range pattern endpoint type mismatch",
                    )
                ):
                    self._report_mismatch(
                        TypeErrorType.TYPE_MISMATCH, endpoint.span, self._pattern_value_node(endpoint),
                        endpoint_type, scrutinee_type, context="Range pattern endpoint type mismatch",
                    )

            self._reject_reversed_constant_range(pattern)
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
            self._report_mismatch(
                TypeErrorType.TYPE_MISMATCH, pattern.span, self._pattern_value_node(pattern),
                pattern_type, scrutinee_type, context="Match pattern type mismatch",
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

    def _reject_reversed_constant_range(self, pattern: ASTNode) -> None:
        """Reject a range pattern whose constant endpoints run backwards.

        Both endpoints resolve through the same iterative constant folder
        used for overlap checks, so literals, named constants, and simple
        constant expressions are covered. Runtime (non-constant) endpoints
        return None and keep the runtime rule: an empty range matches
        nothing.
        """
        if pattern.start is None or pattern.end is None:
            return
        start = self._range_pattern_value(pattern.start, set())
        end = self._range_pattern_value(pattern.end, set())
        if start is None or end is None:
            return
        start_kind, start_value = start
        end_kind, end_value = end
        if start_kind != end_kind:
            return
        if start_value <= end_value:
            return
        self.add_semantic_error(
            SemanticErrorType.INVALID_PATTERN,
            pattern.span,
            context=(
                f"Range pattern '{self._format_match_pattern(pattern)}' is reversed "
                "(start is greater than end); swap the endpoints"
            ),
        )

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

            if enum_name == "":
                union_type = self._scrutinee_tagged_union(scrutinee_type)
                if union_type is None:
                    self.add_type_error(
                        TypeErrorType.TYPE_MISMATCH,
                        pattern.span,
                        expected_type="tagged union",
                        got_type=str(scrutinee_type),
                        context="Leading-dot tag pattern requires a tagged-union match value",
                    )
                    return UNKNOWN
                if union_type.get_field(variant_name) is None:
                    self.add_type_error(
                        TypeErrorType.NO_SUCH_TAG,
                        pattern.span,
                        context=f"Union '{union_type.name}' has no tag '{variant_name}'",
                    )
                    return UNKNOWN
                return scrutinee_type

            enum_symbol = self.symbols.lookup(enum_name)
            if enum_symbol is not None and isinstance(enum_symbol.type, UnionType):
                union_type = self._scrutinee_tagged_union(scrutinee_type)
                if union_type is not None and union_type.name == enum_name:
                    if union_type.get_field(variant_name) is None:
                        self.add_type_error(
                            TypeErrorType.NO_SUCH_TAG,
                            pattern.span,
                            context=f"Union '{union_type.name}' has no tag '{variant_name}'",
                        )
                        return UNKNOWN
                    return scrutinee_type
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
                exact = self.exact_bindings.get(id(symbol.node)) if symbol.node else None
                if exact is not None:
                    # A named constant pattern is a use site. Replacing this
                    # node must not specialize the shared declaration.
                    pattern.kind = NodeKind.IDENTIFIER
                    pattern.exact_constant = exact
                    pattern_type = F64 if exact[1] else I32
                    self.set_type(pattern, pattern_type)
                    return pattern_type
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
                inline_type = getattr(node, "inline_type", None)
                if inline_type is not None:
                    # `struct { x: i32 } { x: 1 }` carries its own type.
                    struct_type = self.resolve_type_node(inline_type)
                else:
                    # Look up type by name
                    symbol = self.symbols.lookup(node.struct_type)
                    struct_type = symbol.type if symbol else None
            else:
                struct_type = self.resolve_type_node(node.struct_type)

        if isinstance(struct_type, UnionType):
            # Generic union instantiation: Result(i32, string){...}
            result_type: Type = struct_type
            type_arg_nodes = getattr(node, "type_arguments", None) or []
            if type_arg_nodes:
                original_union_type = struct_type
                type_args = [self._resolve_type_or_value_arg(arg) for arg in type_arg_nodes]
                union_params = tuple(original_union_type.generic_params or ())
                if not self._generic_argument_count_matches(
                    original_union_type.name, union_params, type_args, node.span
                ):
                    return UNKNOWN
                self._check_instantiation_constraints(
                    original_union_type.name,
                    union_params,
                    self._union_generic_constraints.get(original_union_type.name) or {},
                    self._union_value_param_types.get(original_union_type.name) or {},
                    type_args,
                    node.span,
                )
                struct_type = self._instantiate_union_type(struct_type, type_args)
                if (
                    original_union_type.name
                    and len(original_union_type.generic_params or ()) == len(type_args)
                ):
                    result_type = GenericInstanceType(
                        base_name=original_union_type.name,
                        type_args=tuple(type_args),
                    )
                else:
                    result_type = struct_type
            self._visit_union_init(node, struct_type)
            return result_type

        if not isinstance(struct_type, StructType):
            written = node.struct_type if isinstance(node.struct_type, str) else str(struct_type)
            if struct_type is None:
                self.add_type_error(TypeErrorType.UNDEFINED_TYPE, node.span, context=f"Type '{written}'")
            elif isinstance(struct_type, EnumType):
                self.add_type_error(
                    TypeErrorType.REQUIRES_STRUCT_TYPE,
                    node.span,
                    got_type=str(struct_type),
                    context=(
                        f"'{written}{{...}}' builds a struct or union, and '{written}' is an enum; "
                        f"name a variant as '{written}.Variant'"
                    ),
                )
            elif not isinstance(struct_type, UnknownType):
                self.add_type_error(
                    TypeErrorType.REQUIRES_STRUCT_TYPE,
                    node.span,
                    got_type=str(struct_type),
                    context=f"'{written}{{...}}' builds a struct or union",
                )
            return UNKNOWN

        result_type: Type = struct_type

        # Generic struct instantiation: Pair(i32, string){...}
        type_arg_nodes = getattr(node, "type_arguments", None) or []
        if type_arg_nodes:
            original_struct_type = struct_type
            type_args = [self._resolve_type_or_value_arg(arg) for arg in type_arg_nodes]
            struct_params = tuple(original_struct_type.generic_params or ())
            if not self._generic_argument_count_matches(
                original_struct_type.name, struct_params, type_args, node.span
            ):
                return UNKNOWN
            self._check_instantiation_constraints(
                original_struct_type.name,
                struct_params,
                self._struct_generic_constraints.get(original_struct_type.name) or {},
                self._struct_value_param_types.get(original_struct_type.name) or {},
                type_args,
                node.span,
            )
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

        field_inits = node.field_inits or []
        declared_names = [field.name for field in struct_type.fields]
        # Positional initializers use declaration order, matching normalization.
        # Keep the parsed fields unchanged until preprocessing performs that step.
        supplied = [field.name if field.name is not None else
                    (declared_names[index] if index < len(declared_names) else None)
                    for index, field in enumerate(field_inits)]
        declared = set(declared_names)
        missing = declared - set(supplied)
        unknown_names = [name for name in supplied if name is not None and name not in declared]
        named_supplied = [name for name in supplied if name is not None]
        # The most specific statement about the initializer list is the one
        # reported: an unknown or repeated name explains a wrong count.
        if unknown_names:
            for name in unknown_names:
                self.add_type_error(TypeErrorType.NO_SUCH_FIELD, node.span,
                                    context=f"Struct '{struct_type}' has no field '{name}'")
        elif len(named_supplied) != len(set(named_supplied)):
            self.add_type_error(TypeErrorType.TYPE_MISMATCH, node.span,
                                context="Duplicate struct field initializer")
        elif len(field_inits) > len(declared_names):
            self.add_type_error(TypeErrorType.TYPE_MISMATCH, node.span,
                                context=f"Too many struct field initializers: expected {len(declared_names)}, got {len(field_inits)}")
        elif missing:
            self.add_type_error(TypeErrorType.TYPE_MISMATCH, node.span,
                                context=f"Missing struct fields: {', '.join(sorted(missing))}")

        # Type check field initializers
        if node.field_inits:
            for index, field_init in enumerate(node.field_inits):
                field_name = supplied[index] or ""
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
                        self._report_mismatch(
                            TypeErrorType.TYPE_MISMATCH, field_init.span, field_init.value,
                            actual_type, expected_type, context=f"Field '{field_name}'",
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
            self._report_unknown_union_member(union_type, field_name, field_init.span)
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
                self._report_mismatch(
                    TypeErrorType.TYPE_MISMATCH, field_init.span, field_init.value,
                    actual_type, expected_field.field_type, context=f"Union field '{field_name}'",
                )

        return union_type

    def visit_array_init(self, node: ASTNode) -> Type:
        """Visit an array initialization."""
        elements = node.elements or []
        if not elements:
            # No element to infer from. A declared destination supplies the
            # type; `x := []` is reported where the variable is declared.
            return UNKNOWN

        elem_type = self.visit_expression(elements[0])
        # True while every element so far is built only from untyped constants.
        untyped = self._is_untyped_literal(elements[0])
        for index, element in enumerate(elements[1:], start=1):
            actual_type = self.visit_expression(element)
            if isinstance(actual_type, UnknownType):
                continue  # This element already has its error.
            if isinstance(elem_type, UnknownType):
                elem_type = actual_type
                untyped = self._is_untyped_literal(element)
                continue
            element_untyped = self._is_untyped_literal(element)
            if untyped or element_untyped:
                joined = self._join_untyped(elem_type, actual_type, untyped, element_untyped)
                if joined is not None:
                    # A constant beside a typed element takes that element's type.
                    if element_untyped and not untyped:
                        if isinstance(joined, PrimitiveType):
                            self._fit_exact(element, joined)
                    elif untyped and not element_untyped and isinstance(joined, PrimitiveType):
                        for earlier in elements[:index]:
                            self._fit_exact(earlier, joined)
                    elem_type = joined
                    untyped = untyped and element_untyped
                    continue
            untyped = False
            common_type = self._common_array_literal_element_type(elem_type, actual_type)
            if common_type is None:
                self._report_mismatch(
                    TypeErrorType.TYPE_MISMATCH, element.span, element, actual_type, elem_type,
                    context=f"Array element {index}",
                )
            else:
                elem_type = common_type
        return ArrayType(element_type=elem_type, size=len(elements))

    def _is_untyped_literal(self, node: ASTNode) -> bool:
        """True for an untyped numeric constant, or an array literal of them."""
        stack = [node]
        while stack:
            current = stack.pop()
            if current.kind == NodeKind.ARRAY_INIT and current.elements:
                stack.extend(current.elements)
            elif getattr(current, 'exact_constant', None) is None:
                return False
        return True

    def _join_untyped(self, left: Type, right: Type, left_untyped: bool, right_untyped: bool) -> Optional[Type]:
        """Element type of two array-literal elements when one or both are untyped.

        The shapes must agree down to a numeric leaf. A typed side keeps its
        leaf type; two untyped sides are f64 when either holds a float.
        """
        sizes: List[Optional[int]] = []
        while isinstance(left, ArrayType) and isinstance(right, ArrayType) and left.size == right.size:
            sizes.append(left.size)
            left, right = left.element_type, right.element_type
        if not (isinstance(left, PrimitiveType) and left.is_numeric()
                and isinstance(right, PrimitiveType) and right.is_numeric()):
            return None
        if left_untyped and right_untyped:
            joined: Type = F64 if left.equals(F64) or right.equals(F64) else I32
        else:
            joined = right if left_untyped else left
        for size in reversed(sizes):
            joined = ArrayType(element_type=joined, size=size)
        return joined

    def _common_array_literal_element_type(self, left: Type, right: Type) -> Optional[Type]:
        """Find a common literal element type without accepting unrelated shapes."""
        sizes = []
        while True:
            if right.is_assignable_to(left):
                result = left
                break
            if left.is_assignable_to(right):
                result = right
                break
            if not (isinstance(left, ArrayType) and isinstance(right, ArrayType) and left.size == right.size):
                return None
            sizes.append(left.size)
            left, right = left.element_type, right.element_type
        for size in reversed(sizes):
            result = ArrayType(element_type=result, size=size)
        return result

    def _fit_exact(self, value_node: Optional[ASTNode], expected_type: PrimitiveType) -> Optional[bool]:
        """Fit one exact constant to a numeric destination; None when it is not one."""
        exact = getattr(value_node, 'exact_constant', None)
        if exact is None:
            return None
        if expected_type.name in {'f32', 'f64'}:
            materialize(value_node, exact, width=int(expected_type.name[1:]))
            self.set_type(value_node, expected_type)
            # The final traversal reports value overflow at the operand.
            # Its numeric type is valid, so do not add a type mismatch.
            return True
        if not expected_type.is_integral():
            return None
        value, _floating = exact
        if getattr(value_node, 'exact_diagnosed', False):
            # Already reported once, with a better message. Reporting
            # again here would give the same value two located causes.
            return False
        if value.denominator != 1:
            self.add_error(f"Exact constant {render(value)} is fractional and cannot fit {expected_type}", value_node.span)
            value_node.exact_diagnosed = True
            return False
        if not self._integer_literal_fits_type(value.numerator, expected_type):
            self.add_error(f"Exact constant {render(value)} is out of range for {expected_type}", value_node.span)
            value_node.exact_diagnosed = True
            return False
        materialize(value_node, exact, integer=True)
        self.set_type(value_node, expected_type)
        return True

    def _fit_branch_constants(self, value_node: ASTNode, expected_type: PrimitiveType) -> Optional[bool]:
        """Fit the constant arms of an if or match expression to its destination.

        An arm has no destination of its own, so without this a constant arm
        would take the i32 default even when the declared type is wider.
        Returns None when some arm is not a constant: the caller then checks
        the expression's own type.
        """
        all_constant = True
        stack = [value_node]
        while stack:
            node = stack.pop()
            if node.kind == NodeKind.IF_EXPR:
                stack.extend(arm for arm in (node.then_expr, node.else_expr) if arm is not None)
            elif node.kind == NodeKind.MATCH_EXPR:
                stack.extend(case.expression for case in (node.cases or []) if getattr(case, 'expression', None) is not None)
                if isinstance(node.else_case, ASTNode):
                    stack.append(node.else_case)
            else:
                fitted = self._fit_exact(node, expected_type)
                if fitted is False:
                    value_node.exact_diagnosed = True
                    return False
                if fitted is None:
                    all_constant = False
        if not all_constant:
            return None
        self.set_type(value_node, expected_type)
        return True

    def _instantiated_value_fits(
        self, value: ASTNode, source_type: Type, actual: Type, expected: Type, mapping: Dict[str, Type]
    ) -> bool:
        # Fit literal elements without materializing the shared generic body.
        pending = [(value, source_type, actual, expected)]
        while pending:
            value, source_type, actual, expected = pending.pop()
            if value.kind == NodeKind.ARRAY_INIT and isinstance(expected, ArrayType):
                elements = value.elements or []
                if expected.size is not None and len(elements) != expected.size:
                    return False
                for element in elements:
                    element_type = self.get_type(element)
                    pending.append((element, element_type, self._substitute_generic(element_type, mapping),
                                    expected.element_type))
                continue
            if value.kind in {NodeKind.IF_EXPR, NodeKind.MATCH_EXPR} and isinstance(expected, PrimitiveType):
                branches = [value]
                leaves = []
                while branches:
                    branch = branches.pop()
                    if branch.kind == NodeKind.IF_EXPR:
                        branches.extend(arm for arm in (branch.then_expr, branch.else_expr) if arm is not None)
                    elif branch.kind == NodeKind.MATCH_EXPR:
                        branches.extend(case.expression for case in (branch.cases or [])
                                        if getattr(case, "expression", None) is not None)
                        if isinstance(branch.else_case, ASTNode):
                            branches.append(branch.else_case)
                    else:
                        leaves.append(branch)
                if leaves and all(getattr(leaf, "exact_constant", None) is not None for leaf in leaves):
                    for leaf in leaves:
                        leaf_type = self.get_type(leaf)
                        pending.append((leaf, leaf_type, self._substitute_generic(leaf_type, mapping), expected))
                    continue
            exact = getattr(value, "exact_constant", None)
            if (exact is not None and isinstance(source_type, PrimitiveType) and source_type.is_numeric()
                    and isinstance(expected, PrimitiveType)):
                if expected.is_integral():
                    if exact[0].denominator != 1 or not self._integer_literal_fits_type(exact[0].numerator, expected):
                        return False
                    continue
                if expected.is_floating():
                    try:
                        ieee_bits(exact, int(expected.name[1:]))
                    except ExactArithmeticError:
                        return False
                    continue
            if not actual.is_assignable_to(expected):
                return False
        return True

    def _is_initializer_assignable_to(
        self,
        value_node: Optional[ASTNode],
        actual_type: Type,
        expected_type: Type,
        span: Optional[SourceSpan],
        context: str = "Initializer",
    ) -> bool:
        """Check assignment with literal-specific validation for composite types.

        A type left unresolved by an earlier error fits anything: that error
        is the one report the mistake gets.
        """
        if self._has_unknown(expected_type):
            self._silence_constants(value_node)
            return True
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
        if self._has_unknown(actual_type):
            return True
        if isinstance(expected_type, PrimitiveType):
            fitted = self._fit_exact(value_node, expected_type)
            if fitted is not None:
                return fitted
            if value_node is not None and value_node.kind in {NodeKind.IF_EXPR, NodeKind.MATCH_EXPR}:
                fitted = self._fit_branch_constants(value_node, expected_type)
                if fitted is not None:
                    return fitted
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

        if expected_type.size is not None and len(elements) != expected_type.size:
            self.add_type_error(
                TypeErrorType.TYPE_MISMATCH,
                span or node.span,
                expected_type=str(expected_type),
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
                self._report_mismatch(
                    TypeErrorType.TYPE_MISMATCH, element.span, element,
                    actual_element_type, expected_type.element_type,
                    context=f"{context} element {index}",
                )
                ok = False

        if not ok:
            # Each failing element has its own error; the caller adds none.
            node.diagnosed = True
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
        """A number, or a generic parameter whose constraint admits only numbers."""
        if isinstance(type_, GenericParamType):
            return type_.constraint is not None and type_.constraint.types <= NUMERIC_TYPES
        return type_.is_numeric() or isinstance(type_, UnknownType)

    def _is_integral_compatible(self, type_: Type) -> bool:
        """An integer, or a generic parameter whose constraint admits only integers."""
        if isinstance(type_, GenericParamType):
            return type_.constraint is not None and type_.constraint.types <= INTEGER_TYPES
        return type_.is_integral() or isinstance(type_, UnknownType)

    def _holds_nil(self, type_: Type) -> bool:
        """True for an array or slice type whose innermost element is nil."""
        current = type_
        while isinstance(current, (ArrayType, SliceType)):
            current = current.element_type
        return isinstance(current, NilType) and current is not type_

    def _silence_constants(self, node: Optional[ASTNode]) -> None:
        """Exempt the untyped constants under node from the default-type check.

        Their destination type is unknown because of an error already
        reported, so "does not fit default i32" would be a second error for
        the same mistake.
        """
        stack = [node] if node is not None else []
        while stack:
            current = stack.pop()
            if getattr(current, 'exact_constant', None) is not None:
                current.exact_diagnosed = True
            for value in vars(current).values():
                if isinstance(value, ASTNode):
                    stack.append(value)
                elif isinstance(value, list):
                    stack.extend(child for child in value if isinstance(child, ASTNode))

    def _already_reported(self, value_node: Optional[ASTNode]) -> bool:
        """True when a check on this value node already produced its error."""
        return value_node is not None and bool(
            getattr(value_node, 'exact_diagnosed', False) or getattr(value_node, 'diagnosed', False)
        )

    def _has_unknown(self, type_: Optional[Type]) -> bool:
        """True when an earlier error left part of type_ unresolved."""
        stack = [type_]
        while stack:
            current = stack.pop()
            if isinstance(current, UnknownType):
                return True
            if isinstance(current, (ArrayType, SliceType)):
                stack.append(current.element_type)
            elif isinstance(current, ReferenceType):
                stack.append(current.referent_type)
            elif isinstance(current, PointerType):
                stack.append(current.pointee_type)
            elif isinstance(current, GenericInstanceType):
                stack.extend(current.type_args)
        return False

    def _report_mismatch(
        self,
        error_type: TypeErrorType,
        span: Optional[SourceSpan],
        value_node: Optional[ASTNode],
        actual_type: Type,
        expected_type: Type,
        context: Optional[str] = None,
    ) -> None:
        """Report that a value does not fit its destination, once per value."""
        if self._already_reported(value_node):
            return
        if value_node is not None:
            value_node.diagnosed = True
        if (
            isinstance(actual_type, PrimitiveType) and actual_type.is_integral()
            and isinstance(expected_type, PrimitiveType) and expected_type.is_floating()
        ):
            name = value_node.name if value_node is not None and value_node.kind == NodeKind.IDENTIFIER and value_node.name else "value"
            note = f"an integer variable does not convert to a float by itself; write cast({expected_type}, {name})"
            context = f"{context}: {note}" if context else note
        self.add_type_error(
            error_type,
            span,
            expected_type=str(expected_type),
            got_type=str(actual_type),
            context=context,
        )

    def _collect_generic_type_names(self, type_: Type, out: List[str]) -> None:
        """Collect GenericParamType names reachable from a semantic Type object."""
        stack: List[Type] = [type_]
        # A record may reach itself through `ref`; visit each record once.
        seen: Set[int] = set()
        while stack:
            current = stack.pop()
            if isinstance(current, (StructType, UnionType)):
                if id(current) in seen:
                    continue
                seen.add(id(current))
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
            elif isinstance(current, UnionType):
                for field in current.fields:
                    stack.append(field.field_type)

    def _generic_argument_count_matches(
        self,
        owner_name: Optional[str],
        params: Tuple[str, ...],
        type_args: List[Type],
        span: Optional[SourceSpan],
    ) -> bool:
        """Report `Name(args)` whose argument count differs from Name's parameters."""
        if not params or len(params) == len(type_args):
            return True
        listed = ", ".join(f"${name}" for name in params)
        self.add_semantic_error(
            SemanticErrorType.GENERIC_PARAM_MISMATCH,
            span,
            context=(
                f"{owner_name} takes {len(params)} generic argument(s) ({listed}), "
                f"got {len(type_args)}"
            ),
        )
        return False

    def _check_instantiation_constraints(
        self,
        owner_name: Optional[str],
        params: Tuple[str, ...],
        constraints: Dict[str, TypeSet],
        value_kinds: Dict[str, str],
        type_args: List[Type],
        span: Optional[SourceSpan],
    ) -> None:
        """Reject generic arguments of the wrong kind or outside a declared set.

        Generic parameters pair positionally with arguments, matching
        _instantiate_struct_type's and _instantiate_union_type's mapping.
        """
        if not owner_name:
            return
        self._check_generic_argument_kinds(owner_name, params, value_kinds, type_args, span)
        for param_name, concrete in zip(params, type_args):
            if param_name in value_kinds or isinstance(concrete, GenericValueArg):
                continue
            constraint = constraints.get(param_name)
            if constraint is not None and not constraint.contains(concrete):
                self.add_semantic_error(
                    SemanticErrorType.CONSTRAINT_VIOLATION,
                    span,
                    context=(
                        f"Generic parameter '${param_name}' of {owner_name} requires {constraint}, "
                        f"got {concrete}"
                    ),
                )

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

    def _instantiate_union_type(self, union_type: UnionType, type_args: List[Type]) -> UnionType:
        """Instantiate a generic union with concrete type arguments."""
        params = list(union_type.generic_params or ())
        if not params:
            return union_type
        if len(params) != len(type_args):
            # Keep original type for error reporting paths.
            return union_type

        mapping: Dict[str, Type] = {name: arg for name, arg in zip(params, type_args)}
        new_fields = tuple(
            UnionField(name=field.name, field_type=self._substitute_generic(field.field_type, mapping))
            for field in union_type.fields
        )
        return UnionType(name=union_type.name, fields=new_fields, generic_params=())

    def _resolve_generic_instance_union(self, instance: GenericInstanceType) -> Optional[UnionType]:
        """Resolve GenericInstanceType(base, args) to a concrete UnionType if base is a union."""
        symbol = self.symbols.lookup(instance.base_name)
        if not symbol or not isinstance(symbol.type, UnionType):
            return None
        return self._instantiate_union_type(symbol.type, list(instance.type_args))
