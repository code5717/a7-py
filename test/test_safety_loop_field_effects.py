"""Loop heads include direct parameter deletion through tracked reference fields.

Unsafe cases are compiled only. Readonly callees and unrelated allocations
must retain their existing accepted behavior.
"""

import pytest

from conftest import expect_exit, expect_ok

HEADER = '''io :: import "std/io"
Box :: struct { value: i32 }
Holder :: struct { ptr: ref Box; other: ref Box }
'''


def loop_program(callees, body, *, loop='while', before='', after=''):
    statement = ('while i<2 {' + body + ';i+=1}') if loop == 'while' else ('for item in [1,2] {' + body + '}')
    return HEADER + callees + '''
main :: fn(){
 b:=new Box;if b==nil {ret}
 c:=new Box;if c==nil {del b;ret}
 h:=Holder{ptr:b,other:c}
 i:usize=0
''' + before + statement + '\n' + after + '\n}\n'


@pytest.mark.parametrize('callee', [
    'drop :: fn(p:ref Box){del p}',
    'drop :: fn(p:ref Box){saved:=p;del saved}',
    'drop :: fn(p:ref Box){forward(p)}\nforward :: fn(p:ref Box){del p}',
])
def test_loop_field_direct_and_forwarded_parameter_deletion_is_rejected(tmp_path, callee):
    source = loop_program(callee, 'io.println("{}",h.ptr.value);drop(h.ptr)')
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


def test_loop_head_deletion_reaches_saved_alias_of_field(tmp_path):
    source = loop_program('drop :: fn(p:ref Box){del p}',
                          'io.println("{}",saved.value);drop(h.ptr)', before='saved:=h.ptr;')
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


@pytest.mark.parametrize('callee', [
    'visit :: fn(p:ref Box){io.println("{}",p.value)}',
    'visit :: fn(p:ref Box){local:=new Box;if local!=nil {del local}}',
    'visit :: fn(p:ref Box){local:=p;local=new Box;if local!=nil {del local}}',
])
def test_readonly_or_fresh_local_deletion_keeps_loop_field_live(tmp_path, callee):
    expect_ok(loop_program(callee, 'io.println("{}",h.ptr.value);visit(h.ptr)'), tmp_path)


def test_fresh_field_before_each_iteration_read_remains_valid(tmp_path):
    source = loop_program('drop :: fn(p:ref Box){del p}',
                          'h.ptr=new Box;if h.ptr==nil {ret};io.println("{}",h.ptr.value);drop(h.ptr)', after='del b')
    expect_ok(source, tmp_path)


@pytest.mark.parametrize('same_argument', [False, True])
def test_rebound_callee_alias_deletes_only_its_affected_parameter(tmp_path, same_argument):
    args = 'h.ptr,h.ptr' if same_argument else 'h.ptr,h.other'
    source = loop_program('drop :: fn(p:ref Box,q:ref Box){local:=p;local=q;del local}',
                          'h.other=new Box;if h.other==nil {ret};io.println("{}",h.ptr.value);drop(' + args + ')')
    if same_argument:
        expect_exit(source, tmp_path, 6, 'Use after move or delete')
    else:
        expect_ok(source, tmp_path)


def test_forwarded_parameter_positions_do_not_poison_other_field(tmp_path):
    callee = '''drop :: fn(p:ref Box,q:ref Box){forward(q,p)}
forward :: fn(first:ref Box,second:ref Box){del first}
'''
    source = loop_program(callee, 'h.other=new Box;if h.other==nil {ret};io.println("{}",h.ptr.value);drop(h.ptr,h.other)')
    expect_ok(source, tmp_path)


def test_deferred_field_argument_deletion_seeds_for_in_head(tmp_path):
    source = loop_program('drop :: fn(p:ref Box){del p}',
                          'io.println("{}",h.ptr.value);defer drop(h.ptr)', loop='for_in')
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


