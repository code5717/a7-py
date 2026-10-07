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
from rich.markup import escape

from .ast_walk import STATEMENT_FIELDS, iter_children
from .scope_walk import iter_scopes

# Statement fields whose BLOCK child is not shown as a node of its own: its
# statements hang directly under the owner (function, loop, `if`, case).
_INLINE_BLOCK_FIELDS = frozenset({"body", "then_stmt", "statement"})
# Label prefix that tells a child apart from the owner's main body.
_FIELD_PREFIXES = {
    "else_stmt": "[blue]ELSE[/blue] → ",
    "else_case": "[blue]ELSE[/blue] → ",
    "init": "[dim]init[/dim] ",
    "update": "[dim]update[/dim] ",
}


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
                        Text(sym.get("name", "?")),
                        sym.get("kind", "?"),
                        Text(sym.get("type", "?")),
                        Text(sym.get("scope", "global")),
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
                self.console.print(f"  [red]✗[/red] {escape(msg)}{line}")
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
            f"  Backend: [cyan]{escape(backend_name)}[/cyan]  Output: [green]{escape(output_label)}[/green]  Size: [dim]{byte_count} bytes[/dim]"
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
                    title=Text(f"Generated {backend_name}: {output_path or 'in-memory'}"),
                    border_style="magenta",
                    padding=(0, 1),
                )
                self.console.print(code_panel)
            except Exception:
                self.console.print(Panel(Text(output_code), title="Generated Code", border_style="magenta"))

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
            summary.add_row("Codegen", f"[green]✓[/green] {escape(output_path)} ({byte_count} bytes)")
        elif output_code:
            summary.add_row("Codegen", f"[green]✓[/green] generated in-memory ({byte_count} bytes)")
        else:
            summary.add_row("Codegen", "[dim]skipped[/dim]")

        panel = Panel(summary, title=Text(f"Compilation Summary: {input_path}", style="bold"), border_style="blue")
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
        """Walk scopes to collect symbols (iterative, see scope_walk.iter_scopes)."""
        for current, cur_name in iter_scopes(scope, scope_name, visited):
            sym_dict = getattr(current, 'symbols', {})
            for name, sym in sym_dict.items():
                kind_str = sym.kind.name if hasattr(sym, 'kind') and hasattr(sym.kind, 'name') else "?"
                display_name = self._format_symbol_name(sym, name, cur_name)
                type_str = self._format_symbol_type(sym, cur_name)
                symbols.append({"name": display_name, "kind": kind_str, "type": type_str, "scope": cur_name})

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

        # A7 has no Pygments lexer; the Rust one is the closest match.
        source_syntax = Syntax(source_code, "rust", theme="monokai", line_numbers=True)

        code_panel = Panel(source_syntax, title=Text(title), border_style="blue")
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
                Text(repr(token.value) if token.value else "''"),
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
        """Format type wrappers and child types without recursive calls."""
        parts = []
        stack = [("visit", type_node)]
        active = set()
        while stack:
            event, current = stack.pop()
            if event == "exit":
                active.remove(current)
                continue
            if event == "text":
                parts.append(current)
                continue
            if not current:
                parts.append("?")
                continue
            identity = id(current)
            if identity in active:
                parts.append("<cycle>")
                continue
            active.add(identity)
            stack.append(("exit", identity))
            kind = getattr(getattr(current, "kind", None), "name", None)
            children = []
            if kind == "TYPE_ARRAY":
                size_node = getattr(current, "size", None)
                size = str(size_node.literal_value) if size_node and hasattr(size_node, "literal_value") else "?"
                parts.append(f"[{size}]")
                children = [("visit", getattr(current, "element_type", None))]
            elif kind == "TYPE_SLICE":
                parts.append("[]")
                children = [("visit", getattr(current, "element_type", None))]
            elif kind == "TYPE_POINTER":
                parts.append("ref ")
                children = [("visit", getattr(current, "target_type", None))]
            elif kind == "TYPE_PRIMITIVE":
                parts.append(getattr(current, "type_name", None) or "primitive")
            elif kind == "TYPE_IDENTIFIER":
                parts.append(getattr(current, "name", None) or "identifier")
            elif kind in {"TYPE_GENERIC", "TYPE_FUNCTION", "TYPE_SET"}:
                generic = kind == "TYPE_GENERIC"
                argument_field = "type_args" if generic else "types" if kind == "TYPE_SET" else "parameter_types"
                args = getattr(current, argument_field, None) or []
                parts.append((getattr(current, "name", None) or "?") if generic
                             else "@type_set" if kind == "TYPE_SET" else "fn")
                if args or not generic:
                    parts.append("(")
                    for index, arg in enumerate(args):
                        if index:
                            children.append(("text", ", "))
                        children.append(("visit", arg))
                    children.append(("text", ")"))
                result = getattr(current, "return_type", None)
                if kind == "TYPE_FUNCTION" and result:
                    children.extend([("text", " "), ("visit", result)])
            elif kind == "TYPE_STRUCT":
                parts.append(f"struct {{ {len(getattr(current, 'fields', None) or [])} fields }}")
            else:
                parts.append(getattr(current, "type_name", None)
                             or getattr(current, "name", None) or kind or str(current))
            stack.extend(reversed(children))
        return "".join(str(part) for part in parts)

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
                lit_val = f" [dim]{escape(val_str)}[/dim]"
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

    def _format_pattern(self, pattern) -> str:
        """One match pattern as source-like text."""
        def literal_text(holder) -> str:
            literal = getattr(holder, "literal", None)
            if literal is None:
                return "?"
            return str(literal.raw_text or literal.literal_value)

        kind = pattern.kind.name
        if kind == "PATTERN_WILDCARD":
            return "_"
        if kind == "PATTERN_IDENTIFIER":
            return pattern.name or "?"
        if kind == "PATTERN_ENUM":
            return f"{pattern.enum_type or ''}.{pattern.variant or '?'}"
        if kind == "PATTERN_LITERAL":
            return literal_text(pattern)
        if kind == "PATTERN_RANGE":
            return f"{literal_text(pattern.start)}..{literal_text(pattern.end)}"
        return kind.lower()

    def format_statement_label(self, stmt) -> str:
        """Format a statement label with detailed information."""
        prefixes = []
        seen = set()
        while (stmt and getattr(getattr(stmt, "kind", None), "name", None) == "DEFER"
               and getattr(stmt, "statement", None)):
            if id(stmt) in seen:
                return "".join(prefixes) + "[dim]<cycle>[/dim]"
            seen.add(id(stmt))
            prefixes.append("[blue]DEFER[/blue] → ")
            stmt = stmt.statement
        prefix = "".join(prefixes)
        if not stmt or not hasattr(stmt, "kind"):
            return prefix + "[dim]unknown[/dim]"

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

        # Match cases - show the patterns
        elif kind == "CASE_BRANCH":
            patterns = [self._format_pattern(pattern) for pattern in (stmt.patterns or [])]
            stmt_label += f" [yellow]{escape(', '.join(patterns))}[/yellow]"

        # Break/Continue with labels
        elif kind in ("BREAK", "CONTINUE"):
            if hasattr(stmt, "label") and stmt.label:
                stmt_label += f" [yellow]{stmt.label}[/yellow]"

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

        return prefix + stmt_label

    def _add_statements_to_tree(self, parent_node, statements):
        """Add one tree node per statement, with every nested statement under it.

        Children come from the shared `iter_children`, filtered to the
        statement-holding fields: loop bodies, both `if` branches (an
        `else if` chain included), match cases and the match `else`, `for`
        init and update, and the statement under a `defer`. Expressions are
        summarized in the statement label and get no node of their own.
        Iterative: explicit stack.
        """
        if statements is None:
            return

        # ("stmt", parent tree node, statement, label prefix) adds a node;
        # ("children", tree node, statement, "") adds what is nested in it.
        stack = [("stmt", parent_node, stmt, "") for stmt in reversed(statements)]
        while stack:
            op, tree_node, stmt, label_prefix = stack.pop()
            if op == "stmt":
                stmt_node = tree_node.add(label_prefix + self.format_statement_label(stmt))
                stack.append(("children", stmt_node, stmt, ""))
                continue

            # The label already spells out a `defer` chain down to the
            # deferred statement; nested statements are that statement's.
            seen = set()
            while (getattr(getattr(stmt, "kind", None), "name", None) == "DEFER"
                   and getattr(stmt, "statement", None) and id(stmt) not in seen):
                seen.add(id(stmt))
                stmt = stmt.statement
            if not hasattr(stmt, "kind"):
                continue

            nested = []
            for field, _, child in iter_children(stmt):
                if field not in STATEMENT_FIELDS:
                    continue
                if field in _INLINE_BLOCK_FIELDS and child.kind.name == "BLOCK":
                    nested.append(("children", tree_node, child, ""))
                else:
                    nested.append(("stmt", tree_node, child, _FIELD_PREFIXES.get(field, "")))
            stack.extend(reversed(nested))
