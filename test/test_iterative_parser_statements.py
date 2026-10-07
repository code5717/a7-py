"""Statement nesting uses logical parser depth, independent of Python frames."""
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.parametrize("shape", ["block", "if", "while", "for", "match", "defer", "function", "label"])
def test_deep_statements_at_python_limit_100(shape):
    code = textwrap.dedent('''
        import sys
        from a7.parser import Parser
        from a7.tokens import Tokenizer
        from a7.ast_nodes import NodeKind
        shape = sys.argv[1]
        templates = {
            "block": ("{", "}"), "if": ("if true {", "}"),
            "while": ("while true {", "}"), "for": ("for {", "}"),
            "match": ("match 1 { case 1: {", "}}"),
            "defer": ("defer ", ""), "label": ("@outer for {", "}"),
        }
        if shape == "function":
            source = "".join(f"localfn{i} :: fn() {{" for i in range(60)) + "ret" + "}" * 60
        else:
            opening, closing = templates[shape]
            source = "main :: fn(){" + opening * 60 + "ret" + closing * 60 + "}"
        parser = Parser(Tokenizer(source).tokenize())
        sys.setrecursionlimit(100)
        root = parser.parse()
        assert parser._nesting_depth == 0
        assert parser._header_depth is None
        assert parser.at_end()
        node = root.declarations[0].body.statements[0]
        for _ in range(59 if shape == "function" else 60):
            if shape == "function":
                assert node.kind == NodeKind.FUNCTION
                node = node.body.statements[0]
            elif shape == "block":
                assert node.kind == NodeKind.BLOCK
                node = node.statements[0]
            elif shape == "if":
                assert node.kind == NodeKind.IF_STMT
                node = node.then_stmt.statements[0]
            elif shape == "match":
                assert node.kind == NodeKind.MATCH
                node = node.cases[0].statement.statements[0]
            elif shape == "defer":
                assert node.kind == NodeKind.DEFER
                node = node.statement
            else:
                assert node.kind == (NodeKind.WHILE if shape == "while" else NodeKind.FOR)
                if shape == "label":
                    assert node.label == "outer"
                node = node.body.statements[0]
        assert node.kind == NodeKind.RETURN
    ''')
    result = subprocess.run([sys.executable, "-c", code, shape], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_logical_depth_error_unwinds_suspended_statements():
    code = textwrap.dedent('''
        import sys
        from a7.parser import Parser
        from a7.tokens import Tokenizer
        from a7.errors import ParseError
        sys.setrecursionlimit(100)
        valid = Parser(Tokenizer("main :: fn(){" + "{" * 255 + "ret" + "}" * 256).tokenize())
        valid.parse()
        assert valid._nesting_depth == 0
        source = "main :: fn(){" + "{" * 257 + "ret" + "}" * 258
        parser = Parser(Tokenizer(source).tokenize())
        try:
            parser.parse()
        except ParseError as error:
            assert "Maximum nesting depth (256) exceeded" in str(error)
        else:
            raise AssertionError("logical nesting cap not enforced")
        assert parser._nesting_depth == 0
        assert parser._header_depth is None
    ''')
    result = subprocess.run([sys.executable, "-c", code], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