def test_nested_readonly_callee_keeps_declaration_identity(tmp_path):
    source = loop_program('visit :: fn(p:ref Box){del p}',
                          'io.println("{}",h.ptr.value);visit(h.ptr)',
                          before='visit :: fn(p:ref Box){io.println("{}",p.value)};')
    expect_ok(source, tmp_path)


def test_deleting_descendant_does_not_delete_reference_parameter_itself(tmp_path):
    source = '''io :: import "std/io"
Box :: struct {value:i32}
Holder :: struct {child:ref Box;value:i32}
Outer :: struct {holder:ref Holder}
clear :: fn(h:ref Holder){del h.child}
main :: fn(){
 h:=new Holder;if h==nil {ret}
 outer:=Outer{holder:h}
 i:usize=0
 while i<2 {
  outer.holder.child=new Box
  io.println("{}",outer.holder.value)
  clear(outer.holder)
  i+=1
 }
 del h
}
'''
    expect_ok(source, tmp_path)


@pytest.mark.parametrize('reference_capture', [False, True])
def test_later_argument_deletion_distinguishes_captured_value_from_reference(tmp_path, reference_capture):
    parameter = 'ref Box' if reference_capture else 'i32'
    read = 'p.value' if reference_capture else 'p'
    capture = 'h.ptr' if reference_capture else 'h.ptr.value'
    callees = ('take :: fn(p:' + parameter + ',n:i32){io.println("{}",' + read + ')}\n'
               'drop :: fn(p:ref Box) i32 {del p;ret 0}\n')
    source = loop_program(callees,
                          'h.ptr=new Box;if h.ptr==nil {ret};take(' + capture + ',drop(h.ptr))')
    if reference_capture:
        expect_exit(source, tmp_path, 6, 'Use after move or delete')
    else:
        expect_ok(source, tmp_path)


@pytest.mark.parametrize('reference_capture', [False, True])
def test_later_argument_replacement_does_not_retarget_captured_reference(tmp_path, reference_capture):
    parameter = 'ref Box' if reference_capture else 'i32'
    read = 'p.value' if reference_capture else 'p'
    capture = 'h.ptr' if reference_capture else 'h.ptr.value'
    callees = ('take :: fn(p:' + parameter + ',n:i32){io.println("{}",' + read + ')}\n'
               'replace :: fn(h:ref Holder,old:ref Box,fresh:ref Box) i32 {h.ptr=fresh;del old;ret 0}\n')
    source = loop_program(callees,
                          'h.ptr=new Box;if h.ptr==nil {ret};if h.other==nil {ret};take('
                          + capture + ',replace(h,h.ptr,h.other))')
    if reference_capture:
        expect_exit(source, tmp_path, 6, 'Use after move or delete')
    else:
        expect_ok(source, tmp_path)


def test_transferred_entry_allocation_is_deleted_without_poisoning_old_field_value(tmp_path):
    from conftest import compile_program, failure_text

    source = loop_program('drop :: fn(p:ref Box){del p}',
                          'io.println("{}",c.value);h.ptr=c;drop(h.ptr)', after='del b')
    result = compile_program(source, tmp_path)
    output = failure_text(result)
    assert result.exit_code == 6, output
    assert "'c' was moved or deleted" in output
    assert "'b' was moved or deleted" not in output


@pytest.mark.parametrize('keep_entry', [False, True])
def test_branch_field_replacement_joins_entry_origins(tmp_path, keep_entry):
    from conftest import compile_program, failure_text

    replacement = ('if flag {h.ptr=new Box}' if keep_entry
                   else 'if flag {h.ptr=new Box}else{h.ptr=new Box}')
    source = loop_program('drop :: fn(p:ref Box){del p}',
                          replacement + ';if h.ptr==nil {ret};drop(h.ptr)',
                          before='flag:=false;', after='del b')
    result = compile_program(source, tmp_path)
    output = failure_text(result)
    if keep_entry:
        assert result.exit_code == 6, output
        assert "'b' was moved or deleted" in output
    else:
        assert result.ok, output


