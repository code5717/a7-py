"""
Semantic validation pass for A7.

Validates semantic rules beyond type checking:
- Control flow (break/continue in loops, return paths)
- Memory management (new/del matching, defer scoping)
- A7-specific rules (nil only for ref types, etc.)
"""

from typing import List, Optional, Set

from a7.ast_nodes import ASTNode, NodeKind, LiteralKind
from a7.symbol_table import SymbolTable
from a7.semantic_context import SemanticContext
from a7.types import Type, TypeKind, ReferenceType, EnumType
from a7.errors import SemanticError, SemanticErrorType, SourceSpan


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
        self._function_graph: dict[str, set[str]] = {}
        self._function_spans: dict[str, Optional[SourceSpan]] = {}
        self._function_param_call_positions: dict[str, set[int]] = {}
        self._function_param_invocations: dict[str, list[tuple[int, list[Optional[int]]]]] = {}

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

        self._validate_fall_usage(program)

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

        self._validate_no_recursion(node)

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
                self._report_unreachable_in_block(nd.statements or [])
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
                    else_statements = self._as_statement_list(nd.else_case)
                    self._report_unreachable_in_block(else_statements)
                    for stmt in reversed(else_statements):
                        stack.append(('visit_stmt', stmt))
                # Schedule case branches
                if nd.cases:
                    for case in reversed(nd.cases):
                        case_stmt = getattr(case, "statement", None)
                        if case_stmt:
                            stack.append(('visit_stmt', case_stmt))
                        elif case.statements:
                            self._report_unreachable_in_block(case.statements)
                            for stmt in reversed(case.statements):
                                stack.append(('visit_stmt', stmt))

            elif nd.kind == NodeKind.BREAK:
                self.visit_break_stmt(nd)
            elif nd.kind == NodeKind.CONTINUE:
                self.visit_continue_stmt(nd)
            elif nd.kind == NodeKind.RETURN:
                self.visit_return_stmt(nd)
            elif nd.kind == NodeKind.FALL:
                self.visit_fall_stmt(nd)
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

    def visit_fall_stmt(self, node: ASTNode) -> None:
        """Validate a fallthrough statement.

        Exact placement rules are checked in a separate structural pass because
        the main visitor intentionally visits match branches without parent
        context.
        """
        return

    def _validate_fall_usage(self, program: ASTNode) -> None:
        """Validate the intentionally narrow source-language `fall` contract."""
        stack: list[tuple[ASTNode, bool]] = [(program, False)]

        while stack:
            node, inside_allowed_fall_site = stack.pop()
            if node is None:
                continue

            if node.kind == NodeKind.MATCH:
                cases = node.cases or []
                for index, case in enumerate(cases):
                    statements = self._case_direct_statements(case)
                    fall_positions = [
                        pos for pos, stmt in enumerate(statements)
                        if stmt.kind == NodeKind.FALL
                    ]

                    for pos in fall_positions:
                        if index == len(cases) - 1:
                            self.add_error(
                                SemanticErrorType.UNSUPPORTED_FALLTHROUGH,
                                statements[pos].span,
                                "fall cannot appear in the final match case",
                            )
                        elif pos != len(statements) - 1:
                            self.add_error(
                                SemanticErrorType.UNSUPPORTED_FALLTHROUGH,
                                statements[pos].span,
                                "fall must be the final statement in its match case",
                            )

                    for stmt in statements:
                        stack.append((stmt, stmt.kind == NodeKind.FALL))

                for stmt in self._as_statement_list(node.else_case):
                    stack.append((stmt, False))

                self._push_non_match_children(node, stack, skip_case_bodies=True)
                continue

            if node.kind == NodeKind.FALL:
                if not inside_allowed_fall_site:
                    self.add_error(
                        SemanticErrorType.UNSUPPORTED_FALLTHROUGH,
                        node.span,
                        "fall can only be the final direct statement of a non-final match case",
                    )
                continue

            self._push_non_match_children(node, stack)

    def _case_direct_statements(self, case: ASTNode) -> List[ASTNode]:
        case_stmt = getattr(case, "statement", None)
        if case_stmt is None:
            return list(getattr(case, "statements", None) or [])
        if case_stmt.kind == NodeKind.BLOCK:
            return list(case_stmt.statements or [])
        return [case_stmt]

    def _push_non_match_children(
        self,
        node: ASTNode,
        stack: list[tuple[ASTNode, bool]],
        *,
        skip_case_bodies: bool = False,
    ) -> None:
        child_attrs = (
            "declarations", "statements", "body", "then_stmt", "else_stmt",
            "init", "update", "expression", "condition", "value", "target",
            "function", "arguments", "field_inits", "elements", "operand",
            "left", "right", "pointer", "then_expr", "else_expr", "iterable",
            "statement", "patterns", "object", "index", "literal", "start",
            "end", "explicit_type", "param_type", "return_type", "target_type",
            "element_type", "parameter_types", "type_args", "type_arguments",
            "fields", "parameters", "variants",
        )
        if not skip_case_bodies:
            child_attrs = child_attrs + ("cases", "else_case")
        for attr_name in child_attrs:
            val = getattr(node, attr_name, None)
            if isinstance(val, ASTNode):
                stack.append((val, False))
            elif isinstance(val, list):
                for item in reversed(val):
                    if isinstance(item, ASTNode):
                        stack.append((item, False))

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

    def _validate_no_recursion(self, program: ASTNode) -> None:
        """Reject direct and mutual recursion between top-level functions."""
        functions = {
            decl.name: decl
            for decl in program.declarations or []
            if decl.kind == NodeKind.FUNCTION and decl.name
        }
        self._function_spans = {name: func.span for name, func in functions.items()}
        self._function_param_call_positions = {}
        self._function_param_invocations = {}
        for name, func in functions.items():
            positions, invocations = self._collect_called_parameter_usage(func)
            self._function_param_call_positions[name] = positions
            self._function_param_invocations[name] = invocations
        self._function_graph = {
            name: self._collect_function_calls(func, set(functions))
            for name, func in functions.items()
        }

        reported_nodes: set[str] = set()
        for name in functions:
            if name in reported_nodes:
                continue
            path = self._find_recursion_path(name)
            if not path:
                continue
            reported_nodes.update(path)
            self.add_error(
                SemanticErrorType.RECURSION_NOT_ALLOWED,
                self._function_spans.get(name),
                f"Cycle: {' -> '.join(path)}",
            )

    def _find_recursion_path(self, start: str) -> Optional[list[str]]:
        stack: list[tuple[str, list[str]]] = [(start, [start])]
        while stack:
            current, path = stack.pop()
            for callee in sorted(self._function_graph.get(current, set()), reverse=True):
                if callee == start:
                    return path + [callee]
                if callee in path:
                    continue
                stack.append((callee, path + [callee]))
        return None

    def _collect_function_calls(self, function: ASTNode, function_names: set[str]) -> set[str]:
        if function.body is None:
            return set()

        calls: set[str] = set()
        function_aliases = self._collect_function_aliases(function, function_names)
        shadowed = {
            param.name
            for param in function.parameters or []
            if param.name in function_names
        }
        stack: list[tuple[str, object, int, set[str]]] = [
            ("stmt", function.body, 0, shadowed)
        ]

        while stack:
            action, payload, index, active_shadowed = stack.pop()

            if action == "stmt_list":
                statements = payload if isinstance(payload, list) else []
                if index >= len(statements):
                    continue
                next_shadowed = self._schedule_statement_calls(
                    statements[index],
                    function_names,
                    function_aliases,
                    set(active_shadowed),
                    calls,
                    stack,
                )
                stack.append(("stmt_list", statements, index + 1, next_shadowed))
                continue

            if isinstance(payload, ASTNode):
                self._schedule_statement_calls(
                    payload,
                    function_names,
                    function_aliases,
                    set(active_shadowed),
                    calls,
                    stack,
                )

        return calls

    def _schedule_statement_calls(
        self,
        node: ASTNode,
        function_names: set[str],
        function_aliases: dict[str, str],
        shadowed: set[str],
        calls: set[str],
        stack: list[tuple[str, object, int, set[str]]],
    ) -> set[str]:
        """Collect calls in one statement and schedule nested statement scopes."""
        if node.kind == NodeKind.BLOCK:
            stack.append(("stmt_list", node.statements or [], 0, set(shadowed)))

        elif node.kind in (NodeKind.VAR, NodeKind.CONST):
            if node.value:
                calls.update(self._collect_expression_calls(node.value, function_names, function_aliases, shadowed))
            if node.name in function_names:
                shadowed.add(node.name)

        elif node.kind == NodeKind.FUNCTION:
            # Nested functions introduce a local name for following statements.
            # Their bodies are validated independently where supported; they are
            # not calls made by the containing function.
            if node.name in function_names:
                shadowed.add(node.name)

        elif node.kind == NodeKind.EXPRESSION_STMT:
            if node.expression:
                calls.update(self._collect_expression_calls(node.expression, function_names, function_aliases, shadowed))

        elif node.kind == NodeKind.RETURN:
            if node.value:
                calls.update(self._collect_expression_calls(node.value, function_names, function_aliases, shadowed))

        elif node.kind == NodeKind.ASSIGNMENT:
            if node.target:
                calls.update(self._collect_expression_calls(node.target, function_names, function_aliases, shadowed))
            if node.value:
                calls.update(self._collect_expression_calls(node.value, function_names, function_aliases, shadowed))

        elif node.kind == NodeKind.DEL:
            if node.expression:
                calls.update(self._collect_expression_calls(node.expression, function_names, function_aliases, shadowed))

        elif node.kind == NodeKind.DEFER:
            if node.expression:
                calls.update(self._collect_expression_calls(node.expression, function_names, function_aliases, shadowed))
            if node.statement:
                stack.append(("stmt", node.statement, 0, set(shadowed)))

        elif node.kind == NodeKind.IF_STMT:
            if node.condition:
                calls.update(self._collect_expression_calls(node.condition, function_names, function_aliases, shadowed))
            if node.then_stmt:
                stack.append(("stmt", node.then_stmt, 0, set(shadowed)))
            if node.else_stmt:
                stack.append(("stmt", node.else_stmt, 0, set(shadowed)))

        elif node.kind == NodeKind.WHILE:
            if node.condition:
                calls.update(self._collect_expression_calls(node.condition, function_names, function_aliases, shadowed))
            if node.body:
                stack.append(("stmt", node.body, 0, set(shadowed)))

        elif node.kind == NodeKind.FOR:
            loop_shadowed = set(shadowed)
            if node.init:
                loop_shadowed = self._schedule_statement_calls(
                    node.init,
                    function_names,
                    function_aliases,
                    loop_shadowed,
                    calls,
                    stack,
                )
            if node.condition:
                calls.update(self._collect_expression_calls(node.condition, function_names, function_aliases, loop_shadowed))
            if node.update:
                calls.update(self._collect_expression_calls(node.update, function_names, function_aliases, loop_shadowed))
            if node.body:
                stack.append(("stmt", node.body, 0, loop_shadowed))

        elif node.kind in (NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED):
            loop_shadowed = set(shadowed)
            if node.iterable:
                calls.update(self._collect_expression_calls(node.iterable, function_names, function_aliases, loop_shadowed))
            if node.iterator in function_names:
                loop_shadowed.add(node.iterator)
            if node.index_var in function_names:
                loop_shadowed.add(node.index_var)
            if node.body:
                stack.append(("stmt", node.body, 0, loop_shadowed))

        elif node.kind == NodeKind.MATCH:
            if node.expression:
                calls.update(self._collect_expression_calls(node.expression, function_names, function_aliases, shadowed))
            for case in node.cases or []:
                case_stmt = getattr(case, "statement", None)
                if case_stmt:
                    stack.append(("stmt", case_stmt, 0, set(shadowed)))
                else:
                    stack.append(("stmt_list", case.statements or [], 0, set(shadowed)))
            else_statements = self._as_statement_list(node.else_case)
            if else_statements:
                stack.append(("stmt_list", else_statements, 0, set(shadowed)))

        return shadowed

    def _collect_expression_calls(
        self,
        root: Optional[ASTNode],
        function_names: set[str],
        function_aliases: dict[str, str],
        shadowed: set[str],
    ) -> set[str]:
        if root is None:
            return set()

        calls: set[str] = set()
        stack = [root]
        while stack:
            node = stack.pop()
            if node is None:
                continue

            if node.kind == NodeKind.CALL:
                callee = self._direct_callee_name(node, function_aliases, shadowed)
                if callee in function_names:
                    calls.add(callee)
                    calls.update(
                        self._collect_higher_order_argument_calls(
                            callee,
                            node.arguments or [],
                            function_names,
                            function_aliases,
                            shadowed,
                        )
                    )

            if node.kind == NodeKind.FUNCTION:
                continue

            for child in self._iter_child_nodes(node):
                stack.append(child)
        return calls

    def _collect_higher_order_argument_calls(
        self,
        callee: str,
        arguments: list[ASTNode],
        function_names: set[str],
        function_aliases: dict[str, str],
        shadowed: set[str],
    ) -> set[str]:
        """Conservatively model calls made through function-typed parameters.

        If `callee` calls one of its parameters as a function, then passing a
        top-level function into that parameter can create a recursion cycle even
        though the immediate callee is only the trampoline. Add graph edges to
        those top-level function arguments so cycle detection sees the path.
        """
        calls: set[str] = set()
        for position in self._function_param_call_positions.get(callee, set()):
            if position >= len(arguments):
                continue
            target = self._function_value_name(arguments[position], function_names, function_aliases, shadowed)
            if target:
                calls.add(target)
        for callback_position, forwarded_positions in self._function_param_invocations.get(callee, []):
            if callback_position >= len(arguments):
                continue
            callback_target = self._function_value_name(
                arguments[callback_position],
                function_names,
                function_aliases,
                shadowed,
            )
            if not callback_target:
                continue
            for called_position in self._function_param_call_positions.get(callback_target, set()):
                if called_position >= len(forwarded_positions):
                    continue
                forwarded_position = forwarded_positions[called_position]
                if forwarded_position is None or forwarded_position >= len(arguments):
                    continue
                target = self._function_value_name(
                    arguments[forwarded_position],
                    function_names,
                    function_aliases,
                    shadowed,
                )
                if target:
                    calls.add(target)
        return calls

    def _function_value_name(
        self,
        node: Optional[ASTNode],
        function_names: set[str],
        function_aliases: dict[str, str],
        shadowed: set[str],
    ) -> Optional[str]:
        if node is None or node.kind != NodeKind.IDENTIFIER or not node.name:
            return None
        if node.name in function_aliases:
            return function_aliases[node.name]
        if node.name in shadowed:
            return None
        if node.name in function_names:
            return node.name
        return None

    def _direct_callee_name(
        self,
        node: ASTNode,
        function_aliases: dict[str, str],
        shadowed: set[str],
    ) -> Optional[str]:
        if node.kind != NodeKind.CALL or not node.function:
            return None
        function = node.function
        if function.kind != NodeKind.IDENTIFIER or not function.name:
            return None
        if function.name in function_aliases:
            return function_aliases[function.name]
        if function.name in shadowed:
            return None
        return function.name

    def _collect_called_parameter_usage(
        self,
        function: ASTNode,
    ) -> tuple[set[int], list[tuple[int, list[Optional[int]]]]]:
        """Return callback parameter use and simple forwarding summaries."""
        param_positions = {
            param.name: index
            for index, param in enumerate(function.parameters or [])
            if getattr(param, "name", None)
        }
        if function.body is None or not param_positions:
            return set(), []

        called: set[int] = set()
        invocations: list[tuple[int, list[Optional[int]]]] = []
        stack: list[tuple[str, object, int, set[str], dict[str, int]]] = [
            ("stmt", function.body, 0, set(), {})
        ]

        while stack:
            action, payload, index, shadowed, aliases = stack.pop()

            if action == "stmt_list":
                statements = payload if isinstance(payload, list) else []
                if index >= len(statements):
                    continue
                next_shadowed, next_aliases = self._schedule_parameter_call_positions(
                    statements[index],
                    param_positions,
                    set(shadowed),
                    dict(aliases),
                    called,
                    invocations,
                    stack,
                )
                stack.append(("stmt_list", statements, index + 1, next_shadowed, next_aliases))
                continue

            if isinstance(payload, ASTNode):
                self._schedule_parameter_call_positions(
                    payload,
                    param_positions,
                    set(shadowed),
                    dict(aliases),
                    called,
                    invocations,
                    stack,
                )

        return called, invocations

    def _schedule_parameter_call_positions(
        self,
        node: ASTNode,
        param_positions: dict[str, int],
        shadowed: set[str],
        aliases: dict[str, int],
        called: set[int],
        invocations: list[tuple[int, list[Optional[int]]]],
        stack: list[tuple[str, object, int, set[str], dict[str, int]]],
    ) -> tuple[set[str], dict[str, int]]:
        """Collect parameter-as-callee uses in one statement."""
        if node.kind == NodeKind.BLOCK:
            stack.append(("stmt_list", node.statements or [], 0, set(shadowed), dict(aliases)))

        elif node.kind in (NodeKind.VAR, NodeKind.CONST):
            if node.value:
                called.update(
                    self._collect_expression_parameter_calls(
                        node.value,
                        param_positions,
                        shadowed,
                        aliases,
                        invocations,
                    )
                )
                target = self._parameter_value_position(node.value, param_positions, shadowed, aliases)
                if target is not None and node.name:
                    aliases[node.name] = target
            if node.name:
                if node.name in param_positions:
                    shadowed.add(node.name)
                elif node.name in aliases and self._parameter_value_position(node.value, param_positions, shadowed, aliases) is None:
                    aliases.pop(node.name, None)

        elif node.kind == NodeKind.FUNCTION:
            if node.name:
                shadowed.add(node.name)
                aliases.pop(node.name, None)

        elif node.kind == NodeKind.EXPRESSION_STMT:
            if node.expression:
                called.update(self._collect_expression_parameter_calls(node.expression, param_positions, shadowed, aliases, invocations))

        elif node.kind == NodeKind.RETURN:
            if node.value:
                called.update(self._collect_expression_parameter_calls(node.value, param_positions, shadowed, aliases, invocations))

        elif node.kind == NodeKind.ASSIGNMENT:
            if node.target:
                called.update(self._collect_expression_parameter_calls(node.target, param_positions, shadowed, aliases, invocations))
            if node.value:
                called.update(self._collect_expression_parameter_calls(node.value, param_positions, shadowed, aliases, invocations))
                if node.target and node.target.kind == NodeKind.IDENTIFIER and node.target.name:
                    target = self._parameter_value_position(node.value, param_positions, shadowed, aliases)
                    if target is not None:
                        aliases[node.target.name] = target
                    else:
                        aliases.pop(node.target.name, None)

        elif node.kind == NodeKind.DEFER:
            if node.expression:
                called.update(self._collect_expression_parameter_calls(node.expression, param_positions, shadowed, aliases, invocations))
            if node.statement:
                stack.append(("stmt", node.statement, 0, set(shadowed), dict(aliases)))

        elif node.kind == NodeKind.DEL:
            if node.expression:
                called.update(self._collect_expression_parameter_calls(node.expression, param_positions, shadowed, aliases, invocations))

        elif node.kind == NodeKind.IF_STMT:
            if node.condition:
                called.update(self._collect_expression_parameter_calls(node.condition, param_positions, shadowed, aliases, invocations))
            if node.then_stmt:
                stack.append(("stmt", node.then_stmt, 0, set(shadowed), dict(aliases)))
            if node.else_stmt:
                stack.append(("stmt", node.else_stmt, 0, set(shadowed), dict(aliases)))

        elif node.kind == NodeKind.WHILE:
            if node.condition:
                called.update(self._collect_expression_parameter_calls(node.condition, param_positions, shadowed, aliases, invocations))
            if node.body:
                stack.append(("stmt", node.body, 0, set(shadowed), dict(aliases)))

        elif node.kind == NodeKind.FOR:
            loop_shadowed = set(shadowed)
            loop_aliases = dict(aliases)
            if node.init:
                loop_shadowed, loop_aliases = self._schedule_parameter_call_positions(
                    node.init,
                    param_positions,
                    loop_shadowed,
                    loop_aliases,
                    called,
                    invocations,
                    stack,
                )
            if node.condition:
                called.update(self._collect_expression_parameter_calls(node.condition, param_positions, loop_shadowed, loop_aliases, invocations))
            if node.update:
                called.update(self._collect_expression_parameter_calls(node.update, param_positions, loop_shadowed, loop_aliases, invocations))
            if node.body:
                stack.append(("stmt", node.body, 0, loop_shadowed, loop_aliases))

        elif node.kind in (NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED):
            loop_shadowed = set(shadowed)
            loop_aliases = dict(aliases)
            if node.iterable:
                called.update(self._collect_expression_parameter_calls(node.iterable, param_positions, loop_shadowed, loop_aliases, invocations))
            for name in (node.iterator, node.index_var):
                if name:
                    if name in param_positions:
                        loop_shadowed.add(name)
                    loop_aliases.pop(name, None)
            if node.body:
                stack.append(("stmt", node.body, 0, loop_shadowed, loop_aliases))

        elif node.kind == NodeKind.MATCH:
            if node.expression:
                called.update(self._collect_expression_parameter_calls(node.expression, param_positions, shadowed, aliases, invocations))
            for case in node.cases or []:
                case_stmt = getattr(case, "statement", None)
                if case_stmt:
                    stack.append(("stmt", case_stmt, 0, set(shadowed), dict(aliases)))
                else:
                    stack.append(("stmt_list", case.statements or [], 0, set(shadowed), dict(aliases)))
            else_statements = self._as_statement_list(node.else_case)
            if else_statements:
                stack.append(("stmt_list", else_statements, 0, set(shadowed), dict(aliases)))

        return shadowed, aliases

    def _collect_expression_parameter_calls(
        self,
        root: Optional[ASTNode],
        param_positions: dict[str, int],
        shadowed: set[str],
        aliases: dict[str, int],
        invocations: list[tuple[int, list[Optional[int]]]],
    ) -> set[int]:
        if root is None:
            return set()

        called: set[int] = set()
        stack = [root]
        while stack:
            node = stack.pop()
            if node is None:
                continue
            if node.kind == NodeKind.CALL:
                position = self._parameter_callee_position(node, param_positions, shadowed, aliases)
                if position is not None:
                    called.add(position)
                    invocations.append(
                        (
                            position,
                            [
                                self._parameter_value_position(arg, param_positions, shadowed, aliases)
                                for arg in (node.arguments or [])
                            ],
                        )
                    )
            if node.kind == NodeKind.FUNCTION:
                continue
            for child in self._iter_child_nodes(node):
                stack.append(child)
        return called

    def _parameter_callee_position(
        self,
        node: ASTNode,
        param_positions: dict[str, int],
        shadowed: set[str],
        aliases: dict[str, int],
    ) -> Optional[int]:
        if node.kind != NodeKind.CALL or not node.function:
            return None
        function = node.function
        if function.kind != NodeKind.IDENTIFIER or not function.name:
            return None
        if function.name in aliases:
            return aliases[function.name]
        if function.name in shadowed:
            return None
        return param_positions.get(function.name)

    def _parameter_value_position(
        self,
        node: Optional[ASTNode],
        param_positions: dict[str, int],
        shadowed: set[str],
        aliases: dict[str, int],
    ) -> Optional[int]:
        if node is None or node.kind != NodeKind.IDENTIFIER or not node.name:
            return None
        if node.name in aliases:
            return aliases[node.name]
        if node.name in shadowed:
            return None
        return param_positions.get(node.name)

    def _collect_function_aliases(self, function: ASTNode, function_names: set[str]) -> dict[str, str]:
        """Find local names that may hold top-level functions.

        A7 forbids source recursion. Calls through function-typed local aliases
        are therefore treated conservatively as calls to the aliased top-level
        function. This intentionally prefers rejecting ambiguous cycles over
        allowing recursion through an indirection.
        """
        aliases: dict[str, str] = {}
        if function.body is None:
            return aliases

        stack = [function.body]
        while stack:
            node = stack.pop()
            if not isinstance(node, ASTNode) or node.kind == NodeKind.FUNCTION:
                continue

            target_name: Optional[str] = None
            value: Optional[ASTNode] = None
            if node.kind in (NodeKind.VAR, NodeKind.CONST):
                target_name = node.name
                value = node.value
            elif node.kind == NodeKind.ASSIGNMENT and node.target and node.target.kind == NodeKind.IDENTIFIER:
                target_name = node.target.name
                value = node.value

            if (
                target_name
                and value
                and value.kind == NodeKind.IDENTIFIER
                and value.name in function_names
            ):
                aliases[target_name] = value.name

            stack.extend(self._iter_child_nodes(node))

        return aliases

    def _as_statement_list(self, value: object) -> List[ASTNode]:
        if isinstance(value, ASTNode):
            return [value]
        if isinstance(value, list):
            return [item for item in value if isinstance(item, ASTNode)]
        return []

    def _iter_child_nodes(self, node: ASTNode) -> List[ASTNode]:
        children: List[ASTNode] = []
        for attr in (
            "body",
            "value",
            "left",
            "right",
            "operand",
            "function",
            "object",
            "index",
            "start",
            "end",
            "pointer",
            "expression",
            "condition",
            "then_expr",
            "else_expr",
            "statement",
            "target",
            "literal",
            "init",
            "update",
            "iterable",
            "then_stmt",
            "else_stmt",
        ):
            child = getattr(node, attr, None)
            if isinstance(child, ASTNode):
                children.append(child)

        for attr in (
            "statements",
            "declarations",
            "parameters",
            "arguments",
            "field_inits",
            "elements",
            "cases",
            "else_case",
            "patterns",
        ):
            value = getattr(node, attr, None)
            if isinstance(value, ASTNode):
                children.append(value)
            elif value:
                children.extend(child for child in value if isinstance(child, ASTNode))
        return children

    def _report_unreachable_in_block(self, statements: List[ASTNode]) -> None:
        """Report statements that cannot execute after a block-local terminator."""
        terminated = False
        terminator: Optional[ASTNode] = None
        for stmt in statements:
            if terminated:
                self.add_error(
                    SemanticErrorType.UNREACHABLE_CODE,
                    stmt.span,
                    f"Statement after '{self._terminator_name(terminator)}' is unreachable",
                )
                continue

            if self._statement_exits_current_block(stmt):
                terminated = True
                terminator = stmt

    def _terminator_name(self, node: Optional[ASTNode]) -> str:
        if node is None:
            return "terminator"
        if node.kind == NodeKind.RETURN:
            return "ret"
        if node.kind == NodeKind.BREAK:
            return "break"
        if node.kind == NodeKind.CONTINUE:
            return "continue"
        if node.kind == NodeKind.FALL:
            return "fall"
        if node.kind == NodeKind.IF_STMT:
            return "if"
        if node.kind == NodeKind.MATCH:
            return "match"
        return node.kind.name.lower()

    def _statement_exits_current_block(self, node: Optional[ASTNode]) -> bool:
        """Return True when a statement prevents later statements in the same block."""
        if node is None:
            return False

        if node.kind == NodeKind.RETURN:
            return self.context.in_function()

        if node.kind == NodeKind.BREAK:
            return self.context.validate_break(node.label)

        if node.kind == NodeKind.CONTINUE:
            return self.context.validate_continue(node.label)

        if node.kind == NodeKind.FALL:
            return True

        if node.kind == NodeKind.BLOCK:
            return self._block_exits_current_block(node.statements or [])

        if node.kind == NodeKind.IF_STMT:
            return (
                node.then_stmt is not None
                and node.else_stmt is not None
                and self._statement_exits_current_block(node.then_stmt)
                and self._statement_exits_current_block(node.else_stmt)
            )

        if node.kind == NodeKind.MATCH:
            if not node.cases:
                return False

            for case in node.cases:
                case_stmt = getattr(case, "statement", None)
                if case_stmt is not None:
                    if not self._statement_exits_current_block(case_stmt):
                        return False
                elif not self._block_exits_current_block(getattr(case, "statements", None) or []):
                    return False

            if node.else_case:
                return self._block_exits_current_block(node.else_case)

            return self._is_match_exhaustive(node)

        return False

    def _block_exits_current_block(self, statements: List[ASTNode]) -> bool:
        for stmt in statements:
            if self._statement_exits_current_block(stmt):
                return True
        return False

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
