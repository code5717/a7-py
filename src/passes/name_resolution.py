"""
Name resolution pass for A7 semantic analysis.

Builds symbol tables, resolves names to declarations, and validates
scoping rules.
"""

from typing import Optional, List

from src.ast_nodes import ASTNode, NodeKind
from src.symbol_table import SymbolTable, Symbol, SymbolKind, ModuleTable
from src.types import Type, UNKNOWN, get_primitive_type, GenericParamType
from src.errors import SemanticError, SemanticErrorType, SourceSpan


class NameResolutionPass:
    """
    First pass of semantic analysis.

    Walks the AST to:
    1. Build symbol tables for all scopes
    2. Register all declarations
    3. Detect name collisions
    4. Prepare for type checking

    Does NOT perform type checking - that's in the next pass.
    """

    def __init__(self):
        """Initialize name resolution pass."""
        self.symbols = SymbolTable()
        self.modules = ModuleTable()
        self.errors: List[SemanticError] = []
        self.current_file: str = "<unknown>"
        self.source_lines: List[str] = []

    def analyze(self, program: ASTNode, filename: str = "<unknown>") -> SymbolTable:
        """
        Perform name resolution on a program.

        Args:
            program: Root program node
            filename: Source file name (for error messages)

        Returns:
            Symbol table with all declarations

        Note:
            Collects ALL errors instead of stopping at the first one.
            Check self.errors after calling to see if there were any issues.
        """
        self.current_file = filename
        self.errors = []

        # Visit the program
        self.visit_program(program)

        # Return symbol table - caller should check self.errors
        return self.symbols

    def add_error(
        self,
        error_type: SemanticErrorType,
        span: Optional[SourceSpan] = None,
        context: Optional[str] = None,
    ) -> None:
        """Add a semantic error with structured type."""
        error = SemanticError.from_type(
            error_type,
            span=span,
            filename=self.current_file,
            source_lines=self.source_lines,
            context=context,
        )
        self.errors.append(error)

    # Visitor methods

    def visit_program(self, node: ASTNode) -> None:
        """Visit program root."""
        if node.kind != NodeKind.PROGRAM:
            self.add_error(
                SemanticErrorType.UNEXPECTED_NODE_KIND,
                node.span,
                f"Expected program node, got {node.kind}"
            )
            return

        # Process all declarations
        for decl in node.declarations or []:
            self.visit_declaration(decl)

    def visit_declaration(self, node: ASTNode) -> None:
        """Visit a top-level declaration."""
        if node.kind == NodeKind.IMPORT:
            self.visit_import(node)
        elif node.kind == NodeKind.FUNCTION:
            self.visit_function_decl(node)
        elif node.kind == NodeKind.STRUCT:
            self.visit_struct_decl(node)
        elif node.kind == NodeKind.ENUM:
            self.visit_enum_decl(node)
        elif node.kind == NodeKind.UNION:
            self.visit_union_decl(node)
        elif node.kind == NodeKind.TYPE_ALIAS:
            self.visit_type_alias(node)
        elif node.kind == NodeKind.CONST:
            self.visit_const_decl(node)
        elif node.kind == NodeKind.VAR:
            self.visit_var_decl(node)
        else:
            self.add_error(SemanticErrorType.UNEXPECTED_NODE_KIND, node.span, f"declaration kind: {node.kind}")

    def visit_import(self, node: ASTNode) -> None:
        """Visit an import declaration."""
        # Import resolution will be handled by ModuleResolver
        # Register the import intent and create module symbols
        module_path = node.module_path or "<unknown>"

        if node.alias:
            # io :: import "std/io" → register 'io' as a MODULE symbol
            self.modules.add_alias(node.alias, module_path)
            module_symbol = Symbol(
                name=node.alias,
                kind=SymbolKind.MODULE,
                type=UNKNOWN,
                node=node,
                is_mutable=False,
            )
            self.symbols.define(module_symbol)
        elif node.is_using:
            # using import "io"
            self.modules.add_using_import(module_path)
        elif node.imported_items:
            # import "vector" { Vec3, dot }
            for item in node.imported_items:
                self.modules.add_named_import(item, module_path)

    def visit_function_decl(self, node: ASTNode) -> None:
        """Visit a function declaration."""
        func_name = node.name or "<anonymous>"

        # Create function symbol (type will be determined in type checking pass)
        func_symbol = Symbol(
            name=func_name,
            kind=SymbolKind.FUNCTION,
            type=UNKNOWN,  # Will be resolved by type checker
            node=node,
            is_mutable=False
        )

        # Register in current scope
        if not self.symbols.define(func_symbol):
            self.add_error(SemanticErrorType.ALREADY_DEFINED, node.span, f"Function '{func_name}'")
            return

        # Enter function scope
        self.symbols.enter_scope(f"function_{func_name}")

        # Register generic parameters in the function scope. The function symbol itself
        # must remain in the parent scope so generic functions are callable by name.
        if node.generic_params:
            for gparam in node.generic_params:
                self.visit_generic_param(gparam)

        # Register parameters
        if node.parameters:
            for param in node.parameters:
                self.visit_parameter(param)

        # Visit function body
        if node.body:
            self.visit_statement(node.body)

        # Exit function scope
        self.symbols.exit_scope()

    def visit_generic_param(self, node: ASTNode) -> None:
        """Visit a generic parameter declaration."""
        if node.kind != NodeKind.GENERIC_PARAM:
            self.add_error(SemanticErrorType.UNEXPECTED_NODE_KIND, node.span, f"Expected generic param, got {node.kind}")
            return

        param_name = node.name or "<unknown>"

        # Create generic parameter symbol
        # The constraint will be resolved by type checker
        generic_symbol = Symbol(
            name=param_name,
            kind=SymbolKind.GENERIC_PARAM,
            type=UNKNOWN,  # Will be GenericParamType in type checker
            node=node,
            is_mutable=False
        )

        if not self.symbols.define(generic_symbol):
            self.add_error(SemanticErrorType.DUPLICATE_GENERIC_PARAM, node.span, f"Generic parameter '{param_name}'")

    def visit_parameter(self, node: ASTNode) -> None:
        """Visit a function parameter."""
        if node.kind != NodeKind.PARAMETER:
            self.add_error(SemanticErrorType.UNEXPECTED_NODE_KIND, node.span, f"Expected parameter, got {node.kind}")
            return

        param_name = node.name or "<unknown>"

        # Create parameter symbol (type will be resolved by type checker)
        param_symbol = Symbol(
            name=param_name,
            kind=SymbolKind.VARIABLE,
            type=UNKNOWN,
            node=node,
            is_mutable=False  # Parameters are immutable by default
        )

        if not self.symbols.define(param_symbol):
            self.add_error(SemanticErrorType.ALREADY_DEFINED, node.span, f"Parameter '{param_name}'")

    def visit_struct_decl(self, node: ASTNode) -> None:
        """Visit a struct declaration."""
        struct_name = node.name or "<anonymous>"

        # Create struct symbol
        struct_symbol = Symbol(
            name=struct_name,
            kind=SymbolKind.STRUCT,
            type=UNKNOWN,  # Will be StructType in type checker
            node=node,
            is_mutable=False
        )

        if not self.symbols.define(struct_symbol):
            self.add_error(SemanticErrorType.ALREADY_DEFINED, node.span, f"Struct '{struct_name}'")
            return

        # Enter struct scope for fields
        self.symbols.enter_scope(f"struct_{struct_name}")

        # Register fields (just names, types resolved later)
        if node.fields:
            for field in node.fields:
                if field.kind == NodeKind.FIELD:
                    field_name = field.name or "<unknown>"
                    field_symbol = Symbol(
                        name=field_name,
                        kind=SymbolKind.VARIABLE,
                        type=UNKNOWN,
                        node=field,
                        is_mutable=False
                    )
                    if not self.symbols.define(field_symbol):
                        self.add_error(SemanticErrorType.DUPLICATE_FIELD, field.span, f"'{field_name}' in struct '{struct_name}'")

        self.symbols.exit_scope()

    def visit_enum_decl(self, node: ASTNode) -> None:
        """Visit an enum declaration."""
        enum_name = node.name or "<anonymous>"

        # Create enum symbol
        enum_symbol = Symbol(
            name=enum_name,
            kind=SymbolKind.ENUM,
            type=UNKNOWN,  # Will be EnumType in type checker
            node=node,
            is_mutable=False
        )

        if not self.symbols.define(enum_symbol):
            self.add_error(SemanticErrorType.ALREADY_DEFINED, node.span, f"Enum '{enum_name}'")
            return

        # Register variants
        if node.variants:
            for variant in node.variants:
                if variant.kind == NodeKind.ENUM_VARIANT:
                    variant_name = variant.name or "<unknown>"
                    # Enum variants are accessible as EnumName.VariantName
                    # They're also sometimes directly accessible depending on language semantics
                    variant_symbol = Symbol(
                        name=f"{enum_name}.{variant_name}",
                        kind=SymbolKind.ENUM_VARIANT,
                        type=UNKNOWN,
                        node=variant,
                        is_mutable=False
                    )
                    self.symbols.define(variant_symbol)

    def visit_union_decl(self, node: ASTNode) -> None:
        """Visit a union declaration."""
        union_name = node.name or "<anonymous>"

        # Create union symbol
        union_symbol = Symbol(
            name=union_name,
            kind=SymbolKind.UNION,
            type=UNKNOWN,  # Will be UnionType in type checker
            node=node,
            is_mutable=False
        )

        if not self.symbols.define(union_symbol):
            self.add_error(SemanticErrorType.ALREADY_DEFINED, node.span, f"Union '{union_name}'")
            return

        # Enter union scope for fields
        self.symbols.enter_scope(f"union_{union_name}")

        # Register fields
        if node.fields:
            for field in node.fields:
                if field.kind == NodeKind.FIELD:
                    field_name = field.name or "<unknown>"
                    field_symbol = Symbol(
                        name=field_name,
                        kind=SymbolKind.VARIABLE,
                        type=UNKNOWN,
                        node=field,
                        is_mutable=False
                    )
                    if not self.symbols.define(field_symbol):
                        self.add_error(SemanticErrorType.DUPLICATE_FIELD, field.span, f"'{field_name}' in union '{union_name}'")

        self.symbols.exit_scope()

    def visit_type_alias(self, node: ASTNode) -> None:
        """Visit a type alias declaration."""
        alias_name = node.name or "<anonymous>"

        # Create type alias symbol
        alias_symbol = Symbol(
            name=alias_name,
            kind=SymbolKind.TYPE,
            type=UNKNOWN,  # Will be resolved in type checker
            node=node,
            is_mutable=False
        )

        if not self.symbols.define(alias_symbol):
            self.add_error(SemanticErrorType.ALREADY_DEFINED, node.span, f"Type alias '{alias_name}'")

    def visit_const_decl(self, node: ASTNode) -> None:
        """Visit a constant declaration."""
        const_name = node.name or "<unknown>"

        # Create constant symbol
        const_symbol = Symbol(
            name=const_name,
            kind=SymbolKind.CONSTANT,
            type=UNKNOWN,  # Will be inferred in type checker
            node=node,
            is_mutable=False
        )

        if not self.symbols.define(const_symbol):
            self.add_error(SemanticErrorType.ALREADY_DEFINED, node.span, f"Constant '{const_name}'")

    def visit_var_decl(self, node: ASTNode) -> None:
        """Visit a variable declaration."""
        var_name = node.name or "<unknown>"

        # Create variable symbol
        var_symbol = Symbol(
            name=var_name,
            kind=SymbolKind.VARIABLE,
            type=UNKNOWN,  # Will be inferred or explicitly typed in type checker
            node=node,
            is_mutable=True
        )

        if not self.symbols.define(var_symbol):
            self.add_error(SemanticErrorType.ALREADY_DEFINED, node.span, f"Variable '{var_name}'")

    def visit_statement(self, node: ASTNode) -> None:
        """Visit a statement (iterative)."""
        # Stack items: ('visit', node) or ('action', callable)
        stack: list = [('visit', node)]

        while stack:
            action, item = stack.pop()

            if action == 'action':
                item()  # Execute deferred action (scope exit, etc.)
                continue

            nd = item  # action == 'visit'

            if nd.kind == NodeKind.BLOCK:
                self.symbols.enter_scope("block")
                stack.append(('action', lambda: self.symbols.exit_scope()))
                for stmt in reversed(nd.statements or []):
                    stack.append(('visit', stmt))

            elif nd.kind == NodeKind.VAR:
                self.visit_var_decl(nd)
            elif nd.kind == NodeKind.CONST:
                self.visit_const_decl(nd)
            elif nd.kind == NodeKind.TYPE_ALIAS:
                self.visit_type_alias(nd)

            elif nd.kind == NodeKind.IF_STMT:
                # Else branch
                if nd.else_stmt:
                    if nd.else_stmt.kind == NodeKind.BLOCK:
                        stack.append(('visit', nd.else_stmt))
                    else:
                        stack.append(('action', lambda: self.symbols.exit_scope()))
                        stack.append(('visit', nd.else_stmt))
                        stack.append(('action', lambda: self.symbols.enter_scope("if_else")))
                # Then branch
                if nd.then_stmt:
                    if nd.then_stmt.kind == NodeKind.BLOCK:
                        stack.append(('visit', nd.then_stmt))
                    else:
                        stack.append(('action', lambda: self.symbols.exit_scope()))
                        stack.append(('visit', nd.then_stmt))
                        stack.append(('action', lambda: self.symbols.enter_scope("if_then")))

            elif nd.kind == NodeKind.WHILE:
                if nd.body:
                    if nd.body.kind == NodeKind.BLOCK:
                        stack.append(('visit', nd.body))
                    else:
                        stack.append(('action', lambda: self.symbols.exit_scope()))
                        stack.append(('visit', nd.body))
                        stack.append(('action', lambda: self.symbols.enter_scope("while")))

            elif nd.kind == NodeKind.FOR:
                self.symbols.enter_scope("for")
                stack.append(('action', lambda: self.symbols.exit_scope()))
                if nd.body:
                    stack.append(('visit', nd.body))
                if nd.init:
                    stack.append(('visit', nd.init))

            elif nd.kind == NodeKind.FOR_IN:
                self.symbols.enter_scope("for_in")
                iterator_name = nd.iterator or "<unknown>"
                iter_symbol = Symbol(
                    name=iterator_name, kind=SymbolKind.VARIABLE,
                    type=UNKNOWN, node=nd, is_mutable=False
                )
                if not self.symbols.define(iter_symbol):
                    self.add_error(SemanticErrorType.ALREADY_DEFINED, nd.span, f"Iterator variable '{iterator_name}'")
                stack.append(('action', lambda: self.symbols.exit_scope()))
                if nd.body:
                    stack.append(('visit', nd.body))

            elif nd.kind == NodeKind.FOR_IN_INDEXED:
                self.symbols.enter_scope("for_in_indexed")
                index_name = nd.index_var or "<unknown>"
                index_symbol = Symbol(
                    name=index_name, kind=SymbolKind.VARIABLE,
                    type=UNKNOWN, node=nd, is_mutable=False
                )
                if not self.symbols.define(index_symbol):
                    self.add_error(SemanticErrorType.ALREADY_DEFINED, nd.span, f"Index variable '{index_name}'")
                iterator_name = nd.iterator or "<unknown>"
                iter_symbol = Symbol(
                    name=iterator_name, kind=SymbolKind.VARIABLE,
                    type=UNKNOWN, node=nd, is_mutable=False
                )
                if not self.symbols.define(iter_symbol):
                    self.add_error(SemanticErrorType.ALREADY_DEFINED, nd.span, f"Iterator variable '{iterator_name}'")
                stack.append(('action', lambda: self.symbols.exit_scope()))
                if nd.body:
                    stack.append(('visit', nd.body))

            elif nd.kind == NodeKind.MATCH:
                # Schedule else case (pushed first, executes last)
                if nd.else_case:
                    stack.append(('action', lambda: self.symbols.exit_scope()))
                    for stmt in reversed(nd.else_case):
                        stack.append(('visit', stmt))
                    stack.append(('action', lambda: self.symbols.enter_scope("match_else")))
                # Schedule case branches
                if nd.cases:
                    for case in reversed(nd.cases):
                        if case.kind == NodeKind.CASE_BRANCH:
                            stack.append(('action', lambda: self.symbols.exit_scope()))
                            case_stmt = getattr(case, "statement", None)
                            if case_stmt:
                                stack.append(('visit', case_stmt))
                            elif case.statements:
                                for stmt in reversed(case.statements):
                                    stack.append(('visit', stmt))
                            stack.append(('action', lambda: self.symbols.enter_scope("match_case")))

            # RETURN, BREAK, CONTINUE, DEFER, DEL, ASSIGNMENT, EXPRESSION_STMT
            # don't introduce names — nothing to do

    def get_module_table(self) -> ModuleTable:
        """Get the module table."""
        return self.modules
