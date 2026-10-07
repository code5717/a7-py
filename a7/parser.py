"""
Recursive descent parser for the A7 programming language.

This parser implements the A7 grammar as specified in docs/SPEC.md section 13.
It uses a simple recursive descent approach with precedence climbing for expressions.
"""

from typing import List, Optional
from .tokens import Token, TokenType, Tokenizer
from .ast_nodes import (
    ASTNode,
    NodeKind,
    create_program,
    create_identifier,
    create_binary_expr,
    create_function_decl,
    create_primitive_type,
    create_block,
    create_parameter,
    create_function_type,
    create_inline_struct_type,
    create_return_stmt,
    create_call_expr,
    create_assignment_stmt,
    create_var_decl,
    create_const_decl,
    create_cast_expr,
    create_new_expr,
    create_del_stmt,
    create_literal_from_token,
    create_span_from_token,
    create_span_from_tokens,
    combine_spans,
    token_to_binary_op,
    token_to_unary_op,
    token_to_assign_op,
    get_binary_precedence,
)
from .errors import ParseError, SourceSpan


_PRIMITIVE_TYPE_TOKENS = frozenset({
    TokenType.I8, TokenType.I16, TokenType.I32, TokenType.I64,
    TokenType.U8, TokenType.U16, TokenType.U32, TokenType.U64,
    TokenType.ISIZE, TokenType.USIZE, TokenType.F32, TokenType.F64,
    TokenType.BOOL, TokenType.CHAR, TokenType.STRING,
})
# Tokens that start a type and cannot start an expression.
_TYPE_ONLY_STARTS = _PRIMITIVE_TYPE_TOKENS | {TokenType.REF, TokenType.GENERIC_TYPE}
# Every token that can start a type.
_TYPE_STARTS = _TYPE_ONLY_STARTS | {
    TokenType.IDENTIFIER, TokenType.LEFT_BRACKET, TokenType.FN, TokenType.STRUCT,
}
_OPENERS = {
    TokenType.LEFT_PAREN: TokenType.RIGHT_PAREN,
    TokenType.LEFT_BRACKET: TokenType.RIGHT_BRACKET,
    TokenType.LEFT_BRACE: TokenType.RIGHT_BRACE,
}
_CLOSERS = frozenset(_OPENERS.values())
_ASSIGNABLE_KINDS = frozenset({NodeKind.IDENTIFIER, NodeKind.FIELD_ACCESS, NodeKind.INDEX})


def _scan_brackets(tokens: List[Token]) -> tuple[List[int], dict]:
    """One pass over the tokens: nesting depth before each token, and for
    each opening bracket the index of its matching closer (absent when the
    brackets do not pair up)."""
    depth_at: List[int] = []
    close_at: dict = {}
    open_stack: List[int] = []
    for index, token in enumerate(tokens):
        depth_at.append(len(open_stack))
        if token.type in _OPENERS:
            open_stack.append(index)
        elif token.type in _CLOSERS and open_stack:
            opener = open_stack.pop()
            if _OPENERS[tokens[opener].type] == token.type:
                close_at[opener] = index
    return depth_at, close_at


def _describe(token: Token) -> str:
    """How a diagnostic names the token it found."""
    if token.type == TokenType.EOF:
        return "end of file"
    if token.type == TokenType.TERMINATOR:
        return "';'" if token.value == ";" else "a line break"
    return f"'{token.value}'"


def _span_through(start: SourceSpan, end_token: Token) -> SourceSpan:
    """Span from the start of `start` through `end_token`."""
    return SourceSpan(
        start_line=start.start_line,
        start_column=start.start_column,
        end_line=end_token.line,
        end_column=end_token.column + end_token.length,
    )