def test_saved_entry_alias_survives_only_fresh_field_deletions(tmp_path):
    source = loop_program('drop :: fn(p:ref Box){del p}',
                          'h.ptr=new Box;if h.ptr==nil {ret};drop(h.ptr);io.println("{}",saved.value)',
                          before='saved:=h.ptr;', after='del saved')
    expect_ok(source, tmp_path)


@pytest.mark.parametrize('setter', [
    'replace :: fn(h:ref Holder){h.ptr=new Box}',
    'replace :: fn(h:ref Holder){local:=new Box;h.ptr=local}',
    'replace :: fn(h:ref Holder){forward(h)}\nforward :: fn(h:ref Holder){h.ptr=new Box}',
    'replace :: fn(h:ref Holder){if h.other!=nil {h.ptr=new Box;ret};h.ptr=new Box}',
])
def test_fresh_setter_preserves_original_allocation_cleanup(tmp_path, setter):
    source = loop_program(setter + '\ndrop :: fn(p:ref Box){del p}',
                          'replace(h);if h.ptr==nil{ret};io.println("{}",h.ptr.value);drop(h.ptr)', after='del b')
    expect_ok(source, tmp_path)


@pytest.mark.parametrize('setter', [
    'replace :: fn(h:ref Holder,p:ref Box){h.ptr=p}',
    'replace :: fn(h:ref Holder,p:ref Box){saved:=p;forward(h,saved)}\nforward :: fn(h:ref Holder,p:ref Box){h.ptr=p}',
])
def test_transfer_setter_reaches_transferred_allocation(tmp_path, setter):
    source = loop_program(setter + '\ndrop :: fn(p:ref Box){del p}',
                          'io.println("{}",c.value);replace(h,c);if h.ptr==nil{ret};drop(h.ptr)', after='del b')
    from conftest import compile_program, failure_text

    result = compile_program(source, tmp_path)
    output = failure_text(result)
    assert result.exit_code == 6, output
    assert "'c' was moved or deleted" in output
    assert "'b' was moved or deleted" not in output


@pytest.mark.parametrize('body', [
    'if h.other!=nil {h.ptr=new Box}',
    'if h.other!=nil {ret};h.ptr=new Box',
])
def test_conditional_setter_retains_old_origin_on_no_store_exit(tmp_path, body):
    source = loop_program('replace :: fn(h:ref Holder){' + body + '}\ndrop :: fn(p:ref Box){del p}',
                          'replace(h);if h.ptr==nil{ret};drop(h.ptr)', after='del b')
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


@pytest.mark.parametrize('capture_old', [False, True])
def test_setter_uses_value_captured_before_later_argument_replacement(tmp_path, capture_old):
    from conftest import compile_program, failure_text

    callees = '''set :: fn(h:ref Holder,p:ref Box,n:i32){h.ptr=p}
replace :: fn(h:ref Holder) i32 {h.ptr=new Box;ret 0}
drop :: fn(p:ref Box){del p}
'''
    # A saved alias retains b even when a later argument replaces h.ptr.
    value = 'saved' if capture_old else 'h.ptr'
    prefix = '' if capture_old else 'h.ptr=new Box;if h.ptr==nil{ret};'
    source = loop_program(callees, prefix + 'set(h,' + value + ',replace(h));if h.ptr==nil{ret};drop(h.ptr)',
                          before='saved:=h.ptr;', after='del b')
    result = compile_program(source, tmp_path)
    output = failure_text(result)
    if capture_old:
        assert result.exit_code == 6, output
        assert "'b' was moved or deleted" in output
    else:
        assert result.ok, output


@pytest.mark.parametrize('iterations,read_deleted', [(1, False), (1, True), (2, False)])
def test_single_iteration_has_no_deletion_backedge_but_keeps_exit_effect(tmp_path, iterations, read_deleted):
    callees = 'set :: fn(h:ref Holder,p:ref Box){h.ptr=p}\ndrop :: fn(p:ref Box){del p}'
    after = 'if c!=nil {io.println("{}",c.value)}' if read_deleted else 'io.println("{}",b.value);del b'
    source = loop_program(callees, 'if c==nil{ret};set(h,c);if h.ptr==nil{ret};drop(h.ptr)', after=after)
    source = source.replace('while i<2', 'while i<' + str(iterations))
    if iterations > 1 or read_deleted:
        expect_exit(source, tmp_path, 6, 'Use after move or delete')
    else:
        expect_ok(source, tmp_path)


