"""AST dataclass behavior stays usable on parsed trees at recursion limit 100."""

from dataclasses import fields, make_dataclass
from pathlib import Path
import subprocess
import sys

import pytest

from a7.ast_nodes import ASTNode, NodeKind


def test_parsed_deep_ast_methods_and_wrappers_at_limit_100():
    code = '''
import sys
from a7.ast_nodes import ASTNode
from a7.parser import Parser
from a7.tokens import Tokenizer
from a7.module_resolver import ModuleInfo
from a7.semantic_context import FunctionContext, DeferContext
from a7.symbol_table import Symbol, SymbolKind
from a7.types import I32
sys.setrecursionlimit(100)
source = 'main :: fn() { x := ' + ' + '.join(['1'] * 301) + ' }'
a = Parser(Tokenizer(source).tokenize()).parse()
b = Parser(Tokenizer(source).tokenize()).parse()
wrappers = [lambda n: n, lambda n: ModuleInfo('main', 'main.a7', n),
            lambda n: FunctionContext('main', I32, n), lambda n: DeferContext(n, 0),
            lambda n: Symbol('main', SymbolKind.FUNCTION, I32, n)]
for wrap in wrappers:
    assert wrap(a) == wrap(b)
    assert repr(wrap(a)) == repr(wrap(b))
leaf = b.declarations[0].body.statements[0].value
while leaf.left is not None:
    leaf = leaf.left
leaf.literal_value = 2
for wrap in wrappers:
    assert wrap(a) != wrap(b)
left = right = 7
for index in range(300):
    left = {'nested': [(left,)]}
    right = {'nested': [(right,)]}
payload_a = ASTNode(a.kind, literal_value=left)
payload_b = ASTNode(a.kind, literal_value=right)
assert payload_a == payload_b
assert repr(payload_a) == repr(payload_b)
assert sys.getrecursionlimit() == 100
'''
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, '-c', code], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_repr_matches_generated_dataclass_and_repeats_shared_children():
    baseline = make_dataclass('ASTNode', [(f.name, f.type, f) for f in fields(ASTNode)])
    child = ASTNode(NodeKind.IDENTIFIER, name='shared')
    payload = {'items': [child, (child,)], 'empty': (), 'text': "quote'"}
    current = ASTNode(NodeKind.BLOCK, statements=[child, child], literal_value=payload)
    expected = baseline(**{f.name: getattr(current, f.name) for f in fields(ASTNode)})
    current.dynamic_annotation = 'ignored'
    assert repr(current) == repr(expected)
    assert repr(current).count("name='shared'") == 4
    assert 'dynamic_annotation' not in repr(current)


def test_equality_preserves_fields_class_identity_and_unhashability():
    a = ASTNode(NodeKind.IDENTIFIER, name='x')
    b = ASTNode(NodeKind.IDENTIFIER, name='x')
    a.extra = 'ignored'
    assert a == b
    b.is_used = False
    assert a != b
    assert ASTNode.__eq__(a, 1) is NotImplemented
    class Derived(ASTNode):
        pass
    assert a != Derived(NodeKind.IDENTIFIER, name='x')
    assert Derived(NodeKind.IDENTIFIER, name='x') == Derived(NodeKind.IDENTIFIER, name='x')
    with pytest.raises(TypeError):
        hash(a)


def test_cycles_keep_dataclass_behavior_and_dag_equality():
    a = ASTNode(NodeKind.BLOCK)
    b = ASTNode(NodeKind.BLOCK)
    a.body = a
    b.body = b
    assert a == a
    assert 'body=...' in repr(a)
    with pytest.raises(RecursionError):
        _ = a == b
    children = []
    children.append(children)
    a.literal_value = children
    assert 'literal_value=[[...]]' in repr(a)
    x = ASTNode(NodeKind.IDENTIFIER, name='x')
    assert ASTNode(NodeKind.BLOCK, statements=[x, x]) == ASTNode(
        NodeKind.BLOCK, statements=[ASTNode(NodeKind.IDENTIFIER, name='x'),
                                   ASTNode(NodeKind.IDENTIFIER, name='x')])


def test_leaf_eq_uses_eq_not_ne_and_preserves_short_circuit():
    events = []
    class Leaf:
        def __eq__(self, other):
            events.append('eq')
            return True
        def __ne__(self, other):
            raise AssertionError('dataclass tuple equality must use eq')
    assert ASTNode(NodeKind.LITERAL, literal_value=Leaf()) == ASTNode(NodeKind.LITERAL, literal_value=Leaf())
    assert events == ['eq']
    assert ASTNode(NodeKind.LITERAL, name='a', literal_value=Leaf()) != ASTNode(NodeKind.LITERAL, name='b', literal_value=Leaf())
    assert events == ['eq']


def test_repr_leaf_exception_cleanup_and_reentrant_cycle():
    class Broken:
        def __repr__(self):
            raise ValueError('leaf failure')
    node = ASTNode(NodeKind.LITERAL, literal_value=Broken())
    with pytest.raises(ValueError, match='leaf failure'):
        repr(node)
    node.literal_value = 7
    assert 'literal_value=7' in repr(node)
    class BackReference:
        def __repr__(self):
            return repr(node)
    node.literal_value = BackReference()
    assert 'literal_value=...' in repr(node)


def test_repr_field_reads_follow_leaf_rendering_order():
    node = ASTNode(NodeKind.LITERAL)
    class Mutator:
        def __repr__(self):
            node.raw_text = 'after'
            return 'leaf'
    node.literal_value = Mutator()
    assert "literal_value=leaf, raw_text='after'" in repr(node)


def test_subclass_overrides_remain_leaf_methods():
    class Custom(ASTNode):
        def __eq__(self, other):
            return False
        def __repr__(self):
            return 'custom-ast'
    a = Custom(NodeKind.IDENTIFIER, name='x')
    b = Custom(NodeKind.IDENTIFIER, name='x')
    assert ASTNode.__eq__(a, b) is True
    assert 'name=' in ASTNode.__repr__(a)
    assert ASTNode(NodeKind.BLOCK, body=a) != ASTNode(NodeKind.BLOCK, body=b)
    assert 'body=custom-ast' in repr(ASTNode(NodeKind.BLOCK, body=a))
    class CustomList(list):
        def __eq__(self, other):
            return False
        def __repr__(self):
            return 'custom-list'
    assert ASTNode(NodeKind.BLOCK, statements=CustomList()) != ASTNode(NodeKind.BLOCK, statements=CustomList())
    assert 'statements=custom-list' in repr(ASTNode(NodeKind.BLOCK, statements=CustomList()))


def test_dictionary_leaf_comparisons_precede_later_missing_keys():
    class Broken:
        def __eq__(self, other):
            raise ValueError('first value')
    left = ASTNode(NodeKind.LITERAL, literal_value={'first': Broken(), 'missing': 1})
    right = ASTNode(NodeKind.LITERAL, literal_value={'first': Broken(), 'other': 1})
    with pytest.raises(ValueError, match='first value'):
        _ = left == right


@pytest.mark.parametrize('container', [list, tuple])
def test_list_length_shortcut_and_tuple_common_prefix_order(container):
    class Broken:
        def __eq__(self, other):
            raise ValueError('first element')
    left = ASTNode(NodeKind.LITERAL, literal_value=container([Broken()]))
    right = ASTNode(NodeKind.LITERAL, literal_value=container([Broken(), 1]))
    if container is list:
        assert left != right
    else:
        with pytest.raises(ValueError, match='first element'):
            _ = left == right
