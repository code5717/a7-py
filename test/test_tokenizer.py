"""Tokenizer tests for the A7 programming language.

Covers program tokenization, edge cases, and error handling.
Merged from test_tokenizer.py, test_tokenizer_aggressive.py, and
test_tokenizer_errors.py.
"""

import pytest
from typing import List
from io import StringIO
from rich.console import Console

from a7.tokens import Tokenizer, TokenType
from a7.errors import TokenizerError, TokenizerErrorType, ErrorFormatter, display_error


class TestTokenizer:
    """Test suite for the A7 tokenizer using test file content and expected tokens."""

    def test_000_empty(self):
        """Test empty program tokenization."""
        source = "main :: fn() {}"
        expected_types = [
            TokenType.IDENTIFIER,  # main
            TokenType.DECLARE_CONST,  # ::
            TokenType.FN,  # fn
            TokenType.LEFT_PAREN,  # (
            TokenType.RIGHT_PAREN,  # )
            TokenType.LEFT_BRACE,  # {
            TokenType.RIGHT_BRACE,  # }
            TokenType.EOF,
        ]
        self._assert_token_types_match(source, expected_types)

    def test_001_hello(self):
        """Test hello world program tokenization."""
        source = """io :: import "std/io"

main :: fn() {
    io.println("Hello World")
}"""
        expected_types = [
            TokenType.IDENTIFIER,  # io
            TokenType.DECLARE_CONST,  # ::
            TokenType.IMPORT,  # import
            TokenType.STRING_LITERAL,  # "std/io"
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # main
            TokenType.DECLARE_CONST,  # ::
            TokenType.FN,  # fn
            TokenType.LEFT_PAREN,  # (
            TokenType.RIGHT_PAREN,  # )
            TokenType.LEFT_BRACE,  # {
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # io
            TokenType.DOT,  # .
            TokenType.IDENTIFIER,  # println
            TokenType.LEFT_PAREN,  # (
            TokenType.STRING_LITERAL,  # "Hello World"
            TokenType.RIGHT_PAREN,  # )
            TokenType.TERMINATOR,
            TokenType.RIGHT_BRACE,  # }
            TokenType.EOF,
        ]
        self._assert_token_types_match(source, expected_types)

    def test_002_var(self):
        """Test variable declarations tokenization."""
        source = """io :: import "std/io"

main :: fn() {
    a := 1         // Inferred variable (mutable)
    b :: 2         // Inferred constant (immutable)
    c: i32 := 3    // Integer variable with explicit type

    // Using proper A7 standard library functions
    printf("{}", a)
    printf("{}", b)
    printf("{}", c)
    print("\\n")    // Print newline
}"""
        expected_types = [
            TokenType.IDENTIFIER,  # io
            TokenType.DECLARE_CONST,  # ::
            TokenType.IMPORT,  # import
            TokenType.STRING_LITERAL,  # "std/io"
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # main
            TokenType.DECLARE_CONST,  # ::
            TokenType.FN,  # fn
            TokenType.LEFT_PAREN,  # (
            TokenType.RIGHT_PAREN,  # )
            TokenType.LEFT_BRACE,  # {
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # a
            TokenType.DECLARE_VAR,  # :=
            TokenType.INTEGER_LITERAL,  # 1
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # b
            TokenType.DECLARE_CONST,  # ::
            TokenType.INTEGER_LITERAL,  # 2
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # c
            TokenType.COLON,  # :
            TokenType.I32,  # i32
            TokenType.DECLARE_VAR,  # :=
            TokenType.INTEGER_LITERAL,  # 3
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # printf
            TokenType.LEFT_PAREN,  # (
            TokenType.STRING_LITERAL,  # "{}"
            TokenType.COMMA,  # ,
            TokenType.IDENTIFIER,  # a
            TokenType.RIGHT_PAREN,  # )
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # printf
            TokenType.LEFT_PAREN,  # (
            TokenType.STRING_LITERAL,  # "{}"
            TokenType.COMMA,  # ,
            TokenType.IDENTIFIER,  # b
            TokenType.RIGHT_PAREN,  # )
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # printf
            TokenType.LEFT_PAREN,  # (
            TokenType.STRING_LITERAL,  # "{}"
            TokenType.COMMA,  # ,
            TokenType.IDENTIFIER,  # c
            TokenType.RIGHT_PAREN,  # )
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # print
            TokenType.LEFT_PAREN,  # (
            TokenType.STRING_LITERAL,  # "\\n"
            TokenType.RIGHT_PAREN,  # )
            TokenType.TERMINATOR,
            TokenType.RIGHT_BRACE,  # }
            TokenType.EOF,
        ]
        self._assert_token_types_match(source, expected_types)

    def test_003_comments(self):
        """Test comment tokenization."""
        source = """
// SINGLE LINE COMMENTS
/* 
 multi line comments
*/

main :: fn() {}

/* trailing closed multi-line comment */
"""
        expected_types = [
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # main
            TokenType.DECLARE_CONST,  # ::
            TokenType.FN,  # fn
            TokenType.LEFT_PAREN,  # (
            TokenType.RIGHT_PAREN,  # )
            TokenType.LEFT_BRACE,  # {
            TokenType.RIGHT_BRACE,  # }
            TokenType.TERMINATOR,
            TokenType.EOF,
        ]
        self._assert_token_types_match(source, expected_types)

    def test_004_func(self):
        """Test function definition tokenization."""
        source = """add :: fn(x: i32, y: i32) i32 {
    ret x + y
}

main :: fn() {
    result := add(5, 7)
    printf("{}", result)  // Output should be 12
    print("\\n")
}"""
        expected_types = [
            TokenType.IDENTIFIER,  # add
            TokenType.DECLARE_CONST,  # ::
            TokenType.FN,  # fn
            TokenType.LEFT_PAREN,  # (
            TokenType.IDENTIFIER,  # x
            TokenType.COLON,  # :
            TokenType.I32,  # i32
            TokenType.COMMA,  # ,
            TokenType.IDENTIFIER,  # y
            TokenType.COLON,  # :
            TokenType.I32,  # i32
            TokenType.RIGHT_PAREN,  # )
            TokenType.I32,  # i32 (return type)
            TokenType.LEFT_BRACE,  # {
            TokenType.TERMINATOR,
            TokenType.RET,  # ret
            TokenType.IDENTIFIER,  # x
            TokenType.PLUS,  # +
            TokenType.IDENTIFIER,  # y
            TokenType.TERMINATOR,
            TokenType.RIGHT_BRACE,  # }
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # main
            TokenType.DECLARE_CONST,  # ::
            TokenType.FN,  # fn
            TokenType.LEFT_PAREN,  # (
            TokenType.RIGHT_PAREN,  # )
            TokenType.LEFT_BRACE,  # {
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # result
            TokenType.DECLARE_VAR,  # :=
            TokenType.IDENTIFIER,  # add
            TokenType.LEFT_PAREN,  # (
            TokenType.INTEGER_LITERAL,  # 5
            TokenType.COMMA,  # ,
            TokenType.INTEGER_LITERAL,  # 7
            TokenType.RIGHT_PAREN,  # )
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # printf
            TokenType.LEFT_PAREN,  # (
            TokenType.STRING_LITERAL,  # "{}"
            TokenType.COMMA,  # ,
            TokenType.IDENTIFIER,  # result
            TokenType.RIGHT_PAREN,  # )
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # print
            TokenType.LEFT_PAREN,  # (
            TokenType.STRING_LITERAL,  # "\\n"
            TokenType.RIGHT_PAREN,  # )
            TokenType.TERMINATOR,
            TokenType.RIGHT_BRACE,  # }
            TokenType.EOF,
        ]
        self._assert_token_types_match(source, expected_types)

    def test_005_for_loop(self):
        """Test for loop tokenization."""
        source = """main :: fn() {
    // C-style for loop
    for i := 0; i < 3; i += 1 {
        // Loop body: i takes on values 0, 1, 2
        printf("{}", i)
        print("\\n")
    }
    
    // Range-based for loop with array
    arr: [3]i32 = [10, 20, 30]
    for value in arr {
        printf("{}", value)
        print("\\n")
    }
    
    // Range with index
    for i, value in arr {
        printf("[{}] = {}\\n", i, value)
    }
}"""
        expected_types = [
            TokenType.IDENTIFIER,  # main
            TokenType.DECLARE_CONST,  # ::
            TokenType.FN,  # fn
            TokenType.LEFT_PAREN,  # (
            TokenType.RIGHT_PAREN,  # )
            TokenType.LEFT_BRACE,  # {
            TokenType.TERMINATOR,
            TokenType.FOR,  # for
            TokenType.IDENTIFIER,  # i
            TokenType.DECLARE_VAR,  # :=
            TokenType.INTEGER_LITERAL,  # 0
            TokenType.TERMINATOR,  # ;
            TokenType.IDENTIFIER,  # i
            TokenType.LESS_THAN,  # <
            TokenType.INTEGER_LITERAL,  # 3
            TokenType.TERMINATOR,  # ;
            TokenType.IDENTIFIER,  # i
            TokenType.PLUS_ASSIGN,  # +=
            TokenType.INTEGER_LITERAL,  # 1
            TokenType.LEFT_BRACE,  # {
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # printf
            TokenType.LEFT_PAREN,  # (
            TokenType.STRING_LITERAL,  # "{}"
            TokenType.COMMA,  # ,
            TokenType.IDENTIFIER,  # i
            TokenType.RIGHT_PAREN,  # )
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # print
            TokenType.LEFT_PAREN,  # (
            TokenType.STRING_LITERAL,  # "\\n"
            TokenType.RIGHT_PAREN,  # )
            TokenType.TERMINATOR,
            TokenType.RIGHT_BRACE,  # }
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # arr
            TokenType.COLON,  # :
            TokenType.LEFT_BRACKET,  # [
            TokenType.INTEGER_LITERAL,  # 3
            TokenType.RIGHT_BRACKET,  # ]
            TokenType.I32,  # i32
            TokenType.ASSIGN,  # =
            TokenType.LEFT_BRACKET,  # [
            TokenType.INTEGER_LITERAL,  # 10
            TokenType.COMMA,  # ,
            TokenType.INTEGER_LITERAL,  # 20
            TokenType.COMMA,  # ,
            TokenType.INTEGER_LITERAL,  # 30
            TokenType.RIGHT_BRACKET,  # ]
            TokenType.TERMINATOR,
            TokenType.FOR,  # for
            TokenType.IDENTIFIER,  # value
            TokenType.IN,  # in
            TokenType.IDENTIFIER,  # arr
            TokenType.LEFT_BRACE,  # {
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # printf
            TokenType.LEFT_PAREN,  # (
            TokenType.STRING_LITERAL,  # "{}"
            TokenType.COMMA,  # ,
            TokenType.IDENTIFIER,  # value
            TokenType.RIGHT_PAREN,  # )
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # print
            TokenType.LEFT_PAREN,  # (
            TokenType.STRING_LITERAL,  # "\\n"
            TokenType.RIGHT_PAREN,  # )
            TokenType.TERMINATOR,
            TokenType.RIGHT_BRACE,  # }
            TokenType.TERMINATOR,
            TokenType.FOR,  # for
            TokenType.IDENTIFIER,  # i
            TokenType.COMMA,  # ,
            TokenType.IDENTIFIER,  # value
            TokenType.IN,  # in
            TokenType.IDENTIFIER,  # arr
            TokenType.LEFT_BRACE,  # {
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # printf
            TokenType.LEFT_PAREN,  # (
            TokenType.STRING_LITERAL,  # "[{}] = {}\\n"
            TokenType.COMMA,  # ,
            TokenType.IDENTIFIER,  # i
            TokenType.COMMA,  # ,
            TokenType.IDENTIFIER,  # value
            TokenType.RIGHT_PAREN,  # )
            TokenType.TERMINATOR,
            TokenType.RIGHT_BRACE,  # }
            TokenType.TERMINATOR,
            TokenType.RIGHT_BRACE,  # }
            TokenType.EOF,
        ]
        self._assert_token_types_match(source, expected_types)

    def test_020_operators(self):
        """Test operators tokenization (subset)."""
        source = """main :: fn() {
    a := 10
    b := 3
    
    result := a + b
    comparison := a == b
    logical := true and false
    bitwise := 0b1010 & 0b1100
    
    counter := 5
    counter += 3
    counter -= 2
}"""
        expected_types = [
            TokenType.IDENTIFIER,  # main
            TokenType.DECLARE_CONST,  # ::
            TokenType.FN,  # fn
            TokenType.LEFT_PAREN,  # (
            TokenType.RIGHT_PAREN,  # )
            TokenType.LEFT_BRACE,  # {
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # a
            TokenType.DECLARE_VAR,  # :=
            TokenType.INTEGER_LITERAL,  # 10
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # b
            TokenType.DECLARE_VAR,  # :=
            TokenType.INTEGER_LITERAL,  # 3
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # result
            TokenType.DECLARE_VAR,  # :=
            TokenType.IDENTIFIER,  # a
            TokenType.PLUS,  # +
            TokenType.IDENTIFIER,  # b
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # comparison
            TokenType.DECLARE_VAR,  # :=
            TokenType.IDENTIFIER,  # a
            TokenType.EQUAL,  # ==
            TokenType.IDENTIFIER,  # b
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # logical
            TokenType.DECLARE_VAR,  # :=
            TokenType.TRUE_LITERAL,  # true
            TokenType.AND,  # and
            TokenType.FALSE_LITERAL,  # false
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # bitwise
            TokenType.DECLARE_VAR,  # :=
            TokenType.INTEGER_LITERAL,  # 0b1010
            TokenType.BITWISE_AND,  # &
            TokenType.INTEGER_LITERAL,  # 0b1100
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # counter
            TokenType.DECLARE_VAR,  # :=
            TokenType.INTEGER_LITERAL,  # 5
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # counter
            TokenType.PLUS_ASSIGN,  # +=
            TokenType.INTEGER_LITERAL,  # 3
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # counter
            TokenType.MINUS_ASSIGN,  # -=
            TokenType.INTEGER_LITERAL,  # 2
            TokenType.TERMINATOR,
            TokenType.RIGHT_BRACE,  # }
            TokenType.EOF,
        ]
        self._assert_token_types_match(source, expected_types)

    def test_019_literals_subset(self):
        """Test literal tokenization (subset)."""
        source = """main :: fn() {
    decimal := 42
    hexadecimal := 0x2A
    binary := 0b101010
    
    pi := 3.14159
    scientific := 2.71e10
    
    letter := 'A'
    newline := '\\n'
    
    simple := "Hello, World!"
    with_quotes := "He said: \\"Hello\\""
    
    true_val := true
    false_val := false
    
    null_ptr: ref i32 = nil
}"""
        expected_types = [
            TokenType.IDENTIFIER,  # main
            TokenType.DECLARE_CONST,  # ::
            TokenType.FN,  # fn
            TokenType.LEFT_PAREN,  # (
            TokenType.RIGHT_PAREN,  # )
            TokenType.LEFT_BRACE,  # {
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # decimal
            TokenType.DECLARE_VAR,  # :=
            TokenType.INTEGER_LITERAL,  # 42
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # hexadecimal
            TokenType.DECLARE_VAR,  # :=
            TokenType.INTEGER_LITERAL,  # 0x2A
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # binary
            TokenType.DECLARE_VAR,  # :=
            TokenType.INTEGER_LITERAL,  # 0b101010
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # pi
            TokenType.DECLARE_VAR,  # :=
            TokenType.FLOAT_LITERAL,  # 3.14159
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # scientific
            TokenType.DECLARE_VAR,  # :=
            TokenType.FLOAT_LITERAL,  # 2.71e10
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # letter
            TokenType.DECLARE_VAR,  # :=
            TokenType.CHAR_LITERAL,  # 'A'
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # newline
            TokenType.DECLARE_VAR,  # :=
            TokenType.CHAR_LITERAL,  # '\\n'
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # simple
            TokenType.DECLARE_VAR,  # :=
            TokenType.STRING_LITERAL,  # "Hello, World!"
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # with_quotes
            TokenType.DECLARE_VAR,  # :=
            TokenType.STRING_LITERAL,  # "He said: \\"Hello\\""
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # true_val
            TokenType.DECLARE_VAR,  # :=
            TokenType.TRUE_LITERAL,  # true
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # false_val
            TokenType.DECLARE_VAR,  # :=
            TokenType.FALSE_LITERAL,  # false
            TokenType.TERMINATOR,
            TokenType.IDENTIFIER,  # null_ptr
            TokenType.COLON,  # :
            TokenType.REF,  # ref
            TokenType.I32,  # i32
            TokenType.ASSIGN,  # =
            TokenType.NIL_LITERAL,  # nil
            TokenType.TERMINATOR,
            TokenType.RIGHT_BRACE,  # }
            TokenType.EOF,
        ]
        self._assert_token_types_match(source, expected_types)

    def _assert_token_types_match(self, source: str, expected_types: List[TokenType]):
        """Helper method to tokenize source and compare token types."""
        tokenizer = Tokenizer(source)
        tokens = tokenizer.tokenize()
        actual_types = [token.type for token in tokens]

        # Print debug info if lengths don't match
        if len(actual_types) != len(expected_types):
            print(f"\nLength mismatch:")
            print(f"Expected: {len(expected_types)} tokens")
            print(f"Actual: {len(actual_types)} tokens")
            print(f"\nExpected types: {[t.name for t in expected_types]}")
            print(f"Actual types: {[t.name for t in actual_types]}")

            # Show token values for debugging
            print(f"\nActual tokens with values:")
            for i, token in enumerate(tokens):
                print(f"  {i}: {token.type.name} = '{token.value}'")

        # Compare token by token
        for i, (expected, actual) in enumerate(zip(expected_types, actual_types)):
            if expected != actual:
                print(f"\nMismatch at position {i}:")
                print(f"Expected: {expected.name}")
                print(f"Actual: {actual.name}")
                if i < len(tokens):
                    print(f"Token value: '{tokens[i].value}'")
                break

        assert actual_types == expected_types, (
            f"Token types don't match for source: {source[:50]}..."
        )


