"""A typed array arm supplies the existing destination for literal arms."""
import pytest

import a7.compile as compiler
from a7.ast_nodes import ASTNode

from a7.passes import type_checker as candidate
from conftest import run_both_profiles


def compile_source(source, tmp_path):
    path = tmp_path / 'input.a7'
    path.write_text(source)
    return compiler.A7Compiler().compile_file_detailed(str(path), str(path.with_suffix('.zig')))


@pytest.mark.parametrize('expression', [
    'if flag {small}else{[3,4]}',
    'if flag {[3,4]}else{small}',
    'match flag {case true:small else:[3,4]}',
    'match flag {case true:[3,4] else:small}',
    'if flag {small}else{if flag{[1,2]}else{[3,4]}}',
    'match flag {case true:small else:match flag{case true:[1,2] else:[3,4]}}',
    'if flag {small}else{[if flag{1}else{2},3]}',
])
def test_literal_arms_fit_typed_array_destination(expression, tmp_path):
    source = 'choose::fn(flag:bool)[2]i8{small:[2]i8=[1,2];ret '+expression+'}\nmain::fn(){x:=choose(true)}'
    assert compile_source(source, tmp_path).ok


def test_nested_array_literal_arm_fits_numeric_leaf(tmp_path):
    source = 'choose::fn(flag:bool)[2][2]i8{small:[2][2]i8=[[1,2],[3,4]];ret if flag{small}else{[[5,6],[7,8]]}}\nmain::fn(){x:=choose(true)}'
    assert compile_source(source, tmp_path).ok


@pytest.mark.parametrize('expression,diagnostic', [
    ('if flag {small}else{[3,300]}', 'Exact constant 300 is out of range for i8'),
    ('match flag {case true:[300,4] else:small}', 'Exact constant 300 is out of range for i8'),
    ('if flag {small}else{[3]}', 'If expression branches have different types'),
    ('if flag {small}else{[true,false]}', 'If expression branches have different types'),
    ('if flag {small}else{wide}', 'If expression branches have different types'),
    ('match flag {case true:wide else:small}', 'If expression branches have different types'),
])
def test_bad_literal_or_typed_array_arm_remains_rejected(expression, diagnostic, tmp_path, capsys):
    source = 'choose::fn(flag:bool)[2]i8{small:[2]i8=[1,2];wide:[2]i32=[1,2];ret '+expression+'}\nmain::fn(){x:=choose(true)}'
    assert int(compile_source(source, tmp_path).exit_code) == 6
    assert diagnostic in capsys.readouterr().err


def test_range_errors_follow_arm_and_element_source_order(tmp_path, capsys):
    source = 'choose::fn(n:i32)[2]i8{small:[2]i8=[1,2];ret match n{case 0:small case 1:[300,400] else:[500,600]}}\nmain::fn(){x:=choose(0)}'
    assert int(compile_source(source, tmp_path).exit_code) == 6
    output = capsys.readouterr().err
    offsets = [output.index('Exact constant '+str(value)+' is out of range') for value in (300,400,500,600)]
    assert offsets == sorted(offsets)
    assert output.count('error: Exact constant') == 4


def test_generic_instantiations_do_not_refit_fixed_typed_arm(tmp_path, monkeypatch):
    original = candidate.TypeCheckingPass._instantiated_value_fits
    observations = []

    def observe(self, value, source_type, actual, expected, mapping):
        pending = [value]
        nodes = []
        while pending:
            node = pending.pop()
            nodes.append(node)
            for child in vars(node).values():
                if isinstance(child, ASTNode):
                    pending.append(child)
                elif isinstance(child, list):
                    pending.extend(item for item in child if isinstance(item, ASTNode))
        before = [repr(vars(node)) for node in nodes]
        result = original(self, value, source_type, actual, expected, mapping)
        assert before == [repr(vars(node)) for node in nodes]
        observations.append((id(value), str(expected), result))
        return result

    monkeypatch.setattr(candidate.TypeCheckingPass, '_instantiated_value_fits', observe)
    for calls in ('invoke(small,true);invoke(wide,false)', 'invoke(wide,false);invoke(small,true)'):
        observations.clear()
        source = 'invoke::fn(f:fn($T),flag:bool){a:[2]i8=[1,2];f(if flag{a}else{[3,4]})}\nsmall::fn(x:[2]i8){}\nwide::fn(x:[2]i32){}\nmain::fn(){'+calls+'}'
        assert int(compile_source(source, tmp_path).exit_code) == 6
        assert {(expected,result) for _,expected,result in observations} == {('[2]i8',True),('[2]i32',False)}
        assert len({identity for identity,_,_ in observations}) == 1


def test_mixed_array_branches_execute_both_paths(tmp_path, zig):
    assert run_both_profiles('''
io :: import "std/io"
choose :: fn(flag: bool) [2]i8 {
    a: [2]i8 = [1, 2]
    ret if flag { a } else { [3, 4] }
}
choose_match :: fn(flag: bool) [2][2]i16 {
    a: [2][2]i16 = [[5, 6], [7, 8]]
    ret match flag { case true: [[9, 10], [11, 12]] else: a }
}
main :: fn() {
    a := choose(true)
    b := choose(false)
    c := choose_match(true)
    d := choose_match(false)
    io.println("{} {} {} {}", a[0], a[1], b[0], b[1])
    io.println("{} {} {} {}", c[0][0], c[1][1], d[0][0], d[1][1])
}
''', tmp_path, zig) == "1 2 3 4\n9 12 5 8\n"
