"""
Fuzzing and property-based tests for the A7 parser.
Uses random generation to find edge cases and ensure robustness.
"""

import pytest
import random
import string
import itertools
from typing import List, Optional
from a7.parser import Parser
from a7.tokens import Tokenizer, Token, TokenType
from a7.errors import ParseError, TokenizerError
from a7.ast_nodes import NodeKind


class RandomCodeGenerator:
    """Generate random but semi-valid A7 code for fuzzing."""

    def __init__(self, seed: Optional[int] = None):
        if seed:
            random.seed(seed)

    def random_identifier(self, length: Optional[int] = None) -> str:
        """Generate a random identifier."""
        if length is None:
            length = random.randint(1, 20)
        # First char must be letter or underscore
        first = random.choice(string.ascii_letters + "_")
        rest = "".join(
            random.choice(string.ascii_letters + string.digits + "_")
            for _ in range(length - 1)
        )
        return first + rest

    def random_number(self) -> str:
        """Generate a random number literal."""
        choice = random.choice(["int", "float", "hex", "binary", "octal"])

        if choice == "int":
            return str(random.randint(-1000000, 1000000))
        elif choice == "float":
            return f"{random.uniform(-1000, 1000):.6f}"
        elif choice == "hex":
            return f"0x{random.randint(0, 0xFFFF):x}"
        elif choice == "binary":
            return f"0b{random.randint(0, 255):b}"
        else:  # octal
            return f"0o{random.randint(0, 777):o}"

    def random_string(self) -> str:
        """Generate a random string literal."""
        length = random.randint(0, 50)
        chars = []
        for _ in range(length):
            if random.random() < 0.1:  # 10% chance of escape sequence
                chars.append(random.choice(["\\n", "\\t", "\\\"", "\\\\"]))
            else:
                # Printable ASCII characters
                chars.append(random.choice(string.printable.replace('"', '')))
        return f'"{""

