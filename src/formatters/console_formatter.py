"""
Rich console output formatter for A7 compiler.

Provides beautiful, detailed output for all compilation stages:
tokenization, parsing, semantic analysis, and code generation.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree
from rich.syntax import Syntax
from rich.columns import Columns


class ConsoleFormatter:
    """Formats compilation results for Rich console display."""

    _ANONYMOUS_MARKERS = {"<anonymous>", "<unknown>", "__inline__", "", "anonymous"}

    def __init__(self, mode: str = "compile", backend: str = "zig"):
        self.mode = mode
        self.backend = backend
        self.console = Console()

    def display_compilation(self, tokens: list, ast, source_code: str, input_path: str):
        """Display compilation results for analysis modes (tokens, ast)."""
        self._display_source_panel(source_code, input_path)
        self._display_tokens(tokens)
        if self.mode != "tokens":
            self._display_ast(ast)
        self.console.print(f"\n[bold dim]Analysis complete[/bold dim]")

    def display_full_pipeline(
        self,
        input_path: str,
        source_code: str,
        tokens: list,
        ast,
        semantic_results: dict,
        codegen_result: dict,
    ):
        """
        Display results for all compiler stages in verbose mode.

        Args:
            input_path: Source file path
            source_code: Original source code
            tokens: Token list
            ast: AST root
            semantic_results: Dict with keys: symbol_table, type_map, errors, passes
            codegen_result: Dict with keys: output_code, output_path, bytes
        """
        self._display_source_panel(source_code, input_path)
        self._display_stage_header("1", "LEXICAL ANALYSIS", "cyan")
        self._display_tokens(tokens)
        self._display_stage_header("2", "SYNTACTIC ANALYSIS", "green")
        self._display_ast(ast)
        self._display_stage_header("3", "SEMANTIC ANALYSIS", "yellow")
        self._display_semantic(semantic_results)
        self._display_stage_header("4", "CODE GENERATION", "magenta")
        self._display_codegen(codegen_result)
        self._display_pipeline_summary(tokens, ast, semantic_results, codegen_result, input_path)

    def display_through_semantic(
        self,
        input_path: str,
        source_code: str,
        tokens: list,
        ast,
        semantic_results: dict,
    ):
        """Display stages 1-3 (tokenize, parse, semantic) with visuals."""
        self._display_source_panel(source_code, input_path)
        self._display_stage_header("1", "LEXICAL ANALYSIS", "cyan")
        self._display_tokens(tokens)
        self._display_stage_header("2", "SYNTACTIC ANALYSIS", "green")
        self._display_ast(ast)
        self._display_stage_header("3", "SEMANTIC ANALYSIS", "yellow")
        self._display_semantic(semantic_results)
        self._display_pipeline_summary(tokens, ast, semantic_results, {}, input_path)

    def _display_stage_header(self, number: str, title: str, color: str):
        """Display a stage header with number and title."""
        self.console.print(f"\n[bold {color}]━━━ Stage {number}: {title} ━━━[/bold {color}]")

    def _display_semantic(self, results: dict):
        """Display semantic analysis results."""
        if not results:
            self.console.print("[dim]  Semantic analysis skipped[/dim]")
            return

        passes = results.get("passes", [])
        errors = results.get("errors", [])
        symbol_table = results.get("symbol_table")
        type_map = results.get("type_map")

        # Pass results table
        pass_table = Table(show_header=True, header_style="bold yellow", box=None, pad_edge=False)
        pass_table.add_column("Pass", style="bold", width=22)
        pass_table.add_column("Status", width=8)
        pass_table.add_column("Details", style="dim")

        for p in passes:
            name = p.get("name", "Unknown")
            ok = p.get("ok", False)
            error_count = p.get("errors", 0)
            status = "[green]✓ pass[/green]" if ok else f"[red]✗ fail[/red]"
            detail = f"{error_count} error(s)" if not ok else ""
            pass_table.add_row(name, status, detail)

        self.console.print(pass_table)

        # Symbol table summary
        if symbol_table:
            symbols = self._collect_symbols(symbol_table)
            if symbols:
                self.console.print(f"\n[bold]Symbol Table[/bold] [dim]({len(symbols)} symbols)[/dim]")
                sym_table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
                sym_table.add_column("Name", style="yellow", width=20)
                sym_table.add_column("Kind", style="cyan", width=14)
                sym_table.add_column("Type", style="green")
                sym_table.add_column("Scope", style="dim", width=12)

                for sym in symbols[:30]:  # Limit to 30 symbols
                    sym_table.add_row(
                        sym.get("name", "?"),
                        sym.get("kind", "?"),
                        sym.get("type", "?"),
                        sym.get("scope", "global"),
                    )

                self.console.print(sym_table)
                if len(symbols) > 30:
                    self.console.print(f"[dim]  ... and {len(symbols) - 30} more symbols[/dim]")

        # Errors/warnings
        if errors:
            self.console.print(f"\n[bold red]Semantic Errors ({len(errors)})[/bold red]")
            for err in errors[:10]:
                msg = str(err) if not hasattr(err, 'message') else err.message
                line = ""
                if hasattr(err, 'span') and err.span:
                    line = f" [dim](line {err.span.start_line})[/dim]"
                self.console.print(f"  [red]✗[/red] {msg}{line}")
            if len(errors) > 10:
                self.console.print(f"  [dim]... and {len(errors) - 10} more[/dim]")

    def _display_codegen(self, result: dict):
        """Display code generation results."""
        if not result:
            self.console.print("[dim]  Code generation skipped[/dim]")
            return

        output_code = result.get("output_code", "")
        output_path = result.get("output_path", "")
        byte_count = result.get("bytes", len(output_code))
        output_label = output_path or "(not written; in-memory)"
        backend_name = result.get("language", self.backend.capitalize())
        syntax_name = result.get("syntax", self.backend)

        # Summary line
        self.console.print(
            f"  Backend: [cyan]{backend_name}[/cyan]  Output: [green]{output_label}[/green]  Size: [dim]{byte_count} bytes[/dim]"
        )

        # Show generated code with backend-specific syntax highlighting
        if output_code:
            try:
                code_syntax = Syntax(
                    output_code.rstrip(),
                    syntax_name,
                    theme="monokai",
                    line_numbers=True,
                )
                code_panel = Panel(
                    code_syntax,
                    title=f"Generated {backend_name}: {output_path or 'in-memory'}",
                    border_style="magenta",
                    padding=(0, 1),
                )
                self.console.print(code_panel)
            except Exception:
                self.console.print(Panel(output_code, title="Generated Code", border_style="magenta"))

    def _display_pipeline_summary(self, tokens, ast, semantic_results, codegen_result, input_path):
        """Display a final pipeline summary."""
        self.console.print()

        token_count = len([t for t in tokens if t.type.name != 'EOF']) if tokens else 0
        decl_count = len(ast.declarations) if ast and hasattr(ast, 'declarations') and ast.declarations else 0
        errors = semantic_results.get("errors", []) if semantic_results else []
        error_count = len(errors)
        output_path = codegen_result.get("output_path", "") if codegen_result else ""
        byte_count = codegen_result.get("bytes", 0) if codegen_result else 0
        output_code = codegen_result.get("output_code", "") if codegen_result else ""

        summary = Table(show_header=False, box=None, pad_edge=False, show_edge=False)
        summary.add_column("Stage", style="bold", width=20)
        summary.add_column("Result")

        summary.add_row("Lexer", f"[green]{token_count}[/green] tokens")
        summary.add_row("Parser", f"[green]{decl_count}[/green] declarations")
        if error_count > 0:
            summary.add_row("Semantic", f"[red]{error_count}[/red] errors")
        else:
            summary.add_row("Semantic", "[green]✓[/green] clean")
        if output_path:
            summary.add_row("Codegen", f"[green]✓[/green] {output_path} ({byte_count} bytes)")
        elif output_code:
            summary.add_row("Codegen", f"[green]✓[/green] generated in-memory ({byte_count} bytes)")
        else:
            summary.add_row("Codegen", "[dim]skipped[/dim]")

        panel = Panel(summary, title=f"[bold]Compilation Summary: {input_path}[/bold]", border_style="blue")
        self.console.print(panel)

    def _collect_symbols(self, symbol_table) -> list:
        """Collect symbols from a symbol table for display."""
        symbols = []
        scope = symbol_table.current_scope if hasattr(symbol_table, 'current_scope') else None
        if scope is None and hasattr(symbol_table, 'global_scope'):
            scope = symbol_table.global_scope

        visited = set()
        self._walk_scope(scope, symbols, "global", visited)
        return symbols

    def _walk_scope(self, scope, symbols: list, scope_name: str, visited: set):
        """Walk scopes to collect symbols (iterative)."""
        if scope is None:
            return

        stack = [(scope, scope_name)]
        while stack:
            current, cur_name = stack.pop()
            if current is None or id(current) in visited:
                continue
            visited.add(id(current))

            sym_dict = getattr(current, 'symbols', {})
            for name, sym in sym_dict.items():
                kind_str = sym.kind.name if hasattr(sym, 'kind') and hasattr(sym.kind, 'name') else "?"
                display_name = self._format_symbol_name(sym, name, cur_name)
                type_str = self._format_symbol_type(sym, cur_name)
                symbols.append({"name": display_name, "kind": kind_str, "type": type_str, "scope": cur_name})

            children = getattr(current, 'children', [])
            for i, child in enumerate(reversed(children)):
                child_name = getattr(child, 'name', f"scope_{len(children) - 1 - i}")
                stack.append((child, child_name))

    def _is_unknown_symbol_type(self, sym) -> bool:
        """Check whether a symbol currently has an unresolved/unknown type."""
        sym_type = getattr(sym, "type", None)
        if sym_type is None:
            return True

        kind = getattr(sym_type, "kind", None)
        if getattr(kind, "name", None) == "UNKNOWN":
            return True

        try:
            return str(sym_type) == "unknown type"
        except Exception:
            return True

    def _is_anonymous_marker(self, value: str) -> bool:
        text = (value or "").strip().lower()
        return text in self._ANONYMOUS_MARKERS

    def _format_symbol_name(self, sym, fallback_name: str, scope_name: str) -> str:
        """Create a readable symbol name, including anonymous/inline forms."""
        raw_name = getattr(sym, "name", None) or fallback_name or ""
        kind_name = getattr(getattr(sym, "kind", None), "name", "?")

        if not self._is_anonymous_marker(raw_name):
            return raw_name

        if kind_name == "STRUCT":
            return "(anonymous struct)"
        if kind_name == "ENUM":
            return "(anonymous enum)"
        if kind_name == "UNION":
            return "(anonymous union)"
        if kind_name == "FUNCTION":
            return "(anonymous function)"
        if kind_name == "TYPE":
            return "(anonymous type)"
        if kind_name == "ENUM_VARIANT":
            return "(anonymous enum variant)"
        if kind_name == "CONSTANT":
            return "(anonymous constant)"
        if kind_name == "MODULE":
            return "(anonymous module)"
        if kind_name == "VARIABLE":
            if scope_name.startswith("struct_") or scope_name.startswith("union_"):
                return "(anonymous field)"
            return "(anonymous variable)"
        return "(anonymous symbol)"

    def _format_symbol_type(self, sym, scope_name: str) -> str:
        """Render symbol type in a user-facing, kind-aware format."""
        kind_name = getattr(getattr(sym, "kind", None), "name", "?")
        raw_name = getattr(sym, "name", "") or ""
        anonymous = self._is_anonymous_marker(raw_name)

        if not self._is_unknown_symbol_type(sym):
            try:
                return str(sym.type)
            except Exception:
                return "unresolved"

        if kind_name == "MODULE":
            return "module"
        if kind_name == "FUNCTION":
            return "fn (anonymous)" if anonymous else "fn(...)"
        if kind_name == "STRUCT":
            return "struct (anonymous)" if anonymous else f"struct {raw_name}"
        if kind_name == "ENUM":
            return "enum (anonymous)" if anonymous else f"enum {raw_name}"
        if kind_name == "UNION":
            return "union (anonymous)" if anonymous else f"union {raw_name}"
        if kind_name == "TYPE":
            return "type (anonymous)" if anonymous else f"type {raw_name}"
        if kind_name == "GENERIC_PARAM":
            return "generic parameter"
        if kind_name == "ENUM_VARIANT":
            return "enum variant"
        if kind_name == "CONSTANT":
            return "unresolved constant"
        if kind_name == "VARIABLE":
            if scope_name.startswith("struct_") or scope_name.startswith("union_"):
                return "unresolved field"
            return "unresolved variable"
        return "unresolved"

    def _display_source_panel(self, source_code: str, input_path: str):
        """Display source code with syntax highlighting."""
        if self.mode == "tokens":
            title = f"Tokenization: {input_path}"
        elif self.mode == "ast":
            title = f"Parsing: {input_path}"
        elif self.mode == "semantic":
            title = f"Semantic Analysis: {input_path}"
        elif self.mode == "pipeline":
            title = f"Pipeline Inspection: {input_path}"
        elif self.mode == "doc":
            title = f"Documentation Build: {input_path}"
        else:
            title = f"Compilation: {input_path}"

        # Use syntax highlighting for A7 code (fallback to text)
        try:
            source_syntax = Syntax(
                source_code, "rust", theme="monokai", line_numbers=True
            )
        except:
            source_syntax = source_code

        code_panel = Panel(source_syntax, title=title, border_style="blue")
        self.console.print(code_panel)

    def _display_tokens(self, tokens: list):
        """Display tokenization results in a table."""
        self.console.print("\n[bold cyan]TOKENIZATION RESULTS[/bold cyan]")

        token_table = Table(show_header=True, header_style="bold magenta")
        token_table.add_column("Pos", style="dim", width=6)
        token_table.add_column("Line:Col", style="cyan", width=8)
        token_table.add_column("Token Type", style="green", width=16)
        token_table.add_column("Value", style="yellow")
        token_table.add_column("Length", style="dim", width=6)

        for i, token in enumerate(tokens):
            if token.type.name == "EOF":
                continue  # Skip EOF for cleaner display

            token_table.add_row(
                str(i),
                f"{token.line}:{token.column}",
                token.type.name,
                repr(token.value) if token.value else "''",
                str(token.length) if hasattr(token, "length") else "?",
            )

        self.console.print(token_table)
        self.console.print(
            f"[dim]Total tokens: {len([t for t in tokens if t.type.name != 'EOF'])}[/dim]"
        )

    def _display_ast(self, ast):
        """Display AST structure as a tree."""
        self.console.print("\n[bold cyan]PARSING RESULTS[/bold cyan]")

        if ast:
            self.console.print("[green]Successfully parsed into AST[/green]")

            # AST summary
            summary_text = Text()
            summary_text.append("AST Root: ", style="bold")
            summary_text.append(f"{ast.kind.name}", style="cyan bold")
            if hasattr(ast, "declarations") and ast.declarations:
                summary_text.append(
                    f" with {len(ast.declarations)} top-level declarations",
                    style="dim",
                )
            self.console.print(summary_text)

            # AST tree structure
            if hasattr(ast, "declarations") and ast.declarations:
                tree = Tree("Program")
                for decl in ast.declarations:
                    decl_node = tree.add(self.format_declaration_node(decl))

                    # Add function body details
                    if (
                        hasattr(decl, "body")
                        and decl.body
                        and hasattr(decl.body, "statements")
                        and decl.body.statements is not None
                    ):
                        self._add_statements_to_tree(
                            decl_node, decl.body.statements
                        )

                self.console.print(tree)

            # Stop here for AST mode
            if self.mode == "ast":
                self.console.print(
                    "\n[bold dim]Stopping before semantic analysis and code generation[/bold dim]"
                )
        else:
            self.console.print("[red]Failed to parse AST[/red]")
            self.console.print(
                "[dim]Check tokenization output above for potential issues[/dim]"
            )

    def format_declaration_node(self, decl) -> str:
        """Format a declaration node for tree display."""
        label = f"[green]{decl.kind.name}[/green]"

        if hasattr(decl, "name") and decl.name:
            label += f" [yellow]{decl.name}[/yellow]"

        # Add parameters with types for functions
        if decl.kind.name == "FUNCTION":
            if hasattr(decl, "parameters") and decl.parameters:
                params = []
                for param in decl.parameters:
                    param_str = ""
                    if hasattr(param, "name") and param.name:
                        param_str = param.name
                    if hasattr(param, "param_type") and param.param_type:
                        type_str = self.format_type(param.param_type)
                        if param_str:
                            param_str += f": {type_str}"
                        else:
                            param_str = type_str
                    elif not param_str:
                        param_str = "?"
                    params.append(param_str)

                label += f" [blue]({', '.join(params)})[/blue]"
            else:
                label += f" [blue]()[/blue]"

            # Add return type
            if hasattr(decl, "return_type") and decl.return_type:
                ret_type_str = self.format_type(decl.return_type)
                label += f" [cyan]→ {ret_type_str}[/cyan]"
            else:
                label += f" [dim]→ void[/dim]"

        # For other declarations, show type if available
        elif hasattr(decl, "explicit_type") and decl.explicit_type:
            type_str = self.format_type(decl.explicit_type)
            label += f" [cyan]: {type_str}[/cyan]"

        if hasattr(decl, "span") and decl.span:
            label += f" [dim](line {decl.span.start_line})[/dim]"

        return label

    def format_type(self, type_node) -> str:
        """Format a type node for display (iterative for wrapper chains)."""
        if not type_node:
            return "?"

        # Iteratively unwrap wrapper types (array/slice/pointer)
        prefixes: list = []
        current = type_node

        while current and hasattr(current, "kind"):
            kind = current.kind.name
            if kind == "TYPE_ARRAY":
                if hasattr(current, "size") and current.size:
                    size = str(current.size.literal_value) if hasattr(current.size, "literal_value") else "?"
                else:
                    size = "?"
                prefixes.append(f"[{size}]")
                current = current.element_type if hasattr(current, "element_type") else None
            elif kind == "TYPE_SLICE":
                prefixes.append("[]")
                current = current.element_type if hasattr(current, "element_type") else None
            elif kind == "TYPE_POINTER":
                prefixes.append("ref ")
                current = current.target_type if hasattr(current, "target_type") else None
            else:
                break  # Leaf type

        # Format the leaf type
        leaf = "?"
        if current and hasattr(current, "kind"):
            kind = current.kind.name
            if kind == "TYPE_PRIMITIVE":
                leaf = current.type_name if hasattr(current, "type_name") else "primitive"
            elif kind == "TYPE_IDENTIFIER":
                leaf = current.name if hasattr(current, "name") else "identifier"
            elif kind == "TYPE_GENERIC":
                base_name = current.name if hasattr(current, "name") else "?"
                if hasattr(current, "type_args") and current.type_args:
                    args = [self.format_type(arg) for arg in current.type_args]
                    leaf = f"{base_name}({', '.join(args)})"
                else:
                    leaf = base_name
            elif kind == "TYPE_FUNCTION":
                param_types = []
                if hasattr(current, "parameter_types") and current.parameter_types:
                    param_types = [self.format_type(pt) for pt in current.parameter_types]
                params_str = ", ".join(param_types)
                ret_type = ""
                if hasattr(current, "return_type") and current.return_type:
                    ret_type = " " + self.format_type(current.return_type)
                leaf = f"fn({params_str}){ret_type}"
            elif kind == "TYPE_STRUCT":
                field_count = len(current.fields) if hasattr(current, "fields") and current.fields else 0
                leaf = f"struct {{ {field_count} fields }}"
            else:
                if hasattr(current, "type_name"):
                    leaf = current.type_name
                elif hasattr(current, "name"):
                    leaf = current.name
                else:
                    leaf = str(current)
        elif current:
            if hasattr(current, "type_name"):
                leaf = current.type_name
            elif hasattr(current, "name"):
                leaf = current.name
            else:
                leaf = str(current)

        return "".join(prefixes) + leaf

    def format_expression_detail(self, expr) -> str:
        """Format expression detail for display in AST tree."""
        if not expr or not hasattr(expr, "kind"):
            return None

        kind = expr.kind.name

        # Function calls - show function name
        if kind == "CALL":
            func_name = "?"
            if hasattr(expr, "function") and expr.function:
                func_expr = expr.function
                # Check if it's a field access (method call) first
                if hasattr(func_expr, "kind") and func_expr.kind.name == "FIELD_ACCESS":
                    obj_name = "_"
                    if hasattr(func_expr, "object") and func_expr.object and hasattr(func_expr.object, "name") and func_expr.object.name:
                        obj_name = func_expr.object.name
                    field_name = "?"
                    if hasattr(func_expr, "field") and func_expr.field:
                        field_name = func_expr.field
                    func_name = f"{obj_name}.{field_name}"
                # Check if it's a simple identifier
                elif hasattr(func_expr, "name") and func_expr.name:
                    func_name = func_expr.name

            arg_count = len(expr.arguments) if hasattr(expr, "arguments") and expr.arguments else 0
            return f"[magenta]call[/magenta] [yellow]{func_name}[/yellow]() [dim]({arg_count} args)[/dim]"

        # Binary operations - show operator
        elif kind == "BINARY":
            op = "?"
            if hasattr(expr, "operator") and expr.operator:
                op = expr.operator.name.lower()
            return f"[magenta]binary_op[/magenta] [cyan]{op}[/cyan]"

        # Unary operations - show operator
        elif kind == "UNARY":
            op = "?"
            if hasattr(expr, "operator") and expr.operator:
                op = expr.operator.name.lower()
            return f"[magenta]unary_op[/magenta] [cyan]{op}[/cyan]"

        # Identifier - show name
        elif kind == "IDENTIFIER":
            name = expr.name if hasattr(expr, "name") else "?"
            return f"[magenta]identifier[/magenta] [yellow]{name}[/yellow]"

        # Literal - show kind and value
        elif kind == "LITERAL":
            lit_kind = "?"
            lit_val = ""
            if hasattr(expr, "literal_kind") and expr.literal_kind:
                lit_kind = expr.literal_kind.name.lower()
            if hasattr(expr, "literal_value"):
                val_str = str(expr.literal_value)
                if len(val_str) > 20:
                    val_str = val_str[:20] + "..."
                lit_val = f" [dim]{val_str}[/dim]"
            return f"[magenta]literal[/magenta] [cyan]{lit_kind}[/cyan]{lit_val}"

        # Field access - show field name
        elif kind == "FIELD_ACCESS":
            field = expr.field if hasattr(expr, "field") else "?"
            return f"[magenta]field_access[/magenta] [yellow].{field}[/yellow]"

        # Array index
        elif kind == "INDEX":
            return f"[magenta]index[/magenta]"

        # Cast expression
        elif kind == "CAST":
            type_str = "?"
            if hasattr(expr, "target_type"):
                type_str = self.format_type(expr.target_type)
            return f"[magenta]cast[/magenta] [cyan]→ {type_str}[/cyan]"

        # If expression
        elif kind == "IF_EXPR":
            return f"[magenta]if_expr[/magenta]"

        # Struct initialization
        elif kind == "STRUCT_INIT":
            type_name = "?"
            if hasattr(expr, "struct_type"):
                type_name = self.format_type(expr.struct_type)
            field_count = len(expr.field_inits) if hasattr(expr, "field_inits") and expr.field_inits else 0
            return f"[magenta]struct_init[/magenta] [cyan]{type_name}[/cyan] [dim]({field_count} fields)[/dim]"

        # Array initialization
        elif kind == "ARRAY_INIT":
            elem_count = len(expr.elements) if hasattr(expr, "elements") and expr.elements else 0
            return f"[magenta]array_init[/magenta] [dim]({elem_count} elements)[/dim]"

        # New expression
        elif kind == "NEW_EXPR":
            type_str = "?"
            if hasattr(expr, "target_type"):
                type_str = self.format_type(expr.target_type)
            return f"[magenta]new[/magenta] [cyan]{type_str}[/cyan]"

        # Default - just show the kind
        else:
            return f"[magenta]{kind.lower()}[/magenta]"

    def format_statement_label(self, stmt) -> str:
        """Format a statement label with detailed information."""
        if not stmt or not hasattr(stmt, "kind"):
            return "[dim]unknown[/dim]"

        kind = stmt.kind.name
        stmt_label = f"[blue]{kind}[/blue]"

        # Variable/Constant declarations
        if kind in ("VAR", "CONST"):
            if hasattr(stmt, "name") and stmt.name:
                stmt_label += f" [yellow]{stmt.name}[/yellow]"
            if hasattr(stmt, "explicit_type") and stmt.explicit_type:
                type_str = self.format_type(stmt.explicit_type)
                stmt_label += f" [cyan]{type_str}[/cyan]"
            if hasattr(stmt, "value") and stmt.value:
                val_detail = self.format_expression_detail(stmt.value)
                if val_detail:
                    stmt_label += f" = {val_detail}"

        # Expression statements - show what kind of expression
        elif kind == "EXPRESSION_STMT":
            if hasattr(stmt, "expression") and stmt.expression:
                expr_detail = self.format_expression_detail(stmt.expression)
                if expr_detail:
                    stmt_label += f" → {expr_detail}"

        # Assignment statements
        elif kind == "ASSIGNMENT":
            if hasattr(stmt, "target"):
                target_name = "?"
                if hasattr(stmt.target, "name"):
                    target_name = stmt.target.name
                elif hasattr(stmt.target, "field"):
                    target_name = f"_.{stmt.target.field}"
                stmt_label += f" [yellow]{target_name}[/yellow]"

            if hasattr(stmt, "operator") and stmt.operator:
                op_str = "="
                if hasattr(stmt.operator, "name"):
                    op_name = stmt.operator.name
                    if op_name == "ASSIGN":
                        op_str = "="
                    elif op_name == "ADD_ASSIGN":
                        op_str = "+="
                    elif op_name == "SUB_ASSIGN":
                        op_str = "-="
                    elif op_name == "MUL_ASSIGN":
                        op_str = "*="
                    elif op_name == "DIV_ASSIGN":
                        op_str = "/="
                    elif op_name == "MOD_ASSIGN":
                        op_str = "%="
                    else:
                        op_str = op_name.replace("_ASSIGN", "").lower() + "="
                stmt_label += f" [cyan]{op_str}[/cyan]"

            if hasattr(stmt, "value") and stmt.value:
                val_detail = self.format_expression_detail(stmt.value)
                if val_detail:
                    stmt_label += f" {val_detail}"

        # Return statements
        elif kind == "RETURN":
            if hasattr(stmt, "value") and stmt.value:
                val_detail = self.format_expression_detail(stmt.value)
                if val_detail:
                    stmt_label += f" {val_detail}"
            else:
                stmt_label += " [dim](void)[/dim]"

        # If statements
        elif kind == "IF_STMT":
            if hasattr(stmt, "condition") and stmt.condition:
                cond_detail = self.format_expression_detail(stmt.condition)
                if cond_detail:
                    stmt_label += f" {cond_detail}"

        # While loops
        elif kind == "WHILE":
            if hasattr(stmt, "condition") and stmt.condition:
                cond_detail = self.format_expression_detail(stmt.condition)
                if cond_detail:
                    stmt_label += f" {cond_detail}"

        # For loops
        elif kind == "FOR":
            parts = []
            if hasattr(stmt, "init") and stmt.init and hasattr(stmt.init, "name"):
                parts.append(f"[yellow]{stmt.init.name}[/yellow]")
            if hasattr(stmt, "condition") and stmt.condition:
                cond_detail = self.format_expression_detail(stmt.condition)
                if cond_detail:
                    parts.append(cond_detail)
            if parts:
                stmt_label += f" ({'; '.join(parts)})"

        # For-in loops
        elif kind in ("FOR_IN", "FOR_IN_INDEXED"):
            if hasattr(stmt, "iterator") and stmt.iterator:
                stmt_label += f" [yellow]{stmt.iterator}[/yellow]"
            if kind == "FOR_IN_INDEXED" and hasattr(stmt, "index_var") and stmt.index_var:
                stmt_label = stmt_label.replace(f" [yellow]{stmt.iterator}[/yellow]",
                                                  f" [yellow]{stmt.index_var}, {stmt.iterator}[/yellow]")
            if hasattr(stmt, "iterable") and stmt.iterable:
                iter_detail = self.format_expression_detail(stmt.iterable)
                if iter_detail:
                    stmt_label += f" in {iter_detail}"

        # Match statements
        elif kind == "MATCH":
            if hasattr(stmt, "expression") and stmt.expression:
                expr_detail = self.format_expression_detail(stmt.expression)
                if expr_detail:
                    stmt_label += f" {expr_detail}"
            if hasattr(stmt, "cases") and stmt.cases:
                stmt_label += f" [dim]({len(stmt.cases)} cases)[/dim]"

        # Break/Continue with labels
        elif kind in ("BREAK", "CONTINUE"):
            if hasattr(stmt, "label") and stmt.label:
                stmt_label += f" [yellow]{stmt.label}[/yellow]"

        # Defer statements
        elif kind == "DEFER":
            if hasattr(stmt, "statement") and stmt.statement:
                deferred_detail = self.format_statement_label(stmt.statement)
                stmt_label += f" → {deferred_detail}"

        # Del statements
        elif kind == "DEL":
            if hasattr(stmt, "expression") and stmt.expression:
                expr_detail = self.format_expression_detail(stmt.expression)
                if expr_detail:
                    stmt_label += f" {expr_detail}"

        # Block statements - show statement count
        elif kind == "BLOCK":
            if hasattr(stmt, "statements") and stmt.statements:
                stmt_label += f" [dim]({len(stmt.statements)} stmts)[/dim]"

        return stmt_label

    def _add_statements_to_tree(self, parent_node, statements):
        """Add statement nodes to the tree (iterative)."""
        if statements is None:
            return

        # Stack of (parent_tree_node, statements_list)
        stack = [(parent_node, statements)]
        while stack:
            parent, stmts = stack.pop()
            for stmt in stmts:
                stmt_label = self.format_statement_label(stmt)
                stmt_node = parent.add(stmt_label)

                if hasattr(stmt, "statements") and stmt.statements:
                    stack.append((stmt_node, stmt.statements))
                elif hasattr(stmt, "then_stmt") and stmt.then_stmt:
                    if hasattr(stmt.then_stmt, "statements") and stmt.then_stmt.statements:
                        stack.append((stmt_node, stmt.then_stmt.statements))
                    if hasattr(stmt, "else_stmt") and stmt.else_stmt:
                        if hasattr(stmt.else_stmt, "statements") and stmt.else_stmt.statements:
                            stack.append((stmt_node, stmt.else_stmt.statements))
