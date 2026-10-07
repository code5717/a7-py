"""Type children and alias dependencies resolve without Python recursion."""

from pathlib import Path
import subprocess
import sys

import pytest

from a7.ast_nodes import ASTNode, NodeKind
from a7.parser import Parser
from a7.tokens import Tokenizer
from a7.passes.name_resolution import NameResolutionPass
from a7.passes.type_checker import TypeCheckingPass
from a7.symbol_table import SymbolTable
from a7.types import I32


def checker_for(source):
    ast = Parser(Tokenizer(source).tokenize()).parse()
    resolver = NameResolutionPass()
    symbols = resolver.analyze(ast, 'types.a7')
    assert not resolver.errors
    return ast, TypeCheckingPass(symbols)


def test_deep_alias_full_pipeline_and_compound_types_at_limit_100(tmp_path):
    code = '''
import pathlib, sys
from a7.ast_nodes import ASTNode, NodeKind
from a7.compile import A7Compiler
from a7.parser import Parser
from a7.tokens import Tokenizer
from a7.passes.name_resolution import NameResolutionPass
from a7.passes.type_checker import TypeCheckingPass
from a7.symbol_table import SymbolTable
from a7.types import I32, I64
folder = pathlib.Path(sys.argv[1])
sys.setrecursionlimit(100)
source = '\\n'.join(f'A{i} :: ref A{i+1}' for i in range(200)) + '\\nA200 :: i32\\nmain :: fn() {}'
path = folder/'aliases.a7'; path.write_text(source)
result = A7Compiler().compile_file_detailed(str(path), str(folder/'aliases.zig'))
assert result.ok, result.failure
for shape in ['function', 'struct', 'generic', 'set', 'wrapper']:
    symbols = SymbolTable()
    tc = TypeCheckingPass(symbols)
    if shape == 'generic':
        tree = Parser(Tokenizer('Box($T) :: struct {item:$T}\\nmain :: fn(){}').tokenize()).parse()
        nr = NameResolutionPass(); symbols = nr.analyze(tree, 'generic.a7')
        tc = TypeCheckingPass(symbols); tc.analyze(tree)
    resolved = []
    for leaf_name in ['i32', 'i32', 'i64']:
        node = ASTNode(NodeKind.TYPE_PRIMITIVE, type_name=leaf_name)
        for index in range(200):
            if shape == 'function': node = ASTNode(NodeKind.TYPE_FUNCTION, parameter_types=[node])
            elif shape == 'struct': node = ASTNode(NodeKind.TYPE_STRUCT, fields=[ASTNode(NodeKind.FIELD, name='x', field_type=node)])
            elif shape == 'generic': node = ASTNode(NodeKind.TYPE_IDENTIFIER, name='Box', generic_params=[node])
            elif shape == 'set': node = ASTNode(NodeKind.TYPE_SET, types=[node])
            else: node = ASTNode(NodeKind.TYPE_POINTER, target_type=node)
        resolved.append(tc.resolve_type_node(node))
    assert not tc.errors, tc.errors
    assert resolved[0].equals(resolved[1]), shape
    assert not resolved[0].equals(resolved[2]), shape
assert sys.getrecursionlimit() == 100
'''
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path)], cwd=root,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_function_diagnostic_order_and_generic_base_suppression():
    def missing(name):
        return ASTNode(NodeKind.TYPE_IDENTIFIER, name=name)
    tc = TypeCheckingPass(SymbolTable())
    node = ASTNode(NodeKind.TYPE_FUNCTION, parameter_types=[missing('P1'), missing('P2')],
                   return_type=missing('R'), is_variadic=True, param_type=missing('V'))
    tc.resolve_type_node(node)
    messages = [str(e) for e in tc.errors]
    assert len(messages) == 5
    assert all(name in message for name, message in zip(
        ["'P1'", "'P2'", "'R'", 'Variadic function pointers', "'V'"], messages))
    tc = TypeCheckingPass(SymbolTable())
    node = ASTNode(NodeKind.TYPE_IDENTIFIER, name='MissingBox', generic_params=[missing('P1'), missing('P2')])
    tc.resolve_type_node(node)
    tc.resolve_type_node(node)
    assert [str(e).split("Type '")[1].split("'")[0] for e in tc.errors] == ['P1', 'P2', 'MissingBox', 'P1', 'P2']


def test_alias_cycle_diagnostic_and_cleanup():
    tree, tc = checker_for('A :: ref B\nB :: ref A\nmain :: fn(){}')
    tc.analyze(tree, 'types.a7')
    assert len(tc.errors) == 1
    assert "Circular type alias dependency involving 'A'" in str(tc.errors[0])
    assert tc.errors[0].span == tree.declarations[0].span
    assert not tc._resolving_type_aliases
    assert tc._resolved_type_aliases == {id(tree.declarations[0]), id(tree.declarations[1])}


def test_resolution_exception_unwinds_only_its_alias_marks(monkeypatch):
    tree, tc = checker_for('A :: ref B\nB :: ref Box(i32)\nDone :: i32\nBox($T) :: struct {item:$T}\nmain :: fn(){}')
    tc.register_type_alias(tree.declarations[2])
    foreign_active = -1
    tc._resolving_type_aliases.add(foreign_active)
    original = tc._annotation_arguments_ok
    def fail_at_annotation(*args):
        raise ValueError('annotation failure')
    monkeypatch.setattr(tc, '_annotation_arguments_ok', fail_at_annotation)
    scope = tc.symbols.current_scope
    with pytest.raises(ValueError, match='annotation failure'):
        tc.register_type_alias(tree.declarations[0])
    assert tc._resolving_type_aliases == {foreign_active}
    assert tc._resolved_type_aliases == {id(tree.declarations[2])}
    assert tc.symbols.current_scope is scope
    monkeypatch.setattr(tc, '_annotation_arguments_ok', original)
    tc.register_type_alias(tree.declarations[0])
    assert tc._resolving_type_aliases == {foreign_active}
    assert id(tree.declarations[0]) in tc._resolved_type_aliases
    assert tc.resolve_type_node(ASTNode(NodeKind.TYPE_PRIMITIVE, type_name='i32')) is I32


def test_forward_record_shell_keeps_reference_identity():
    tree, tc = checker_for('Owner :: struct { pet:ref Pet }\nPet :: struct {owner:ref Owner, next:ref Pet}\nmain :: fn(){}')
    tc.analyze(tree)
    assert not tc.errors
    owner = tc.symbols.lookup('Owner').type
    pet = tc.symbols.lookup('Pet').type
    assert owner.fields[0].field_type.referent_type is pet
    assert pet.fields[0].field_type.referent_type is owner
    assert pet.fields[1].field_type.referent_type is pet
