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
    declarations = node.declarations or []
    globals_ = [decl for decl in declarations if decl.kind in {NodeKind.CONST, NodeKind.VAR}]
    for decl in globals_:
        self.visit_declaration(decl)
    for decl in declarations:
        if decl.kind not in {NodeKind.CONST, NodeKind.VAR}:
            self.visit_declaration(decl)
