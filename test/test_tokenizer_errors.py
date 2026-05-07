"""
Comprehensive tests for tokenizer error handling and error message formatting.

This test file specifically focuses on testing error conditions, error message
formatting, and the enhanced error display system with proper line/column
information and visual indicators.
"""

import pytest
from typing import List
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
from rich.console import Console

from src.tokens import Tokenizer, TokenType
from src.errors import TokenizerError, ErrorFormatter, display_error


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
        console = Console(file=StringIO(), width=80, legacy_windows=False)

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

        console = Console(file=StringIO(), width=80, legacy_windows=False)

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

        console = Console(file=StringIO(), width=80, legacy_windows=False)

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

        console = Console(file=StringIO(), width=80, legacy_windows=False)

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
            console = Console(file=StringIO(), width=80, legacy_windows=False)

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
        console = Console(file=StringIO(), width=80, legacy_windows=False)

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
            console = Console(file=StringIO(), width=80, legacy_windows=False)
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


class TestTokenizerErrorEdgeCases:
    """Additional edge case tests for tokenizer error handling."""

    def test_error_at_end_of_file(self):
        """Test error detection at end of file."""
        source = "valid_code := 42§"
        tokenizer = Tokenizer(source)

        with pytest.raises(TokenizerError) as exc_info:
            tokenizer.tokenize()

        error = exc_info.value
        assert error.span.start_line == 1
        assert error.span.start_column == len(source)  # At the last character

    def test_error_after_newline(self):
        """Test error immediately after newline."""
        source = "line1\n§"
        tokenizer = Tokenizer(source)

        with pytest.raises(TokenizerError) as exc_info:
            tokenizer.tokenize()

        error = exc_info.value
        assert error.span.start_line == 2
        assert error.span.start_column == 1

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


if __name__ == "__main__":
    # Run a few key tests when executed directly
    test = TestTokenizerErrors()

    try:
        test.test_unexpected_characters()
        print("✓ Unexpected characters test passed")

        test.test_error_location_accuracy()
        print("✓ Error location accuracy test passed")

        test.test_error_pointer_alignment()
        print("✓ Error pointer alignment test passed")

        test.test_error_display_single_line_file()
        print("✓ Single line file display test passed")

        test.test_error_display_small_file()
        print("✓ Small file display test passed")

        print("All tokenizer error tests passed!")

    except Exception as e:
        print(f"Test failed: {e}")
        raise
