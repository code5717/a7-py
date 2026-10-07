"""
Semantic validation pass for A7.

Validates semantic rules beyond type checking:
- Control flow (break/continue in loops, return paths)
- Memory management (new/del matching, defer scoping)
- A7-specific rules (nil only for ref types, etc.)
"""

from dataclasses import fields
from typing import List, Optional, Set

from a7.ast_nodes import ASTNode, NodeKind, LiteralKind
from a7.symbol_table import SymbolTable
from a7.semantic_context import SemanticContext
from a7.types import Type, ReferenceType, EnumType, UnionType, GenericInstanceType, FunctionType, UnknownType
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

        # Tagged-union tag names by union name, rebuilt per analyze() from
        # top-level union declarations. UnionType carries no tagged flag,
        # so the validator resolves tagged-ness from the declaration.
        self._tagged_union_tags: dict[str, list[str]] = {}
        self._function_graph: dict[str, set[str]] = {}
        self._function_spans: dict[str, Optional[SourceSpan]] = {}
        self._function_param_call_positions: dict[str, set[int]] = {}
        self._function_param_invocations: dict[str, list[tuple[int, list[Optional[int]]]]] = {}
        # Written by _collect_expression_calls for the function being
        # scanned: the type of each function named as a value, and the callee
        # type of each call through a function value. None matches any type.
        self._function_values: dict[str, Optional[Type]] = {}
        self._indirect_call_types: list[Optional[Type]] = []
        # Nested functions found by visit_statement; visit_program validates
        # each body after the enclosing function, with an empty loop stack.
        self._pending_nested_functions: list[ASTNode] = []

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
        self._tagged_union_tags = self._collect_tagged_union_tags(program)

        self._validate_fall_usage(program)
        self._validate_match_expression_coverage(program)
        self._validate_union_match_arms(program)
        self._validate_defer_control_flow(program)

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
            while self._pending_nested_functions:
                self.visit_function_decl(self._pending_nested_functions.pop())

    def visit_declaration(self, node: ASTNode) -> None:
        """Visit a top-level declaration."""
        if node.kind == NodeKind.FUNCTION:
            self.visit_function_decl(node)
        # Other declarations don't need validation

    def visit_function_decl(self, node: ASTNode) -> None:
        """Visit and validate a function declaration."""
        func_name = node.name or "<anonymous>"

        self.context.enter_function(func_name, None, node)

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
            elif nd.kind == NodeKind.DEFER:
                deferred = self.visit_defer_stmt(nd)
                if deferred is not None:
                    stack.append(('visit_stmt', deferred))
            elif nd.kind == NodeKind.DEL:
                self.visit_del_stmt(nd)
            elif nd.kind == NodeKind.FUNCTION:
                self._pending_nested_functions.append(nd)

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

    def _validate_fall_usage(self, program: ASTNode) -> None:
        """Validate the intentionally narrow source-language `fall` contract."""
        stack: list[tuple[ASTNode, bool]] = [(program, False)]

        while stack:
            node, inside_allowed_fall_site = stack.pop()
            if node is None:
                continue

            if node.kind == NodeKind.MATCH:
                cases = node.cases or []
                tagged_union = self._match_union_name_and_tags(node)
                for index, case in enumerate(cases):
                    statements = self._case_direct_statements(case)
                    fall_positions = [
                        pos for pos, stmt in enumerate(statements)
                        if stmt.kind == NodeKind.FALL
                    ]

                    for pos in fall_positions:
                        if tagged_union is not None:
                            self.add_error(
                                SemanticErrorType.UNSUPPORTED_FALLTHROUGH,
                                statements[pos].span,
                                f"fall cannot be used in a match over tagged union '{tagged_union[0]}'; "
                                "list both tags in one case instead",
                            )
                        elif index == len(cases) - 1:
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

    def _validate_match_expression_coverage(self, program: ASTNode) -> None:
        """Every value-producing match needs a result for every input."""
        stack = [(program, False)]
        while stack:
            node, _ = stack.pop()
            # A tagged-union match gets its own error, which lists the
            # missing tags (_validate_tagged_union_match).
            if (
                node.kind == NodeKind.MATCH_EXPR
                and self._match_union_name_and_tags(node) is None
                and not self._is_match_exhaustive(node)
            ):
                self.add_error(
                    SemanticErrorType.NON_EXHAUSTIVE_MATCH,
                    node.span,
                    "match expression must cover every value; add an else or wildcard branch",
                )
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

    def visit_defer_stmt(self, node: ASTNode) -> Optional[ASTNode]:
        """Register a defer and return its statement for the traversal stack."""
        if not self.context.in_function():
            self.add_error(SemanticErrorType.DEFER_OUTSIDE_FUNCTION, node.span)
            return

        # Add defer to context and validate the deferred statement.
        scope_depth = self.symbols.get_scope_depth()
        deferred_stmt = getattr(node, "statement", None)
        if deferred_stmt:
            self.context.add_defer(deferred_stmt, scope_depth)
            return deferred_stmt
        elif node.expression:
            self.context.add_defer(node.expression, scope_depth)
            self.visit_expression(node.expression)

    def _validate_defer_control_flow(self, program: ASTNode) -> None:
        """Reject ret, break, continue and fall that would leave a deferred statement.

        A break or continue whose loop is inside the deferred statement stays
        inside it, and so does a fall whose match is inside it.
        """
        work = [program]
        while work:
            node = work.pop()
            work.extend(self._iter_child_nodes(node))
            if node.kind != NodeKind.DEFER:
                continue
            # (node, loops entered inside the defer, their labels, inside a match)
            deferred = [
                (child, 0, frozenset(), False) for child in (node.statement, node.expression)
                if child is not None
            ]
            while deferred:
                current, loops, labels, in_match = deferred.pop()
                # A nested defer is checked by the outer loop; a nested
                # function has its own control flow.
                if current.kind in (NodeKind.DEFER, NodeKind.FUNCTION):
                    continue
                if current.kind == NodeKind.RETURN:
                    leaves = True
                elif current.kind in (NodeKind.BREAK, NodeKind.CONTINUE):
                    leaves = current.label not in labels if current.label else loops == 0
                elif current.kind == NodeKind.FALL:
                    leaves = not in_match
                else:
                    leaves = False
                if leaves:
                    self.add_error(
                        SemanticErrorType.DEFER_CONTROL_FLOW,
                        current.span,
                        f"'{self._terminator_name(current)}' inside defer",
                    )
                if current.kind in (NodeKind.WHILE, NodeKind.FOR, NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED):
                    loops += 1
                    if current.label:
                        labels = labels | {current.label}
                elif current.kind == NodeKind.MATCH:
                    in_match = True
                deferred.extend(
                    (child, loops, labels, in_match) for child in self._iter_child_nodes(current)
                )

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
        """Hook for expression-level rules; the validator has none today.

        test_semantic_control_flow.py pins that a return payload reaches it.
        """

    def _validate_no_recursion(self, program: ASTNode) -> None:
        """Reject recursion in every function, including unused nested declarations.

        Each statement list has its own function namespace. Keeping those lists
        separate avoids merging unrelated nested functions that share a name.
        """
        work = [program]
        validated: set[int] = set()
        reported_top_level: set[str] = set()
        node_fields = fields(ASTNode)
        while work:
            node = work.pop()
            if node.kind == NodeKind.FUNCTION and id(node) not in validated:
                self._validate_function_group({node.name: node})
                validated.add(id(node))
            for field in node_fields:
                value = getattr(node, field.name)
                if isinstance(value, ASTNode):
                    work.append(value)
                elif isinstance(value, list):
                    children = [child for child in value if isinstance(child, ASTNode)]
                    functions = {
                        child.name: child for child in children
                        if child.kind == NodeKind.FUNCTION and child.name
                    }
                    if functions:
                        reported = self._validate_function_group(functions)
                        if node is program:
                            reported_top_level = reported
                        validated.update(id(function) for function in functions.values())
                    work.extend(reversed(children))
        self._validate_function_value_recursion(program, reported_top_level)

    def _validate_function_value_recursion(self, program: ASTNode, reported: set[str]) -> None:
        """Reject cycles that go through function values.

        A function used as a value anywhere in the program (stored, passed,
        returned, bound to a constant) may be the target of any call whose
        callee is a function value of the same function type. The graph has
        an edge to every such function from every function containing such
        a call. The analysis does not track which value reaches which call,
        so it rejects some programs that never recurse. A cycle already
        reported by the direct and alias search is not reported again.
        """
        functions = {
            decl.name: decl for decl in (program.declarations or [])
            if decl.kind == NodeKind.FUNCTION and decl.name
        }
        names = set(functions)
        self._function_param_call_positions = {}
        self._function_param_invocations = {}

        self._function_values = {}
        for decl in program.declarations or []:
            if decl.kind != NodeKind.FUNCTION:
                self._collect_expression_calls(decl, names, {}, set())

        direct: dict[str, set[str]] = {}
        indirect: dict[str, list[Optional[Type]]] = {}
        for name, function in functions.items():
            self._indirect_call_types = []
            calls: set[str] = set()
            # A nested function's body counts as part of the enclosing
            # top-level function. Its own name hides a top-level function of
            # the same name, inside its body too.
            work = [(function, set())]
            while work:
                current, hidden = work.pop()
                calls |= self._collect_function_calls(current, names, hidden, track_aliases=False)
                pending = [current.body] if current.body else []
                while pending:
                    node = pending.pop()
                    if node.kind == NodeKind.FUNCTION:
                        work.append((node, {node.name} & names))
                    else:
                        pending.extend(self._iter_child_nodes(node))
            direct[name] = calls
            indirect[name] = self._indirect_call_types

        used_as_value = self._function_values
        self._function_spans = {name: func.span for name, func in functions.items()}
        self._function_graph = {
            name: direct[name] | {
                target for target, target_type in used_as_value.items()
                if any(
                    self._function_types_may_match(callee_type, target_type)
                    for callee_type in indirect[name]
                )
            }
            for name in functions
        }
        self._report_recursion_cycles(
            list(functions),
            reported,
            " (a call through a function value may reach any function of that type used as a value)",
        )

    def _function_types_may_match(self, callee_type: Optional[Type], function_type: Optional[Type]) -> bool:
        """Whether a call through a value of `callee_type` can reach the function.

        Function types are assignable only when equal, and the safety pass
        rejects casts between them. An unknown type or one with a generic
        parameter (printed with `$`) matches everything.
        """
        if callee_type is None or function_type is None:
            return True
        if callee_type.equals(function_type):
            return True
        return "$" in str(callee_type) or "$" in str(function_type)

    def _validate_function_group(self, functions: dict[str, ASTNode]) -> set[str]:
        """Check one lexical group with the same call and alias rules.

        Returns the functions on a reported cycle. The dict is keyed by name:
        name resolution rejects two functions with one name in one scope.
        """
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
        return self._report_recursion_cycles(list(functions), set(), "")

    def _report_recursion_cycles(self, order: list[str], already_reported: set[str], note: str) -> set[str]:
        """Report one cycle per search over `_function_graph`, in `order`.

        A component holding a function in `already_reported` is skipped.
        Returns the functions on the cycles reported here.
        """
        # Functions on no cycle cannot start one: skip singleton components
        # without a self-call. A cycle through a function stays inside its
        # component, so each search is confined to that component.
        component_of: dict[str, set[str]] = {}
        for component in self._strongly_connected_components():
            members = set(component)
            if len(component) == 1 and component[0] not in self._function_graph[component[0]]:
                continue
            if members & already_reported:
                continue
            for member in component:
                component_of[member] = members

        reported_nodes: set[str] = set()
        for name in order:
            if name in reported_nodes or name not in component_of:
                continue
            path = self._find_recursion_path(name, component_of[name])
            if not path:
                continue
            reported_nodes.update(path)
            self.add_error(
                SemanticErrorType.RECURSION_NOT_ALLOWED,
                self._function_spans.get(name),
                f"Cycle: {' -> '.join(path)}{note}",
            )
        return reported_nodes

    def _strongly_connected_components(self) -> list[list[str]]:
        """Tarjan's algorithm over `_function_graph`, on an explicit stack."""
        graph = self._function_graph
        index: dict[str, int] = {}
        lowlink: dict[str, int] = {}
        on_stack: set[str] = set()
        component_stack: list[str] = []
        components: list[list[str]] = []

        for root in graph:
            if root in index:
                continue
            index[root] = lowlink[root] = len(index)
            component_stack.append(root)
            on_stack.add(root)
            work = [(root, iter(sorted(graph[root])))]
            while work:
                node, callees = work[-1]
                descended = False
                for callee in callees:
                    if callee not in graph:
                        continue
                    if callee not in index:
                        index[callee] = lowlink[callee] = len(index)
                        component_stack.append(callee)
                        on_stack.add(callee)
                        work.append((callee, iter(sorted(graph[callee]))))
                        descended = True
                        break
                    if callee in on_stack:
                        lowlink[node] = min(lowlink[node], index[callee])
                if descended:
                    continue
                work.pop()
                if work:
                    parent = work[-1][0]
                    lowlink[parent] = min(lowlink[parent], lowlink[node])
                if lowlink[node] == index[node]:
                    component: list[str] = []
                    while True:
                        member = component_stack.pop()
                        on_stack.discard(member)
                        component.append(member)
                        if member == node:
                            break
                    components.append(component)
        return components

    def _find_recursion_path(self, start: str, members: set[str]) -> Optional[list[str]]:
        """Return the first simple cycle through `start` in name-ordered DFS order.

        This is the cycle an exhaustive simple-path DFS finds when it tries
        callees in name order and closes the cycle as soon as `start` is a
        callee of the current function. That search fully explores the
        smallest untried callee before any larger one, so its answer is built
        greedily: close the cycle if `start` is a callee; otherwise step to the
        smallest callee off the path that can still reach `start` without
        revisiting the path. Each step is one backward reachability sweep, so
        the search is O(V * (V + E)) over the component `members`.
        """
        callers: dict[str, list[str]] = {member: [] for member in members}
        for member in members:
            for callee in self._function_graph.get(member, set()):
                if callee in callers:
                    callers[callee].append(member)

        path = [start]
        on_path = {start}
        current = start
        while True:
            callees = self._function_graph.get(current, set())
            if start in callees:
                return path + [start]

            # Functions off the path that reach `start` through functions off the path.
            reaches_start: set[str] = set()
            worklist = [caller for caller in callers[start] if caller not in on_path]
            while worklist:
                function = worklist.pop()
                if function in reaches_start:
                    continue
                reaches_start.add(function)
                for caller in callers[function]:
                    if caller not in on_path and caller not in reaches_start:
                        worklist.append(caller)

            candidates = [callee for callee in callees if callee in reaches_start]
            if not candidates:
                return None
            current = min(candidates)
            path.append(current)
            on_path.add(current)

    def _collect_function_calls(
        self,
        function: ASTNode,
        function_names: set[str],
        hidden: Optional[set[str]] = None,
        *,
        track_aliases: bool = True,
    ) -> set[str]:
        """Return the functions `function` calls by name.

        `hidden` holds function names that mean something else in the whole
        body. With `track_aliases` off, a call through a local alias is not
        resolved; the caller treats it as a call through a function value.
        """
        if function.body is None:
            return set()

        calls: set[str] = set()
        function_aliases = (
            self._collect_function_aliases(function, function_names) if track_aliases else {}
        )
        shadowed = set(hidden or ()) | {
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
        enclosing_loops = []
        while node.kind == NodeKind.FOR and node.init:
            enclosing_loops.append((node, shadowed))
            shadowed = set(shadowed)
            node = node.init

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
                # A capture named like a function hides it in the case body.
                case_shadowed = shadowed | {
                    pattern.name for pattern in case.patterns or []
                    if pattern.name in function_names
                }
                case_stmt = getattr(case, "statement", None)
                if case_stmt:
                    stack.append(("stmt", case_stmt, 0, case_shadowed))
                else:
                    stack.append(("stmt_list", case.statements or [], 0, case_shadowed))
            else_statements = self._as_statement_list(node.else_case)
            if else_statements:
                stack.append(("stmt_list", else_statements, 0, set(shadowed)))

        for loop, outer_shadowed in reversed(enclosing_loops):
            if loop.condition:
                calls.update(self._collect_expression_calls(loop.condition, function_names, function_aliases, shadowed))
            if loop.update:
                calls.update(self._collect_expression_calls(loop.update, function_names, function_aliases, shadowed))
            if loop.body:
                stack.append(("stmt", loop.body, 0, shadowed))
            shadowed = outer_shadowed
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
        # Callee nodes that name their target; they are not uses as a value.
        named_callees: set[int] = set()
        stack = [root]
        while stack:
            node = stack.pop()
            if node is None:
                continue

            if node.kind == NodeKind.CALL:
                callee = self._direct_callee_name(node, function_aliases, shadowed)
                if callee not in function_names:
                    callee = self._named_function(node.function, function_names, shadowed)
                if callee in function_names:
                    named_callees.add(id(node.function))
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
                elif node.function is not None:
                    function = node.function
                    receiver = function.object if function.kind == NodeKind.FIELD_ACCESS else None
                    receiver_type = self.get_type(receiver) if receiver is not None else None
                    # `alias.name(...)` that is not a file-module function is
                    # a stdlib call such as io.println: no user function runs.
                    # The alias has no type or the unknown type.
                    stdlib_call = (
                        receiver is not None
                        and receiver.kind == NodeKind.IDENTIFIER
                        and (receiver_type is None or isinstance(receiver_type, UnknownType))
                    )
                    if not stdlib_call:
                        callee_type = self.get_type(function)
                        # Reading an untagged union field can reinterpret a
                        # function stored under another field's type.
                        if not isinstance(callee_type, FunctionType) or isinstance(receiver_type, UnionType):
                            callee_type = None
                        self._indirect_call_types.append(callee_type)

            if node.kind == NodeKind.FUNCTION:
                continue

            if id(node) not in named_callees:
                value = self._named_function(node, function_names, shadowed)
                if value:
                    value_type = self.get_type(node)
                    self._function_values[value] = value_type if isinstance(value_type, FunctionType) else None

            for child in self._iter_child_nodes(node):
                stack.append(child)
        return calls

    def _named_function(
        self,
        node: Optional[ASTNode],
        function_names: set[str],
        shadowed: set[str],
    ) -> Optional[str]:
        """Return the function that `name` or `module_alias.name` denotes."""
        if node is None:
            return None
        if node.kind == NodeKind.IDENTIFIER:
            if node.name in function_names and node.name not in shadowed:
                return node.name
            return None
        # A module alias has no type; a struct value holding a function does.
        if (
            node.kind == NodeKind.FIELD_ACCESS
            and node.field in function_names
            and node.object is not None
            and node.object.kind == NodeKind.IDENTIFIER
            and self.get_type(node.object) is None
            and isinstance(self.get_type(node), FunctionType)
        ):
            return node.field
        return None

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
        enclosing_loops = []
        while node.kind == NodeKind.FOR and node.init:
            enclosing_loops.append((node, shadowed, aliases))
            shadowed = set(shadowed)
            aliases = dict(aliases)
            node = node.init

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

        for loop, outer_shadowed, outer_aliases in reversed(enclosing_loops):
            if loop.condition:
                called.update(self._collect_expression_parameter_calls(loop.condition, param_positions, shadowed, aliases, invocations))
            if loop.update:
                called.update(self._collect_expression_parameter_calls(loop.update, param_positions, shadowed, aliases, invocations))
            if loop.body:
                stack.append(("stmt", loop.body, 0, shadowed, aliases))
            shadowed, aliases = outer_shadowed, outer_aliases
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
        """Check block termination with ordered, short-circuit work items."""
        pending = [("visit", node)]
        result = False
        while pending:
            operation, value = pending.pop()
            if operation in ("resume_any", "resume_all"):
                # Preserve context validation side effects: never inspect an
                # unreachable tail or a branch after a decisive result.
                if result == (operation == "resume_any"):
                    continue
                operation = "any" if operation == "resume_any" else "all"

            if operation in ("any", "all"):
                child = next(value, None)
                if child is None:
                    result = operation == "all"
                else:
                    pending.append(("resume_" + operation, value))
                    pending.append(child)
                continue

            if operation == "exhaustive":
                result = self._is_match_exhaustive(value)
                continue

            current = value
            result = False
            if current is None:
                continue
            if current.kind == NodeKind.RETURN:
                result = self.context.in_function()
            elif current.kind == NodeKind.BREAK:
                result = self.context.validate_break(current.label)
            elif current.kind == NodeKind.CONTINUE:
                result = self.context.validate_continue(current.label)
            elif current.kind == NodeKind.FALL:
                result = True
            elif current.kind == NodeKind.BLOCK:
                pending.append(("any", iter(
                    ("visit", stmt) for stmt in (current.statements or [])
                )))
            elif current.kind == NodeKind.IF_STMT:
                if current.then_stmt is not None and current.else_stmt is not None:
                    pending.append(("all", iter([
                        ("visit", current.then_stmt), ("visit", current.else_stmt),
                    ])))
            elif current.kind == NodeKind.MATCH and current.cases:
                branches = []
                for case in current.cases:
                    case_stmt = getattr(case, "statement", None)
                    if case_stmt is not None:
                        branches.append(("visit", case_stmt))
                    else:
                        branches.append(("any", iter(
                            ("visit", stmt)
                            for stmt in (getattr(case, "statements", None) or [])
                        )))
                if current.else_case:
                    branches.append(("any", iter(
                        ("visit", stmt) for stmt in current.else_case
                    )))
                else:
                    branches.append(("exhaustive", current))
                pending.append(("all", iter(branches)))
        return result

    def _returns_on_all_paths(self, node: ASTNode) -> bool:
        """Check return completeness without recursive branch calls."""
        pending = [("visit", node)]
        while pending:
            operation, current = pending.pop()
            if operation == "exhaustive":
                if not self._is_match_exhaustive(current):
                    return False
                continue
            if current is None:
                return False
            if current.kind == NodeKind.RETURN:
                continue
            if current.kind == NodeKind.BLOCK:
                statements = current.statements or []
                if not statements:
                    return False
                pending.append(("visit", statements[-1]))
            elif current.kind == NodeKind.IF_STMT:
                if current.else_stmt is None:
                    return False
                pending.append(("visit", current.else_stmt))
                pending.append(("visit", current.then_stmt))
            elif current.kind == NodeKind.MATCH:
                # Every branch must return. The fallback/coverage check runs
                # after the case bodies, as in the original short-circuit walk.
                if current.else_case:
                    pending.append(("visit", current.else_case[-1]))
                else:
                    pending.append(("exhaustive", current))
                branches = []
                for case in (current.cases or []):
                    case_stmt = getattr(case, "statement", None)
                    if case_stmt is None:
                        statements = getattr(case, "statements", None) or []
                        case_stmt = statements[-1] if statements else None
                    branches.append(("visit", case_stmt))
                pending.extend(reversed(branches))
            elif current.kind == NodeKind.WHILE:
                if not self._loops_forever(current):
                    return False
            else:
                return False
        return True

    def _loops_forever(self, loop: ASTNode) -> bool:
        """True for `while true` with no break that leaves the loop.

        Control never reaches the statement after such a loop, so a function
        ending in one needs no return after it.
        """
        condition = loop.condition
        if not (
            condition is not None
            and condition.kind == NodeKind.LITERAL
            and condition.literal_kind == LiteralKind.BOOLEAN
            and condition.literal_value is True
        ):
            return False
        # (node, loops entered inside `loop`, their labels)
        work = [(loop.body, 0, frozenset())] if loop.body else []
        while work:
            node, loops, labels = work.pop()
            if node.kind == NodeKind.FUNCTION:
                continue
            if node.kind == NodeKind.BREAK:
                if node.label not in labels if node.label else loops == 0:
                    return False
            if node.kind in (NodeKind.WHILE, NodeKind.FOR, NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED):
                loops += 1
                if node.label:
                    labels = labels | {node.label}
            work.extend((child, loops, labels) for child in self._iter_child_nodes(node))
        return True

    def _collect_tagged_union_tags(self, program: ASTNode) -> dict[str, list[str]]:
        """Map each top-level tagged union name to its tag names in order."""
        tags: dict[str, list[str]] = {}
        for decl in (getattr(program, "declarations", None) or []):
            if not isinstance(decl, ASTNode):
                continue
            if decl.kind != NodeKind.UNION or not getattr(decl, "is_tagged", False):
                continue
            if not decl.name or decl.name in tags:
                continue
            tags[decl.name] = [
                field.name for field in (decl.fields or [])
                if getattr(field, "name", None)
            ]
        return tags

    def _match_union_name_and_tags(self, node: ASTNode) -> Optional[tuple[str, list[str]]]:
        """Return (union name, tags) when the match scrutinee is a tagged union."""
        scrutinee_type = self.get_type(node.expression) if node.expression else None
        if isinstance(scrutinee_type, ReferenceType):
            scrutinee_type = scrutinee_type.referent_type
        if isinstance(scrutinee_type, UnionType):
            name = scrutinee_type.name
        elif isinstance(scrutinee_type, GenericInstanceType):
            name = scrutinee_type.base_name
        else:
            return None
        tags = self._tagged_union_tags.get(name)
        if tags is None:
            return None
        return (name, tags)

    def _union_covered_tags(self, node: ASTNode, union_name: str, tag_set: Set[str]) -> Set[str]:
        """Collect union tags covered by leading-dot or qualified tag patterns."""
        covered: Set[str] = set()
        for case in (node.cases or []):
            for pattern in (case.patterns or []):
                if pattern.kind != NodeKind.PATTERN_ENUM:
                    continue
                variant = pattern.variant or ""
                enum_type = pattern.enum_type or ""
                if variant in tag_set and enum_type in ("", union_name):
                    covered.add(variant)
        return covered

    def _validate_union_tag_patterns(self, node: ASTNode, union_name: str) -> None:
        """Reject a payload binding that shares its case with another pattern."""
        for case in (node.cases or []):
            patterns = case.patterns or []
            bound = [
                pattern for pattern in patterns
                if pattern.kind == NodeKind.PATTERN_ENUM
                and (pattern.enum_type or "") in ("", union_name)
                and (pattern.name or "")
            ]
            if len(patterns) > 1 and bound:
                self.add_error(
                    SemanticErrorType.INVALID_PATTERN,
                    bound[0].span,
                    f"payload binding '{bound[0].name}' over tagged union "
                    f"'{union_name}' must be the only pattern in its case",
                )

    def _union_match_has_explicit_wildcard(self, node: ASTNode) -> bool:
        """Return True when a match has an explicit `_` wildcard arm."""
        for case in (node.cases or []):
            for pattern in (case.patterns or []):
                if pattern.kind == NodeKind.PATTERN_WILDCARD:
                    return True
                if pattern.kind == NodeKind.PATTERN_IDENTIFIER and (pattern.name or "") == "_":
                    return True
        return False

    def _validate_union_match_arms(self, program: ASTNode) -> None:
        """Reject bare captures and non-exhaustive matches over tagged unions."""
        stack = [program]
        while stack:
            node = stack.pop()
            if node is None:
                continue
            if node.kind in (NodeKind.MATCH, NodeKind.MATCH_EXPR):
                resolved = self._match_union_name_and_tags(node)
                if resolved is not None:
                    union_name, tags = resolved
                    self._validate_tagged_union_match(node, union_name, tags)
            stack.extend(self._iter_child_nodes(node))

    def _validate_tagged_union_match(self, node: ASTNode, union_name: str, tags: list[str]) -> None:
        """Check one match over a tagged union: no bare arms, full coverage."""
        bare_arms = 0
        for case in (node.cases or []):
            for pattern in (case.patterns or []):
                if pattern.kind == NodeKind.PATTERN_IDENTIFIER and (pattern.name or "") != "_":
                    bare_arms += 1
                    self.add_error(
                        SemanticErrorType.INVALID_PATTERN,
                        pattern.span,
                        f"case '{pattern.name}' over tagged union '{union_name}' "
                        "captures the whole value and never tests the tag",
                    )
        if bare_arms:
            return
        tag_set = set(tags)
        self._validate_union_tag_patterns(node, union_name)
        if node.else_case:
            return
        if self._union_match_has_explicit_wildcard(node):
            return
        covered = self._union_covered_tags(node, union_name, tag_set)
        missing = [tag for tag in tags if tag not in covered]
        if missing:
            self.add_error(
                SemanticErrorType.NON_EXHAUSTIVE_MATCH,
                node.span,
                f"match over tagged union '{union_name}' misses tag(s): "
                f"{', '.join(missing)}; cover every tag or add an else branch",
            )

    def _is_match_exhaustive(self, node: ASTNode) -> bool:
        """Check a fallback or complete bool/enum coverage."""
        if node.else_case:
            return True

        scrutinee_type = self.get_type(node.expression) if node.expression else None
        if scrutinee_type is None:
            return False

        union_resolved = self._match_union_name_and_tags(node)
        if union_resolved is not None:
            union_name, tags = union_resolved
            if self._union_match_has_explicit_wildcard(node):
                return True
            covered = self._union_covered_tags(node, union_name, set(tags))
            return set(tags).issubset(covered)

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
        return pattern.kind == NodeKind.PATTERN_IDENTIFIER and (
            (pattern.name or "") == "_" or bool(getattr(pattern, "is_capture_pattern", False))
        )

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
