from pathlib import Path
p=Path('tmp/untyped-constants-next/candidate/a7/passes/type_checker.py')
s=p.read_text().replace('from a7.stdlib import StdlibRegistry','from a7.stdlib import StdlibRegistry\nfrom a7.exact_constants import evaluate, materialize')
s=s.replace('self.stdlib = StdlibRegistry()', 'self.stdlib = StdlibRegistry()\n        self.exact_bindings = {}')
s=s.replace('        # Third pass: type check all declarations (including function bodies)\n        for decl in node.declarations or []:\n            self.visit_declaration(decl)', '''        # Resolve exact global bindings without moving runtime declarations.
        pending = [d for d in node.declarations or [] if d.kind == NodeKind.CONST and not d.explicit_type]
        while pending:
            remaining = []
            for decl in pending:
                exact = evaluate(decl.value, self.symbols.lookup, self.exact_bindings)
                if exact is None:
                    remaining.append(decl)
                else:
                    self.exact_bindings[id(decl)] = exact
            if len(remaining) == len(pending):
                break
            pending = remaining

        # Resolve global types using dependencies. No initializer is executed here.
        globals_ = [d for d in node.declarations or [] if d.kind in {NodeKind.CONST, NodeKind.VAR}]
        pending = list(globals_)
        global_ids = {id(d) for d in globals_}
        done = set()
        while pending:
            remaining = []
            for decl in pending:
                dependencies = set()
                stack = [decl.value] if decl.value else []
                while stack:
                    expr = stack.pop()
                    if expr.kind == NodeKind.IDENTIFIER:
                        symbol = self.symbols.lookup(expr.name)
                        if symbol and id(symbol.node) in global_ids:
                            dependencies.add(id(symbol.node))
                    for value in vars(expr).values():
                        if isinstance(value, ASTNode):
                            stack.append(value)
                        elif isinstance(value, list):
                            stack.extend(child for child in value if isinstance(child, ASTNode))
                if dependencies - done:
                    remaining.append(decl)
                else:
                    self.visit_declaration(decl)
                    done.add(id(decl))
            if len(remaining) == len(pending):
                for decl in remaining:
                    self.add_error(f"Unresolved global value dependency involving '{decl.name}'", decl.span)
                break
            pending = remaining
        for decl in node.declarations or []:
            if decl.kind not in {NodeKind.CONST, NodeKind.VAR}:
                self.visit_declaration(decl)''')
s=s.replace('        const_name = node.name or "<unknown>"','''        const_name = node.name or "<unknown>"
        if not node.explicit_type:
            exact = evaluate(node.value, self.symbols.lookup, self.exact_bindings)
            if exact is not None:
                self.exact_bindings[id(node)] = exact''')
s=s.replace('        expr_type = self._visit_expression_impl(node)', '''        exact = evaluate(node, self.symbols.lookup, self.exact_bindings)
        if exact is not None:
            materialize(node, exact)
        expr_type = self._visit_expression_impl(node)''')
s=s.replace('        if isinstance(expected_type, PrimitiveType):\n            literal_value = self._integer_literal_value(value_node)', '''        if isinstance(expected_type, PrimitiveType):
            exact = getattr(value_node, 'exact_constant', None)
            if exact is not None and expected_type.is_integral():
                value, floating = exact
                if value.denominator != 1:
                    self.add_error(f"Exact constant {value} is fractional and cannot fit {expected_type}", value_node.span)
                    return False
                if not self._integer_literal_fits_type(value.numerator, expected_type):
                    self.add_error(f"Exact constant {value} is out of range for {expected_type}", value_node.span)
                    return False
                materialize(value_node, exact, integer=True)
                self.set_type(value_node, expected_type)
                return True
            literal_value = self._integer_literal_value(value_node)''')
# Default inferred variables must not silently widen.
s=s.replace('        self.set_type(node, value_type)\n        # Update the existing symbol', '''        if not node.explicit_type and node.value:
            exact = getattr(node.value, 'exact_constant', None)
            if exact is not None and not exact[1] and not self._integer_literal_fits_type(exact[0].numerator, I32):
                self.add_error("Exact constant does not fit default i32; use an explicit destination type", node.value.span)
        self.set_type(node, value_type)
        # Update the existing symbol''')
p.write_text(s)
p=Path('tmp/untyped-constants-next/candidate/a7/backends/zig.py')
s=p.read_text().replace('        elif lk == LiteralKind.FLOAT:\n            if isinstance(val, float)', '''        elif lk == LiteralKind.FLOAT:
            if getattr(node, 'exact_constant', None) is not None:
                return raw
            if isinstance(val, float)''')
p.write_text(s)