@pytest.mark.parametrize('change', ['continue', 'i=0', 'reset()', 'borrowed'])
def test_single_iteration_proof_refuses_bypassed_or_mutated_counter(tmp_path, change):
    declarations = 'drop :: fn(p:ref Box){del p}\nborrow :: fn(p:ref usize) ref usize {ret p}\nmutate :: fn(p:ref usize){zero:usize=0;p=zero}'
    before = 'reset :: fn(){i=0};' if change == 'reset()' else ''
    if change == 'continue':
        change = 'if i==0 {continue}'
    if change == 'borrowed':
        before = 'alias:=borrow(i);'
        change = 'if alias!=nil {mutate(alias)}'
    source = loop_program(declarations, 'io.println("{}",h.ptr.value);drop(h.ptr);' + change,
                          before=before).replace('while i<2', 'while i<1')
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


def test_wrapping_counter_does_not_prove_a_single_iteration(tmp_path):
    source = loop_program('drop :: fn(p:ref Box){del p}', 'io.println("{}",h.ptr.value);drop(h.ptr)')
    source = source.replace('i:usize=0', 'i:u8=254').replace('while i<2', 'while i<255').replace('i+=1', 'i+=2')
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


@pytest.mark.parametrize('expression,argument', [
    ('flag and fresh(h)', 'false'),
    ('flag or fresh(h)', 'true'),
    ('if flag {fresh(h)} else {false}', 'false'),
    ('match flag {case true: fresh(h) else: false}', 'false'),
])
def test_conditional_setter_cannot_hide_old_child_deletion(tmp_path, expression, argument):
    callees = '''fresh :: fn(h:ref Holder)bool {h.ptr=new Box;ret true}
maybe :: fn(h:ref Holder,flag:bool){unused:=''' + expression + '''}
drop :: fn(p:ref Box){del p}
'''
    source = loop_program(callees,
                          'maybe(h,' + argument + ');if h.ptr==nil{ret};'
                          'io.println("{}",h.ptr.value);drop(h.ptr)')
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


@pytest.mark.parametrize('expression', [
    'true and fresh(h)',
    'false or fresh(h)',
    'if true {fresh(h)} else {false}',
    'fresh(h) and false',
    'if fresh(h) {true} else {false}',
    'match fresh(h) {case true: true else: false}',
    'match flag {case true: fresh(h) else: fresh(h)}',
])
def test_mandatory_expression_setter_preserves_original_allocation(tmp_path, expression):
    callees = '''fresh :: fn(h:ref Holder)bool {h.ptr=new Box;ret true}
replace :: fn(h:ref Holder,flag:bool){unused:=''' + expression + '''}
drop :: fn(p:ref Box){del p}
'''
    source = loop_program(callees,
                          'replace(h,false);if h.ptr==nil{ret};'
                          'io.println("{}",h.ptr.value);drop(h.ptr)', after='del b;del c')
    expect_ok(source, tmp_path)


@pytest.mark.parametrize('statement', [
    'if fresh(h) {}',
    'match fresh(h) {case true: {} else: {}}',
])
def test_statement_condition_setter_precedes_both_branch_snapshots(tmp_path, statement):
    callees = '''fresh :: fn(h:ref Holder)bool {h.ptr=new Box;ret true}
replace :: fn(h:ref Holder){''' + statement + '''}
drop :: fn(p:ref Box){del p}
'''
    source = loop_program(callees,
                          'replace(h);if h.ptr==nil{ret};'
                          'io.println("{}",h.ptr.value);drop(h.ptr)', after='del b;del c')
    expect_ok(source, tmp_path)
