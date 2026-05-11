"""
Token types and tokenizer for the A7 programming language.
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, List, Union
import re
import string
from .errors import TokenizerError, TokenizerErrorType


# A7 Language limits (matching C implementation)
MAX_IDENTIFIER_LENGTH = 100
MAX_NUMBER_LENGTH = 100
MAX_STRING_LENGTH = 2**15 - 1  # Very large but finite limit


class TokenType(Enum):
    # Literals
    INTEGER_LITERAL = auto()
    FLOAT_LITERAL = auto()
    STRING_LITERAL = auto()
    CHAR_LITERAL = auto()
    TRUE_LITERAL = auto()
    FALSE_LITERAL = auto()
    NIL_LITERAL = auto()

    # Identifiers and Keywords
    IDENTIFIER = auto()
    BUILTIN_ID = auto()  # @function

    # Keywords
    AND = auto()  # and
    AS = auto()  # as
    BOOL = auto()  # bool
    BREAK = auto()  # break
    CASE = auto()  # case
    CHAR = auto()  # char
    CONTINUE = auto()  # continue
    DEL = auto()  # del (delete)
    DEFER = auto()  # defer
    ELSE = auto()  # else
    ENUM = auto()  # enum
    F32 = auto()  # f32
    F64 = auto()  # f64
    FALL = auto()  # fall
    FALSE = auto()  # false
    FLOAT = auto()  # float
    FN = auto()  # fn
    FOR = auto()  # for
    IF = auto()  # if
    IMPORT = auto()  # import
    IN = auto()  # in
    INT = auto()  # int
    I8 = auto()  # i8
    I16 = auto()  # i16
    I32 = auto()  # i32
    I64 = auto()  # i64
    ISIZE = auto()  # isize
    LET = auto()  # let
    MATCH = auto()  # match
    NEW = auto()  # new
    NIL = auto()  # nil
    NOT = auto()  # not
    OR = auto()  # or
    PUB = auto()  # pub
    REF = auto()  # ref
    RET = auto()  # ret
    STRING = auto()  # string
    STRUCT = auto()  # struct
    TRUE = auto()  # true
    UNION = auto()  # union
    U8 = auto()  # u8
    U16 = auto()  # u16
    U32 = auto()  # u32
    U64 = auto()  # u64
    UINT = auto()  # uint
    USIZE = auto()  # usize
    WHERE = auto()  # where
    WHILE = auto()  # while

    # Operators
    PLUS = auto()  # +
    MINUS = auto()  # -
    MULTIPLY = auto()  # *
    DIVIDE = auto()  # /
    MODULO = auto()  # %

    # Assignment operators
    ASSIGN = auto()  # =
    PLUS_ASSIGN = auto()  # +=
    MINUS_ASSIGN = auto()  # -=
    MULTIPLY_ASSIGN = auto()  # *=
    DIVIDE_ASSIGN = auto()  # /=
    MODULO_ASSIGN = auto()  # %=

    # Comparison operators
    EQUAL = auto()  # ==
    NOT_EQUAL = auto()  # !=
    LESS_THAN = auto()  # <
    LESS_EQUAL = auto()  # <=
    GREATER_THAN = auto()  # >
    GREATER_EQUAL = auto()  # >=

    # Bitwise operators
    BITWISE_AND = auto()  # &
    BITWISE_OR = auto()  # |
    BITWISE_XOR = auto()  # ^
    BITWISE_NOT = auto()  # ~
    LEFT_SHIFT = auto()  # <<
    RIGHT_SHIFT = auto()  # >>

    # Bitwise assignment operators
    BITWISE_AND_ASSIGN = auto()  # &=
    BITWISE_OR_ASSIGN = auto()  # |=
    BITWISE_XOR_ASSIGN = auto()  # ^=
    LEFT_SHIFT_ASSIGN = auto()  # <<=
    RIGHT_SHIFT_ASSIGN = auto()  # >>=

    # Logical operators (handled as keywords)
    LOGICAL_NOT = auto()  # !

    # Punctuation
    SEMICOLON = auto()  # ;
    COLON = auto()  # :
    COMMA = auto()  # ,
    DOT = auto()  # .
    DOT_DOT = auto()  # ..

    # Declaration operators
    DECLARE_CONST = auto()  # ::
    DECLARE_VAR = auto()  # :=

    # Brackets and Parentheses
    LEFT_PAREN = auto()  # (
    RIGHT_PAREN = auto()  # )
    LEFT_BRACKET = auto()  # [
    RIGHT_BRACKET = auto()  # ]
    LEFT_BRACE = auto()  # {
    RIGHT_BRACE = auto()  # }

    # Pointer operators
    ADDRESS_OF = auto()  # &
    DEREFERENCE = auto()  # ptr.* (handled specially)

    # Comments
    COMMENT = auto()  # // or /* */

    # Generic/Template operators
    GENERIC_TYPE = auto()  # $T, $TYPE, $MY_TYPE (generic type parameters)

    # Special tokens
    # NEWLINE = auto()         # \n (significant in A7)
    TERMINATOR = auto()  # "\n" or ";" as Statement terminator
    EOF = auto()  # End of file


@dataclass
class Token:
    """Represents a single token in the A7 language."""

    type: TokenType
    value: str
    line: int
    column: int
    length: int = 0

    def __post_init__(self):
        if self.length == 0:
            self.length = len(self.value)


class Tokenizer:
    """Tokenizes A7 source code into tokens."""

    # Keywords mapping
    KEYWORDS = {
        "and": TokenType.AND,
        "as": TokenType.AS,
        "bool": TokenType.BOOL,
        "break": TokenType.BREAK,
        "case": TokenType.CASE,
        "char": TokenType.CHAR,
        "continue": TokenType.CONTINUE,
        "del": TokenType.DEL,
        "defer": TokenType.DEFER,
        "else": TokenType.ELSE,
        "enum": TokenType.ENUM,
        "f32": TokenType.F32,
        "f64": TokenType.F64,
        "fall": TokenType.FALL,
        "false": TokenType.FALSE,
        "float": TokenType.FLOAT,
        "fn": TokenType.FN,
        "for": TokenType.FOR,
        "if": TokenType.IF,
        "import": TokenType.IMPORT,
        "in": TokenType.IN,
        "int": TokenType.INT,
        "i8": TokenType.I8,
        "i16": TokenType.I16,
        "i32": TokenType.I32,
        "i64": TokenType.I64,
        "isize": TokenType.ISIZE,
        "let": TokenType.LET,
        "match": TokenType.MATCH,
        "new": TokenType.NEW,
        "nil": TokenType.NIL,
        "not": TokenType.NOT,
        "or": TokenType.OR,
        "pub": TokenType.PUB,
        "ref": TokenType.REF,
        "ret": TokenType.RET,
        "string": TokenType.STRING,
        "struct": TokenType.STRUCT,
        "true": TokenType.TRUE,
        "union": TokenType.UNION,
        "u8": TokenType.U8,
        "u16": TokenType.U16,
        "u32": TokenType.U32,
        "u64": TokenType.U64,
        "uint": TokenType.UINT,
        "usize": TokenType.USIZE,
        "where": TokenType.WHERE,
        "while": TokenType.WHILE,
    }

    def __init__(self, source_code: str, filename: Optional[str] = None):
        # Strip a leading UTF-8 BOM (Windows editors often emit one).
        # CR characters are still treated as horizontal whitespace by
        # skip_whitespace; tokenizer tests rely on that legacy behavior.
        if source_code.startswith("﻿"):
            source_code = source_code[1:]
        self.source = source_code
        self.filename = filename
        self.source_lines = source_code.splitlines()
        self.position = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []

    def current_char(self) -> Optional[str]:
        """Get the current character at position."""
        if self.position >= len(self.source):
            return None
        return self.source[self.position]

    def peek_char(self, offset: int = 1) -> Optional[str]:
        """Peek at character at current position + offset."""
        pos = self.position + offset
        if pos >= len(self.source):
            return None
        return self.source[pos]

    def advance(self) -> Optional[str]:
        """Advance position and return the current character."""
        if self.position >= len(self.source):
            return None

        char = self.source[self.position]
        self.position += 1

        if char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1

        return char

    def skip_whitespace(self):
        """Skip whitespace characters except newlines. Detect tabs and raise error."""
        while self.current_char() and self.current_char() in " \t\r":
            if self.current_char() == "\t":
                # A7 doesn't support tabs - raise error
                raise TokenizerError.from_type_and_location(
                    TokenizerErrorType.TABS_UNSUPPORTED,
                    self.line,
                    self.column,
                    1,
                    self.filename,
                    self.source_lines,
                    "Tabs '\\t' are unsupported",
                )
            self.advance()

    def tokenize(self) -> List[Token]:
        """Tokenize the source code and return list of tokens."""
        while self.position < len(self.source):
            self.skip_whitespace()

            if self.current_char() is None:
                break

            # Handle newlines as terminators
            if self.current_char() == "\n":
                self._add_token(TokenType.TERMINATOR, "\n")
                self.advance()
                continue

            # Handle comments
            if self._try_comment():
                continue

            # Handle numbers (including leading dot floats like .5)
            if self.current_char() and self.current_char().isdigit():
                self._tokenize_number()
                continue

            # Handle leading dot float literals (.5, .123, etc.)
            if self.current_char() == "." and self.peek_char() and self.peek_char().isdigit():
                self._tokenize_number()
                continue

            # Handle strings
            if self.current_char() == '"':
                self._tokenize_string()
                continue

            # Handle character literals
            if self.current_char() == "'":
                self._tokenize_char()
                continue

            # Handle identifiers and keywords
            if self.current_char() and (
                self.current_char().isascii()
                and self.current_char().isalpha()
                or self.current_char() == "_"
            ):
                self._tokenize_identifier()
                continue

            # Handle builtin functions (@function)
            if self.current_char() == "@":
                self._tokenize_builtin()
                continue

            # Handle generic types ($TYPE)
            if self.current_char() == "$":
                if self._try_generic_type():
                    continue

            # Handle operators and punctuation
            if self._try_operator():
                continue

            # Unknown character
            raise TokenizerError.from_type_and_location(
                TokenizerErrorType.INVALID_CHARACTER,
                self.line,
                self.column,
                1,
                self.filename,
                self.source_lines,
                f"Unexpected character: '{self.current_char()}'",
            )

        # Add EOF token
        self._add_token(TokenType.EOF, "")
        return self.tokens

    def _add_token(self, token_type: TokenType, value: str, column: int = None):
        """Add a token to the tokens list."""
        # Handle TERMINATOR deduplication
        if token_type == TokenType.TERMINATOR:
            # Don't add if the last token is already a TERMINATOR
            if self.tokens and self.tokens[-1].type == TokenType.TERMINATOR:
                return

        # Use provided column or calculate from current position
        if column is None:
            column = self.column - len(value)
        token = Token(token_type, value, self.line, column)
        self.tokens.append(token)

    def _try_comment(self) -> bool:
        """Try to tokenize a comment. Returns True if successful. Comments are discarded but line counting is preserved."""
        if self.current_char() == "/" and self.peek_char() == "/":
            # Single line comment - consume but don't add token
            while self.current_char() and self.current_char() != "\n":
                self.advance()
            # Leave newline for main tokenizer to handle as TERMINATOR
            return True

        if self.current_char() == "/" and self.peek_char() == "*":
            # Multi-line comment - consume but don't add token. EOF is an
            # accepted comment terminator (see test_003_comments) so an
            # unterminated /* simply consumes the rest of the file.
            self.advance()  # /
            self.advance()  # *

            depth = 1
            while self.current_char() and depth > 0:
                if self.current_char() == "/" and self.peek_char() == "*":
                    self.advance()
                    self.advance()
                    depth += 1
                elif self.current_char() == "*" and self.peek_char() == "/":
                    self.advance()
                    self.advance()
                    depth -= 1
                else:
                    self.advance()
            return True

        if self.current_char() == "#":
            # Alternative single line comment - consume but don't add token
            while self.current_char() and self.current_char() != "\n":
                self.advance()
            # Leave newline for main tokenizer to handle as TERMINATOR
            return True

        return False

    def _tokenize_number(self):
        """Tokenize integer or float literals."""
        start_pos = self.position
        start_column = self.column
        is_float = False

        # Handle binary numbers (0b)
        if self.current_char() == "0" and self.peek_char() == "b":
            self.advance()  # 0
            self.advance()  # b
            digit_start = self.position
            while self.current_char() and (self.current_char() in "01" or self.current_char() == "_"):
                self.advance()

            # Validate at least one binary digit was consumed (ignoring underscores)
            number_text = self.source[start_pos : self.position]
            if self.position == digit_start or number_text.replace("0b", "").replace("_", "") == "":
                raise TokenizerError.from_type_and_location(
                    TokenizerErrorType.INVALID_BINARY_NUMBER,
                    self.line,
                    start_column,
                    len(number_text),
                    self.filename,
                    self.source_lines,
                    "Binary literal must have at least one digit after '0b'",
                )

            # Check number length limit
            if len(number_text) > MAX_NUMBER_LENGTH:
                raise TokenizerError.from_type_and_location(
                    TokenizerErrorType.TOO_LONG_NUMBER,
                    self.line,
                    start_column,
                    len(number_text),
                    self.filename,
                    self.source_lines,
                )

            self._add_token(TokenType.INTEGER_LITERAL, number_text, start_column)
            return

        # Handle hexadecimal numbers (0x)
        if self.current_char() == "0" and self.peek_char() == "x":
            self.advance()  # 0
            self.advance()  # x
            digit_start = self.position
            while (
                self.current_char() and (self.current_char() in "0123456789abcdefABCDEF" or self.current_char() == "_")
            ):
                self.advance()

            # Validate at least one hex digit was consumed (ignoring underscores)
            number_text = self.source[start_pos : self.position]
            if self.position == digit_start or number_text.replace("0x", "").replace("_", "") == "":
                raise TokenizerError.from_type_and_location(
                    TokenizerErrorType.INVALID_HEX_NUMBER,
                    self.line,
                    start_column,
                    len(number_text),
                    self.filename,
                    self.source_lines,
                    "Hexadecimal literal must have at least one digit after '0x'",
                )

            # Check number length limit
            if len(number_text) > MAX_NUMBER_LENGTH:
                raise TokenizerError.from_type_and_location(
                    TokenizerErrorType.TOO_LONG_NUMBER,
                    self.line,
                    start_column,
                    len(number_text),
                    self.filename,
                    self.source_lines,
                )

            self._add_token(TokenType.INTEGER_LITERAL, number_text, start_column)
            return

        # Handle octal numbers (0o)
        if self.current_char() == "0" and self.peek_char() == "o":
            self.advance()  # 0
            self.advance()  # o
            digit_start = self.position
            while self.current_char() and (self.current_char() in "01234567" or self.current_char() == "_"):
                self.advance()

            # Validate at least one octal digit was consumed (ignoring underscores)
            number_text = self.source[start_pos : self.position]
            if self.position == digit_start or number_text.replace("0o", "").replace("_", "") == "":
                raise TokenizerError.from_type_and_location(
                    TokenizerErrorType.INVALID_OCTAL_NUMBER,
                    self.line,
                    start_column,
                    len(number_text),
                    self.filename,
                    self.source_lines,
                    "Octal literal must have at least one digit after '0o'",
                )

            # Check number length limit
            if len(number_text) > MAX_NUMBER_LENGTH:
                raise TokenizerError.from_type_and_location(
                    TokenizerErrorType.TOO_LONG_NUMBER,
                    self.line,
                    start_column,
                    len(number_text),
                    self.filename,
                    self.source_lines,
                )

            self._add_token(TokenType.INTEGER_LITERAL, number_text, start_column)
            return

        # Handle decimal numbers (including leading dot like .5)
        # First, consume integer part (if present)
        while self.current_char() and (self.current_char().isdigit() or self.current_char() == "_"):
            self.advance()

        # Check for decimal point (but not range operator ..)
        if self.current_char() == "." and self.peek_char() != ".":
            is_float = True
            self.advance()  # .
            # Consume fractional part (if present - allows trailing dots like 5.)
            while self.current_char() and (self.current_char().isdigit() or self.current_char() == "_"):
                self.advance()

        # Check for scientific notation (e or E followed by optional +/- and digits)
        if self.current_char() and self.current_char() in "eE":
            is_float = True
            self.advance()  # e or E

            # Optional + or - after e/E
            if self.current_char() and self.current_char() in "+-":
                self.advance()

            # Must have at least one digit after e/E (and optional +/-)
            if not (self.current_char() and self.current_char().isdigit()):
                raise TokenizerError.from_type_and_location(
                    TokenizerErrorType.INVALID_SCIENTIFIC_NOTATION,
                    self.line,
                    self.column,
                    1,
                    self.filename,
                    self.source_lines,
                )

            # Parse exponent digits
            while self.current_char() and (self.current_char().isdigit() or self.current_char() == "_"):
                self.advance()

        number_text = self.source[start_pos : self.position]

        # Check number length limit
        if len(number_text) > MAX_NUMBER_LENGTH:
            raise TokenizerError.from_type_and_location(
                TokenizerErrorType.TOO_LONG_NUMBER,
                self.line,
                start_column,
                len(number_text),
                self.filename,
                self.source_lines,
            )

        token_type = TokenType.FLOAT_LITERAL if is_float else TokenType.INTEGER_LITERAL
        self._add_token(token_type, number_text, start_column)

    def _tokenize_string(self):
        """Tokenize string literals."""
        start_pos = self.position
        start_line = self.line
        start_column = self.column
        self.advance()  # Opening quote

        while self.current_char() and self.current_char() != '"':
            if self.current_char() == "\\":
                self._consume_string_escape(start_line, start_column)
            else:
                self.advance()

        if not self.current_char():
            # Report error at the end of the string where the quote should be
            error_length = self.position - start_pos
            raise TokenizerError.from_type_and_location(
                TokenizerErrorType.NOT_CLOSED_STRING,
                start_line,
                start_column,
                error_length,
                self.filename,
                self.source_lines,
            )

        self.advance()  # Closing quote
        string_text = self.source[start_pos : self.position]
        # For multi-line strings, we need to use the stored start position
        token = Token(TokenType.STRING_LITERAL, string_text, start_line, start_column)
        self.tokens.append(token)

    def _consume_string_escape(self, start_line: int, start_column: int) -> None:
        escape_line = self.line
        escape_column = self.column
        self.advance()  # Backslash
        escape_char = self.current_char()

        if escape_char is None:
            raise TokenizerError.from_type_and_location(
                TokenizerErrorType.NOT_CLOSED_STRING,
                start_line,
                start_column,
                1,
                self.filename,
                self.source_lines,
            )

        if escape_char == "x":
            self.advance()  # 'x'
            for _ in range(2):
                if (
                    self.current_char()
                    and self.current_char().lower() in "0123456789abcdef"
                ):
                    self.advance()
                    continue
                raise TokenizerError.from_type_and_location(
                    TokenizerErrorType.INVALID_ESCAPE_CHAR,
                    escape_line,
                    escape_column,
                    max(1, self.column - escape_column + 1),
                    self.filename,
                    self.source_lines,
                    "Invalid string escape sequence",
                )
            return

        if escape_char in "ntr\\'\"0":
            self.advance()
            return

        raise TokenizerError.from_type_and_location(
            TokenizerErrorType.INVALID_ESCAPE_CHAR,
            escape_line,
            escape_column,
            2,
            self.filename,
            self.source_lines,
            "Invalid string escape sequence",
        )

    def _tokenize_char(self):
        """Tokenize character literals."""
        start_pos = self.position
        start_line = self.line
        start_column = self.column
        self.advance()  # Opening quote

        # Check for empty char literal
        if self.current_char() == "'":
            raise TokenizerError.from_type_and_location(
                TokenizerErrorType.NOT_CLOSED_CHAR,
                self.line,
                self.column,
                1,
                self.filename,
                self.source_lines,
            )

        # Check for EOF
        if self.current_char() is None:
            raise TokenizerError.from_type_and_location(
                TokenizerErrorType.NOT_CLOSED_CHAR,
                self.line,
                self.column,
                1,
                self.filename,
                self.source_lines,
            )

        if self.current_char() == "\\":
            self.advance()  # Escape character
            escape_char = self.current_char()
            if escape_char is None:
                raise TokenizerError.from_type_and_location(
                    TokenizerErrorType.NOT_CLOSED_CHAR,
                    self.line,
                    self.column,
                    1,
                    self.filename,
                    self.source_lines,
                )
            elif escape_char == "x":
                # Hex escape sequence: \x41
                self.advance()  # 'x'
                # Read two hex digits
                for _ in range(2):
                    if (
                        self.current_char()
                        and self.current_char().lower() in "0123456789abcdef"
                    ):
                        self.advance()
                    else:
                        raise TokenizerError.from_type_and_location(
                            TokenizerErrorType.NOT_CLOSED_CHAR,
                            self.line,
                            self.column,
                            1,
                            self.filename,
                            self.source_lines,
                        )
            elif escape_char in "ntr\\'\"0":
                # Standard escape sequences: \n, \t, \r, \\, \', \", \0
                self.advance()
            else:
                # Invalid escape sequence
                raise TokenizerError.from_type_and_location(
                    TokenizerErrorType.NOT_CLOSED_CHAR,
                    self.line,
                    self.column,
                    1,
                    self.filename,
                    self.source_lines,
                )
        else:
            # Single character
            self.advance()

            # Check for multiple characters (like 'ab')
            if self.current_char() and self.current_char() != "'":
                raise TokenizerError.from_type_and_location(
                    TokenizerErrorType.NOT_CLOSED_CHAR,
                    self.line,
                    self.column,
                    1,
                    self.filename,
                    self.source_lines,
                )

        if self.current_char() != "'":
            raise TokenizerError.from_type_and_location(
                TokenizerErrorType.NOT_CLOSED_CHAR,
                self.line,
                self.column,
                1,
                self.filename,
                self.source_lines,
            )

        self.advance()  # Closing quote
        char_text = self.source[start_pos : self.position]
        # Use stored start position for correct column
        token = Token(TokenType.CHAR_LITERAL, char_text, start_line, start_column)
        self.tokens.append(token)

    def _tokenize_identifier(self):
        """Tokenize identifiers and keywords."""
        start_pos = self.position
        start_column = self.column

        while self.current_char() and (
            self.current_char().isascii()
            and self.current_char().isalnum()
            or self.current_char() == "_"
        ):
            self.advance()

        identifier_text = self.source[start_pos : self.position]

        # Check identifier length limit
        if len(identifier_text) > MAX_IDENTIFIER_LENGTH:
            raise TokenizerError.from_type_and_location(
                TokenizerErrorType.TOO_LONG_IDENTIFIER,
                self.line,
                start_column,
                len(identifier_text),
                self.filename,
                self.source_lines,
            )

        # Check if it's a keyword
        token_type = self.KEYWORDS.get(identifier_text, TokenType.IDENTIFIER)

        # Handle boolean literals
        if identifier_text == "true":
            token_type = TokenType.TRUE_LITERAL
        elif identifier_text == "false":
            token_type = TokenType.FALSE_LITERAL
        elif identifier_text == "nil":
            token_type = TokenType.NIL_LITERAL

        self._add_token(token_type, identifier_text)

    def _tokenize_builtin(self):
        """Tokenize builtin function identifiers (@function)."""
        start_pos = self.position
        self.advance()  # @

        while self.current_char() and (
            self.current_char().isalnum() or self.current_char() == "_"
        ):
            self.advance()

        builtin_text = self.source[start_pos : self.position]
        self._add_token(TokenType.BUILTIN_ID, builtin_text)

    def _try_operator(self) -> bool:
        """Try to tokenize operators and punctuation. Returns True if successful."""
        char = self.current_char()
        next_char = self.peek_char()

        # Three-character operators (check these first!)
        if char == "<" and next_char == "<" and self.peek_char(2) == "=":
            self._add_token(TokenType.LEFT_SHIFT_ASSIGN, "<<=")
            self.advance()
            self.advance()
            self.advance()
            return True
        elif char == ">" and next_char == ">" and self.peek_char(2) == "=":
            self._add_token(TokenType.RIGHT_SHIFT_ASSIGN, ">>=")
            self.advance()
            self.advance()
            self.advance()
            return True

        # Two-character operators
        two_char = char + (next_char or "")

        if two_char == "::":
            self._add_token(TokenType.DECLARE_CONST, "::")
            self.advance()
            self.advance()
            return True
        elif two_char == ":=":
            self._add_token(TokenType.DECLARE_VAR, ":=")
            self.advance()
            self.advance()
            return True
        elif two_char == "==":
            self._add_token(TokenType.EQUAL, "==")
            self.advance()
            self.advance()
            return True
        elif two_char == "!=":
            self._add_token(TokenType.NOT_EQUAL, "!=")
            self.advance()
            self.advance()
            return True
        elif two_char == "<=":
            self._add_token(TokenType.LESS_EQUAL, "<=")
            self.advance()
            self.advance()
            return True
        elif two_char == ">=":
            self._add_token(TokenType.GREATER_EQUAL, ">=")
            self.advance()
            self.advance()
            return True
        elif two_char == "<<":
            self._add_token(TokenType.LEFT_SHIFT, "<<")
            self.advance()
            self.advance()
            return True
        elif two_char == ">>":
            self._add_token(TokenType.RIGHT_SHIFT, ">>")
            self.advance()
            self.advance()
            return True
        elif two_char == "+=":
            self._add_token(TokenType.PLUS_ASSIGN, "+=")
            self.advance()
            self.advance()
            return True
        elif two_char == "-=":
            self._add_token(TokenType.MINUS_ASSIGN, "-=")
            self.advance()
            self.advance()
            return True
        elif two_char == "*=":
            self._add_token(TokenType.MULTIPLY_ASSIGN, "*=")
            self.advance()
            self.advance()
            return True
        elif two_char == "/=":
            self._add_token(TokenType.DIVIDE_ASSIGN, "/=")
            self.advance()
            self.advance()
            return True
        elif two_char == "%=":
            self._add_token(TokenType.MODULO_ASSIGN, "%=")
            self.advance()
            self.advance()
            return True
        elif two_char == "&=":
            self._add_token(TokenType.BITWISE_AND_ASSIGN, "&=")
            self.advance()
            self.advance()
            return True
        elif two_char == "|=":
            self._add_token(TokenType.BITWISE_OR_ASSIGN, "|=")
            self.advance()
            self.advance()
            return True
        elif two_char == "^=":
            self._add_token(TokenType.BITWISE_XOR_ASSIGN, "^=")
            self.advance()
            self.advance()
            return True
        elif two_char == "..":
            self._add_token(TokenType.DOT_DOT, "..")
            self.advance()
            self.advance()
            return True

        # Single-character operators
        operators = {
            "+": TokenType.PLUS,
            "-": TokenType.MINUS,
            "*": TokenType.MULTIPLY,
            "/": TokenType.DIVIDE,
            "%": TokenType.MODULO,
            "=": TokenType.ASSIGN,
            "<": TokenType.LESS_THAN,
            ">": TokenType.GREATER_THAN,
            "&": TokenType.BITWISE_AND,  # Also ADDRESS_OF, context-dependent
            "|": TokenType.BITWISE_OR,
            "^": TokenType.BITWISE_XOR,
            "~": TokenType.BITWISE_NOT,
            "!": TokenType.LOGICAL_NOT,
            ";": TokenType.TERMINATOR,
            ":": TokenType.COLON,
            ",": TokenType.COMMA,
            ".": TokenType.DOT,
            "(": TokenType.LEFT_PAREN,
            ")": TokenType.RIGHT_PAREN,
            "[": TokenType.LEFT_BRACKET,
            "]": TokenType.RIGHT_BRACKET,
            "{": TokenType.LEFT_BRACE,
            "}": TokenType.RIGHT_BRACE,
        }

        if char in operators:
            self._add_token(operators[char], char)
            self.advance()
            return True

        return False

    def _try_generic_type(self) -> bool:
        """Try to tokenize a generic type ($T, $TYPE, $MY_TYPE) or generic type argument ($i32, $string, etc.)."""
        if self.current_char() != "$":
            return False

        # Look ahead to check if it's followed by valid generic pattern
        saved_pos = self.position
        saved_line = self.line
        saved_column = self.column

        self.advance()  # consume '$'

        # Check if character after '$' is valid (must be a letter)
        if not (self.current_char() and self.current_char().isalpha()):
            # Create error for invalid generic syntax
            if self.current_char():
                raise TokenizerError.from_type_and_location(
                    TokenizerErrorType.INVALID_GENERIC_SYNTAX,
                    self.line,
                    saved_column,
                    self.position - saved_pos + 1,
                    self.filename,
                    self.source_lines,
                    f"Invalid generic syntax: generic types must start with a letter after '$'",
                )
            else:
                raise TokenizerError.from_type_and_location(
                    TokenizerErrorType.INVALID_GENERIC_SYNTAX,
                    self.line,
                    saved_column,
                    1,
                    self.filename,
                    self.source_lines,
                    f"Invalid generic syntax: '$' cannot be used alone",
                )
            return True

        # Collect the type name
        start_pos = self.position - 1  # Include the '$'
        type_name = "$"

        # For generic types: letters, digits, and underscores allowed ($T, $T1, $TYPE, $MY_TYPE)
        while self.current_char() and (
            self.current_char().isalnum() or self.current_char() == "_"
        ):
            type_name += self.current_char()
            self.advance()

        # Always create generic token, let parser validate the pattern
        if len(type_name) > 1:
            self._add_token(TokenType.GENERIC_TYPE, type_name)
            return True

        # Should not reach here due to earlier checks, but handle as fallback
        self.position = saved_pos
        self.line = saved_line
        self.column = saved_column
        return False