class Parser:
    """Parse A7 using statement and expression worklists."""

    # Logical grammar-depth cap, independent of the Python stack. Binary and
    # unary entries both count, so one parenthesis level consumes two entries.
    MAX_NESTING_DEPTH = 256

    def __init__(
        self,
        tokens: List[Token],
        filename: Optional[str] = None,
        source_lines: Optional[List[str]] = None,
    ):
        self.tokens = tokens
        self.filename = filename
        self.source_lines = source_lines or []
        self.position = 0
        self._nesting_depth = 0
        # Bracket nesting depth before each token, and the index of the
        # closer that matches each opening bracket token.
        self._depth_at, self._close_at = _scan_brackets(tokens)
        # Depth of the `if`/`while`/`for`/`match` header being parsed, or
        # None outside a header. At that depth `Name {` opens the body.
        self._header_depth: Optional[int] = None
        # Start positions where `Name(types){...}` was tried and failed.
        self._not_generic_literal: set = set()

        # Skip to first non-terminator token
        self.skip_terminators()

    def _enter_nesting(self) -> None:
        """Count one nesting level; abort cleanly past the cap."""
        self._nesting_depth += 1
        if self._nesting_depth > self.MAX_NESTING_DEPTH:
            self._nesting_depth -= 1
            raise ParseError.from_token(
                f"Maximum nesting depth ({self.MAX_NESTING_DEPTH}) exceeded",
                self.current(),
                self.filename,
                self.source_lines,
            )

    def _exit_nesting(self) -> None:
        self._nesting_depth -= 1

    def current(self) -> Token:
        """Get current token."""
        if self.position >= len(self.tokens):
            return self.tokens[-1]  # Return EOF token
        return self.tokens[self.position]

    def peek(self, offset: int = 1) -> Token:
        """Peek at token at current position + offset."""
        pos = self.position + offset
        if pos >= len(self.tokens):
            return self.tokens[-1]  # Return EOF token
        return self.tokens[pos]

    def advance(self) -> Token:
        """Advance to next token and return the previous one."""
        prev = self.current()
        if self.position < len(self.tokens) - 1:
            self.position += 1
        return prev

    def _step_back(self) -> None:
        """Move back one token. Never moves before the start of input."""
        if self.position > 0:
            self.position -= 1

    def match(self, *token_types: TokenType) -> bool:
        """Check if current token matches any of the given types."""
        return self.current().type in token_types

    def consume(self, token_type: TokenType, message: str = None) -> Token:
        """Consume a token of the expected type or raise an error."""
        if not self.match(token_type):
            if message is None:
                message = f"Expected {token_type.name}, got {self.current().type.name}"
            raise ParseError.from_token(
                message, self.current(), self.filename, self.source_lines
            )
        return self.advance()

    def skip_terminators(self):
        """Skip newline and semicolon terminators."""
        while self.match(TokenType.TERMINATOR):
            self.advance()

    def at_end(self) -> bool:
        """Check if we're at the end of input."""
        return self.match(TokenType.EOF)

    def _fatal_error(self, message: str, token: Token) -> ParseError:
        """Build a diagnostic for a parser progress failure."""
        error = ParseError.from_token(message, token, self.filename, self.source_lines)
        error.fatal = True
        return error

    def _require_progress(self, iteration_start: int, construct: str) -> None:
        """Raise if one iteration of a loop that runs to a closing token consumed nothing."""
        if self.position == iteration_start and not self.at_end():
            token = self.current()
            raise self._fatal_error(
                f"Unexpected token '{token.value}' in {construct}", token
            )

    def _should_parse_struct_literal(self) -> bool:
        """True if `Name {` at the current `{` is a struct literal.

        In an `if`/`while`/`for`/`match` header the `{` at header depth opens
        the body. Inside parentheses, brackets or braces within the header,
        and everywhere outside a header, `Name {` is a struct literal.
        """
        return (
            self._header_depth is None
            or self._depth_at[self.position] > self._header_depth
        )

    def _require_statement_end(self) -> None:
        """A statement or declaration ends at a newline, `;`, `}` or end of file."""
        if self.match(TokenType.TERMINATOR, TokenType.RIGHT_BRACE, TokenType.EOF):
            return
        # A construct that reads past its own newline (a trailing `where`
        # probe) leaves the terminator just behind the current token.
        if self.position > 0 and self.tokens[self.position - 1].type == TokenType.TERMINATOR:
            return
        token = self.current()
        raise ParseError.from_token(
            f"A statement must end at a newline; unexpected {_describe(token)} on the same line",
            token,
            self.filename,
            self.source_lines,
        )

    def _list_separator(
        self,
        closer: TokenType,
        what: str,
        newlines: bool = True,
        newline_separates: bool = False,
    ) -> None:
        """Consume the separator after one list item.

        Leaves the next item or `closer` current. Items need a `,`; with
        `newline_separates` a newline also separates. A trailing separator
        before `closer` is allowed. `newlines` says whether line breaks may
        appear inside the list at all.
        """
        saw_newline = newlines and self.match(TokenType.TERMINATOR)
        if newlines:
            self.skip_terminators()
        if self.match(TokenType.COMMA):
            self.advance()
            if newlines:
                self.skip_terminators()
            return
        if self.match(closer) or (saw_newline and newline_separates):
            return
        token = self.current()
        separator = "',' or a newline" if newline_separates else "','"
        raise ParseError.from_token(
            f"Expected {separator} between items in {what}, found {_describe(token)}",
            token,
            self.filename,
            self.source_lines,
        )

    def parse(self) -> ASTNode:
        """Parse the entire program."""
        declarations = []

        self.skip_terminators()

        # Compilation cannot use a partial AST. A failed declaration must not
        # disappear or promote its remaining local statements to module scope.
        while not self.at_end():
            previous_position = self.position
            declaration = self.parse_declaration()
            if declaration is not None:
                declarations.append(declaration)
            self._require_statement_end()
            self.skip_terminators()
            self._require_progress(previous_position, "program")

        # Create span for program node
        if declarations:
            first_span = declarations[0].span
            last_span = declarations[-1].span
            if first_span and last_span:
                span = SourceSpan(
                    start_line=first_span.start_line,
                    start_column=first_span.start_column,
                    end_line=last_span.end_line,
                    end_column=last_span.end_column
                )
            else:
                # Default span if declarations don't have spans
                span = SourceSpan(1, 0, 1, 0)
        else:
            # Empty program - use default span
            span = SourceSpan(1, 0, 1, 0)
        return create_program(declarations, span)

    def parse_declaration(self) -> Optional[ASTNode]:
        """Parse top-level declarations."""
        # Skip any leading terminators at declaration level
        self.skip_terminators()

        # Check if we've reached the end after skipping terminators
        if self.at_end():
            return None

        # Handle public modifier
        is_public = False
        if self.match(TokenType.PUB):
            is_public = True
            self.advance()

        # Import declarations: `import "p"` and `using import "p"`.
        # `using` is an identifier, not a keyword (SPEC 2.4).
        if self.match(TokenType.IMPORT) or (
            self.match(TokenType.IDENTIFIER)
            and self.current().value == "using"
            and self.peek().type == TokenType.IMPORT
        ):
            if is_public:
                # SPEC 10.4 and 13.1 allow `pub` on functions, variables,
                # constants and type declarations, not on this import form.
                raise ParseError.from_token(
                    "'pub' cannot be applied to an import; write 'import \"path\"' without it",
                    self.current(),
                    self.filename,
                    self.source_lines,
                )
            return self.parse_import()

        # Struct, enum, union declarations use Name :: keyword syntax
        # They are handled in parse_const_or_function_decl

        # Check for identifier followed by declaration operators
        if self.match(TokenType.IDENTIFIER):
            # Look ahead to see what kind of declaration this is
            if self.peek().type == TokenType.DECLARE_CONST:  # name ::
                return self.parse_const_or_function_decl(is_public)
            elif self.peek().type == TokenType.DECLARE_VAR:  # name :=
                return self.parse_var_decl(is_public)
            elif self.peek().type == TokenType.COLON:
                # Typed declaration: name: type = value (or uninitialized)
                name_token = self.advance()
                self.consume(TokenType.COLON)
                explicit_type = self.parse_type()
                value = None
                if self.match(TokenType.ASSIGN):
                    self.advance()
                    value = self.parse_expression()
                var_decl = create_var_decl(
                    name=name_token.value,
                    value=value,
                    is_public=is_public,
                    span=create_span_from_token(name_token),
                )
                var_decl.explicit_type = explicit_type
                return var_decl
            elif self.peek().type == TokenType.LEFT_PAREN:
                # Could be generic declaration: Name($T, $U) :: struct { ... }
                return self.parse_generic_decl(is_public)

        # Function declarations can also start with just 'fn'
        if self.match(TokenType.FN):
            raise ParseError.from_token(
                "Function declarations must have names", self.current(), self.filename
            )

        # If we reach here, this is not a valid declaration
        raise ParseError.from_token(
            "Expected declaration (constant, variable, or function)",
            self.current(),
            self.filename,
        )

    def parse_generic_decl(self, is_public: bool) -> ASTNode:
        """Parse generic declarations: Name($T, $U) :: struct/fn/etc."""
        name_token = self.consume(TokenType.IDENTIFIER)
        name = name_token.value

        # Parse generic parameters
        generic_params = self.parse_generic_parameters()

        self.consume(TokenType.DECLARE_CONST)  # ::

        # Check what kind of declaration follows
        if self.match(TokenType.STRUCT):
            decl = self.parse_struct_decl_with_name(name, is_public, name_token)
            decl.generic_params = generic_params
            return decl
        elif self.match(TokenType.ENUM):
            decl = self.parse_enum_decl_with_name(name, is_public, name_token)
            decl.generic_params = generic_params
            return decl
        elif self.match(TokenType.UNION):
            decl = self.parse_union_decl_with_name(name, is_public, name_token)
            decl.generic_params = generic_params
            return decl
        elif self.match(TokenType.FN):
            decl = self.parse_function_decl_with_name(name, is_public, name_token)
            decl.generic_params = generic_params
            return decl
        else:
            # Generic constant — fall through to expression
            value = self.parse_expression()
            decl = create_const_decl(
                name=name,
                value=value,
                is_public=is_public,
                span=create_span_from_token(name_token),
            )
            decl.generic_params = generic_params
            return decl

    def parse_import(self) -> ASTNode:
        """Parse import declarations including using and named imports."""
        # Check for 'using import'
        is_using = False
        import_token = None

        if self.match(TokenType.IDENTIFIER) and self.current().value == "using":
            is_using = True
            self.advance()  # consume 'using'
            import_token = self.consume(TokenType.IMPORT)
        else:
            import_token = self.consume(TokenType.IMPORT)

        # Parse module path
        if not self.match(TokenType.STRING_LITERAL):
            raise ParseError.from_token(
                "Expected module path after import", self.current(), self.filename
            )

        module_path = self.advance().value[1:-1]  # Remove quotes

        # Check for named imports: import "path" { Name1, Name2 }
        imported_items = None
        if self.match(TokenType.LEFT_BRACE):
            self.advance()
            imported_items = []

            while not self.match(TokenType.RIGHT_BRACE):
                if not self.match(TokenType.IDENTIFIER):
                    raise ParseError.from_token(
                        f"Expected an imported name in import list, found {_describe(self.current())}",
                        self.current(),
                        self.filename,
                        self.source_lines,
                    )
                imported_items.append(self.advance().value)
                self._list_separator(TokenType.RIGHT_BRACE, "import list", newlines=False)

            self.consume(TokenType.RIGHT_BRACE)

        return ASTNode(
            kind=NodeKind.IMPORT,
            module_path=module_path,
            is_using=is_using,
            imported_items=imported_items,
            span=create_span_from_token(import_token),
        )

    def parse_const_or_function_decl(self, is_public: bool) -> ASTNode:
        """Parse constant, function, struct, enum, or union declaration (name :: ...)."""
        name_token = self.consume(TokenType.IDENTIFIER)
        name = name_token.value
        self.consume(TokenType.DECLARE_CONST)  # ::

        # Check if this is a function (fn keyword)
        if self.match(TokenType.FN):
            # Distinguish between function declaration and function TYPE alias:
            #   fn(name: type, ...) RetType { body } → function declaration
            #   fn(Type, ...) RetType               → function type alias (no body)
            # Heuristic: peek inside fn( — if first token is IDENTIFIER followed
            # by COLON, it's a named param → function decl. Otherwise → type alias.
            if self._is_fn_type_alias():
                return self._parse_fn_type_alias(name, is_public, name_token)
            return self.parse_function_decl_with_name(name, is_public, name_token)

        # Check if this is a struct declaration
        if self.match(TokenType.STRUCT):
            return self.parse_struct_decl_with_name(name, is_public, name_token)

        # Check if this is an enum declaration
        if self.match(TokenType.ENUM):
            return self.parse_enum_decl_with_name(name, is_public, name_token)

        # Check if this is a union declaration
        if self.match(TokenType.UNION):
            return self.parse_union_decl_with_name(name, is_public, name_token)

        # Check if this is an import declaration
        if self.match(TokenType.IMPORT):
            self.advance()  # consume 'import'
            if self.match(TokenType.STRING_LITERAL):
                module_path = self.advance().value[1:-1]  # Remove quotes
                return ASTNode(
                    kind=NodeKind.IMPORT,
                    alias=name,
                    module_path=module_path,
                    is_public=is_public,
                    span=create_span_from_token(name_token),
                )
            else:
                raise ParseError.from_token(
                    "Expected module path after import", self.current(), self.filename
                )

        # Type alias: Handle :: u64, Vector :: [3]f32, etc.
        # A bare identifier stays a constant: `Alias :: N` aliases the
        # value N, and the parser cannot tell a value from a named type.
        if (
            self._is_type_start()
            or self.match(TokenType.LEFT_BRACKET)
        ):
            type_node = self.parse_type()
            return ASTNode(
                kind=NodeKind.TYPE_ALIAS,
                name=name,
                value=type_node,
                is_public=is_public,
                span=create_span_from_token(name_token),
            )

        # Otherwise it's a constant declaration
        value = self.parse_expression()
        return create_const_decl(
            name=name,
            value=value,
            is_public=is_public,
            span=create_span_from_token(name_token),
        )

    def _is_fn_type_alias(self) -> bool:
        """Check if current fn(...) is a type alias (no named params) vs function decl.

        We're positioned at 'fn'. Peek into fn( to check if first param has a name:colon.
        """
        # fn should be current, ( should be next
        paren = self.peek(1)
        if paren.type != TokenType.LEFT_PAREN:
            return False

        # Skip terminators after '(' to find the first meaningful token
        offset = 2
        while self.peek(offset).type == TokenType.TERMINATOR:
            offset += 1
        first_inside = self.peek(offset)

        # fn() — empty params, could be either. Check if body follows.
        if first_inside.type == TokenType.RIGHT_PAREN:
            # Look past ) for optional return type, then check for {
            offset += 1
            while offset < len(self.tokens) - self.position:
                tok = self.peek(offset)
                if tok.type == TokenType.LEFT_BRACE:
                    return False  # Has body → function declaration
                if tok.type == TokenType.TERMINATOR:
                    # The body or a where-clause may start on the next line,
                    # as it may after a parameter list with named parameters.
                    after = self.peek(offset + 1).type
                    return after not in (TokenType.LEFT_BRACE, TokenType.WHERE)
                if tok.type == TokenType.EOF:
                    return True  # No body → type alias
                offset += 1
            return True

        # fn(IDENTIFIER COLON ...) → named param → function declaration
        if first_inside.type == TokenType.IDENTIFIER:
            # Skip terminators after identifier too
            after_offset = offset + 1
            while self.peek(after_offset).type == TokenType.TERMINATOR:
                after_offset += 1
            after_ident = self.peek(after_offset)
            if after_ident.type == TokenType.COLON:
                return False  # Named param
            # IDENTIFIER without colon → type name → type alias
            return True

        # fn(type_keyword ...) or fn(ref ...) or fn([ ...) → type alias
        return True

    def _parse_fn_type_alias(self, name: str, is_public: bool, name_token) -> ASTNode:
        """Parse function type alias: Name :: fn(Type, ...) RetType"""
        # Use parse_type() which already handles fn(...) RetType as a type expression
        fn_type = self.parse_type()
        return ASTNode(
            kind=NodeKind.TYPE_ALIAS,
            name=name,
            value=fn_type,
            is_public=is_public,
            span=create_span_from_token(name_token),
        )

    def parse_var_decl(self, is_public: bool) -> ASTNode:
        """Parse variable declaration (name := value)."""
        name_token = self.consume(TokenType.IDENTIFIER)
        name = name_token.value
        self.consume(TokenType.DECLARE_VAR)  # :=

        value = self.parse_expression()
        return create_var_decl(
            name=name,
            value=value,
            is_public=is_public,
            span=create_span_from_token(name_token),
        )

    def parse_function_decl_with_name(
        self, name: str, is_public: bool, name_token: Token
    ) -> ASTNode:
        """Parse function declaration after we have the name and :: fn."""
        return self._statement_work("parse_function_decl_with_name", (name, is_public, name_token))

    def _statement_work(self, action, payload):
        # Suspended frames retain token order and unwind nesting guards on errors.
        pending = [self._statement_steps(action, payload)]
        result = None
        try:
            while pending:
                try:
                    action, payload = pending[-1].send(result)
                except StopIteration as finished:
                    pending.pop()
                    result = finished.value
                    continue
                pending.append(self._statement_steps(action, payload))
                result = None
            return result
        finally:
            for frame in reversed(pending):
                frame.close()

    def _statement_steps(self, action, payload):
        if action == "parse_function_decl_with_name":
            name, is_public, name_token = payload
            self.consume(TokenType.FN)

            # Function parameters (which may include generics)
            self.consume(TokenType.LEFT_PAREN)
            generic_params, parameters = self.parse_mixed_parameters()

            # Return type (optional)
            return_type = None
            # Only parse return type if we don't immediately see a left brace
            # This handles functions like: fn() { ... } vs fn() i32 { ... }
            if not self.match(TokenType.LEFT_BRACE):
                if self.current().type in _TYPE_STARTS:
                    return_type = self.parse_type()

            # Minimal where-clause between signature and body.
            where_clause = None
            self.skip_terminators()
            if self.match(TokenType.WHERE):
                where_clause = self.parse_where_clause()
                self.skip_terminators()

            # Function body (required)
            if not self.match(TokenType.LEFT_BRACE):
                raise ParseError.from_token(
                    "Expected function body after function signature",
                    self.current(),
                    self.filename,
                )
            body = (yield ("parse_block", None))

            decl = create_function_decl(
                name=name,
                parameters=parameters,
                return_type=return_type,
                body=body,
                is_public=is_public,
                span=create_span_from_token(name_token),
            )
            if where_clause is not None:
                decl.where_clause = where_clause
            return decl

        if action == "parse_block":
            start_token = self.consume(TokenType.LEFT_BRACE)
            statements = []

            self.skip_terminators()

            while not self.match(TokenType.RIGHT_BRACE) and not self.at_end():
                iteration_start = self.position
                stmt = (yield ("parse_statement", None))
                if stmt:
                    statements.append(stmt)
                self._require_statement_end()
                self.skip_terminators()
                self._require_progress(iteration_start, "block")

            end_token = self.consume(TokenType.RIGHT_BRACE)

            return create_block(
                statements=statements, span=create_span_from_tokens(start_token, end_token)
            )

        if action == "parse_statement":
            self._enter_nesting()
            try:
                start_token = self.current()

                # Loop label prefix: @outer for ... / @outer while ...
                if self.match(TokenType.BUILTIN_ID) and self.peek().type in (
                    TokenType.FOR,
                    TokenType.WHILE,
                ):
                    label_token = self.advance()
                    label = label_token.value[1:]
                    loop_stmt = (yield ("parse_statement", None))
                    loop_stmt.label = label
                    return loop_stmt

                # Return statement
                if self.match(TokenType.RET):
                    self.advance()
                    value = None
                    if not self.match(TokenType.TERMINATOR, TokenType.RIGHT_BRACE):
                        value = self.parse_expression()
                    return create_return_stmt(value, create_span_from_token(start_token))

                # Break statement (optionally with label: break outer)
                if self.match(TokenType.BREAK):
                    self.advance()
                    label = None
                    if self.match(TokenType.IDENTIFIER) and not self.match(TokenType.TERMINATOR, TokenType.RIGHT_BRACE):
                        label = self.advance().value
                    return ASTNode(
                        kind=NodeKind.BREAK, label=label, span=create_span_from_token(start_token)
                    )

                # Continue statement (optionally with label: continue outer)
                if self.match(TokenType.CONTINUE):
                    self.advance()
                    label = None
                    if self.match(TokenType.IDENTIFIER) and not self.match(TokenType.TERMINATOR, TokenType.RIGHT_BRACE):
                        label = self.advance().value
                    return ASTNode(
                        kind=NodeKind.CONTINUE, label=label, span=create_span_from_token(start_token)
                    )

                # Fall statement (fallthrough in match)
                if self.match(TokenType.FALL):
                    self.advance()
                    return ASTNode(
                        kind=NodeKind.FALL, span=create_span_from_token(start_token)
                    )

                # Match statement
                if self.match(TokenType.MATCH):
                    return (yield ("parse_match_statement", None))

                # Defer statement
                if self.match(TokenType.DEFER):
                    return (yield ("parse_defer_statement", None))

                # Del statement
                if self.match(TokenType.DEL):
                    return self.parse_del_statement()

                # If statement
                if self.match(TokenType.IF):
                    return (yield ("parse_if_statement", None))

                # While statement
                if self.match(TokenType.WHILE):
                    return (yield ("parse_while_statement", None))

                # For statement
                if self.match(TokenType.FOR):
                    return (yield ("parse_for_statement", None))

                # Block statement
                if self.match(TokenType.LEFT_BRACE):
                    return (yield ("parse_block", None))

                # Variable or constant declarations inside function body
                if self.match(TokenType.IDENTIFIER):
                    lookahead = self.peek()
                    if lookahead.type == TokenType.DECLARE_VAR:
                        # Simple: name := value
                        name_token = self.advance()
                        self.consume(TokenType.DECLARE_VAR)
                        value = self.parse_expression()
                        return create_var_decl(
                            name=name_token.value,
                            value=value,
                            is_public=False,
                            span=create_span_from_token(name_token),
                        )
                    elif lookahead.type == TokenType.COLON:
                        # Reject the old label: spelling for loop labels.
                        peek2 = self.peek(2)
                        if peek2.type in (TokenType.FOR, TokenType.WHILE):
                            raise ParseError.from_token(
                                "Use '@label' before a loop instead of 'label:'",
                                self.current(),
                                self.filename,
                                self.source_lines,
                            )

                        # Explicit type annotation: name: type = value (initialization optional)
                        name_token = self.advance()
                        self.consume(TokenType.COLON)
                        explicit_type = self.parse_type()

                        # Make initialization optional - allow uninitialized declarations
                        value = None
                        if self.match(TokenType.ASSIGN):
                            self.advance()
                            value = self.parse_expression()

                        var_decl = create_var_decl(
                            name=name_token.value,
                            value=value,
                            is_public=False,
                            span=create_span_from_token(name_token),
                        )
                        var_decl.explicit_type = explicit_type
                        return var_decl
                    elif lookahead.type == TokenType.DECLARE_CONST:
                        # Constant or local type declaration: name :: value|struct|enum|union|fn
                        name_token = self.advance()
                        self.consume(TokenType.DECLARE_CONST)

                        # Check for struct/enum/union/function declarations
                        if self.match(TokenType.STRUCT):
                            return self.parse_struct_decl_with_name(name_token.value, False, name_token)
                        elif self.match(TokenType.ENUM):
                            return self.parse_enum_decl_with_name(name_token.value, False, name_token)
                        elif self.match(TokenType.UNION):
                            return self.parse_union_decl_with_name(name_token.value, False, name_token)
                        elif self.match(TokenType.FN):
                            # Check if this is a function type alias or function declaration
                            if self._is_fn_type_alias():
                                return self._parse_fn_type_alias(name_token.value, False, name_token)
                            return (yield ("parse_function_decl_with_name", (name_token.value, False, name_token)))
                        elif (
                            self._is_type_start()
                            or self.match(TokenType.LEFT_BRACKET)
                        ):
                            # Type alias: Handle :: u64, Vector :: [3]f32, etc.
                            # A bare identifier stays a constant (see above).
                            type_node = self.parse_type()
                            return ASTNode(
                                kind=NodeKind.TYPE_ALIAS,
                                name=name_token.value,
                                value=type_node,
                                is_public=False,
                                span=create_span_from_token(name_token),
                            )
                        else:
                            # Regular constant declaration
                            value = self.parse_expression()
                            return create_const_decl(
                                name=name_token.value,
                                value=value,
                                is_public=False,
                                span=create_span_from_token(name_token),
                            )

                # Expression statement or assignment
                return self.parse_expression_or_assignment()

            finally:
                self._exit_nesting()

        if action == "parse_if_statement":
            if_token = self.consume(TokenType.IF)
            condition = self._parse_header_expression()
            self._require_block_start("the if condition")
            then_stmt = (yield ("parse_block", None))

            else_stmt = None
            if self.match(TokenType.ELSE):
                self.advance()
                if not self.match(TokenType.IF):
                    self._require_block_start("'else'")
                else_stmt = (yield ("parse_statement", None))

            return ASTNode(
                kind=NodeKind.IF_STMT,
                condition=condition,
                then_stmt=then_stmt,
                else_stmt=else_stmt,
                span=create_span_from_token(if_token),
            )

        if action == "parse_while_statement":
            while_token = self.consume(TokenType.WHILE)
            condition = self._parse_header_expression()
            self._require_block_start("the while condition")
            body = (yield ("parse_block", None))

            return ASTNode(
                kind=NodeKind.WHILE,
                condition=condition,
                body=body,
                span=create_span_from_token(while_token),
            )

        if action == "parse_for_statement":
            for_token = self.consume(TokenType.FOR)

            # Simple infinite loop: for { ... }
            if self.match(TokenType.LEFT_BRACE):
                body = (yield ("parse_block", None))
                return ASTNode(
                    kind=NodeKind.FOR, body=body, span=create_span_from_token(for_token)
                )

            saved = self._header_depth
            self._header_depth = self._depth_at[self.position]
            try:
                kind, header = self._parse_for_header()
            finally:
                self._header_depth = saved

            body = (yield ("parse_block", None))
            return ASTNode(
                kind=kind, body=body, span=create_span_from_token(for_token), **header
            )

        if action == "parse_match_statement":
            match_token = self.consume(TokenType.MATCH)
            expression = self._parse_header_expression()

            self.consume(TokenType.LEFT_BRACE)
            cases = []
            else_case = None

            while not self.at_end():
                iteration_start = self.position
                self.skip_terminators()
                if self.match(TokenType.RIGHT_BRACE) or self.at_end():
                    break
                self._check_match_arm_order(else_case is not None)

                if self.match(TokenType.CASE):
                    case_token = self.advance()

                    # Parse patterns (supporting ranges, multiple values, enum access)
                    patterns = [self.parse_pattern()]
                    while self.match(TokenType.COMMA):
                        self.advance()
                        patterns.append(self.parse_pattern())

                    self.consume(TokenType.COLON)
                    body = (yield ("parse_statement", None))

                    case_node = ASTNode(
                        kind=NodeKind.CASE_BRANCH,
                        patterns=patterns,
                        statement=body,
                        span=create_span_from_token(case_token),
                    )
                    cases.append(case_node)

                elif self.match(TokenType.ELSE):
                    self.advance()
                    self.consume(TokenType.COLON)
                    else_case = [(yield ("parse_statement", None))]

                else:
                    raise self._fatal_error(
                        "Expected 'case' or 'else' in match statement",
                        self.current(),
                    )

                self.skip_terminators()
                self._require_progress(iteration_start, "match statement")

            self.consume(TokenType.RIGHT_BRACE)

            return ASTNode(
                kind=NodeKind.MATCH,
                expression=expression,
                cases=cases,
                else_case=else_case,
                span=create_span_from_token(match_token),
            )

        if action == "parse_defer_statement":
            defer_token = self.consume(TokenType.DEFER)
            statement = (yield ("parse_statement", None))

            return ASTNode(
                kind=NodeKind.DEFER,
                statement=statement,
                span=create_span_from_token(defer_token),
            )

    def parse_generic_parameters(self) -> List[ASTNode]:
        """Parse generic type parameters with optional constraints: $T, $T: Numeric, $T: @type_set(...)."""
        params = []
        self.consume(TokenType.LEFT_PAREN)

        while not self.match(TokenType.RIGHT_PAREN):
            if not self.match(TokenType.GENERIC_TYPE):
                raise ParseError.from_token(
                    f"Expected a generic parameter such as $T, found {_describe(self.current())}",
                    self.current(),
                    self.filename,
                    self.source_lines,
                )
            generic_token = self.advance()
            # Extract the name without the $ prefix for consistency
            param_name = generic_token.value[1:]

            # Check for constraint: $T: Constraint
            constraint = None
            if self.match(TokenType.COLON):
                self.advance()  # consume ':'
                constraint = self.parse_type()  # identifier or @type_set

            params.append(
                ASTNode(
                    kind=NodeKind.GENERIC_PARAM,
                    name=param_name,
                    constraint=constraint,
                    span=create_span_from_token(generic_token),
                )
            )
            self._list_separator(
                TokenType.RIGHT_PAREN, "generic parameter list", newlines=False
            )

        self.consume(TokenType.RIGHT_PAREN)
        return params

    def parse_where_clause(self) -> List[ASTNode]:
        """Parse `where T: Set, U: Set`: conjunctions of set memberships only."""
        self.consume(TokenType.WHERE)
        entries: List[ASTNode] = []
        self.skip_terminators()
        while not self.at_end():
            self.skip_terminators()
            if self.match(TokenType.LEFT_BRACE) or self.at_end():
                break
            start = self.current()
            name: Optional[str] = None
            if self.match(TokenType.IDENTIFIER):
                name = self.advance().value
            self.skip_terminators()
            if name is not None and self.match(TokenType.COLON):
                self.advance()  # consume ':'
                self.skip_terminators()
                constraint = self.parse_type()
                entry = ASTNode(
                    kind=NodeKind.GENERIC_PARAM,
                    name=name,
                    constraint=constraint,
                    span=create_span_from_token(start),
                )
                if self.match(TokenType.COMMA, TokenType.LEFT_BRACE) or self.at_end():
                    entries.append(entry)
                elif self.match(TokenType.TERMINATOR):
                    # A newline ends the clause; a comma after it continues it.
                    self.skip_terminators()
                    entries.append(entry)
                else:
                    # Anything else trailing the type is not a set membership.
                    entry.where_valid = False
                    entries.append(entry)
                    self._skip_where_bound()
            else:
                # Not `Name: ...`: a richer predicate. Mark it so the checker
                # rejects it instead of the parser accepting it silently.
                marker = ASTNode(
                    kind=NodeKind.GENERIC_PARAM,
                    name=name,
                    constraint=None,
                    span=create_span_from_token(start),
                )
                marker.where_valid = False
                entries.append(marker)
                self._skip_where_bound()
            if not self.match(TokenType.COMMA):
                break
            self.advance()
            self.skip_terminators()
            if self.match(TokenType.LEFT_BRACE) or self.at_end():
                raise ParseError.from_token(
                    "Expected a constraint after ',' in where clause",
                    self.current(),
                    self.filename,
                )
        if not entries:
            raise ParseError.from_token(
                "Expected at least one constraint after 'where'",
                self.current(),
                self.filename,
            )
        return entries

    def _skip_where_bound(self) -> None:
        """Skip one malformed where entry; stop before comma, brace, or EOL."""
        depth = 0
        while not self.at_end():
            if depth == 0 and self.match(
                TokenType.COMMA,
                TokenType.LEFT_BRACE,
                TokenType.RIGHT_BRACE,
                TokenType.TERMINATOR,
            ):
                break
            if self.match(TokenType.LEFT_PAREN, TokenType.LEFT_BRACKET, TokenType.LEFT_BRACE):
                depth += 1
            elif self.match(TokenType.RIGHT_PAREN, TokenType.RIGHT_BRACKET, TokenType.RIGHT_BRACE):
                if depth > 0:
                    depth -= 1
                else:
                    break
            self.advance()

    def _parse_trailing_where_clause(self) -> Optional[List[ASTNode]]:
        """Parse an optional where-clause after a struct/union body."""
        self.skip_terminators()
        if not self.match(TokenType.WHERE):
            return None
        return self.parse_where_clause()

    def _expression_work(self, action, payload):
        # Only the driver resumes child frames and unwinds nesting guards.
        pending = [self._expression_steps(action, payload)]
        result = None
        failure = None
        try:
            while pending:
                try:
                    if failure is None:
                        action, payload = pending[-1].send(result)
                    else:
                        error = failure
                        failure = None
                        action, payload = pending[-1].throw(error)
                except StopIteration as finished:
                    pending.pop()
                    result = finished.value
                    continue
                except BaseException as error:
                    pending.pop()
                    if not pending:
                        raise
                    failure = error
                    result = None
                    continue
                pending.append(self._expression_steps(action, payload))
                result = None
            return result
        finally:
            for frame in reversed(pending):
                frame.close()

    def _expression_steps(self, action, payload):
        if action == "parse_type_set":
            start_token = self.consume(TokenType.BUILTIN_ID)  # @type_set
            self.consume(TokenType.LEFT_PAREN)

            types = []
            while not self.match(TokenType.RIGHT_PAREN):
                types.append((yield ("parse_type", ())))
                self._list_separator(TokenType.RIGHT_PAREN, "@type_set", newlines=False)

            self.consume(TokenType.RIGHT_PAREN)

            return ASTNode(
                kind=NodeKind.TYPE_SET,
                types=types,
                span=create_span_from_token(start_token)
            )

        if action == "parse_type":
            self._enter_nesting()
            try:
                start_token = self.current()

                # Builtin type sets: @type_set(i32, i64, ...)
                if self.match(TokenType.BUILTIN_ID):
                    builtin_token = self.current()
                    if builtin_token.value == "@type_set":
                        return (yield ("parse_type_set", ()))

                # Reference types: ref T
                if self.match(TokenType.REF):
                    self.advance()
                    target_type = (yield ("parse_type", ()))
                    return ASTNode(
                        kind=NodeKind.TYPE_POINTER,
                        target_type=target_type,
                        span=create_span_from_token(start_token),
                    )

                # Array/slice types: [N]T or []T
                if self.match(TokenType.LEFT_BRACKET):
                    self.advance()
                    size = None

                    # Check if it's a slice (empty brackets) or array (with size)
                    if not self.match(TokenType.RIGHT_BRACKET):
                        size = (yield ("parse_expression", ()))

                    self.consume(TokenType.RIGHT_BRACKET)
                    element_type = (yield ("parse_type", ()))

                    if size:
                        return ASTNode(
                            kind=NodeKind.TYPE_ARRAY,
                            element_type=element_type,
                            size=size,
                            span=create_span_from_token(start_token),
                        )
                    else:
                        return ASTNode(
                            kind=NodeKind.TYPE_SLICE,
                            element_type=element_type,
                            span=create_span_from_token(start_token),
                        )

                # Function types: fn(params) return_type
                if self.match(TokenType.FN):
                    fn_token = self.advance()

                    # Parse parameter types (not full parameters with names)
                    self.consume(TokenType.LEFT_PAREN)
                    param_types = []

                    self.skip_terminators()
                    while not self.match(TokenType.RIGHT_PAREN):
                        # Parse just the type, no parameter name
                        param_types.append((yield ("parse_type", ())))
                        self._list_separator(
                            TokenType.RIGHT_PAREN, "function type parameter list"
                        )

                    self.consume(TokenType.RIGHT_PAREN)

                    # Parse return type (optional, defaults to void)
                    return_type = None
                    if not self.match(
                        TokenType.TERMINATOR,
                        TokenType.ASSIGN,
                        TokenType.RIGHT_PAREN,
                        TokenType.RIGHT_BRACKET,
                        TokenType.RIGHT_BRACE,
                        TokenType.LEFT_BRACE,
                        TokenType.COMMA,
                        TokenType.EOF,
                    ):
                        return_type = (yield ("parse_type", ()))

                    return create_function_type(
                        param_types=param_types,
                        return_type=return_type,
                        span=create_span_from_token(fn_token),
                    )

                # Inline struct types: struct { field: type, ... }
                if self.match(TokenType.STRUCT):
                    struct_token = self.advance()
                    self.consume(TokenType.LEFT_BRACE)

                    fields = []
                    self.skip_terminators()

                    while not self.match(TokenType.RIGHT_BRACE):
                        # Parse field: name: type
                        field_name_token = self.consume(TokenType.IDENTIFIER)
                        self.consume(TokenType.COLON)
                        field_type = (yield ("parse_type", ()))

                        field = ASTNode(
                            kind=NodeKind.FIELD,
                            name=field_name_token.value,
                            field_type=field_type,
                            span=create_span_from_token(field_name_token),
                        )
                        fields.append(field)
                        self._list_separator(
                            TokenType.RIGHT_BRACE, "inline struct type", newline_separates=True
                        )

                    self.consume(TokenType.RIGHT_BRACE)

                    return create_inline_struct_type(
                        fields=fields,
                        span=create_span_from_token(struct_token),
                    )

                # Generic types: $T, $TYPE, etc.
                if self.match(TokenType.GENERIC_TYPE):
                    generic_token = self.advance()
                    # Remove the $ prefix for consistency
                    type_name = generic_token.value[1:]
                    return ASTNode(
                        kind=NodeKind.TYPE_GENERIC,
                        name=type_name,
                        span=create_span_from_token(generic_token),
                    )

                # Primitive or identifier types
                if self.match(TokenType.IDENTIFIER):
                    type_name_token = self.advance()
                    type_name = type_name_token.value

                    # Check for generic parameters: Type(T1, T2, ...)
                    if self.match(TokenType.LEFT_PAREN):
                        self.advance()
                        generic_params = []
                        while not self.match(TokenType.RIGHT_PAREN):
                            generic_params.append((yield ("parse_type", ())))
                            self._list_separator(
                                TokenType.RIGHT_PAREN, "type argument list", newlines=False
                            )
                        self.consume(TokenType.RIGHT_PAREN)

                        # Create a generic type instantiation node
                        return ASTNode(
                            kind=NodeKind.TYPE_IDENTIFIER,
                            name=type_name,
                            generic_params=generic_params,
                            span=create_span_from_token(type_name_token),
                        )

                    return ASTNode(
                        kind=NodeKind.TYPE_IDENTIFIER,
                        name=type_name,
                        span=create_span_from_token(type_name_token),
                    )

                # Primitive types: the keyword text is the type name
                if start_token.type in _PRIMITIVE_TYPE_TOKENS:
                    self.advance()
                    return create_primitive_type(
                        start_token.value, create_span_from_token(start_token)
                    )

                raise ParseError.from_token("Expected type", self.current(), self.filename)

            finally:
                self._exit_nesting()

        if action == "parse_expression":
            return (yield ("parse_binary_expression", (0,)))

        if action == "parse_binary_expression":
            min_precedence, = payload
            self._enter_nesting()
            try:
                left = (yield ("parse_unary_expression", ()))

                while True:
                    # Check if current token is a binary operator
                    if not self.match(
                        TokenType.PLUS,
                        TokenType.MINUS,
                        TokenType.MULTIPLY,
                        TokenType.DIVIDE,
                        TokenType.MODULO,
                        TokenType.EQUAL,
                        TokenType.NOT_EQUAL,
                        TokenType.LESS_THAN,
                        TokenType.LESS_EQUAL,
                        TokenType.GREATER_THAN,
                        TokenType.GREATER_EQUAL,
                        TokenType.AND,
                        TokenType.OR,
                        TokenType.BITWISE_AND,
                        TokenType.BITWISE_OR,
                        TokenType.BITWISE_XOR,
                        TokenType.LEFT_SHIFT,
                        TokenType.RIGHT_SHIFT,
                    ):
                        break

                    op_token = self.current()
                    binary_op = token_to_binary_op(op_token.type)
                    if not binary_op:
                        break

                    precedence = get_binary_precedence(binary_op)
                    if precedence < min_precedence:
                        break

                    self.advance()  # Consume operator

                    # Check if we're at end of input or terminator after operator
                    if self.at_end() or self.match(TokenType.TERMINATOR, TokenType.RIGHT_PAREN,
                                                   TokenType.RIGHT_BRACE, TokenType.RIGHT_BRACKET,
                                                   TokenType.COMMA):
                        raise ParseError.from_token(
                            f"Expected expression after '{op_token.value}' operator",
                            self.current(), self.filename
                        )

                    # Right associative operators would use precedence here,
                    # but A7 operators are left associative
                    right = (yield ("parse_binary_expression", (precedence + 1,)))

                    left = create_binary_expr(left, binary_op, right)

                return left

            finally:
                self._exit_nesting()

        if action == "parse_unary_expression":
            self._enter_nesting()
            try:
                start_token = self.current()

                # Unary operators
                if self.match(
                    TokenType.MINUS,
                    TokenType.NOT,
                    TokenType.LOGICAL_NOT,
                    TokenType.BITWISE_NOT,
                ):
                    op_token = self.advance()
                    unary_op = token_to_unary_op(op_token.type)
                    if unary_op:
                        operand = (yield ("parse_unary_expression", ()))
                        return ASTNode(
                            kind=NodeKind.UNARY,
                            operator=unary_op,
                            operand=operand,
                            span=combine_spans(
                                create_span_from_token(start_token), operand.span
                            ),
                        )

                return (yield ("parse_postfix_expression", ()))

            finally:
                self._exit_nesting()

        if action == "parse_postfix_expression":
            expr = (yield ("parse_primary_expression", ()))

            while True:
                if self.match(TokenType.LEFT_PAREN):
                    if expr.kind == NodeKind.NEW_EXPR:
                        raise ParseError.from_token(
                            "new expressions do not take initializer arguments; use 'new T' or 'new(T)'",
                            self.current(),
                            self.filename,
                            self.source_lines,
                        )
                    # Function call
                    expr = (yield ("parse_call_expression", (expr,)))
                elif self.match(TokenType.LEFT_BRACKET):
                    # Array indexing
                    expr = (yield ("parse_index_expression", (expr,)))
                elif self.match(TokenType.DOT):
                    # Field access or dereference
                    expr = self.parse_field_or_deref_expression(expr)
                else:
                    break

            return expr

        if action == "_parse_call_argument":
            # A type keyword, `ref`, `$T` or `fn` cannot start an expression.
            if self._is_type_start() or self.match(TokenType.FN):
                return (yield ("parse_type", ()))
            # `[` opens an array type [N]T or an array literal [1, 2, 3].
            if self.match(TokenType.LEFT_BRACKET) and self._bracket_starts_type():
                return (yield ("parse_type", ()))
            # An identifier is an expression here, also when it names a type
            # such as Option(i32).
            return (yield ("parse_expression", ()))

        if action == "parse_call_expression":
            function, = payload
            self.consume(TokenType.LEFT_PAREN)
            arguments = []
            self.skip_terminators()

            while not self.match(TokenType.RIGHT_PAREN):
                arguments.append((yield ("_parse_call_argument", ())))
                self._list_separator(TokenType.RIGHT_PAREN, "call arguments")

            end_token = self.consume(TokenType.RIGHT_PAREN)

            return create_call_expr(
                function=function,
                arguments=arguments,
                span=_span_through(function.span, end_token),
            )

        if action == "parse_index_expression":
            object_expr, = payload
            self.consume(TokenType.LEFT_BRACKET)

            # Check for slice notation
            if self.match(TokenType.DOT_DOT):
                # This is a slice [..end]
                self.advance()
                end = (
                    (yield ("parse_expression", ()))
                    if not self.match(TokenType.RIGHT_BRACKET)
                    else None
                )
                end_token = self.consume(TokenType.RIGHT_BRACKET)

                return ASTNode(
                    kind=NodeKind.SLICE,
                    object=object_expr,
                    start=None,
                    end=end,
                    span=_span_through(object_expr.span, end_token),
                )

            index = (yield ("parse_expression", ()))

            # Check for slice notation
            if self.match(TokenType.DOT_DOT):
                self.advance()
                end = (
                    (yield ("parse_expression", ()))
                    if not self.match(TokenType.RIGHT_BRACKET)
                    else None
                )
                end_token = self.consume(TokenType.RIGHT_BRACKET)

                return ASTNode(
                    kind=NodeKind.SLICE,
                    object=object_expr,
                    start=index,
                    end=end,
                    span=_span_through(object_expr.span, end_token),
                )

            end_token = self.consume(TokenType.RIGHT_BRACKET)

            return ASTNode(
                kind=NodeKind.INDEX,
                object=object_expr,
                index=index,
                span=_span_through(object_expr.span, end_token),
            )

        if action == "parse_primary_expression":
            start_token = self.current()

            # Literals
            if self.match(
                TokenType.INTEGER_LITERAL,
                TokenType.FLOAT_LITERAL,
                TokenType.CHAR_LITERAL,
                TokenType.STRING_LITERAL,
                TokenType.TRUE_LITERAL,
                TokenType.FALSE_LITERAL,
                TokenType.NIL_LITERAL,
            ):
                return create_literal_from_token(self.advance())

            # Inline struct type with initialization: struct { x: i32 } { x: 42 }
            if self.match(TokenType.STRUCT):
                struct_type = (yield ("parse_type", ()))  # Parses struct { fields... }
                # If followed by { it's a struct literal initialization
                if self.match(TokenType.LEFT_BRACE):
                    return (yield ("_parse_inline_struct_init", (struct_type,)))
                return struct_type

            # Generic type parameters used in expression context (e.g., [$N]$T array sizes)
            if self.match(TokenType.GENERIC_TYPE):
                token = self.advance()
                name = token.value[1:]  # Remove '$' prefix
                return create_identifier(name, create_span_from_token(token))

            # New expression: new Type or new [size]Type
            if self.match(TokenType.NEW):
                return (yield ("parse_new_expression", ()))

            # Array literals: [1, 2, 3]
            if self.match(TokenType.LEFT_BRACKET):
                return (yield ("parse_array_literal", ()))

            # Builtin intrinsics: @size_of(T), @align_of(T), etc.
            if self.match(TokenType.BUILTIN_ID):
                return (yield ("parse_builtin_intrinsic", ()))

            # Identifiers, cast expressions, or struct literals
            if self.match(TokenType.IDENTIFIER):
                name = self.advance().value

                # Check for cast expression: cast(type, expr)
                if name == "cast" and self.match(TokenType.LEFT_PAREN):
                    return (yield ("parse_cast_expression", (start_token,)))

                # Generic struct literal instantiation: Pair(i32, string){...}.
                # Tried only when a `{` follows the matching `)` and a struct
                # literal may start there; a failed try is not repeated.
                saved_position = self.position
                close = self._close_at.get(saved_position)
                if (
                    self.match(TokenType.LEFT_PAREN)
                    and close is not None
                    and self.tokens[close + 1].type == TokenType.LEFT_BRACE
                    and self._should_parse_struct_literal()
                    and saved_position not in self._not_generic_literal
                ):
                    type_args = []
                    self.advance()  # consume '('
                    try:
                        while not self.match(TokenType.RIGHT_PAREN):
                            type_args.append((yield ("parse_type", ())))
                            self._list_separator(
                                TokenType.RIGHT_PAREN, "type argument list", newlines=False
                            )
                        self.advance()  # consume ')'
                        struct_literal = (yield ("parse_struct_literal", (name, create_span_from_token(start_token))))
                        struct_literal.type_arguments = type_args
                        return struct_literal
                    except ParseError as e:
                        if getattr(e, "fatal", False):
                            raise
                        # Not a generic struct literal: parse it as a call.
                        self._not_generic_literal.add(saved_position)
                        self.position = saved_position

                # Check for struct literal: Person{...}
                # Only parse as struct literal if we're in an appropriate context
                # (not in a statement context where { would start a block)
                if self.match(TokenType.LEFT_BRACE) and self._should_parse_struct_literal():
                    return (yield ("parse_struct_literal", (name, create_span_from_token(start_token))))
                else:
                    return create_identifier(name, create_span_from_token(start_token))

            # Parenthesized expressions
            if self.match(TokenType.LEFT_PAREN):
                self.advance()
                expr = (yield ("parse_expression", ()))
                end_token = self.consume(TokenType.RIGHT_PAREN)
                expr.span = create_span_from_tokens(start_token, end_token)
                return expr

            # If expressions
            if self.match(TokenType.IF):
                return (yield ("parse_if_expression", ()))

            # Match expressions (match used in expression context)
            if self.match(TokenType.MATCH):
                return (yield ("parse_match_expression", ()))

            raise ParseError.from_token(
                "Expected expression", self.current(), self.filename, self.source_lines
            )

        if action == "parse_cast_expression":
            start_token, = payload
            self.advance()  # consume '('

            # Parse the target type
            target_type = (yield ("parse_type", ()))

            # Expect comma
            self.consume(TokenType.COMMA, "Expected ',' after type in cast expression")

            # Parse the expression to cast
            expression = (yield ("parse_expression", ()))

            # Expect closing paren
            end_token = self.consume(TokenType.RIGHT_PAREN, "Expected ')' after cast expression")

            return create_cast_expr(
                target_type=target_type,
                expression=expression,
                span=create_span_from_tokens(start_token, end_token),
            )

        if action == "parse_builtin_intrinsic":
            # @type_set(...) is both a type and value-level construct in tests.
            # Reuse dedicated parser to produce a TYPE_SET AST node.
            if self.match(TokenType.BUILTIN_ID) and self.current().value == "@type_set":
                return (yield ("parse_type_set", ()))

            builtin_token = self.consume(TokenType.BUILTIN_ID)
            builtin_name = builtin_token.value  # Includes '@' prefix

            # Parse arguments
            self.consume(TokenType.LEFT_PAREN)
            arguments = []

            # Some builtins take types, some take expressions
            # For simplicity, we'll parse types for size_of, align_of, type_id
            # and expressions for others

            if not self.match(TokenType.RIGHT_PAREN):
                # Check if this is a type-taking builtin
                if builtin_name in ("@size_of", "@align_of", "@type_id", "@type_name"):
                    # Parse type arguments
                    arguments.append((yield ("parse_type", ())))
                    while self.match(TokenType.COMMA):
                        self.advance()
                        arguments.append((yield ("parse_type", ())))
                else:
                    # Parse expression arguments
                    arguments.append((yield ("parse_expression", ())))
                    while self.match(TokenType.COMMA):
                        self.advance()
                        arguments.append((yield ("parse_expression", ())))

            end_token = self.consume(TokenType.RIGHT_PAREN)

            return ASTNode(
                kind=NodeKind.CALL,
                function=create_identifier(builtin_name, create_span_from_token(builtin_token)),
                arguments=arguments,
                span=create_span_from_tokens(builtin_token, end_token),
            )

        if action == "parse_new_expression":
            new_token = self.consume(TokenType.NEW)

            # Support optional parenthesized syntax: new(Type) or new([size]Type)
            has_parens = False
            if self.match(TokenType.LEFT_PAREN):
                has_parens = True
                self.advance()

            # Parse the type (which may include array dimensions)
            type_node = (yield ("parse_type", ()))

            if has_parens:
                self.consume(TokenType.RIGHT_PAREN, "Expected ')' after type in new expression")

            return create_new_expr(
                type_node=type_node,
                span=create_span_from_token(new_token)
            )

        if action == "parse_if_expression":
            self._enter_nesting()
            try:
                if_token = self.consume(TokenType.IF)
                saved = self._header_depth
                self._header_depth = self._depth_at[self.position]
                try:
                    condition = (yield ("parse_expression", ()))
                finally:
                    self._header_depth = saved
                self.consume(TokenType.LEFT_BRACE)
                self.skip_terminators()
                then_expr = (yield ("parse_expression", ()))
                self.skip_terminators()
                self.consume(TokenType.RIGHT_BRACE)

                # An if expression yields a value on every path.
                if not self.match(TokenType.ELSE):
                    raise ParseError.from_token(
                        "An if expression needs an 'else' branch",
                        self.current(),
                        self.filename,
                        self.source_lines,
                    )
                self.advance()
                if self.match(TokenType.IF):
                    # else if — recursively parse another if expression
                    else_expr = (yield ("parse_if_expression", ()))
                else:
                    self.consume(TokenType.LEFT_BRACE)
                    self.skip_terminators()
                    else_expr = (yield ("parse_expression", ()))
                    self.skip_terminators()
                    self.consume(TokenType.RIGHT_BRACE)

                return ASTNode(
                    kind=NodeKind.IF_EXPR,
                    condition=condition,
                    then_expr=then_expr,
                    else_expr=else_expr,
                    span=create_span_from_token(if_token),
                )

            finally:
                self._exit_nesting()

        if action == "parse_match_expression":
            match_token = self.consume(TokenType.MATCH)
            saved = self._header_depth
            self._header_depth = self._depth_at[self.position]
            try:
                expression = (yield ("parse_expression", ()))
            finally:
                self._header_depth = saved

            self.consume(TokenType.LEFT_BRACE)
            cases = []
            else_case = None

            while not self.at_end():
                iteration_start = self.position
                self.skip_terminators()
                if self.match(TokenType.RIGHT_BRACE) or self.at_end():
                    break
                self._check_match_arm_order(else_case is not None)

                if self.match(TokenType.CASE):
                    case_token = self.advance()

                    patterns = [(yield ("parse_pattern", ()))]
                    while self.match(TokenType.COMMA):
                        self.advance()
                        patterns.append((yield ("parse_pattern", ())))

                    self.consume(TokenType.COLON)
                    # In expression context, parse an expression (not a statement)
                    value = (yield ("parse_expression", ()))

                    case_node = ASTNode(
                        kind=NodeKind.CASE_BRANCH,
                        patterns=patterns,
                        expression=value,
                        span=create_span_from_token(case_token),
                    )
                    cases.append(case_node)

                elif self.match(TokenType.ELSE):
                    self.advance()
                    self.consume(TokenType.COLON)
                    else_case = (yield ("parse_expression", ()))

                else:
                    raise self._fatal_error(
                        "Expected 'case' or 'else' in match expression",
                        self.current(),
                    )

                self.skip_terminators()
                self._require_progress(iteration_start, "match expression")

            self.consume(TokenType.RIGHT_BRACE)

            return ASTNode(
                kind=NodeKind.MATCH_EXPR,
                expression=expression,
                cases=cases,
                else_case=else_case,
                span=create_span_from_token(match_token),
            )

        if action == "parse_array_literal":
            start_token = self.consume(TokenType.LEFT_BRACKET)
            elements = []
            self.skip_terminators()

            while not self.match(TokenType.RIGHT_BRACKET):
                elements.append((yield ("parse_expression", ())))
                self._list_separator(TokenType.RIGHT_BRACKET, "array literal")

            self.consume(TokenType.RIGHT_BRACKET)

            return ASTNode(
                kind=NodeKind.ARRAY_INIT,
                elements=elements,
                span=create_span_from_token(start_token),
            )

        if action == "parse_struct_literal":
            struct_name, span = payload
            self.consume(TokenType.LEFT_BRACE)
            field_inits = []

            # Skip terminators after opening brace
            self.skip_terminators()

            # Named (`field: value`) or positional (`value`); the first item decides.
            is_named = self.match(TokenType.IDENTIFIER) and self.peek().type == TokenType.COLON

            while not self.match(TokenType.RIGHT_BRACE):
                if is_named:
                    field_name_token = self.consume(TokenType.IDENTIFIER)
                    self.consume(TokenType.COLON)
                    field_value = (yield ("parse_expression", ()))
                    field_name = field_name_token.value
                    field_span = create_span_from_token(field_name_token)
                else:
                    field_value = (yield ("parse_expression", ()))
                    field_name = None
                    field_span = field_value.span
                field_inits.append(
                    ASTNode(
                        kind=NodeKind.FIELD_INIT,
                        name=field_name,
                        value=field_value,
                        span=field_span,
                    )
                )
                self._list_separator(TokenType.RIGHT_BRACE, "struct literal")

            self.consume(TokenType.RIGHT_BRACE)

            return ASTNode(
                kind=NodeKind.STRUCT_INIT,
                struct_type=struct_name,
                field_inits=field_inits,
                span=span,
            )

        if action == "_parse_inline_struct_init":
            struct_type, = payload
            init = (yield ("parse_struct_literal", ("__inline__", struct_type.span)))
            init.inline_type = struct_type
            return init

        if action == "parse_pattern":
            start_token = self.current()

            # Parse the first part of the pattern
            pattern = (yield ("parse_primary_pattern", ()))

            # Check for range pattern: expr..expr
            if self.match(TokenType.DOT_DOT):
                self.advance()  # consume '..'
                end_pattern = (yield ("parse_primary_pattern", ()))

                return ASTNode(
                    kind=NodeKind.PATTERN_RANGE,
                    start=pattern,
                    end=end_pattern,
                    span=create_span_from_token(start_token),
                )

            return pattern

        if action == "parse_primary_pattern":
            start_token = self.current()

            # Literals
            if self.match(
                TokenType.INTEGER_LITERAL,
                TokenType.FLOAT_LITERAL,
                TokenType.CHAR_LITERAL,
                TokenType.STRING_LITERAL,
                TokenType.TRUE_LITERAL,
                TokenType.FALSE_LITERAL,
                TokenType.NIL_LITERAL,
            ):
                return ASTNode(
                    kind=NodeKind.PATTERN_LITERAL,
                    literal=create_literal_from_token(self.advance()),
                    span=create_span_from_token(start_token),
                )

            # Leading-dot tag patterns for tagged unions: `.tag` tests the tag
            # without binding; `.tag(name)` tests and binds the payload by value.
            # There is no `.tag(_)` placeholder form; omit the binding instead.
            if self.match(TokenType.DOT):
                self.advance()  # consume '.'
                if not self.match(TokenType.IDENTIFIER):
                    raise ParseError.from_token(
                        "Expected a tag name after '.' in pattern",
                        self.current(), self.filename
                    )
                tag_identifier = self.advance()
                binding: Optional[str] = None
                if self.match(TokenType.LEFT_PAREN):
                    self.advance()  # consume '('
                    if not self.match(TokenType.IDENTIFIER):
                        raise ParseError.from_token(
                            "Expected a binding name in '.tag(name)' pattern",
                            self.current(), self.filename
                        )
                    binding_identifier = self.advance()
                    if binding_identifier.value == "_":
                        raise ParseError.from_token(
                            "No '.tag(_)' form: write bare '.tag' to test without binding",
                            binding_identifier, self.filename
                        )
                    binding = binding_identifier.value
                    self.consume(TokenType.RIGHT_PAREN)
                return ASTNode(
                    kind=NodeKind.PATTERN_ENUM,
                    enum_type="",
                    variant=tag_identifier.value,
                    name=binding,
                    span=create_span_from_token(start_token),
                )

            # Identifiers and enum access patterns
            if self.match(TokenType.IDENTIFIER):
                first_identifier = self.advance()

                # Check for enum access: EnumType.Variant
                if self.match(TokenType.DOT):
                    self.advance()  # consume '.'
                    if not self.match(TokenType.IDENTIFIER):
                        raise ParseError.from_token(
                            "Expected identifier after '.' in pattern",
                            self.current(), self.filename
                        )
                    variant_identifier = self.advance()

                    return ASTNode(
                        kind=NodeKind.PATTERN_ENUM,
                        enum_type=first_identifier.value,
                        variant=variant_identifier.value,
                        span=create_span_from_token(start_token),
                    )
                else:
                    if first_identifier.value == "_":
                        return ASTNode(
                            kind=NodeKind.PATTERN_WILDCARD,
                            span=create_span_from_token(start_token),
                        )
                    # Simple identifier pattern
                    return ASTNode(
                        kind=NodeKind.PATTERN_IDENTIFIER,
                        name=first_identifier.value,
                        span=create_span_from_token(start_token),
                    )

            # Fall back to expression parsing for complex patterns
            return (yield ("parse_expression", ()))

    def parse_type_set(self) -> ASTNode:
        """Parse type set: @type_set(i32, i64, f32)."""
        return self._expression_work("parse_type_set", ())

    def parse_mixed_parameters(self) -> tuple[List[ASTNode], List[ASTNode]]:
        """Parse function parameters.
        Returns (generic_params, regular_params).
        Note: With new syntax, generic params are not declared in parameter list."""
        generic_params = []  # Always empty with new syntax
        regular_params = []

        self.skip_terminators()
        while not self.match(TokenType.RIGHT_PAREN):
            # Parse regular function parameter (which may use generic types like $T)
            regular_params.append(self.parse_parameter())
            self._list_separator(TokenType.RIGHT_PAREN, "parameter list")

        self.consume(TokenType.RIGHT_PAREN)
        return generic_params, regular_params

    def parse_parameter(self) -> ASTNode:
        """Parse function parameter (including variadic parameters)."""
        # Check for variadic parameter: args: ..i32 or args: ..
        if self.match(TokenType.IDENTIFIER):
            name_token = self.advance()
            name = name_token.value
            self.consume(TokenType.COLON)

            # Check for variadic marker (..)
            is_variadic = False
            if self.match(TokenType.DOT_DOT):
                is_variadic = True
                self.advance()

            # Only the variadic form may omit the type: `args: ..`
            param_type = None
            if not self.match(TokenType.COMMA, TokenType.RIGHT_PAREN):
                param_type = self.parse_type()
            elif not is_variadic:
                raise ParseError.from_token(
                    f"Expected a type after ':' for parameter '{name}'",
                    self.current(),
                    self.filename,
                    self.source_lines,
                )

            return create_parameter(
                name=name,
                param_type=param_type,
                is_variadic=is_variadic,
                span=create_span_from_token(name_token)
            )

        raise ParseError.from_token(
            "Expected parameter name", self.current(), self.filename
        )

    def parse_type(self) -> ASTNode:
        """Parse type expressions."""
        return self._expression_work("parse_type", ())

    def parse_block(self) -> ASTNode:
        """Parse block statement."""
        return self._statement_work("parse_block", None)

    def parse_statement(self) -> Optional[ASTNode]:
        """Parse statements."""
        return self._statement_work("parse_statement", None)

    def _parse_header_expression(self) -> ASTNode:
        """Parse the expression of an `if`/`while`/`match` header.

        Up to the `{` that opens the body, `Name {` at header depth is not a
        struct literal.
        """
        saved = self._header_depth
        self._header_depth = self._depth_at[self.position]
        try:
            return self.parse_expression()
        finally:
            self._header_depth = saved

    def _require_block_start(self, after: str) -> None:
        if not self.match(TokenType.LEFT_BRACE):
            token = self.current()
            raise ParseError.from_token(
                f"Expected '{{' to open a block after {after}, found {_describe(token)}",
                token,
                self.filename,
                self.source_lines,
            )

    def parse_if_statement(self) -> ASTNode:
        """Parse if statement. Both branches are blocks; `else if` chains."""
        return self._statement_work("parse_if_statement", None)

    def parse_while_statement(self) -> ASTNode:
        """Parse while statement. The body is a block."""
        return self._statement_work("parse_while_statement", None)

    def parse_for_statement(self) -> ASTNode:
        """Parse for statement."""
        return self._statement_work("parse_for_statement", None)

    def _parse_for_header(self) -> tuple[NodeKind, dict]:
        """Parse a for header up to the body: the node kind and its header fields."""
        if not self.match(TokenType.IDENTIFIER):
            raise ParseError.from_token(
                "Expected identifier or '{' after 'for' keyword",
                self.current(), self.filename
            )

        first_identifier = self.current()

        # Indexed iteration: for i, value in arr
        if self.peek().type == TokenType.COMMA:
            self.advance()
            self.advance()  # consume comma
            if not self.match(TokenType.IDENTIFIER):
                raise ParseError.from_token(
                    "Expected identifier after comma in for loop",
                    self.current(), self.filename
                )
            second_identifier = self.advance()

            if not self.match(TokenType.IN):
                raise ParseError.from_token(
                    "Expected 'in' keyword in for loop",
                    self.current(), self.filename
                )
            self.consume(TokenType.IN)
            return NodeKind.FOR_IN_INDEXED, {
                "index_var": first_identifier.value,
                "iterator": second_identifier.value,
                "iterable": self.parse_expression(),
            }

        # Range-based: for value in arr
        if self.peek().type == TokenType.IN:
            self.advance()
            self.consume(TokenType.IN)
            return NodeKind.FOR_IN, {
                "iterator": first_identifier.value,
                "iterable": self.parse_expression(),
            }

        # C-style: for init; condition; update
        if self.peek().type == TokenType.DECLARE_VAR:
            name_token = self.advance()
            self.consume(TokenType.DECLARE_VAR)
            init = create_var_decl(
                name=name_token.value,
                value=self.parse_expression(),
                is_public=False,
                span=create_span_from_token(name_token),
            )
        else:
            init = self.parse_expression_or_assignment()
        self._consume_for_separator()
        condition = self.parse_expression()
        self._consume_for_separator()
        update = self.parse_expression_or_assignment()
        return NodeKind.FOR, {"init": init, "condition": condition, "update": update}

    def _consume_for_separator(self) -> None:
        if not self.match(TokenType.TERMINATOR):
            raise ParseError.from_token(
                "Expected ';' or newline in for loop", self.current(), self.filename
            )
        self.advance()

    def parse_expression_or_assignment(self) -> ASTNode:
        """Parse expression statement or assignment."""
        start_token = self.current()
        expr = self.parse_expression()

        # Check for assignment operators
        if self.match(
            TokenType.ASSIGN,
            TokenType.PLUS_ASSIGN,
            TokenType.MINUS_ASSIGN,
            TokenType.MULTIPLY_ASSIGN,
            TokenType.DIVIDE_ASSIGN,
            TokenType.MODULO_ASSIGN,
            TokenType.BITWISE_AND_ASSIGN,
            TokenType.BITWISE_OR_ASSIGN,
            TokenType.BITWISE_XOR_ASSIGN,
            TokenType.LEFT_SHIFT_ASSIGN,
            TokenType.RIGHT_SHIFT_ASSIGN,
        ):
            if expr.kind not in _ASSIGNABLE_KINDS:
                raise ParseError.from_token(
                    "Invalid assignment target: assign to a variable, a field or an indexed element",
                    start_token,
                    self.filename,
                    self.source_lines,
                )
            op_token = self.advance()
            value = self.parse_expression()
            return create_assignment_stmt(
                target=expr,
                op=token_to_assign_op(op_token.type),
                value=value,
                span=combine_spans(expr.span, value.span),
            )

        # Otherwise it's an expression statement
        return ASTNode(
            kind=NodeKind.EXPRESSION_STMT,
            expression=expr,
            span=expr.span,
        )

    def parse_expression(self) -> ASTNode:
        """Parse expressions using precedence climbing."""
        return self._expression_work("parse_expression", ())

    def parse_binary_expression(self, min_precedence: int) -> ASTNode:
        """Parse binary expressions with precedence climbing."""
        return self._expression_work("parse_binary_expression", (min_precedence,))

    def parse_unary_expression(self) -> ASTNode:
        """Parse unary expressions."""
        return self._expression_work("parse_unary_expression", ())

    def parse_postfix_expression(self) -> ASTNode:
        """Parse postfix expressions (calls, indexing, field access)."""
        return self._expression_work("parse_postfix_expression", ())

    def _is_type_start(self) -> bool:
        """Check if the current token starts a type that cannot be an expression."""
        return self.current().type in _TYPE_ONLY_STARTS

    def _bracket_starts_type(self) -> bool:
        """True if the `[` at the current token opens an array or slice type.

        `[N]T` and `[]T` continue with a type after the matching `]`; an
        array literal does not. The decision reads the matching-bracket table
        and never parses, so a `[`-led argument is parsed once.
        """
        index = self.position
        while self.tokens[index].type == TokenType.LEFT_BRACKET:
            close = self._close_at.get(index)
            if close is None:
                return False
            index = close + 1
        return self.tokens[index].type in _TYPE_STARTS

    def _parse_call_argument(self) -> ASTNode:
        """Parse a single call argument, which may be an expression or a type argument."""
        return self._expression_work("_parse_call_argument", ())

    def parse_call_expression(self, function: ASTNode) -> ASTNode:
        """Parse function call expression."""
        return self._expression_work("parse_call_expression", (function,))

    def parse_index_expression(self, object_expr: ASTNode) -> ASTNode:
        """Parse array indexing expression."""
        return self._expression_work("parse_index_expression", (object_expr,))

    def parse_field_or_deref_expression(self, object_expr: ASTNode) -> ASTNode:
        """Parse field access."""
        self.consume(TokenType.DOT)

        if self.match(TokenType.IDENTIFIER):
            field_token = self.advance()
            return ASTNode(
                kind=NodeKind.FIELD_ACCESS,
                object=object_expr,
                field=field_token.value,
                span=_span_through(object_expr.span, field_token),
            )

        raise ParseError.from_token(
            "Expected field name after '.'", self.current(), self.filename
        )

    def parse_primary_expression(self) -> ASTNode:
        """Parse primary expressions."""
        return self._expression_work("parse_primary_expression", ())

    def parse_cast_expression(self, start_token: Token) -> ASTNode:
        """Parse cast expression: cast(type, expr)"""
        return self._expression_work("parse_cast_expression", (start_token,))

    def parse_builtin_intrinsic(self) -> ASTNode:
        """Parse builtin intrinsic: @size_of(T), @align_of(T), @type_id(T), @unreachable(), etc."""
        return self._expression_work("parse_builtin_intrinsic", ())

    def parse_new_expression(self) -> ASTNode:
        """Parse new expression: new Type, new [size]Type, or new(Type)"""
        return self._expression_work("parse_new_expression", ())

    def parse_if_expression(self) -> ASTNode:
        """Parse if expressions: if cond { expr } else if cond { expr } else { expr }"""
        return self._expression_work("parse_if_expression", ())

    def parse_match_expression(self) -> ASTNode:
        """Parse match expression (match used in expression context).
        Reuses the same syntax as match statements but produces a MATCH_EXPR node."""
        return self._expression_work("parse_match_expression", ())

    def parse_array_literal(self) -> ASTNode:
        """Parse array literals: [1, 2, 3]"""
        return self._expression_work("parse_array_literal", ())

    def parse_struct_literal(self, struct_name: str, span: SourceSpan) -> ASTNode:
        """Parse struct literals: Person{name: "John", age: 30} or Token{1, [10, 20, 30]}"""
        return self._expression_work("parse_struct_literal", (struct_name, span))

    def _parse_inline_struct_init(self, struct_type: ASTNode) -> ASTNode:
        """Parse inline struct initialization: struct { ... } { field: value, ... }"""
        return self._expression_work("_parse_inline_struct_init", (struct_type,))

    def parse_struct_decl_with_name(
        self, name: str, is_public: bool, name_token: Token
    ) -> ASTNode:
        """Parse struct declarations when name is already parsed."""
        self.consume(TokenType.STRUCT)

        # No generic parameter declarations needed - $T used directly in fields
        generic_params = []

        # Struct body
        self.consume(TokenType.LEFT_BRACE)
        fields = []

        self.skip_terminators()
        while not self.match(TokenType.RIGHT_BRACE):
            # Handle optional 'pub' modifier on fields
            field_is_public = False
            if self.match(TokenType.PUB):
                field_is_public = True
                self.advance()
            field_name_token = self.consume(TokenType.IDENTIFIER)
            self.consume(TokenType.COLON)
            field_type = self.parse_type()

            field = ASTNode(
                kind=NodeKind.FIELD,
                name=field_name_token.value,
                field_type=field_type,
                is_public=field_is_public,
                span=create_span_from_token(field_name_token),
            )
            fields.append(field)
            self._list_separator(
                TokenType.RIGHT_BRACE, "struct fields", newline_separates=True
            )

        self.consume(TokenType.RIGHT_BRACE)

        where_clause = self._parse_trailing_where_clause()
        node = ASTNode(
            kind=NodeKind.STRUCT,
            name=name,
            fields=fields,
            generic_params=generic_params,
            is_public=is_public,
            span=create_span_from_token(name_token),
        )
        if where_clause is not None:
            node.where_clause = where_clause
        return node

    def parse_enum_decl_with_name(
        self, name: str, is_public: bool, name_token: Token
    ) -> ASTNode:
        """Parse enum declarations when name is already parsed."""
        self.consume(TokenType.ENUM)

        # Enum body
        self.consume(TokenType.LEFT_BRACE)
        variants = []

        self.skip_terminators()

        while not self.match(TokenType.RIGHT_BRACE):
            variant_name_token = self.consume(TokenType.IDENTIFIER)
            variant_value = None

            # Optional explicit value
            if self.match(TokenType.ASSIGN):
                self.advance()
                variant_value = self.parse_expression()

            variant = ASTNode(
                kind=NodeKind.ENUM_VARIANT,
                name=variant_name_token.value,
                value=variant_value,
                span=create_span_from_token(variant_name_token),
            )
            variants.append(variant)
            self._list_separator(
                TokenType.RIGHT_BRACE, "enum variants", newline_separates=True
            )

        self.consume(TokenType.RIGHT_BRACE)

        return ASTNode(
            kind=NodeKind.ENUM,
            name=name,
            variants=variants,
            is_public=is_public,
            span=create_span_from_token(name_token),
        )

    def parse_union_decl_with_name(
        self, name: str, is_public: bool, name_token: Token
    ) -> ASTNode:
        """Parse union declarations when name is already parsed."""
        self.consume(TokenType.UNION)

        # Check for tagged union
        is_tagged = False
        if self.match(TokenType.LEFT_PAREN):
            self.advance()
            if self.match(TokenType.IDENTIFIER) and self.current().value == "tag":
                is_tagged = True
                self.advance()
            self.consume(TokenType.RIGHT_PAREN)

        # Union body
        self.consume(TokenType.LEFT_BRACE)
        fields = []

        self.skip_terminators()
        while not self.match(TokenType.RIGHT_BRACE):
            field_name_token = self.consume(TokenType.IDENTIFIER)
            self.consume(TokenType.COLON)
            field_type = self.parse_type()

            field = ASTNode(
                kind=NodeKind.FIELD,
                name=field_name_token.value,
                field_type=field_type,
                span=create_span_from_token(field_name_token),
            )
            fields.append(field)
            self._list_separator(
                TokenType.RIGHT_BRACE, "union fields", newline_separates=True
            )

        self.consume(TokenType.RIGHT_BRACE)

        where_clause = self._parse_trailing_where_clause()
        node = ASTNode(
            kind=NodeKind.UNION,
            name=name,
            fields=fields,
            is_tagged=is_tagged,
            is_public=is_public,
            span=create_span_from_token(name_token),
        )
        if where_clause is not None:
            node.where_clause = where_clause
        return node

    def parse_pattern(self) -> ASTNode:
        """Parse match patterns including ranges, literals, and enum access."""
        return self._expression_work("parse_pattern", ())

    def parse_primary_pattern(self) -> ASTNode:
        """Parse primary pattern elements (literals, identifiers with dots)."""
        return self._expression_work("parse_primary_pattern", ())

    def parse_match_statement(self) -> ASTNode:
        """Parse match statements."""
        return self._statement_work("parse_match_statement", None)

    def _check_match_arm_order(self, else_seen: bool) -> None:
        """`else:` is the last arm of a match and appears once."""
        if not else_seen:
            return
        if self.match(TokenType.ELSE):
            message = "A match has one 'else:' arm; this is a second one"
        elif self.match(TokenType.CASE):
            message = "A 'case' arm cannot follow 'else:'; put 'else:' last"
        else:
            return
        raise ParseError.from_token(
            message, self.current(), self.filename, self.source_lines
        )

    def parse_defer_statement(self) -> ASTNode:
        """Parse defer statements."""
        return self._statement_work("parse_defer_statement", None)

    def parse_del_statement(self) -> ASTNode:
        """Parse del statements."""
        del_token = self.consume(TokenType.DEL)
        expr = self.parse_expression()
        return create_del_stmt(
            expr=expr,
            span=create_span_from_token(del_token),
        )


def parse_a7(source_code: str, filename: Optional[str] = None) -> ASTNode:
    """Parse A7 source code and return an AST."""
    tokenizer = Tokenizer(source_code, filename)
    tokens = tokenizer.tokenize()
    source_lines = source_code.splitlines() if source_code else []
    parser = Parser(tokens, filename, source_lines)
    return parser.parse()
