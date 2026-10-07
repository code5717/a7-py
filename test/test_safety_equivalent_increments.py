import pytest

from conftest import expect_exit, expect_ok


def program(update, *, counter='i:usize=0', guard='i<1', after='', declarations=''):
    return ('Box::struct{value:i32}\n' + declarations + '\n'
            'check::fn(flag:bool){b:=new Box;if b==nil{ret};' + counter + ';while ' + guard +
            '{v:=b.value;del b;' + update + '};' + after + '}\nmain::fn(){check(false)}')


@pytest.mark.parametrize('update,guard', [
    ('if flag{i+=1;continue};i+=1', 'i<1'),
    ('if flag{i+=1}else{i+=2}', 'i<1'),
    ('i+=1;i+=1', 'i<2'),
    ('i+=3', 'i<3'),
    ('if flag{defer i+=1;continue};i+=1', 'i<1'),
    ('defer i+=1;if flag{continue}', 'i<1'),
    ('j:usize=0;while j<1{j+=1;continue};if flag{i+=1;continue};i+=1', 'i<1'),
    ('if flag{i:usize=0;i+=2};i+=1', 'i<1'),
])
def test_every_backedge_crosses_guard(update, guard, tmp_path):
    expect_ok(program(update, guard=guard), tmp_path)


@pytest.mark.parametrize('update,guard', [
    ('if flag{continue};i+=1', 'i<1'),
    ('if flag{i+=1;continue};i+=1', 'i<2'),
    ('if flag{i+=1}else{i+=2}', 'i<2'),
    ('i+=3', 'i<4'),
    ('if flag{continue};defer i+=1', 'i<1'),
    ('if flag{i:usize=0;i+=1;continue};i+=1', 'i<1'),
])
def test_missing_or_insufficient_backedge_delta_still_rejects(update, guard, tmp_path):
    expect_exit(program(update, guard=guard), tmp_path, 6, 'Use after move or delete')


@pytest.mark.parametrize('counter,guard,update,expected', [
    ('i:i8=125', 'i<126', 'if flag{i+=1}else{i+=2}', 0),
    ('i:i8=126', 'i<127', 'if flag{i+=1}else{i+=2}', 6),
    ('i:u8=253', 'i<=253', 'i+=1;i+=1', 0),
    ('i:u8=254', 'i<=254', 'i+=1;i+=1', 6),
    ('i:i8=-2', 'i<0', 'if flag{i+=2}else{i+=3}', 0),
])
def test_all_intermediate_and_final_counter_values_fit(counter, guard, update, expected, tmp_path):
    source = program(update, counter=counter, guard=guard)
    if expected == 0:
        expect_ok(source, tmp_path)
    else:
        expect_exit(source, tmp_path, 6, 'Use after move or delete')


def test_proof_does_not_restore_deleted_value_after_loop(tmp_path):
    expect_exit(program('if flag{i+=1;continue};i+=1', after='v:=b.value'),
                tmp_path, 6, 'Use after move or delete')


def test_labeled_continue_runs_outer_deferred_update(tmp_path):
    source = program('defer i+=1;j:usize=0;while j<1{continue outer}')
    source = source.replace('while i<1', '@outer while i<1')
    expect_ok(source, tmp_path)


def test_labeled_continue_bypasses_outer_deferred_update(tmp_path):
    source = program('j:usize=0;while j<1{continue outer};defer i+=1')
    source = source.replace('while i<1', '@outer while i<1')
    expect_exit(source, tmp_path, 6, 'Use after move or delete')


def test_for_continue_still_runs_update(tmp_path):
    source = program('if flag{continue}').replace('i:usize=0;while i<1', 'for i:=0;i<1;i+=1')
    expect_ok(source, tmp_path)


@pytest.mark.parametrize('update', ['i=0;i+=1', 'j:usize=0;while j<1{i+=1;j+=1};i+=1'])
def test_existing_unsupported_counter_updates_remain_unproven(update, tmp_path):
    # This patch proves direct positive increments, not replacement or nested writes.
    expect_exit(program(update), tmp_path, 6, 'Use after move or delete')


def test_indirect_callee_counter_reset_cannot_prove_one_trip(tmp_path):
    source = program('action();i+=1').replace(
        'i:usize=0;', 'i:usize=0;reset::fn(){i=0};action:=reset;')
    expect_exit(source, tmp_path, 6, 'Use after move or delete')
