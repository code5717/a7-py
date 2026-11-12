"""Compile-only contracts for known fixed-array reference aliases.

Uncertain-index, loop-invalidation and escape controls pin existing acceptance,
not memory safety.
No unsafe fixture is built or executed.
"""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
HEADER = 'io :: import "std/io"\nBox :: struct { value: i32 }\nmutate :: fn(xs: ref [2]ref Box, value: ref Box) { xs = [value, value] }\n'
SETUP = 'p := new Box; if p == nil { ret }; r := new Box; if r == nil { ret }; refs: [2]ref Box = [p, r]; '
READ = 'q := refs[0]; if q != nil { io.println("{}", q.value) }; '
CASES = [
    ('deleted_source', 'del p; ' + READ, 6),
    ('before_delete', READ + 'del p; del r;', 0),
    ('distinct_slot', 'del p; q := refs[1]; if q != nil { io.println("{}", q.value) }; del r;', 0),
    ('fresh_overwrite', 'del p; refs[0] = new Box; ' + READ, 0),
    ('copy_reference', 'q := refs[0]; s := q; del p; if s != nil { io.println("{}", s.value) };', 6),
    ('delete_slot', 'del refs[0]; if p != nil { io.println("{}", p.value) };', 6),
    ('delete_saved_alias', 'q := refs[0]; del q; ' + 's := refs[0];', 6),
    ('repeat_delete_slot', 'del refs[0]; del refs[0];', 6),
    ('slot_to_slot', 'refs[1] = refs[0]; del p; q := refs[1];', 6),
    ('copy_array_alias', 'copy := refs; del p; q := copy[0];', 6),
    ('copy_independent_cells', 'copy := refs; refs[0] = r; del p; q := refs[0]; if q != nil { io.println("{}", q.value) };', 0),
    ('copy_retains_old_referent', 'copy := refs; refs[0] = r; del p; q := copy[0];', 6),
    ('dynamic_write', 'del p; if i < 2 { refs[i] = r }; ' + READ, 0),
    ('dynamic_read', 'del p; if i < 2 { q := refs[i]; if q != nil { io.println("{}", q.value) } };', 0),
    ('joined_write', 'if flag { refs[0] = r }; del p; ' + READ,6),
    ('branch_delete_slot', 'if flag { del refs[0] }; ' + READ,6),
    ('saved_slot_join', 'q := refs[0]; if flag { del p }; if q != nil { io.println("{}", q.value) };',6),
    ('saved_slot_loop', 'q := refs[0]; while flag { del p; break }; if q != nil { io.println("{}", q.value) };', 6),
    ('slot_loop', 'while flag { del refs[0]; break }; ' + READ, 6),
    ('ordinary_alias_join', 'q := p; if flag { del p }; if q != nil { io.println("{}", q.value) };', 6),
    ('ordinary_alias_loop', 'q := p; while flag { del p; break }; if q != nil { io.println("{}", q.value) };', 6),
    ('slice_escape_late_write', 'view := refs[0..2]; refs[0] = p; view[0] = r; del p; ' + READ, 0),
    ('borrowed_mutation', 'mutate(refs, r); del p; ' + READ, 0),
    ('slice_copy_retains_escape', 'view := refs[0..2]; other := view; refs[0] = p; other[0] = r; del p; ' + READ, 0),
    ('unguarded_index_unchanged', 'q := refs[0]; io.println("{}", q.value);', 6),
]

GRID = 'grid: [2][2]ref Box = [[r, r], [r, r]]; grid[0][0] = p; '
GRID_READ = 'del p; q := grid[0][0]; if q != nil { io.println("{}", q.value) };'
CASES += [
    ('nested_borrow', GRID + 'mutate(grid[0], r); ' + GRID_READ, 0),
    ('nested_view', GRID + 'view := grid[0][0..2]; view[0] = r; ' + GRID_READ, 0),
    ('nested_dynamic_inner_write', GRID + 'if i >= 2 { ret }; grid[0][i] = r; ' + GRID_READ, 0),
    ('nested_dynamic_outer_write', GRID + 'if i >= 2 { ret }; grid[i][0] = r; ' + GRID_READ, 0),
    ('nested_dynamic_borrow', GRID + 'if i >= 2 { ret }; mutate(grid[i], r); ' + GRID_READ, 0),
    ('nested_dynamic_view', GRID + 'if i >= 2 { ret }; view := grid[i][0..2]; view[0] = r; ' + GRID_READ, 0),
    ('nested_escaped_late_write', GRID + 'view := grid[0][0..2]; grid[0][0] = p; view[0] = r; ' + GRID_READ, 0),
    ('nested_known_zero_write', GRID + 'j: usize = 0; grid[0][j] = r; ' + GRID_READ, 0),
    ('nested_root_dynamic_write', GRID + 'if i >= 2 { ret }; grid[i] = [r, r]; ' + GRID_READ, 0),
    ('nested_literal_overwrite', GRID + 'grid[0][0] = r; ' + GRID_READ, 0),
    ('nested_sibling_borrow', GRID + 'mutate(grid[1], r); ' + GRID_READ, 6),
]

@pytest.mark.parametrize('name,body,expected', CASES, ids=[case[0] for case in CASES])
def test_exact_array_reference_lifetime(tmp_path, name, body, expected):
    source = tmp_path / (name + '.a7')
    output = tmp_path / (name + '.zig')
    source.write_text(HEADER + 'run :: fn(i: usize, flag: bool) { ' + SETUP + body + ' }\nmain :: fn() { run(0, true) }\n')
    result = subprocess.run([sys.executable, str(ROOT / 'main.py'), '--mode', 'compile', '--format', 'json', '-o', str(output), str(source)], capture_output=True, text=True)
    assert result.returncode == expected, result.stdout + result.stderr
    assert not result.stderr
    if expected == 6:
        diagnostic = json.loads(result.stdout)
        message = 'Reference not proven non-nil' if name == 'unguarded_index_unchanged' else 'Use after move or delete'
        assert message in str(diagnostic['error']), diagnostic
        assert not output.exists()
        if name in {'joined_write', 'branch_delete_slot', 'saved_slot_join', 'saved_slot_loop'}:
            assert diagnostic['error']['category'] == 'semantic'
            assert any(d['code'] == 'use_after_move' and d['file'] == str(source)
                       and d['span']['start_line'] == 4 for d in diagnostic['error']['details'])
    else:
        assert output.is_file()
        assert 'pub fn main' in output.read_text()
