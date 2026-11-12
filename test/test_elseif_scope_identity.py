"""Else-if checking updates the declarations registered by name resolution."""
import pytest

from a7.compile import A7Compiler
from a7.passes.name_resolution import NameResolutionPass
from a7.types import UnknownType
from conftest import expect_exit, compile_program


@pytest.mark.parametrize('body,expected', [
    ('if flag { first_marker: i32 = 1 } else if false { second_marker: i32 = 2 } else { third_marker: i32 = 3 }', 3),
    ('if flag { item_marker: i32 = 1 } else if false { item_marker: bool = true } else { item_marker: string = "ok" }', 3),
    ('if flag { first_marker: i32 = 1 } else if false { second_marker: bool = true } else if flag { third_marker: string = "ok" } else { fourth_marker: i64 = 4 }; if flag { later_marker: bool = true } else { final_marker: string = "end" }', 6),
    ('shared_marker: string = "parent"; if flag { a_marker: i32 = 0 } else if false { shared_marker: i32 = 1; use_marker: i32 = shared_marker } else { shared_marker: bool = true; use_marker: bool = shared_marker }; tail_marker: string = shared_marker', 7),
    ('shared_marker: string = "parent"; if flag { a_marker: i32 = 0 } else if false { shared_marker: i32 = 1; use_marker: i32 = shared_marker } else { use_marker: string = shared_marker }; tail_marker: string = shared_marker', 6),
    ('outer_marker: i32 = 1; if flag { outer_marker: bool = true } else { if false { outer_marker: string = "ok" } else { inner_marker: i64 = 4 } }; after_marker: i32 = outer_marker', 5),
])
def test_each_declaration_retains_its_symbol_and_scope(tmp_path, monkeypatch, body, expected):
    source = tmp_path / 'main.a7'
    source.write_text('probe :: fn(flag: bool) { ' + body + ' }\nmain :: fn() { probe(false) }')
    registered = {}
    def inventory(table):
        rows = []
        pending = list(table.file_scopes.values()) or [table.global_scope]
        seen = set()
        while pending:
            scope = pending.pop()
            if id(scope) in seen:
                continue
            seen.add(id(scope))
            pending.extend(scope.children)
            rows.extend((symbol, scope) for symbol in scope.symbols.values() if symbol.name.endswith('_marker'))
        return rows
    analyze = NameResolutionPass.analyze
    def observe(self, *args, **kwargs):
        table = analyze(self, *args, **kwargs)
        registered.update({id(symbol.node): (symbol, scope) for symbol, scope in inventory(table)})
        return table
    # Observe the real pass result; no compiler behavior is replaced.
    monkeypatch.setattr(NameResolutionPass, 'analyze', observe)
    output = tmp_path / 'main.zig'
    result = A7Compiler().compile_file_detailed(str(source), str(output))
    assert int(result.exit_code) == 0
    assert output.is_file()
    table = result.semantic_results['symbol_table']
    rows = inventory(table)
    assert len(registered) == len(rows) == expected
    assert len({id(symbol.node) for symbol, _ in rows}) == expected
    for symbol, scope in rows:
        old_symbol, old_scope = registered[id(symbol.node)]
        assert symbol is old_symbol
        assert scope is old_scope
        assert not isinstance(symbol.type, UnknownType)
        value = symbol.node.value
        name = getattr(value, 'name', None)
        if name and name.endswith('_marker'):
            # An initializer use binds to the nearest lexical declaration,
            # including the parent after a shadowing arm has ended.
            owner = scope
            while name not in owner.symbols:
                owner = owner.parent
                assert owner is not None
            assert table.resolved_uses[id(value)] is owner.symbols[name]


@pytest.mark.parametrize('value,expected', [('2', 0), ('128', 6)])
def test_elseif_generic_array_obligation(tmp_path, value, expected):
    result = compile_program('''
make :: fn(seed: $T, flag: bool) [2]$T {
    if flag { first: [2]$T = [1, ''' + value + ''']; ret first } else if false { second: [2]$T = [1, ''' + value + ''']; ret second } else { third: [2]$T = [1, ''' + value + ''']; ret third }
}
main :: fn() { seed: i8 = 0; result := make(seed, false) }
''', tmp_path)
    assert int(result.exit_code) == expected


def test_elseif_wrong_type_is_rejected_in_its_own_arm(tmp_path):
    expect_exit('''
main :: fn() {
    if false { value: i32 = 1 } else if true { value: bool = 2 } else { value: string = "ok" }
}
''', tmp_path, 6, 'bool')


def test_elseif_arm_declaration_does_not_escape(tmp_path):
    expect_exit(
        'main :: fn() { if false { a: i32 = 0 } else if true { shared: i32 = 1 } else { other: i32 = 2 }; tail := shared }',
        tmp_path, 6, 'shared',
    )
