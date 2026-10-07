"""Reporting visits independent file scopes without changing lexical lookup."""
import io
from html import unescape
from pathlib import Path

from rich.console import Console

from a7.compile import A7Compiler
from a7.formatters.console_formatter import ConsoleFormatter
from a7.formatters.markdown_formatter import MarkdownFormatter
from a7.symbol_table import SymbolTable


def test_all_file_symbols_render_once_with_owner(tmp_path):
    for name in ('left', 'right'):
        (tmp_path / f'{name}.a7').write_text('answer::fn(input:i32)i32 { local:=input;ret local }')
    source = 'left::import "left"\nright::import "right"\nmain::fn(){result:=left.answer(3)+right.answer(4)}'
    entry = tmp_path / 'main.a7'
    entry.write_text(source)
    result = A7Compiler(mode='semantic').compile_file_detailed(str(entry))
    assert int(result.exit_code) == 0
    semantic = result.semantic_results
    table = semantic['symbol_table']
    roots = dict(table.file_scopes)
    console = ConsoleFormatter()
    markdown = MarkdownFormatter()
    for formatter in (console, markdown):
        rows = formatter._collect_symbols(table)
        assert len(rows) == 10
        for module in ('left', 'right'):
            owner = str(tmp_path / f'{module}.a7')
            owned = [row for row in rows if row['scope'].startswith(owner + '::')]
            assert [row['name'] for row in owned] == ['answer', 'input', 'local']
            assert [row['type'] for row in owned] == ['fn(i32) i32', 'i32', 'i32']
        assert [row['name'] for row in rows if '<entry>::' in row['scope']] == ['main', 'left', 'right', 'result']
    stream = io.StringIO()
    console.console = Console(file=stream, width=500, color_system=None)
    console._display_semantic(semantic)
    rendered = stream.getvalue()
    doc = markdown.format_compilation_doc(str(entry), source, [], None, semantic, None)
    dump = table.dump()
    for text in (rendered, unescape(doc), dump):
        assert 'input' in text and 'local' in text and 'result' in text
        assert 'left.a7' in text and 'right.a7' in text and '<entry>' in text
    assert dump.count('Symbol(answer:') == 2
    assert dump.count('Symbol(input:') == 2
    assert dump.count('Symbol(local:') == 2
    assert dump.count('Symbol(main:') == 1
    assert 'global:' not in dump
    # Reporting must not connect disjoint lookup roots or mutate active scope.
    assert table.file_scopes == roots
    assert all(root.parent is None for root in roots.values())
    assert table.current_scope.lookup('answer') is None
    assert table.current_scope.lookup('input') is None
    one = table.dump(roots[str(tmp_path / 'left.a7')], indent=1)
    assert 'left.a7' in one and 'right.a7' not in one and 'Symbol(main:' not in one


def test_unpartitioned_table_keeps_legacy_reporting():
    table = SymbolTable()
    table.enter_scope('function')
    table.enter_scope('block')
    assert table.dump() == 'global:\n  function:\n    block:'
    assert ConsoleFormatter()._collect_symbols(table) == []
    assert MarkdownFormatter()._collect_symbols(table) == []


def test_markdown_owner_labels_survive_table_rendering(tmp_path):
    from markdown_it import MarkdownIt
    from xml.etree import ElementTree

    names = ['pipe|module', 'angle<box>&amp;module', 'mark_*[link]`~']
    for name in names:
        (tmp_path / (name + '.a7')).write_text('answer::fn(input:i32)i32{ret input}')
    source = '\n'.join(f'p{i}::import "{name}"' for i, name in enumerate(names))
    source += '\nmain::fn(){result:=p0.answer(1)+p1.answer(2)+p2.answer(3)}'
    entry = tmp_path / 'main.a7'
    entry.write_text(source)
    result = A7Compiler(mode='semantic').compile_file_detailed(str(entry))
    assert int(result.exit_code) == 0
    doc = MarkdownFormatter().format_compilation_doc(
        str(entry), source, [], None, result.semantic_results, None,
    )
    section = doc.split('### Symbol Table\n', 1)[1].split('\n## ', 1)[0]
    rendered = MarkdownIt('commonmark').enable('table').render(section)
    root = ElementTree.fromstring('<root>' + rendered + '</root>')
    rows = [[''.join(cell.itertext()) for cell in row.findall('td')]
            for row in root.findall('.//tbody/tr')]
    expected = []
    for name in names:
        owner = str(tmp_path / (name + '.a7'))
        expected += [
            ['answer', 'FUNCTION', 'fn(i32) i32', owner + '::global'],
            ['input', 'VARIABLE', 'i32', owner + '::function_answer'],
        ]
    owner = str(tmp_path / '<entry>')
    expected += [['main', 'FUNCTION', 'fn()', owner + '::global']]
    expected += [[f'p{i}', 'MODULE', 'module', owner + '::global'] for i in range(3)]
    expected += [['result', 'VARIABLE', 'i32', owner + '::block']]
    assert rows == expected
    # Filenames and entry markers must remain text, with no injected elements.
    assert all(
        child.tag == 'code' for cell in root.findall('.//td') for child in cell
    )