.join(chars)}"'

    def random_type(self, depth: int = 0) -> str:
        """Generate a random type expression."""
        if depth > 3:  # Limit nesting depth
            return random.choice(["i32", "f64", "bool", "string"])

        choice = random.choice(["basic", "array", "ref", "generic"])

        if choice == "basic":
            return random.choice(
                ["i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64", "f32", "f64", "bool", "string"]
            )
        elif choice == "array":
            size = random.randint(1, 100)
            inner = self.random_type(depth + 1)
            return f"[{size}]{inner}"
        elif choice == "ref":
            inner = self.random_type(depth + 1)
            return f"ref {inner}"
        else:  # generic
            return f"${self.random_identifier(5).upper()}"

    def random_expression(self, depth: int = 0) -> str:
        """Generate a random expression."""
        if depth > 5:  # Limit nesting depth
            return random.choice([
                self.random_number(),
                self.random_identifier(),
                "true",
                "false",
                "nil",
                self.random_string(),
            ])

        choice = random.choice(["literal", "binary", "unary", "call", "field", "array", "paren"])

        if choice == "literal":
            return random.choice([
                self.random_number(),
                self.random_identifier(),
                "true",
                "false",
                "nil",
                self.random_string(),
            ])
        elif choice == "binary":
            left = self.random_expression(depth + 1)
            right = self.random_expression(depth + 1)
            op = random.choice(["+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">=", "and", "or"])
            return f"{left} {op} {right}"
        elif choice == "unary":
            expr = self.random_expression(depth + 1)
            op = random.choice(["-", "!"])
            return f"{op}{expr}"
        elif choice == "call":
            func = self.random_identifier()
            args = ", ".join(self.random_expression(depth + 1) for _ in range(random.randint(0, 3)))
            return f"{func}({args})"
        elif choice == "field":
            obj = self.random_identifier()
            field = random.choice([self.random_identifier(), "adr", "val"])
            return f"{obj}.{field}"
        elif choice == "array":
            elements = ", ".join(self.random_expression(depth + 1) for _ in range(random.randint(0, 5)))
            return f"[{elements}]"
        else:  # paren
            expr = self.random_expression(depth + 1)
            return f"({expr})"

    def random_statement(self, depth: int = 0) -> str:
        """Generate a random statement."""
        if depth > 3:
            # Simple statements at max depth
            return random.choice([
                f"{self.random_identifier()} := {self.random_expression()}",
                f"{self.random_identifier()} = {self.random_expression()}",
                "break",
                "continue",
                f"ret {self.random_expression()}",
            ])

        choice = random.choice(["assign", "if", "for", "while", "block", "match", "ret"])

        if choice == "assign":
            var = self.random_identifier()
            expr = self.random_expression()
            op = random.choice([":=", "=", "+=", "-=", "*=", "/="])
            return f"{var} {op} {expr}"
        elif choice == "if":
            cond = self.random_expression()
            then_stmt = self.random_statement(depth + 1)
            if random.random() < 0.5:
                else_stmt = self.random_statement(depth + 1)
                return f"if {cond} {{ {then_stmt} }} else {{ {else_stmt} }}"
            return f"if {cond} {{ {then_stmt} }}"
        elif choice == "for":
            var = self.random_identifier()
            return f"for {var} := 0; {var} < 10; {var} += 1 {{ {self.random_statement(depth + 1)} }}"
        elif choice == "while":
            cond = self.random_expression()
            body = self.random_statement(depth + 1)
            return f"while {cond} {{ {body} }}"
        elif choice == "block":
            stmts = "\n    ".join(self.random_statement(depth + 1) for _ in range(random.randint(1, 3)))
            return f"{{ {stmts} }}"
        elif choice == "match":
            expr = self.random_expression()
            cases = []
            for _ in range(random.randint(1, 3)):
                value = self.random_expression()
                body = self.random_statement(depth + 1)
                cases.append(f"case {value}: {{ {body} }}")
            return f"match {expr} {{ {' '.join(cases)} }}"
        else:  # ret
            return f"ret {self.random_expression()}"

    def random_declaration(self) -> str:
        """Generate a random top-level declaration."""
        choice = random.choice(["const", "var", "func", "struct", "enum"])

        name = self.random_identifier()

        if choice == "const":
            value = self.random_expression()
            return f"{name} :: {value}"
        elif choice == "var":
            value = self.random_expression()
            return f"{name} := {value}"
        elif choice == "func":
            params = ", ".join(
                f"{self.random_identifier()}: {self.random_type()}"
                for _ in range(random.randint(0, 3))
            )
            body = self.random_statement()
            return_type = "" if random.random() < 0.5 else f" {self.random_type()}"
            return f"{name} :: fn({params}){return_type} {{ {body} }}"
        elif choice == "struct":
            fields = "\n    ".join(
                f"{self.random_identifier()}: {self.random_type()}"
                for _ in range(random.randint(1, 5))
            )
            return f"{name} :: struct {{ {fields} }}"
        else:  # enum
            variants = ", ".join(self.random_identifier() for _ in range(random.randint(1, 5)))
            return f"{name} :: enum {{ {variants} }}"

    def generate_program(self, num_decls: int = 5) -> str:
        """Generate a complete random program."""
        decls = [self.random_declaration() for _ in range(num_decls)]
        return "\n\n".join(decls)


class TestFuzzing:
    """Fuzzing tests to find parser bugs."""

    def test_random_valid_programs(self):
        """Test parser with randomly generated valid-ish programs."""
        gen = RandomCodeGenerator()

        for i in range(100):  # Generate 100 random programs
            code = gen.generate_program(random.randint(1, 10))

            try:
                lexer = Tokenizer(code)
                tokens = lexer.tokenize()
                parser = Parser(tokens, code)
                ast = parser.parse()
                # If we get here, parsing succeeded
                assert ast is not None
                assert ast.kind == NodeKind.PROGRAM
            except (TokenizerError, ParseError):
                # These are expected for some random inputs
                pass
            except Exception as e:
                # Unexpected errors should not happen
                pytest.fail(f"Unexpected error on iteration {i}: {e}\nCode:\n{code}")

    def test_random_expressions(self):
        """Test parser with random expressions."""
        gen = RandomCodeGenerator()

        for i in range(200):  # Generate 200 random expressions
            expr = gen.random_expression()
            code = f"main :: fn() {{ x := {expr} }}"

            try:
                lexer = Tokenizer(code)
                tokens = lexer.tokenize()
                parser = Parser(tokens, code)
                ast = parser.parse()
                assert ast is not None
            except (TokenizerError, ParseError):
                pass  # Expected for some inputs
            except Exception as e:
                pytest.fail(f"Unexpected error on iteration {i}: {e}\nExpression: {expr}")

    def test_deeply_nested_random_structures(self):
        """Test with deeply nested randomly generated structures."""
        gen = RandomCodeGenerator()

        for depth in [10, 20, 30, 40, 50]:
            # Generate deeply nested parentheses
            expr = "42"
            for _ in range(depth):
                if random.random() < 0.5:
                    expr = f"({expr})"
                else:
                    expr = f"f({expr})"

            code = f"main :: fn() {{ x := {expr} }}"

            try:
                lexer = Tokenizer(code)
                tokens = lexer.tokenize()
                parser = Parser(tokens, code)
                ast = parser.parse()
                assert ast is not None
            except RecursionError:
                pytest.fail(f"Stack overflow at depth {depth}")
            except (TokenizerError, ParseError):
                pass  # Some combinations might be invalid


class TestPropertyBased:
    """Property-based tests that verify invariants."""

    def test_lexer_tokenize_detokenize(self):
        """Test that tokenization preserves information."""
        gen = RandomCodeGenerator()

        for _ in range(50):
            code = gen.generate_program(3)

            try:
                lexer = Tokenizer(code)
                tokens = lexer.tokenize()

                # Property: Number of tokens should be reasonable
                assert len(tokens) > 0
                assert len(tokens) < len(code) * 2  # Rough upper bound

                # Property: All tokens should have valid positions
                for token in tokens:
                    assert token.line >= 1
                    assert token.column >= 0
                    assert token.length > 0 or token.type == TokenType.EOF

            except (TokenizerError, ParseError):
                pass  # Expected for some inputs

    def test_parser_ast_invariants(self):
        """Test that AST maintains certain invariants."""
        gen = RandomCodeGenerator()

        for _ in range(50):
            code = gen.generate_program(3)

            try:
                lexer = Tokenizer(code)
                tokens = lexer.tokenize()
                parser = Parser(tokens, code)
                ast = parser.parse()

                # Property: Root should always be PROGRAM
                assert ast.kind == NodeKind.PROGRAM

                # Property: All nodes should have spans
                def check_spans(node):
                    if hasattr(node, "span"):
                        assert node.span is not None
                        assert node.span.start_line >= 1
                        assert node.span.start_column >= 0

                    # Recursively check children
                    if hasattr(node, "declarations") and node.declarations:
                        for decl in node.declarations:
                            check_spans(decl)
                    if hasattr(node, "body") and node.body:
                        check_spans(node.body)
                    if hasattr(node, "statements") and node.statements:
                        for stmt in node.statements:
                            check_spans(stmt)

                check_spans(ast)

            except (TokenizerError, ParseError):
                pass  # Expected for some inputs

    def test_idempotent_parsing(self):
        """Test that parsing the same code twice gives the same result."""
        gen = RandomCodeGenerator(seed=42)  # Fixed seed for reproducibility

        for _ in range(20):
            code = gen.generate_program(3)

            try:
                # Parse twice
                lexer1 = Tokenizer(code)
                tokens1 = lexer1.tokenize()
                parser1 = Parser(tokens1, code)
                ast1 = parser1.parse()

                lexer2 = Tokenizer(code)
                tokens2 = lexer2.tokenize()
                parser2 = Parser(tokens2, code)
                ast2 = parser2.parse()

                # Property: Same input should give same output
                assert len(tokens1) == len(tokens2)
                assert ast1.kind == ast2.kind
                assert len(ast1.declarations) == len(ast2.declarations)

            except (TokenizerError, ParseError):
                pass  # Expected for some inputs


class TestMutationFuzzing:
    """Mutation-based fuzzing tests."""

    def mutate_string(self, s: str) -> str:
        """Apply random mutations to a string."""
        if not s:
            return s

        mutation = random.choice([
            "insert",
            "delete",
            "replace",
            "duplicate",
            "swap",
        ])

        pos = random.randint(0, len(s) - 1)

        if mutation == "insert":
            char = random.choice(string.printable)
            return s[:pos] + char + s[pos:]
        elif mutation == "delete" and len(s) > 1:
            return s[:pos] + s[pos + 1:]
        elif mutation == "replace":
            char = random.choice(string.printable)
            return s[:pos] + char + s[pos + 1:]
        elif mutation == "duplicate":
            return s[:pos] + s[pos] + s[pos:]
        elif mutation == "swap" and pos < len(s) - 1:
            lst = list(s)
            lst[pos], lst[pos + 1] = lst[pos + 1], lst[pos]
            return "".join(lst)

        return s

    def test_mutate_valid_programs(self):
        """Mutate valid programs and test parser robustness."""
        valid_programs = [
            "x :: 42",
            "main :: fn() { ret 0 }",
            "Point :: struct { x: i32, y: i32 }",
            "Status :: enum { Ok, Error }",
            "arr: [5]i32 = [1, 2, 3, 4, 5]",
        ]

        for program in valid_programs:
            for _ in range(10):  # 10 mutations per program
                mutated = self.mutate_string(program)

                try:
                    lexer = Tokenizer(mutated)
                    tokens = lexer.tokenize()
                    parser = Parser(tokens, mutated)
                    ast = parser.parse()
                    # Mutation might still be valid
                except (TokenizerError, ParseError):
                    # Expected for most mutations
                    pass
                except Exception as e:
                    # Should not crash with unexpected errors
                    pytest.fail(f"Unexpected error: {e}\nMutated code: {mutated}")

    def test_boundary_mutations(self):
        """Test mutations around boundary conditions."""
        # Maximum length identifier (100 chars)
        long_id = "a" * 100
        code = f"{long_id} :: 42"

        mutations = [
            code[:-1],  # 99 chars
            code + "a",  # 101 chars
            code.replace("a", "1", 1),  # Invalid first char
            code.replace("::", ":"),  # Single colon
            code.replace("42", ""),  # Missing value
        ]

        for mutated in mutations:
            try:
                lexer = Tokenizer(mutated)
                tokens = lexer.tokenize()
                parser = Parser(tokens, mutated)
                ast = parser.parse()
            except (TokenizerError, ParseError):
                pass  # Expected
            except Exception as e:
                pytest.fail(f"Unexpected error: {e}\nMutated: {mutated}")


class TestStressScenarios:
    """Stress tests for performance and resource usage."""

    def test_extremely_long_identifier(self):
        """Test with identifier at maximum length."""
        # A7 supports 100 character identifiers
        long_name = "a" * 100
        code = f"""
{long_name} :: 42
main :: fn() {{
    x := {long_name}
}}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_many_small_declarations(self):
        """Test with many small declarations."""
        # Generate 1000 simple declarations
        declarations = [f"var_{i} :: {i}" for i in range(1000)]
        code = "\n".join(declarations)

        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None
        assert len(ast.declarations) == 1000

    def test_extremely_long_string(self):
        """Test with very long string literal."""
        long_string = "a" * 10000
        code = f'main :: fn() {{ s := "{long_string}" }}'

        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_deeply_nested_match(self):
        """Test deeply nested match statements."""
        depth = 20
        code = "main :: fn() {\n"
        indent = "    "

        for i in range(depth):
            code += indent * (i + 1) + f"match x{i} {{\n"
            code += indent * (i + 2) + f"case {i}: {{\n"

        code += indent * (depth + 2) + "x := 1\n"

        for i in range(depth, 0, -1):
            code += indent * (i + 1) + "}\n"
            code += indent * i + "}\n"

        code += "}"

        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_wide_expression_tree(self):
        """Test very wide expression tree."""
        # Create expression with many operands
        expr = " + ".join(str(i) for i in range(100))
        code = f"main :: fn() {{ x := {expr} }}"

        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])