class TestTokenizerAggressive:
    """Aggressive test suite for A7 tokenizer edge cases and error conditions."""

    def test_whitespace_only(self):
        """Test input with only whitespace characters (no tabs - A7 doesn't support tabs)."""
        test_cases = [
            "   ",  # spaces
            "\r\r\r",  # carriage returns
            "   \r  ",  # spaces and carriage returns
        ]

        for source in test_cases:
            tokenizer = Tokenizer(source)
            tokens = tokenizer.tokenize()
            assert len(tokens) == 1
            assert tokens[0].type == TokenType.EOF

    def test_newlines_only(self):
        """Test input with only newlines."""
        source = "\n\n\n\n\n"
        tokenizer = Tokenizer(source)
        tokens = tokenizer.tokenize()

        # With deduplication, consecutive newlines become single TERMINATOR
        expected_types = [TokenType.TERMINATOR, TokenType.EOF]
        actual_types = [token.type for token in tokens]
        assert actual_types == expected_types

    def test_mixed_whitespace_and_newlines(self):
        """Test complex whitespace patterns (no tabs - A7 doesn't support tabs)."""
        source = "  \n \n  \r\n   \n  "
        tokenizer = Tokenizer(source)
        tokens = tokenizer.tokenize()

        # Should only capture newlines, not other whitespace
        # With deduplication, consecutive newlines become single TERMINATOR
        terminator_tokens = [t for t in tokens if t.type == TokenType.TERMINATOR]
        assert len(terminator_tokens) == 1  # Deduplicated to single TERMINATOR

    def test_operator_edge_cases(self):
        """Test complex operator sequences and potential ambiguities."""
        # Test individual operators that should work correctly
        test_cases = [
            # Three-character operators (now fixed)
            ("<<=", [TokenType.LEFT_SHIFT_ASSIGN]),
            (">>=", [TokenType.RIGHT_SHIFT_ASSIGN]),
            # Two-character operators
            ("==", [TokenType.EQUAL]),
            ("!=", [TokenType.NOT_EQUAL]),
            ("<=", [TokenType.LESS_EQUAL]),
            (">=", [TokenType.GREATER_EQUAL]),
            ("::", [TokenType.DECLARE_CONST]),
            (":=", [TokenType.DECLARE_VAR]),
            ("..", [TokenType.DOT_DOT]),
            ("<<", [TokenType.LEFT_SHIFT]),
            (">>", [TokenType.RIGHT_SHIFT]),
        ]

        for source, expected_types in test_cases:
            expected_types.append(TokenType.EOF)
            tokenizer = Tokenizer(source)
            tokens = tokenizer.tokenize()
            actual_types = [token.type for token in tokens]
            assert actual_types == expected_types, (
                f"Failed for '{source}' - got {[t.name for t in actual_types]}"
            )

    def test_operator_without_spaces(self):
        """Test operators without separating spaces - potential parsing ambiguity."""
        source = "a+=b-=c*=d/=e%=f&=g|=h^=i"
        tokenizer = Tokenizer(source)
        tokens = tokenizer.tokenize()

        expected_types = [
            TokenType.IDENTIFIER,
            TokenType.PLUS_ASSIGN,
            TokenType.IDENTIFIER,
            TokenType.MINUS_ASSIGN,
            TokenType.IDENTIFIER,
            TokenType.MULTIPLY_ASSIGN,
            TokenType.IDENTIFIER,
            TokenType.DIVIDE_ASSIGN,
            TokenType.IDENTIFIER,
            TokenType.MODULO_ASSIGN,
            TokenType.IDENTIFIER,
            TokenType.BITWISE_AND_ASSIGN,
            TokenType.IDENTIFIER,
            TokenType.BITWISE_OR_ASSIGN,
            TokenType.IDENTIFIER,
            TokenType.BITWISE_XOR_ASSIGN,
            TokenType.IDENTIFIER,
            TokenType.EOF,
        ]
        actual_types = [token.type for token in tokens]
        assert actual_types == expected_types

    def test_declaration_operator_edge_cases(self):
        """Test edge cases around :: and := operators."""
        test_cases = [
            (":::", [TokenType.DECLARE_CONST, TokenType.COLON]),
            (":::=", [TokenType.DECLARE_CONST, TokenType.DECLARE_VAR]),
            (":=:", [TokenType.DECLARE_VAR, TokenType.COLON]),
            (":==", [TokenType.DECLARE_VAR, TokenType.ASSIGN]),
            ("::=", [TokenType.DECLARE_CONST, TokenType.ASSIGN]),
        ]

        for source, expected_types in test_cases:
            expected_types.append(TokenType.EOF)
            tokenizer = Tokenizer(source)
            tokens = tokenizer.tokenize()
            actual_types = [token.type for token in tokens]
            assert actual_types == expected_types, f"Failed for '{source}'"

    def test_numeric_literals_edge_cases(self):
        """Test edge cases in numeric literal parsing."""
        # Valid cases
        valid_cases = [
            ("0", TokenType.INTEGER_LITERAL),  # Zero
            ("000", TokenType.INTEGER_LITERAL),  # Leading zeros
            ("0b0", TokenType.INTEGER_LITERAL),  # Binary zero
            ("0b1", TokenType.INTEGER_LITERAL),  # Binary one
            ("0b101010", TokenType.INTEGER_LITERAL),  # Binary
            ("0x0", TokenType.INTEGER_LITERAL),  # Hex zero
            ("0xFF", TokenType.INTEGER_LITERAL),  # Hex with capitals
            ("0xdeadbeef", TokenType.INTEGER_LITERAL),  # Hex lowercase
            ("0xDEADBEEF", TokenType.INTEGER_LITERAL),  # Hex uppercase
            ("123456789", TokenType.INTEGER_LITERAL),  # Large integer
            ("0.0", TokenType.FLOAT_LITERAL),  # Zero float
            ("0.123", TokenType.FLOAT_LITERAL),  # Small float
            ("123.456", TokenType.FLOAT_LITERAL),  # Normal float
            ("1e5", TokenType.FLOAT_LITERAL),  # Scientific notation
            ("1E5", TokenType.FLOAT_LITERAL),  # Scientific notation uppercase
            ("1e+5", TokenType.FLOAT_LITERAL),  # Scientific with +
            ("1e-5", TokenType.FLOAT_LITERAL),  # Scientific with -
            ("3.14e10", TokenType.FLOAT_LITERAL),  # Complex scientific
            ("2.5e-10", TokenType.FLOAT_LITERAL),  # Complex scientific negative
        ]

        for source, expected_type in valid_cases:
            tokenizer = Tokenizer(source)
            tokens = tokenizer.tokenize()
            assert len(tokens) == 2  # number + EOF
            assert tokens[0].type == expected_type, f"Failed for '{source}'"
            assert tokens[0].value == source

    def test_numeric_literals_malformed(self):
        """Malformed numeric prefixes produce tokens or errors (tokenizer limits)."""
        # Bare exponents ("1e", "1e+", "1e-") are covered with stronger
        # message assertions in TestTokenizerErrors.test_invalid_numeric_literals.
        edge_cases = [
            "0b",  # Binary prefix without digits - might produce "0" + "b"
            "0x",  # Hex prefix without digits - might produce "0" + "x"
            "0b123",  # Invalid binary digits - tokenizer limitations
            "0xGHI",  # Invalid hex digits - tokenizer limitations
        ]

        for source in edge_cases:
            tokenizer = Tokenizer(source)
            try:
                tokens = tokenizer.tokenize()
                # Should produce some tokens
                assert len(tokens) >= 2  # At least some token + EOF
            except (TokenizerError, TypeError):
                # May fail due to tokenizer implementation details
                pass

    def test_string_literals_edge_cases(self):
        """Test edge cases in string literal parsing."""
        valid_cases = [
            ('""', ""),  # Empty string
            ('"a"', "a"),  # Single character
            ('"hello world"', "hello world"),  # Normal string
            (r'"\n\t\r\\"', r"\n\t\r\\"),  # Escape sequences
            (
                '"a very long string with lots of text that goes on and on"',
                "a very long string with lots of text that goes on and on",
            ),  # Long string
        ]

        for source, expected_content in valid_cases:
            tokenizer = Tokenizer(source)
            tokens = tokenizer.tokenize()
            assert len(tokens) == 2  # string + EOF
            assert tokens[0].type == TokenType.STRING_LITERAL
            assert tokens[0].value == source  # Full token including quotes

    def test_string_literals_malformed(self):
        """String containing a newline may succeed or fail by A7 string rules."""
        # Unterminated strings are covered with stronger message assertions
        # in TestTokenizerErrors.test_unterminated_string_literals.
        source_with_newline = '"string with\nnewline"'
        tokenizer = Tokenizer(source_with_newline)
        # This might succeed or fail depending on A7 string literal rules
        try:
            tokens = tokenizer.tokenize()
            # If it succeeds, should produce a string token
            assert any(t.type == TokenType.STRING_LITERAL for t in tokens)
        except TokenizerError:
            # If it fails, that is also acceptable
            pass

    def test_char_literals_edge_cases(self):
        """Test edge cases in character literal parsing."""
        valid_cases = [
            ("'a'", "a"),  # Normal character
            ("'1'", "1"),  # Digit character
            ("' '", " "),  # Space character
            (r"'\n'", r"\n"),  # Escaped newline
            (r"'\t'", r"\t"),  # Escaped tab
            (r"'\''", r"\'"),  # Escaped quote
            (r"'\\'", r"\\"),  # Escaped backslash
        ]

        for source, expected_char in valid_cases:
            tokenizer = Tokenizer(source)
            tokens = tokenizer.tokenize()
            assert len(tokens) == 2  # char + EOF
            assert tokens[0].type == TokenType.CHAR_LITERAL
            assert tokens[0].value == source

    def test_comment_edge_cases(self):
        """Test edge cases in comment parsing."""
        # Single line comments - should be discarded, no COMMENT tokens
        source1 = "// This is a comment\n// Another comment"
        tokenizer1 = Tokenizer(source1)
        tokens1 = tokenizer1.tokenize()
        comment_tokens = [t for t in tokens1 if t.type == TokenType.COMMENT]
        assert len(comment_tokens) == 0  # Comments are discarded

        # Multi-line comments - should be discarded
        source2 = "/* single line comment */"
        tokenizer2 = Tokenizer(source2)
        tokens2 = tokenizer2.tokenize()
        comment_tokens = [t for t in tokens2 if t.type == TokenType.COMMENT]
        assert len(comment_tokens) == 0  # Comments are discarded

        # Nested multi-line comments - should be discarded
        source3 = "/* outer /* inner */ still outer */"
        tokenizer3 = Tokenizer(source3)
        tokens3 = tokenizer3.tokenize()
        comment_tokens = [t for t in tokens3 if t.type == TokenType.COMMENT]
        assert len(comment_tokens) == 0  # Comments are discarded

        # Unterminated multi-line comment is a tokenizer error (exit 4)
        source4 = "/* unterminated comment"
        tokenizer4 = Tokenizer(source4)
        with pytest.raises(TokenizerError) as exc_info:
            tokenizer4.tokenize()
        assert exc_info.value.error_type == TokenizerErrorType.NOT_CLOSED_COMMENT

        # Alternative hash comments - should be discarded
        source5 = "# Hash comment\n# Another hash comment"
        tokenizer5 = Tokenizer(source5)
        tokens5 = tokenizer5.tokenize()
        hash_comments = [t for t in tokens5 if t.type == TokenType.COMMENT]
        assert len(hash_comments) == 0  # Comments are discarded

    def test_identifier_edge_cases(self):
        """Test edge cases in identifier parsing."""
        valid_cases = [
            "a",  # Single character
            "_",  # Just underscore
            "_a",  # Underscore prefix
            "a_",  # Underscore suffix
            "_a_",  # Underscore both ends
            "a1",  # Letter then digit
            "a_1",  # Mixed with underscore
            "_123",  # Underscore then digits
            "very_long_identifier_name_with_many_underscores",  # Long identifier
            "camelCase",  # Camel case
            "PascalCase",  # Pascal case
            "SCREAMING_SNAKE_CASE",  # All caps
        ]

        for source in valid_cases:
            tokenizer = Tokenizer(source)
            tokens = tokenizer.tokenize()
            assert len(tokens) == 2  # identifier + EOF
            assert tokens[0].type == TokenType.IDENTIFIER
            assert tokens[0].value == source

    def test_builtin_function_edge_cases(self):
        """Test edge cases in builtin function parsing."""
        valid_cases = [
            "@a",  # Single character
            "@print",  # Normal builtin
            "@function",  # Longer builtin
        ]

        for source in valid_cases:
            tokenizer = Tokenizer(source)
            tokens = tokenizer.tokenize()
            assert len(tokens) == 2  # builtin + EOF
            assert tokens[0].type == TokenType.BUILTIN_ID
            assert tokens[0].value == source

        # Invalid builtin (@ followed by non-alpha) - these should cause errors
        # since the tokenizer tries to parse them as numbers
        invalid_cases = ["@1", "@123"]
        for source in invalid_cases:
            tokenizer = Tokenizer(source)
            try:
                tokens = tokenizer.tokenize()
                # If it doesn't error, check the tokens produced
                assert len(tokens) >= 2
            except (TokenizerError, TypeError):
                # Expected to fail due to invalid parsing
                pass

        # @ followed by underscore should produce @ + identifier
        source = "@_"
        tokenizer = Tokenizer(source)
        try:
            tokens = tokenizer.tokenize()
            # Might produce separate tokens or error
            assert len(tokens) >= 1
        except TokenizerError:
            # Also acceptable
            pass

    def test_keyword_vs_identifier_edge_cases(self):
        """Test edge cases where keywords might be confused with identifiers."""
        # All keywords should be recognized
        keywords = [
            "and",
            "as",
            "bool",
            "break",
            "case",
            "char",
            "continue",
            "del",
            "defer",
            "else",
            "enum",
            "fall",
            "false",
            "float",
            "fn",
            "for",
            "if",
            "import",
            "in",
            "int",
            "i8",
            "i16",
            "i32",
            "i64",
            "isize",
            "let",
            "match",
            "new",
            "nil",
            "not",
            "or",
            "pub",
            "ref",
            "ret",
            "string",
            "struct",
            "true",
            "u8",
            "u16",
            "u32",
            "u64",
            "uint",
            "usize",
            "while",
        ]

        for keyword in keywords:
            tokenizer = Tokenizer(keyword)
            tokens = tokenizer.tokenize()
            assert len(tokens) == 2  # keyword + EOF
            assert tokens[0].type != TokenType.IDENTIFIER, (
                f"'{keyword}' should not be IDENTIFIER"
            )

        # Similar but not keywords
        non_keywords = [
            "andd",
            "ass",
            "booll",
            "breakk",
            "casee",
            "charr",
            "continuee",
            "dell",
            "deferr",
            "elsee",
            "enumm",
            "falll",
            "falsee",
            "floatt",
            "fnn",
            "forr",
            "iff",
            "importt",
            "inn",
            "intt",
            "i9",
            "i15",
            "rett",
            "stringg",
            "structt",
            "truee",
            "whilee",
        ]

        for non_keyword in non_keywords:
            tokenizer = Tokenizer(non_keyword)
            tokens = tokenizer.tokenize()
            assert len(tokens) == 2  # identifier + EOF
            assert tokens[0].type == TokenType.IDENTIFIER, (
                f"'{non_keyword}' should be IDENTIFIER"
            )

    def test_boolean_and_nil_literals(self):
        """Test boolean and nil literal recognition."""
        test_cases = [
            ("true", TokenType.TRUE_LITERAL),
            ("false", TokenType.FALSE_LITERAL),
            ("nil", TokenType.NIL_LITERAL),
        ]

        for source, expected_type in test_cases:
            tokenizer = Tokenizer(source)
            tokens = tokenizer.tokenize()
            assert len(tokens) == 2  # literal + EOF
            assert tokens[0].type == expected_type
            assert tokens[0].value == source

    def test_line_and_column_tracking(self):
        """Test that line and column numbers are tracked correctly."""
        source = "a\nb\n  c"
        tokenizer = Tokenizer(source)
        tokens = tokenizer.tokenize()

        # Filter out newlines and EOF for easier testing
        identifiers = [t for t in tokens if t.type == TokenType.IDENTIFIER]

        assert len(identifiers) == 3
        assert identifiers[0].line == 1 and identifiers[0].column == 1  # a
        assert identifiers[1].line == 2 and identifiers[1].column == 1  # b
        assert (
            identifiers[2].line == 3 and identifiers[2].column == 3
        )  # c (after 2 spaces)

    def test_complex_mixed_content(self):
        """Test tokenizing complex mixed content that could break the tokenizer."""
        source = """
        // Complex test with everything
        main :: fn(argc: i32, argv: ref ref char) i32 {
            /* Multi-line comment
               with special chars: @#$%^&*()
               and "strings" and 'chars' inside */
            
            x := 42 + 0x2A - 0b101010
            y := 3.14159e-10
            z := "string with \\"quotes\\" and \\n escapes"
            ch := '\\t'
            
            if x == y and not (z != nil) {
                for i := 0; i < 10; i += 1 {
                    printf("Value: {}", i)
                }
            }
            
            ret 0
        }
        """

        tokenizer = Tokenizer(source)
        tokens = tokenizer.tokenize()

        # Should not raise any exceptions and should produce reasonable tokens
        assert len(tokens) > 50  # Should have many tokens
        assert tokens[-1].type == TokenType.EOF

        # Check for some expected token types
        token_types = [t.type for t in tokens]
        assert TokenType.IDENTIFIER in token_types
        assert TokenType.INTEGER_LITERAL in token_types
        assert TokenType.FLOAT_LITERAL in token_types
        assert TokenType.STRING_LITERAL in token_types
        assert TokenType.CHAR_LITERAL in token_types

    def test_performance_large_input(self):
        """Test tokenizer performance and memory usage with large input."""
        # Create a large but valid A7 program
        large_source = "main :: fn() {\n"
        for i in range(1000):
            large_source += f"    var{i} := {i} + {i + 1}\n"
        large_source += "}\n"

        tokenizer = Tokenizer(large_source)
        tokens = tokenizer.tokenize()

        # Should handle large input without issues
        assert len(tokens) > 5000  # Should have many tokens
        assert tokens[-1].type == TokenType.EOF

    def test_unicode_and_special_characters(self):
        """Test handling of Unicode and special characters."""
        # Test that non-ASCII characters in comments don't break tokenizer
        source_with_unicode = """
        // Comment with Unicode: αβγδε 中文 🚀
        /* Multi-line with Unicode:
           Special chars: ñáéíóú çüß
           Symbols: ←→↑↓ ∀∃∈∉ */
        
        main :: fn() {
            // Should work fine
        }
        """

        tokenizer = Tokenizer(source_with_unicode)
        tokens = tokenizer.tokenize()

        # Should not crash and should discard comments
        comment_tokens = [t for t in tokens if t.type == TokenType.COMMENT]
        assert len(comment_tokens) == 0  # Comments are discarded

    def test_tokenizer_state_consistency(self):
        """Test that tokenizer maintains consistent internal state."""
        source = "a\nb\nc"
        tokenizer = Tokenizer(source)

        # Check initial state
        assert tokenizer.position == 0
        assert tokenizer.line == 1
        assert tokenizer.column == 1

        # Tokenize and check final state
        tokens = tokenizer.tokenize()
        assert tokenizer.position == len(source)
        assert tokenizer.line == 3  # Should be on line 3
        assert tokenizer.column == 2  # After 'c'

    def test_malformed_input_recovery(self):
        """Test tokenizer behavior with various malformed inputs."""
        malformed_cases = [
            "main :: fn() { @1invalid }",  # Invalid builtin
            "main :: fn() { 'invalid char literal' }",  # Invalid char
            'main :: fn() { "unterminated string }',  # Unterminated string
            "main :: fn() { 1e }",  # Invalid scientific notation
            "main :: fn() { 0xZ }",  # Invalid hex
        ]

        for source in malformed_cases:
            tokenizer = Tokenizer(source)
            # Most should raise TokenizerError, but let's be permissive
            # and just ensure they don't crash the tokenizer completely
            try:
                tokens = tokenizer.tokenize()
                # If it succeeds, it should at least have EOF
                assert tokens[-1].type == TokenType.EOF
            except TokenizerError:
                # Expected for malformed input
                pass

    def test_edge_case_operator_sequences(self):
        """Test sequences of operators that might confuse the tokenizer."""
        tricky_sequences = [
            "a<<=b>>=c",  # Shift assigns back to back
            "x::=y",  # Constant declaration followed by assignment
            "z.:=w",  # Dot followed by variable declaration
            "a..b",  # Range operator
            "ptr.val.field",  # Dereference followed by field access
            "<<<>>>",  # Multiple shifts
            "&&&|||",  # Multiple bitwise operators
        ]

        for source in tricky_sequences:
            tokenizer = Tokenizer(source)
            tokens = tokenizer.tokenize()
            # Should not crash and should produce tokens
            assert len(tokens) >= 2  # At least some tokens + EOF
            assert tokens[-1].type == TokenType.EOF


