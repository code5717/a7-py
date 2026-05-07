"""
Semantic validation pass for A7.

Validates semantic rules beyond type checking:
- Control flow (break/continue in loops, return paths)
- Memory management (new/del matching, defer scoping)
- A7-specific rules (nil only for ref types, etc.)
"""

from typing import List, Optional, Set

from src.ast_nodes import ASTNode, NodeKind, LiteralKind
from src.symbol_table import SymbolTable
from src.semantic_context import SemanticContext
from src.types import Type, TypeKind, ReferenceType, EnumType
from src.errors import SemanticError, SemanticErrorType, SourceSpan


class SemanticValidationPass:
    """
    Third pass of semantic analysis.

    Validates:
    1. Control flow correctness (break/continue context)
    2. Return path analysis
    3. Memory management (new/del, defer)
    4. A7-specific semantic rules
    """

    def __init__(self, symbols: SymbolTable, node_types: dict):
        """
        Initialize semantic validation pass.

        Args:
            symbols: Symbol table from name resolution
            node_types: Type information from type checker
        """
        self.symbols = symbols
        self.node_types = node_types
        self.context = SemanticContext()
        self.errors: List[SemanticError] = []
        self.current_file: str = "<unknown>"
        self.source_lines: List[str] = []

        # Track allocations for new/del validation
        self.allocations: Set[str] = set()

    def analyze(self, program: ASTNode, filename: str = "<unknown>") -> None:
        """
        Perform semantic validation on a program.

        Args:
            program: Root program node
            filename: Source file name

        Note:
            Collects ALL errors instead of stopping at the first one.
            Check self.errors after calling to see if there were any issues.
        """
        self.current_file = filename
        self.errors = []

        # Visit the program
        self.visit_program(program)

        # Caller should check self.errors

    def add_error(
        self,
        error_type: SemanticErrorType,
        span: Optional[SourceSpan] = None,
        context: Optional[str] = None,
    ) -> None:
        """Add a semantic validation error with structured type."""
        error = SemanticError.from_type(
            error_type,
            span=span,
            filename=self.current_file,
            source_lines=self.source_lines,
            context=context,
        )
        self.errors.append(error)

    def get_type(self, node: ASTNode) -> Optional[Type]:
        """Get the type of an AST node."""
        return self.node_types.get(id(node))

    # Visitor methods

    def visit_program(self, node: ASTNode) -> None:
        """Visit program root."""
        if node.kind != NodeKind.PROGRAM:
            self.add_error(SemanticErrorType.UNEXPECTED_NODE_KIND, node.span, f"Expected program node, got {node.kind}")
            return

        # Visit all declarations
        for decl in node.declarations or []:
            self.visit_declaration(decl)

    def visit_declaration(self, node: ASTNode) -> None:
        """Visit a top-level declaration."""
        if node.kind == NodeKind.FUNCTION:
            self.visit_function_decl(node)
        # Other declarations don't need validation

    def visit_function_decl(self, node: ASTNode) -> None:
        """Visit and validate a function declaration."""
        func_name = node.name or "<anonymous>"

        # Get return type from node
        return_type = None  # Will be set based on return_type node

        # Enter function context
        self.context.enter_function(func_name, return_type, node)

        # Visit body
        if node.body:
            self.visit_statement(node.body)

        # Check for non-void functions without return on all paths
        if node.return_type and node.body:
            if not self._returns_on_all_paths(node.body):
                self.add_error(
                    SemanticErrorType.MISSING_RETURN,
                    node.span,
                    f"Function '{func_name}' does not return on all paths"
                )

        # Exit function context
        self.context.exit_function()

    def visit_statement(self, node: ASTNode) -> None:
        """Visit a statement (iterative)."""
        # Stack items: ('visit_stmt', node) or ('action', callable)
        stack: list = [('visit_stmt', node)]

        while stack:
            action, item = stack.pop()

            if action == 'action':
                item()  # Execute deferred action
                continue

            if action == 'visit_expr':
                self._visit_expression_iterative(item)
                continue

            # action == 'visit_stmt'
            nd = item
            if nd.kind == NodeKind.BLOCK:
                scope_depth = self.symbols.get_scope_depth()
                # Schedule: pop defers after block statements
                stack.append(('action', lambda sd=scope_depth: self.context.pop_defers_at_depth(sd)))
                # Push statements in reverse so first executes first
                for stmt in reversed(nd.statements or []):
                    stack.append(('visit_stmt', stmt))

            elif nd.kind == NodeKind.IF_STMT:
                if nd.else_stmt:
                    stack.append(('visit_stmt', nd.else_stmt))
                if nd.then_stmt:
                    stack.append(('visit_stmt', nd.then_stmt))

            elif nd.kind == NodeKind.WHILE:
                self.context.enter_loop(nd.label)
                stack.append(('action', lambda: self.context.exit_loop()))
                if nd.body:
                    stack.append(('visit_stmt', nd.body))

            elif nd.kind == NodeKind.FOR:
                self.context.enter_loop(nd.label)
                stack.append(('action', lambda: self.context.exit_loop()))
                if nd.body:
                    stack.append(('visit_stmt', nd.body))
                if nd.init:
                    stack.append(('visit_stmt', nd.init))

            elif nd.kind in (NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED):
                self.context.enter_loop(nd.label)
                stack.append(('action', lambda: self.context.exit_loop()))
                if nd.body:
                    stack.append(('visit_stmt', nd.body))

            elif nd.kind == NodeKind.MATCH:
                # Schedule else case
                if nd.else_case:
                    for stmt in reversed(nd.else_case):
                        stack.append(('visit_stmt', stmt))
                # Schedule case branches
                if nd.cases:
                    for case in reversed(nd.cases):
                        case_stmt = getattr(case, "statement", None)
                        if case_stmt:
                            stack.append(('visit_stmt', case_stmt))
                        elif case.statements:
                            for stmt in reversed(case.statements):
                                stack.append(('visit_stmt', stmt))

            elif nd.kind == NodeKind.BREAK:
                self.visit_break_stmt(nd)
            elif nd.kind == NodeKind.CONTINUE:
                self.visit_continue_stmt(nd)
            elif nd.kind == NodeKind.RETURN:
                self.visit_return_stmt(nd)
            elif nd.kind == NodeKind.DEFER:
                self.visit_defer_stmt(nd)
            elif nd.kind == NodeKind.DEL:
                self.visit_del_stmt(nd)

            elif nd.kind == NodeKind.EXPRESSION_STMT:
                if nd.expression:
                    stack.append(('visit_expr', nd.expression))

            elif nd.kind in (NodeKind.VAR, NodeKind.CONST):
                if nd.value:
                    stack.append(('visit_expr', nd.value))

            elif nd.kind == NodeKind.ASSIGNMENT:
                if nd.value:
                    stack.append(('visit_expr', nd.value))
                if nd.target:
                    stack.append(('visit_expr', nd.target))

    def visit_break_stmt(self, node: ASTNode) -> None:
        """Validate a break statement."""
        if not self.context.validate_break(node.label):
            if node.label:
                self.add_error(SemanticErrorType.BREAK_UNDEFINED_LABEL, node.span, f"Label '{node.label}'")
            else:
                self.add_error(SemanticErrorType.BREAK_OUTSIDE_LOOP, node.span)
        else:
            self.context.mark_loop_has_break()

    def visit_continue_stmt(self, node: ASTNode) -> None:
        """Validate a continue statement."""
        if not self.context.validate_continue(node.label):
            if node.label:
                self.add_error(SemanticErrorType.CONTINUE_UNDEFINED_LABEL, node.span, f"Label '{node.label}'")
            else:
                self.add_error(SemanticErrorType.CONTINUE_OUTSIDE_LOOP, node.span)
        else:
            self.context.mark_loop_has_continue()

    def visit_return_stmt(self, node: ASTNode) -> None:
        """Validate a return statement."""
        if not self.context.in_function():
            self.add_error(SemanticErrorType.RETURN_OUTSIDE_FUNCTION, node.span)
            return

        # Mark function as having return
        self.context.mark_function_returns()

        # RETURN nodes store their payload in `value`.
        if node.value:
            self.visit_expression(node.value)

    def visit_defer_stmt(self, node: ASTNode) -> None:
        """Validate a defer statement."""
        if not self.context.in_function():
            self.add_error(SemanticErrorType.DEFER_OUTSIDE_FUNCTION, node.span)
            return

        # Add defer to context and validate the deferred statement.
        scope_depth = self.symbols.get_scope_depth()
        deferred_stmt = getattr(node, "statement", None)
        if deferred_stmt:
            self.context.add_defer(deferred_stmt, scope_depth)
            self.visit_statement(deferred_stmt)
        elif node.expression:
            self.context.add_defer(node.expression, scope_depth)
            self.visit_expression(node.expression)

    def visit_del_stmt(self, node: ASTNode) -> None:
        """Validate a del statement."""
        # Check that expression is a reference type
        if node.expression:
            self.visit_expression(node.expression)
            expr_type = self.get_type(node.expression)

            if expr_type and not isinstance(expr_type, ReferenceType):
                self.add_error(
                    SemanticErrorType.DELETE_NON_REFERENCE,
                    node.span,
                    f"Got '{expr_type}'"
                )

    def visit_expression(self, node: ASTNode) -> None:
        """Visit an expression for validation (delegates to iterative impl)."""
        self._visit_expression_iterative(node)

    def _visit_expression_iterative(self, node: ASTNode) -> None:
        """Visit an expression for validation (iterative)."""
        stack = [node]

        while stack:
            nd = stack.pop()

            if nd.kind == NodeKind.LITERAL:
                self.visit_literal_expr(nd)

            elif nd.kind == NodeKind.BINARY:
                if nd.right:
                    stack.append(nd.right)
                if nd.left:
                    stack.append(nd.left)

            elif nd.kind == NodeKind.UNARY:
                if nd.operand:
                    stack.append(nd.operand)

            elif nd.kind == NodeKind.CALL:
                if nd.arguments:
                    for arg in reversed(nd.arguments):
                        stack.append(arg)
                if nd.function:
                    stack.append(nd.function)

            elif nd.kind == NodeKind.INDEX:
                if nd.index:
                    stack.append(nd.index)
                if nd.object:
                    stack.append(nd.object)

            elif nd.kind == NodeKind.SLICE:
                if nd.end:
                    stack.append(nd.end)
                if nd.start:
                    stack.append(nd.start)
                if nd.object:
                    stack.append(nd.object)

            elif nd.kind == NodeKind.FIELD_ACCESS:
                if nd.object:
                    stack.append(nd.object)

            elif nd.kind == NodeKind.ADDRESS_OF:
                if nd.operand:
                    stack.append(nd.operand)

            elif nd.kind == NodeKind.DEREF:
                if nd.pointer:
                    stack.append(nd.pointer)

            elif nd.kind == NodeKind.CAST:
                if nd.expression:
                    stack.append(nd.expression)

            elif nd.kind == NodeKind.IF_EXPR:
                if nd.else_expr:
                    stack.append(nd.else_expr)
                if nd.then_expr:
                    stack.append(nd.then_expr)
                if nd.condition:
                    stack.append(nd.condition)

            elif nd.kind == NodeKind.STRUCT_INIT:
                if nd.field_inits:
                    for fi in reversed(nd.field_inits):
                        if fi.value:
                            stack.append(fi.value)

            elif nd.kind == NodeKind.ARRAY_INIT:
                if nd.elements:
                    for elem in reversed(nd.elements):
                        stack.append(elem)

            elif nd.kind == NodeKind.NEW_EXPR:
                self.visit_new_expr(nd)

    def visit_literal_expr(self, node: ASTNode) -> None:
        """Validate a literal expression."""
        # Validate nil usage
        if node.literal_kind == LiteralKind.NIL:
            # nil can only be assigned to reference types
            # This is checked in type checker, but we can add extra validation here
            expr_type = self.get_type(node)
            # Context-dependent validation would go here
            pass

    def visit_new_expr(self, node: ASTNode) -> None:
        """Validate a new expression."""
        # Track that a new allocation occurred
        # In a more complete implementation, we'd track which variable
        # holds the reference and ensure it's del'd before going out of scope
        if node.target_type:
            alloc_type = node.target_type
            # Could track allocation for leak detection
            pass

    def _returns_on_all_paths(self, node: ASTNode) -> bool:
        """Check if a node returns on all execution paths (iterative)."""
        # Use an iterative approach: drill down through blocks/ifs/matches
        current = node
        while current is not None:
            if current.kind == NodeKind.RETURN:
                return True

            if current.kind == NodeKind.BLOCK:
                stmts = current.statements or []
                if not stmts:
                    return False
                current = stmts[-1]
                continue

            if current.kind == NodeKind.IF_STMT:
                if current.else_stmt is None:
                    return False
                # Both branches must return — check each iteratively
                if not self._returns_on_all_paths(current.then_stmt):
                    return False
                current = current.else_stmt
                continue

            if current.kind == NodeKind.MATCH:
                # Check all case branches
                for case in (current.cases or []):
                    case_stmt = getattr(case, "statement", None)
                    if case_stmt is not None:
                        if not self._returns_on_all_paths(case_stmt):
                            return False
                    else:
                        case_stmts = getattr(case, "statements", None)
                        if case_stmts:
                            if not self._returns_on_all_paths(case_stmts[-1]):
                                return False
                        else:
                            return False
                # Else branch, if present, must return as well.
                if current.else_case:
                    else_stmts = current.else_case or []
                    if not else_stmts:
                        return False
                    return self._returns_on_all_paths(else_stmts[-1])

                # Without else, only exhaustive bool/enum matches can be total.
                return self._is_match_exhaustive(current)

            # Any other node kind doesn't return
            return False

        return False

    def _is_match_exhaustive(self, node: ASTNode) -> bool:
        """Check whether a match statement covers all values for bool/enum scrutinees."""
        if node.else_case:
            return True

        scrutinee_type = self.get_type(node.expression) if node.expression else None
        if scrutinee_type is None:
            return False

        bool_coverage: Set[bool] = set()
        enum_coverage: Set[str] = set()

        for case in (node.cases or []):
            for pattern in (case.patterns or []):
                if self._pattern_is_wildcard(pattern):
                    return True

                if scrutinee_type.is_boolean():
                    bool_value = self._extract_bool_pattern_value(pattern)
                    if bool_value is not None:
                        bool_coverage.add(bool_value)

                if isinstance(scrutinee_type, EnumType):
                    variant_name = self._extract_enum_pattern_variant(pattern, scrutinee_type.name)
                    if variant_name:
                        enum_coverage.add(variant_name)

        if scrutinee_type.is_boolean():
            return bool_coverage == {True, False}

        if isinstance(scrutinee_type, EnumType):
            declared_variants = {variant.name for variant in scrutinee_type.variants}
            return declared_variants.issubset(enum_coverage)

        return False

    def _pattern_is_wildcard(self, pattern: ASTNode) -> bool:
        """Return True when a match pattern is a wildcard branch."""
        if pattern.kind == NodeKind.PATTERN_WILDCARD:
            return True
        return pattern.kind == NodeKind.PATTERN_IDENTIFIER and (pattern.name or "") == "_"

    def _extract_bool_pattern_value(self, pattern: ASTNode) -> Optional[bool]:
        """Extract bool literal value from a match pattern, if present."""
        if pattern.kind == NodeKind.PATTERN_LITERAL and pattern.literal:
            literal = pattern.literal
            if literal.kind == NodeKind.LITERAL and literal.literal_kind == LiteralKind.BOOLEAN:
                return bool(literal.literal_value)

        if pattern.kind == NodeKind.LITERAL and pattern.literal_kind == LiteralKind.BOOLEAN:
            return bool(pattern.literal_value)

        return None

    def _extract_enum_pattern_variant(self, pattern: ASTNode, enum_name: str) -> Optional[str]:
        """Extract enum variant name from a match pattern if it matches enum_name."""
        if pattern.kind != NodeKind.PATTERN_ENUM:
            return None

        pattern_enum = pattern.enum_type or ""
        if pattern_enum and pattern_enum != enum_name:
            return None

        return pattern.variant or None

    def validate_nil_usage(self, node: ASTNode, target_type: Type) -> bool:
        """
        Validate that nil is only used with reference types.

        Args:
            node: Literal nil node
            target_type: The type this nil is being assigned to

        Returns:
            True if usage is valid
        """
        if target_type.kind != TypeKind.REFERENCE:
            self.add_error(
                SemanticErrorType.NIL_NOT_REFERENCE_TYPE,
                node.span,
                f"Got '{target_type}'"
            )
            return False
        return True
