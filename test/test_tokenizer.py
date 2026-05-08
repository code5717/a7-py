"""
Comprehensive tokenizer tests for the A7 programming language.

This test file pairs each .a7 test file content with expected token types
and verifies the tokenizer produces the correct tokens.
"""

import pytest
from typing import List
from a7.tokens import Tokenizer, TokenType


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

/* multi line comments do not need to have an
 ending delimiter because EOF is enough for 
 as a comment delimiter
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


if __name__ == "__main__":
    # Run a simple test
    test = TestTokenizer()
    test.test_000_empty()
    print("✓ Empty program test passed")

    test.test_001_hello()
    print("✓ Hello world test passed")

    test.test_002_var()
    print("✓ Variable declarations test passed")

    print("All tests passed!")
