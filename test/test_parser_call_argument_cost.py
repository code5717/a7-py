"""A `[`-led call argument is parsed once: cost grows with the token count.

Before the fix `_parse_call_argument` parsed `[...]` as a type, failed, and
parsed it again as an expression, so `f([f([...])])` cost about 3x per level.
The assertions count `Parser.advance` calls; they hold no wall-clock threshold.
"""

import pytest

from a7.ast_nodes import NodeKind
from a7.errors import ParseError
from a7.parser import Parser
from a7.tokens import Tokenizer


class CountingParser(Parser):
    def __init__(self, tokens):
        self.advances = 0
        super().__init__(tokens)

    def advance(self):
        self.advances += 1
        return super().advance()


def nested_calls(depth: int) -> str:
    return "main :: fn() {\n    x := " + "f([" * depth + "1" + "])" * depth + "\n}\n"


@pytest.mark.parametrize("depth", [10, 40])
def test_nested_bracket_arguments_consume_each_token_once(depth):
    tokens = Tokenizer(nested_calls(depth)).tokenize()
    parser = CountingParser(tokens)
    program = parser.parse()

    assert parser.advances <= len(tokens)
    call = program.declarations[0].body.statements[0].value
    for _ in range(depth):
        assert call.kind == NodeKind.CALL
        assert call.arguments[0].kind == NodeKind.ARRAY_INIT
        call = call.arguments[0].elements[0]
    assert call.kind == NodeKind.LITERAL


def test_failed_generic_literal_tries_are_not_repeated_per_level():
    """`f([...]){}` at every level makes each `Name(types){...}` try fail.

    Each failed try is remembered, so the retries add up to a polynomial in
    the token count instead of doubling per level (2**24 at this depth).
    """
    depth = 24
    source = "main :: fn() {\n    x := " + "f([" * depth + "1" + "]){}" * depth + "\n}\n"
    tokens = Tokenizer(source).tokenize()
    parser = CountingParser(tokens)

    with pytest.raises(ParseError):
        parser.parse()
    assert parser.advances <= len(tokens) ** 2


def test_bracket_led_arguments_keep_their_type_or_literal_meaning():
    source = "main :: fn() {\n    x := f([3]i32, [1, 2], [2][3]i32, [1, 2][0], []u8, [], [n]Point)\n}\n"
    program = Parser(Tokenizer(source).tokenize()).parse()
    kinds = [arg.kind for arg in program.declarations[0].body.statements[0].value.arguments]
    assert kinds == [
        NodeKind.TYPE_ARRAY, NodeKind.ARRAY_INIT, NodeKind.TYPE_ARRAY, NodeKind.INDEX,
        NodeKind.TYPE_SLICE, NodeKind.ARRAY_INIT, NodeKind.TYPE_ARRAY,
    ]