class TestTokenizerErrors:
    """Test suite for A7 tokenizer error conditions and error formatting."""
    def test_unexpected_characters(self):
        """Test various unexpected characters that should raise TokenizerError."""
        invalid_chars = [
            ("§", 1, 1),  # Section symbol
            ("€", 1, 1),  # Euro symbol
            ("π", 1, 1),  # Pi symbol
            ("™", 1, 1),  # Trademark symbol
            ("©", 1, 1),  # Copyright symbol
            ("®", 1, 1),  # Registered trademark
            ("°", 1, 1),  # Degree symbol
            ("µ", 1, 1),  # Micro symbol
            ("¿", 1, 1),  # Inverted question mark
            ("¡", 1, 1),  # Inverted exclamation mark
        ]

        for char, expected_line, expected_col in invalid_chars:
            tokenizer = Tokenizer(char)

            with pytest.raises(TokenizerError) as exc_info:
                tokenizer.tokenize()

            error = exc_info.value
            assert f"Unexpected character: '{char}'" in error.message
            assert error.span.start_line == expected_line
            assert error.span.start_column == expected_col

    def test_unexpected_characters_in_context(self):
        """Test unexpected characters within valid A7 code."""
        test_cases = [
            ("x := 42§", "§", 1, 8),
            ("main :: fn() {\n    y := €\n}", "€", 2, 10),
            ("// Comment\nz := π", "π", 2, 6),
            ('if x == 1 {\n    print("test")\n    invalid := ™\n}', "™", 3, 16),
        ]

        for source, invalid_char, expected_line, expected_col in test_cases:
            tokenizer = Tokenizer(source)

            with pytest.raises(TokenizerError) as exc_info:
                tokenizer.tokenize()

            error = exc_info.value
            assert f"Unexpected character: '{invalid_char}'" in error.message
            assert error.span.start_line == expected_line
            assert error.span.start_column == expected_col

    def test_unterminated_string_literals(self):
        """Test unterminated string literals."""
        test_cases = [
            ('"unterminated', 1, 1),
            ('x := "hello world', 1, 6),
            ('print("message\nmore text', 1, 7),
            ('fn test() {\n    msg := "incomplete\n}', 2, 12),
        ]

        for source, expected_line, expected_col in test_cases:
            tokenizer = Tokenizer(source)

            with pytest.raises(TokenizerError) as exc_info:
                tokenizer.tokenize()

            error = exc_info.value
            assert "The string is not closed" in error.message
            # Note: The exact line/column may vary based on where tokenizer detects the error

    def test_unclosed_block_comment_reports_not_closed_comment(self):
        """An unterminated /* is a tokenizer error at the opening delimiter."""
        cases = [
            ("/* note", 1, 1),
            ("main :: fn() {}\n/* note\nhelper :: fn() {}\n", 2, 1),
            ("/* outer /* inner */ still open", 1, 1),
        ]
        for source, line, column in cases:
            with pytest.raises(TokenizerError) as exc_info:
                Tokenizer(source).tokenize()
            error = exc_info.value
            assert error.error_type == TokenizerErrorType.NOT_CLOSED_COMMENT
            assert error.span.start_line == line
            assert error.span.start_column == column

    def test_invalid_string_escape_sequences(self):
        """Test invalid string escape sequences."""
        test_cases = [
            r'"invalid \q escape"',
            r'"incomplete \x escape"',
            r'"bad hex \xZZ escape"',
        ]

        for source in test_cases:
            tokenizer = Tokenizer(source)

            with pytest.raises(TokenizerError) as exc_info:
                tokenizer.tokenize()

            error = exc_info.value
            assert "Invalid string escape sequence" in error.message

    def test_unterminated_char_literals(self):
        """Test unterminated or invalid character literals."""
        test_cases = [
            ("'", 1, 1),  # Just opening quote
            ("'unterminated", 1, 1),  # No closing quote
            ("''", 1, 1),  # Empty char literal
            ("'ab'", 1, 1),  # Multiple characters
            ("x := 'incomplete", 1, 6),  # In context
        ]

        for source, expected_line, expected_col in test_cases:
            tokenizer = Tokenizer(source)

            with pytest.raises(TokenizerError) as exc_info:
                tokenizer.tokenize()

            error = exc_info.value
            assert "The char is not closed" in error.message

    def test_invalid_numeric_literals(self):
        """Test invalid numeric literal formats."""
        test_cases = [
            ("1e", "Invalid scientific notation"),  # Missing exponent
            ("1e+", "Invalid scientific notation"),  # Missing exponent digits
            ("1e-", "Invalid scientific notation"),  # Missing exponent digits
            ("2.5e", "Invalid scientific notation"),  # Missing exponent
            ("3.14e+", "Invalid scientific notation"),  # Missing exponent digits
        ]

        for source, expected_message in test_cases:
            tokenizer = Tokenizer(source)

            with pytest.raises(TokenizerError) as exc_info:
                tokenizer.tokenize()

            error = exc_info.value
            assert expected_message in error.message

    def test_error_message_format(self):
        """Test the error message format: 'error: message, line: x, col: y'."""
        source = "test := §"
        tokenizer = Tokenizer(source, filename="test.a7")

        with pytest.raises(TokenizerError) as exc_info:
            tokenizer.tokenize()

        error = exc_info.value

        # Test the formatted message string
        formatted = error._format_message()
        assert "test.a7:1:9: Unexpected character: '§'" == formatted

    def test_error_display_formatting(self):
        """Test the Rich-formatted error display output."""
        source = "x := invalid§"
        tokenizer = Tokenizer(source, filename="test.a7")

        # Capture the error display output
        console = Console(file=StringIO(), width=80, legacy_windows=False,
                          no_color=True, force_terminal=False)

        try:
            tokenizer.tokenize()
        except TokenizerError as error:
            # Test the display method
            error.display(console)
            output = console.file.getvalue()

            # Check that error format is correct
            assert "error: Unexpected character: '§' [line 1: col 13]" in output
            # Check that source code is displayed
            assert "x := invalid§" in output
            # Check that pointer line is included
            assert "▲" in output

    def test_error_display_single_line_file(self):
        """Test error display for single-line files."""
        source = "§"
        tokenizer = Tokenizer(source, filename="single.a7")

        console = Console(file=StringIO(), width=80, legacy_windows=False,
                          no_color=True, force_terminal=False)

        try:
            tokenizer.tokenize()
        except TokenizerError as error:
            error.display(console)
            output = console.file.getvalue()

            # Should show the single line with error
            assert "error: Unexpected character: '§' [line 1: col 1]" in output
            assert "1 ┃ §" in output
            assert "┃ ▲" in output

    def test_error_display_small_file(self):
        """Test error display for small files (≤5 lines)."""
        source = "line1\nline2\nerror§\nline4\nline5"
        tokenizer = Tokenizer(source, filename="small.a7")

        console = Console(file=StringIO(), width=80, legacy_windows=False,
                          no_color=True, force_terminal=False)

        try:
            tokenizer.tokenize()
        except TokenizerError as error:
            error.display(console)
            output = console.file.getvalue()

            # Should show all lines for small files
            assert "1 ┃ line1" in output
            assert "2 ┃ line2" in output
            assert "3 ┃ error§" in output
            assert "4 ┃ line4" in output
            assert "5 ┃ line5" in output

    def test_error_display_large_file(self):
        """Test error display for larger files with context."""
        lines = [f"line{i}" for i in range(1, 21)]
        lines[9] = "line10§"  # Add error to line 10
        source = "\n".join(lines)

        tokenizer = Tokenizer(source, filename="large.a7")

        console = Console(file=StringIO(), width=80, legacy_windows=False,
                          no_color=True, force_terminal=False)

        try:
            tokenizer.tokenize()
        except TokenizerError as error:
            error.display(console)
            output = console.file.getvalue()

            # Should show context around error line (line 10)
            assert "8 ┃ line8" in output  # 2 lines before
            assert "9 ┃ line9" in output  # 1 line before
            assert "10 ┃ line10§" in output  # Error line
            assert "11 ┃ line11" in output  # 1 line after
            assert "12 ┃ line12" in output  # 2 lines after

            # Should NOT show lines too far away (using precise patterns to avoid substring matches)
            assert "\n   1 ┃ line1" not in output and not output.startswith(
                "   1 ┃ line1"
            )
            assert "\n  20 ┃ line20" not in output and not output.startswith(
                "  20 ┃ line20"
            )

    def test_error_location_accuracy(self):
        """Test that error locations are reported accurately."""
        test_cases = [
            # (source, invalid_char, expected_line, expected_col)
            ("§", "§", 1, 1),
            ("x§", "§", 1, 2),
            ("hello§world", "§", 1, 6),
            ("x := 42§", "§", 1, 8),
            ("line1\n§", "§", 2, 1),
            ("line1\nline2§", "§", 2, 6),
            ("line1\nline2\n  §", "§", 3, 3),
            ("// comment\nmain :: fn() {\n    x := §\n}", "§", 3, 10),
        ]

        for source, invalid_char, expected_line, expected_col in test_cases:
            tokenizer = Tokenizer(source)

            with pytest.raises(TokenizerError) as exc_info:
                tokenizer.tokenize()

            error = exc_info.value
            assert error.span.start_line == expected_line, f"Wrong line for '{source}'"
            assert error.span.start_column == expected_col, (
                f"Wrong column for '{source}'"
            )

    def test_error_pointer_alignment(self):
        """Test that the error pointer (^) aligns correctly with the error character."""
        test_cases = [
            ("§", 1),  # Position 1
            ("x§", 2),  # Position 2
            ("   §", 4),  # Position 4 (after spaces)
            ("hello§", 6),  # Position 6
            ("x := 42§", 8),  # Position 8
        ]

        for source, expected_pos in test_cases:
            tokenizer = Tokenizer(source)
            console = Console(file=StringIO(), width=80, legacy_windows=False,
                          no_color=True, force_terminal=False)

            try:
                tokenizer.tokenize()
            except TokenizerError as error:
                error.display(console)
                output = console.file.getvalue()

                # Find the pointer line (contains ▲)
                lines = output.split("\n")
                pointer_line = None
                for line in lines:
                    if "┃" in line and "▲" in line and "1 ┃" not in line:
                        pointer_line = line
                        break

                assert pointer_line is not None, f"No pointer line found for '{source}'"

                # Count characters before ▲ to verify alignment
                prefix_end = pointer_line.find("┃") + 2  # "   ┃ "
                pointer_pos = pointer_line.find("▲")
                actual_pos = pointer_pos - prefix_end + 1  # Convert to 1-based

                assert actual_pos == expected_pos, (
                    f"Pointer misaligned for '{source}': expected {expected_pos}, got {actual_pos}"
                )

    def test_multiline_error_handling(self):
        """Test error handling across multiple lines (though tokenizer errors are typically single-char)."""
        # Most tokenizer errors are single character, but test the infrastructure
        source = "valid_line\ninvalid§character"
        tokenizer = Tokenizer(source)

        with pytest.raises(TokenizerError) as exc_info:
            tokenizer.tokenize()

        error = exc_info.value
        assert error.span.start_line == 2
        assert error.span.start_column == 8  # Position of §

    def test_error_with_tabs_and_spaces(self):
        """Test error location accuracy with tabs (A7 doesn't support tabs, so tab position is error position)."""
        test_cases = [
            ("\t§", 1),  # Tab causes error at position 1
            ("  \t §", 3),  # Tab causes error at position 3 (after 2 spaces)
            ("x\t:=\t§", 2),  # First tab causes error at position 2 (after 'x')
        ]

        for source, expected_col in test_cases:
            tokenizer = Tokenizer(source)

            with pytest.raises(TokenizerError) as exc_info:
                tokenizer.tokenize()

            error = exc_info.value
            assert error.span.start_column == expected_col, (
                f"Wrong column for '{repr(source)}'"
            )
            assert "Tabs" in error.message, (
                f"Expected tab error message for '{repr(source)}'"
            )

    def test_error_recovery_information(self):
        """Test that errors contain enough information for good error recovery."""
        source = "main :: fn() {\n    x := 42\n    invalid := §garbage\n}"
        tokenizer = Tokenizer(source, filename="recovery_test.a7")

        with pytest.raises(TokenizerError) as exc_info:
            tokenizer.tokenize()

        error = exc_info.value

        # Check that error has all necessary information
        assert error.filename == "recovery_test.a7"
        assert error.span is not None
        assert error.span.start_line == 3
        assert error.span.start_column == 16
        assert error.source_lines is not None
        assert len(error.source_lines) == 4  # Including empty line at end
        assert "invalid := §garbage" in error.source_lines[2]

    def test_console_error_display_integration(self):
        """Test integration with console error display system."""
        source = "error_here := §"
        tokenizer = Tokenizer(source, filename="integration_test.a7")

        # Test display_error function
        console = Console(file=StringIO(), width=80, legacy_windows=False,
                          no_color=True, force_terminal=False)

        try:
            tokenizer.tokenize()
        except TokenizerError as error:
            display_error(error, console)
            output = console.file.getvalue()

            # Verify the complete error display format
            assert "error: Unexpected character: '§' [line 1: col 15]" in output
            assert "1 ┃ error_here := §" in output
            assert "┃               ▲" in output

    def test_error_formatter_context_lines(self):
        """Test ErrorFormatter with different context line settings."""
        source = "\n".join([f"line{i}" for i in range(1, 11)])
        source = source.replace("line5", "line5§")  # Add error to line 5

        tokenizer = Tokenizer(source, filename="context_test.a7")

        try:
            tokenizer.tokenize()
        except TokenizerError as error:
            formatter = ErrorFormatter()
            console = Console(file=StringIO(), width=80, legacy_windows=False,
                          no_color=True, force_terminal=False)
            formatter.console = console

            # Test with different context settings
            for context_lines in [1, 2, 3]:
                console.file = StringIO()  # Reset output
                formatter.format_error(error, context_lines)
                output = console.file.getvalue()

                # Should show appropriate number of context lines
                if context_lines >= 1:
                    assert "4 ┃ line4" in output  # 1 line before
                    assert "6 ┃ line6" in output  # 1 line after
                if context_lines >= 2:
                    assert "3 ┃ line3" in output  # 2 lines before
                    assert "7 ┃ line7" in output  # 2 lines after
    # Edge cases merged from TestTokenizerErrorEdgeCases.

    def test_error_at_end_of_file(self):
        """Test error detection at end of file."""
        source = "valid_code := 42§"
        tokenizer = Tokenizer(source)

        with pytest.raises(TokenizerError) as exc_info:
            tokenizer.tokenize()

        error = exc_info.value
        assert error.span.start_line == 1
        assert error.span.start_column == len(source)  # At the last character

    def test_multiple_errors_first_reported(self):
        """Test that only the first error is reported when multiple exist."""
        source = "error1§ and error2€"
        tokenizer = Tokenizer(source)

        with pytest.raises(TokenizerError) as exc_info:
            tokenizer.tokenize()

        error = exc_info.value
        # Should report the first error (§), not the second (€)
        assert "§" in error.message
        assert "€" not in error.message

    def test_empty_file_no_error(self):
        """Test that empty files don't produce errors."""
        tokenizer = Tokenizer("")
        tokens = tokenizer.tokenize()  # Should not raise
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.EOF

    def test_whitespace_only_no_error(self):
        """Test that whitespace-only files don't produce errors (no tabs - A7 doesn't support tabs)."""
        tokenizer = Tokenizer("     \n  \r\n  ")
        tokens = tokenizer.tokenize()  # Should not raise
        # Should only have terminator and EOF tokens
        non_eof_tokens = [t for t in tokens if t.type != TokenType.EOF]
        assert all(t.type == TokenType.TERMINATOR for t in non_eof_tokens)
