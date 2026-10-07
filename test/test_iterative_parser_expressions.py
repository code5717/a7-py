"""Expression and type nesting consumes parser frames, not Python call frames."""
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.parametrize('shape', ['calls', 'parentheses', 'if', 'function_type'])
def test_nested_source_preserves_ast_at_python_limit_100(shape):
    code = textwrap.dedent('''
        import sys
        from a7.ast_nodes import ASTNode, NodeKind
        from a7.parser import Parser
        from a7.tokens import Tokenizer
        shape = sys.argv[1]
        if shape == "calls":
            source = "f::fn(x:i32)i32{ret x};main::fn(){x:=" + "f("*60 + "1" + ")"*60 + "}"
            expected_kind, expected_count = NodeKind.CALL, 60
        elif shape == "parentheses":
            source = "main::fn(){x:=" + "("*60 + "1" + ")"*60 + "}"
            expected_kind, expected_count = NodeKind.LITERAL, 1
        elif shape == "if":
            source = "main::fn(){x:=" + "if true {"*40 + "1" + "}else{0}"*40 + "}"
            expected_kind, expected_count = NodeKind.IF_EXPR, 40
        else:
            source = "Alias::" + "fn("*40 + "i32" + ")i32"*40 + ";main::fn(){}"
            expected_kind, expected_count = NodeKind.TYPE_FUNCTION, 40
        outputs = []
        for limit in (1000, 100):
            sys.setrecursionlimit(limit)
            parser = Parser(Tokenizer(source).tokenize())
            root = parser.parse()
            assert parser._nesting_depth == 0 and parser._header_depth is None
            pending = [root]
            count = 0
            while pending:
                node = pending.pop()
                count += node.kind == expected_kind
                for value in vars(node).values():
                    if isinstance(value, ASTNode):
                        pending.append(value)
                    elif isinstance(value, list):
                        pending.extend(child for child in value if isinstance(child, ASTNode))
            assert count == expected_count, (shape, count)
            outputs.append(repr(root))
        assert outputs[0] == outputs[1]
    ''')
    result = subprocess.run([sys.executable, '-c', code, shape], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_nested_speculative_generic_call_restores_header_and_nesting_after_error():
    code = textwrap.dedent('''
        import sys
        from a7.errors import ParseError
        from a7.parser import Parser
        from a7.tokens import Tokenizer
        sys.setrecursionlimit(100)
        parser = Parser(Tokenizer("main::fn(){x:=" + "f("*50 + "1" + ")"*49 + "}").tokenize())
        try:
            parser.parse()
        except ParseError as error:
            assert str(error).endswith("Expected ',' between items in call arguments, found '}'"), str(error)
        else:
            raise AssertionError("missing call delimiter accepted")
        assert parser._nesting_depth == 0
        assert parser._header_depth is None
    ''')
    result = subprocess.run([sys.executable, '-c', code], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
