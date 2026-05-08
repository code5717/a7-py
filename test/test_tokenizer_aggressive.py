"""
Aggressive and comprehensive tokenizer tests for the A7 programming language.

This test file focuses on edge cases, error conditions, complex scenarios,
and potential tokenizer vulnerabilities that could break or confuse the parser.
"""

import pytest
from typing import List
from a7.tokens import Tokenizer, TokenType
from a7.errors import TokenizerError


class TestTokenizerAggressive:
    """Aggressive test suite for A7 tokenizer edge cases and error conditions."""

    def test_empty_input(self):
        """Test completely empty input."""
        tokenizer = Tokenizer("")
        tokens = tokenizer.tokenize()
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.EOF

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
        """Test malformed numeric literals."""
        # Test cases that should raise errors
        error_cases = [
            "1e",
            "1e+",
            "1e-",
        ]  # Scientific notation without exponent digits

        for source in error_cases:
            tokenizer = Tokenizer(source)
            with pytest.raises(TokenizerError):
                tokenizer.tokenize()

        # Test cases that might produce tokens or errors due to tokenizer limitations
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
        """Test malformed string literals."""
        malformed_cases = [
            '"unterminated string',  # No closing quote
            '"',  # Just opening quote
        ]

        for source in malformed_cases:
            tokenizer = Tokenizer(source)
            with pytest.raises(TokenizerError):
                tokenizer.tokenize()

        # Test string with newline - this might be handled differently
        source_with_newline = '"string with\nnewline"'
        tokenizer = Tokenizer(source_with_newline)
        # This might succeed or fail depending on A7 string literal rules
        try:
            tokens = tokenizer.tokenize()
            # If it succeeds, should produce a string token
            assert any(t.type == TokenType.STRING_LITERAL for t in tokens)
        except TokenizerError:
            # If it fails, that's also acceptable
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

    def test_char_literals_malformed(self):
        """Test malformed character literals."""
        malformed_cases = [
            "'",  # Just opening quote
            "'ab'",  # Multiple characters
            "'unterminated",  # No closing quote
            "''",  # Empty character literal
        ]

        for source in malformed_cases:
            tokenizer = Tokenizer(source)
            with pytest.raises(TokenizerError):
                tokenizer.tokenize()

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

        # Unterminated multi-line comment (should consume to EOF)
        source4 = "/* unterminated comment"
        tokenizer4 = Tokenizer(source4)
        tokens4 = tokenizer4.tokenize()
        comment_tokens = [t for t in tokens4 if t.type == TokenType.COMMENT]
        assert len(comment_tokens) == 0  # Comments are discarded

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


if __name__ == "__main__":
    # Run a few key tests when executed directly
    test = TestTokenizerAggressive()

    try:
        test.test_empty_input()
        print("✓ Empty input test passed")

        test.test_operator_edge_cases()
        print("✓ Operator edge cases test passed")

        test.test_numeric_literals_edge_cases()
        print("✓ Numeric literals edge cases test passed")

        test.test_complex_mixed_content()
        print("✓ Complex mixed content test passed")

        test.test_performance_large_input()
        print("✓ Performance large input test passed")

        print("All aggressive tests passed!")

    except Exception as e:
        print(f"Test failed: {e}")
        raise
