"""Known callees replay reference effects with actual caller aliases."""

import pytest

from conftest import expect_exit, expect_ok

HEADER = '''io :: import "std/io"
Box :: struct { value: i32 }
Holder :: struct { child: ref Box; sibling: ref Box }
'''


@pytest.mark.parametrize("body", [
    "h.child = p",
    "local := h; local.child = p",
    "defer h.child = p",
    "if flag { h.child = p }",
    "if flag { defer h.child = p; ret }; h.child = p",
])
def test_replacement_transfers_identity(tmp_path, body):
    source = HEADER + "set :: fn(h:ref Holder,p:ref Box,flag:bool){" + body + "}\n" + '''
main :: fn(){
 b:=new Box; if b==nil {ret}
 c:=new Box; if c==nil {del b;ret}
 h:=Holder{child:b,sibling:nil}
 set(h,c,true)
 del c
 if h.child!=nil {io.println("{}",h.child.value)}
 del b
}
'''
    expect_exit(source, tmp_path, 6, "deleted")


@pytest.mark.parametrize("body", ["del h.child", "local:=h;del local.child", "defer del h.child"])
def test_borrowed_child_delete_poisons_saved_alias(tmp_path, body):
    source = HEADER + "clear :: fn(h:ref Holder){" + body + "}\n" + '''
main :: fn(){
 b:=new Box; if b==nil {ret}
 h:=Holder{child:b,sibling:nil}
 clear(h)
 io.println("{}",b.value)
}
'''
    expect_exit(source, tmp_path, 6, "deleted")


def test_child_delete_preserves_explicit_parent_and_sibling(tmp_path):
    source = HEADER + '''
clear :: fn(h:ref Holder){del h.child}
main :: fn(){
 a:=new Box; if a==nil {ret}
 b:=new Box; if b==nil {del a;ret}
 h:=new Holder; if h==nil {del a;del b;ret}
 h.child=a;h.sibling=b
 clear(h)
 if h.sibling!=nil {io.println("{}",h.sibling.value)}
 del b;del h
}
'''
    expect_ok(source, tmp_path)


@pytest.mark.parametrize("body", [
    'del a;io.println("{}",b.value)',
    'del a;del b',
])
def test_actual_argument_aliases_recheck_lifetime_uses(tmp_path, body):
    source = HEADER + "bad :: fn(a:ref Box,b:ref Box){" + body + "}\n" + '''
main :: fn(){p:=new Box;if p==nil {ret};bad(p,p)}
'''
    expect_exit(source, tmp_path, 6, "deleted")


def test_reads_before_delete_preserve_same_actual_alias(tmp_path):
    source = HEADER + '''
read_then_drop :: fn(a:ref Box,b:ref Box){io.println("{} {}",a.value,b.value);del a}
main :: fn(){p:=new Box;if p==nil {ret};read_then_drop(p,p)}
'''
    expect_ok(source, tmp_path)


@pytest.mark.parametrize("same", [False, True])
def test_actual_alias_write_rechecks_guard(tmp_path, same):
    source = HEADER + '''
change :: fn(a:ref Holder,b:ref Holder){
 if a.child!=nil {b.child=nil;io.println("{}",a.child.value)}
}
main :: fn(){
 p:=new Box;if p==nil {ret}
 a:=Holder{child:p,sibling:nil}
 b:=Holder{child:nil,sibling:nil}
 change(a,''' + ("a" if same else "b") + ''')
 del p
}
'''
    if same:
        expect_exit(source, tmp_path, 6, "Reference not proven non-nil")
    else:
        expect_ok(source, tmp_path)


@pytest.mark.parametrize("reversed_order", [False, True])
def test_deferred_delete_and_replacement_order(tmp_path, reversed_order):
    body = "defer h.child=p;defer del h.child" if not reversed_order else "defer del h.child;defer h.child=p"
    source = HEADER + "change :: fn(h:ref Holder,p:ref Box){" + body + "}\n" + '''
main :: fn(){
 a:=new Box;if a==nil {ret}
 b:=new Box;if b==nil {del a;ret}
 h:=Holder{child:a,sibling:nil}
 change(h,b)
 if h.child!=nil {io.println("{}",h.child.value)}
}
'''
    if reversed_order:
        expect_exit(source, tmp_path, 6, "deleted")
    else:
        expect_ok(source, tmp_path)


def test_forwarded_replacement_keeps_old_alias_alive(tmp_path):
    source = HEADER + '''
forward :: fn(h:ref Holder,p:ref Box){set(h,p)}
set :: fn(h:ref Holder,p:ref Box){h.child=p}
main :: fn(){
 a:=new Box;if a==nil {ret}
 b:=new Box;if b==nil {del a;ret}
 h:=Holder{child:a,sibling:nil}
 forward(h,b)
 io.println("{}",a.value)
 if h.child!=nil {io.println("{}",h.child.value)}
 del a;del b
}
'''
    expect_ok(source, tmp_path)


@pytest.mark.parametrize("reference", [False, True])
def test_nested_call_cannot_revive_captured_reference(tmp_path, reference):
    take = 'take :: fn(p:ref Box,n:i32){io.println("{}",p.value)}' if reference else 'take :: fn(p:i32,n:i32){io.println("{}",p)}'
    source = HEADER + take + '''
drop :: fn(p:ref Box) i32 {del p;ret 0}
main :: fn(){p:=new Box;if p==nil {ret};take(''' + ("p" if reference else "p.value") + ''',drop(p))}
'''
    if reference:
        expect_exit(source, tmp_path, 6, "deleted")
    else:
        expect_ok(source, tmp_path)


@pytest.mark.parametrize("forwarded", ["direct", "call", "defer"])
def test_multiple_conditional_occurrences_are_explicitly_incomplete(tmp_path, monkeypatch, forwarded):
    from a7.passes.safety import SafetyProofPass

    observed = {}
    original = SafetyProofPass._classify_exact_effects

    def record_classification(self, bodies):
        original(self, bodies)
        observed.update({name: set(reasons) for name, reasons in self.exact_effect_reasons.items()})

    monkeypatch.setattr(SafetyProofPass, "_classify_exact_effects", record_classification)
    statement = {"direct": 'if flag { io.println("{}",h.value) };', "call": "read(h,flag);", "defer": "defer read(h,flag);"}[forwarded]
    body = statement * 25
    source = HEADER + '''
read :: fn(h:ref Box,flag:bool){if flag {io.println("{}",h.value)}}
''' + "many :: fn(h:ref Box,flag:bool){" + body + "}\n" + '''
main :: fn(){p:=new Box;if p==nil {ret};many(p,false);del p}
'''
    expect_ok(source, tmp_path)
    assert "more than one transitive conditional occurrence" in observed["many"]
    assert not observed["read"]


def test_exact_effect_valid_controls_native(tmp_path, zig):
    from conftest import run_all_profiles

    source = HEADER + '''
forward :: fn(h:ref Holder,p:ref Box){set(h,p)}
set :: fn(h:ref Holder,p:ref Box){h.child=p}
clear :: fn(h:ref Holder){del h.child}
read_then_drop :: fn(a:ref Box,b:ref Box){io.println("{} {}",a.value,b.value);del a}
main :: fn(){
 a:=new Box;if a==nil {ret}
 b:=new Box;if b==nil {del a;ret}
 c:=new Box;if c==nil {del a;del b;ret}
 h:=new Holder;if h==nil {del a;del b;del c;ret}
 a.value=11;b.value=22;c.value=33
 h.child=a;h.sibling=b
 forward(h,c)
 io.println("{}",a.value)
 if h.child!=nil {io.println("{}",h.child.value)}
 del a
 clear(h)
 if h.sibling!=nil {io.println("{}",h.sibling.value)}
 fresh:=new Box
 if fresh==nil {del b;del h;ret}
 fresh.value=44
 set(h,fresh)
 if h.child!=nil {io.println("{}",h.child.value)}
 del fresh;del b;del h
 p:=new Box;if p==nil {ret}
 p.value=55
 read_then_drop(p,p)
}
'''
    assert run_all_profiles(source, tmp_path, zig) == "11\n33\n22\n44\n55 55\n"


@pytest.mark.parametrize("same", [False, True])
def test_nested_call_argument_rechecks_nonnil_after_alias_write(tmp_path, same):
    source = HEADER + '''
noop :: fn(p:ref Box) {}
change :: fn(a:ref Holder,b:ref Holder){
 if a.child!=nil {b.child=nil;noop(a.child)}
}
main :: fn(){
 p:=new Box;if p==nil {ret}
 a:=Holder{child:p,sibling:nil}
 b:=Holder{child:nil,sibling:nil}
 change(a,''' + ("a" if same else "b") + ''')
 del p
}
'''
    if same:
        expect_exit(source, tmp_path, 6, "Reference not proven non-nil")
    else:
        expect_ok(source, tmp_path)


@pytest.mark.parametrize("deletes", [False, True])
def test_nested_function_global_effects_use_declaration_identity(tmp_path, deletes):
    body = "del global" if deletes else 'if global!=nil {io.println("{}",global.value)}'
    source = HEADER + '''
global: ref Box = nil
inner :: fn(){del global}
change :: fn(){
 inner :: fn(){''' + body + '''}
 inner()
}
main :: fn(){
 global=new Box
 c:=global
 if c==nil {ret}
 change()
 io.println("{}",c.value)
''' + ("" if deletes else "del c") + '''
}
'''
    if deletes:
        expect_exit(source, tmp_path, 6, "deleted")
    else:
        expect_ok(source, tmp_path)


@pytest.mark.parametrize("nested_argument", [False, True])
def test_global_deletion_occurs_after_arguments(tmp_path, nested_argument):
    source = HEADER + '''
global: ref Box = nil
print_and_drop :: fn(v:i32){io.println("{}",v);del global}
read :: fn(p:ref Box) i32 {ret p.value}
main :: fn(){
 global=new Box
 c:=global
 if c==nil {ret}
 print_and_drop(''' + ("read(c)" if nested_argument else "c.value") + ''')
}
'''
    expect_ok(source, tmp_path)


@pytest.mark.parametrize("mutates", [False, True])
def test_argument_effects_revalidate_exact_call_eligibility(tmp_path, mutates):
    body = "h.child=nil" if mutates else 'if h.child!=nil {io.println("{}",h.child.value)}'
    source = HEADER + '''
Slot :: struct {target:ref Holder}
select :: fn(s:ref Slot,p:ref Holder,flag:bool) i32 {if flag {s.target=p};ret 0}
clear :: fn(n:i32,h:ref Holder){''' + body + '''}
main :: fn(){
 x:=new Box;if x==nil {ret}
 a:=new Holder;if a==nil {del x;ret};a.child=x
 b:=new Holder;if b==nil {del a;del x;ret};b.child=x
 s:=Slot{target:a}
 if b.child!=nil {clear(select(s,b,true),s.target);io.println("{}",b.child.value)}
 del a;del b;del x
}
'''
    if mutates:
        expect_exit(source, tmp_path, 6, "Reference not proven non-nil")
    else:
        expect_ok(source, tmp_path)


def test_nested_global_effect_order_native(tmp_path, zig):
    from conftest import run_all_profiles

    source = HEADER + '''
global: ref Box = nil
read :: fn(){
 inner :: fn(){if global!=nil {io.println("{}",global.value)}}
 inner()
}
print_and_drop :: fn(v:i32){io.println("{}",v);del global}
main :: fn(){
 global=new Box
 c:=global
 if c==nil {ret}
 c.value=73
 read()
 print_and_drop(c.value)
}
'''
    assert run_all_profiles(source, tmp_path, zig) == "73\n73\n"


@pytest.mark.parametrize("deferred", [False, True])
def test_doubled_call_chain_has_source_sized_replay_bound(tmp_path, monkeypatch, deferred):
    from a7.passes.safety import SafetyProofPass

    observed = {}
    original = SafetyProofPass._classify_exact_effects

    def record_bound(self, bodies):
        original(self, bodies)
        observed["reasons"] = self.exact_effect_reasons
        observed["work"] = self.exact_effect_work
        observed["budget"] = self.exact_effect_work_budget

    monkeypatch.setattr(SafetyProofPass, "_classify_exact_effects", record_bound)
    prefix = "defer " if deferred else ""
    declarations = ["f0 :: fn() {}"]
    for index in range(1, 25):
        call = f"{prefix}f{index - 1}();"
        declarations.append(f"f{index} :: fn() {{ {call} {call} }}")
    source = "\n".join(declarations) + "\nmain :: fn(){f24()}\n"
    expect_ok(source, tmp_path)
    reason = "transitive effect expansion exceeds source-sized work budget"
    assert reason in observed["reasons"]["f24"]
    assert not observed["reasons"]["f1"]
    assert all(count <= observed["budget"] + 1 for count in observed["work"].values())


def test_later_argument_revalidates_captured_object_descendants(tmp_path):
    source = HEADER + '''
select :: fn(h:ref Holder,p:ref Box,flag:bool) i32 {if flag {h.child=p};ret 0}
clear :: fn(h:ref Holder,n:i32){h.child=nil}
main :: fn(){
 a:=new Box;if a==nil {ret}
 b:=new Box;if b==nil {del a;ret}
 h:=new Holder;if h==nil {del a;del b;ret}
 h.child=a
 if h.child!=nil {clear(h,select(h,b,true));io.println("{}",h.child.value)}
 del a;del b;del h
}
'''
    expect_exit(source, tmp_path, 6, "Reference not proven non-nil")


def joined_holder_program(operation, *, selected='a', field='child'):
    return HEADER + '''
clear :: fn(h:ref Holder){del h.child}
read :: fn(h:ref Holder){if h.child!=nil {io.println("{}",h.child.value)}}
main :: fn(){
 x:=new Box;if x==nil {ret}
 y:=new Box;if y==nil {del x;ret}
 z:=new Box;if z==nil {del x;del y;ret}
 a:=new Holder;if a==nil {del x;del y;del z;ret}
 b:=new Holder;if b==nil {del a;del x;del y;del z;ret}
 a.child=x;b.child=y;a.sibling=z;b.sibling=z
 selected:=''' + selected + '''
 flag:=false
 if flag {selected=b}
 if selected.''' + field + '''!=nil {''' + operation + '''}
 del a;del b
}
'''


@pytest.mark.parametrize('operation', [
    'clear(a);io.println("{}",selected.child.value)',
    'saved:=selected.child;if saved!=nil {clear(a);io.println("{}",saved.value)}',
    'saved:=selected.child;if saved!=nil {clear(a);a.child=z;io.println("{}",saved.value)}',
])
def test_exact_delete_reaches_joined_caller_child_alias(tmp_path, operation):
    expect_exit(joined_holder_program(operation), tmp_path, 6, 'deleted')


@pytest.mark.parametrize('operation,field', [
    ('io.println("{}",selected.child.value);clear(a)', 'child'),
    ('read(a);io.println("{}",selected.child.value)', 'child'),
    ('clear(a);a.child=z;io.println("{}",selected.child.value)', 'child'),
    ('clear(a);io.println("{}",selected.sibling.value)', 'sibling'),
])
def test_exact_delete_preserves_joined_read_order_and_other_children(tmp_path, operation, field):
    expect_ok(joined_holder_program(operation, field=field), tmp_path)


@pytest.mark.parametrize('shared_child', [False, True])
def test_exact_delete_distinguishes_unrelated_holder_children(tmp_path, shared_child):
    source = joined_holder_program('clear(a);io.println("{}",selected.child.value)', selected='b')
    source = source.replace('flag:=false',
                            'other:=new Holder;if other==nil {del a;del b;ret};other.child=z;flag:=false')
    source = source.replace('if flag {selected=b}', 'if flag {selected=other}')
    source = source.replace('del a;del b\n}', 'del a;del b;del other\n}')
    if shared_child:
        source = source.replace('b.child=y', 'b.child=x')
        expect_exit(source, tmp_path, 6, 'deleted')
    else:
        expect_ok(source, tmp_path)


def test_exact_delete_reaches_joined_child_with_unknown_other_holder(tmp_path):
    source = joined_holder_program('clear(a);io.println("{}",selected.child.value)')
    expect_exit(source.replace('b.child=y;', ''), tmp_path, 6, 'deleted')


@pytest.mark.parametrize('depth,guarded', [(2, False), (3, False), (3, True)])
def test_modest_doubling_chain_budget_has_conservative_behavior(tmp_path, depth, guarded):
    declarations = ['f0 :: fn(h:ref Holder,p:ref Box){h.child=p}']
    for index in range(1, depth + 1):
        call = f'f{index - 1}(h,p);'
        declarations.append(f'f{index} :: fn(h:ref Holder,p:ref Box){{{call}{call}}}')
    read = 'io.println("{}",h.child.value)'
    if guarded:
        read = 'if h.child!=nil {' + read + '}'
    source = HEADER + '\n'.join(declarations) + '''
main :: fn(){
 p:=new Box;if p==nil {ret}
 y:=new Box;if y==nil {del p;ret}
 h:=new Holder;if h==nil {del p;del y;ret}
 h.sibling=y
 f''' + str(depth) + '''(h,p)
 ''' + read + '''
 del y;del h;del p
}
'''
    # This concrete source crosses the source-sized budget between depth 2
    # and 3. The fallback requires a caller guard; it is not a depth-24 limit.
    if depth == 3 and not guarded:
        expect_exit(source, tmp_path, 6, 'Reference not proven non-nil')
    else:
        expect_ok(source, tmp_path)


@pytest.mark.parametrize('selection,deleted', [
    ('''p:=a;q:=b;flag:=false;if flag {p=b;q=a}
if p.child!=nil {del p.child}
if q.child!=nil {io.println("{}",q.child.value);del q.child}''', False),
    ('''p:=a;flag:=false;if flag {p=b}
if p.child!=nil {del p.child}
p.child=z
if p.child!=nil {io.println("{}",p.child.value)}''', False),
    ('''p:=a;flag:=false;if flag {p=b}
p.child=z;del z
if p.child!=nil {io.println("{}",p.child.value)}''', True),
], ids=['complementary-selections', 'fresh-selected-store', 'deleted-selected-store'])
def test_selected_child_effects_keep_explicit_stores_and_selection_identity(tmp_path, selection, deleted):
    prefix = joined_holder_program('').split(' selected:=a')[0]
    source = prefix + selection + '\n del a;del b\n}\n'
    if deleted:
        expect_exit(source, tmp_path, 6, 'deleted')
    else:
        expect_ok(source, tmp_path)


@pytest.mark.parametrize('read_before', [False, True])
def test_saved_selected_child_dependencies_are_checked_inside_replay(tmp_path, read_before):
    read = 'io.println("{}",p.value);'
    delete = 'clear(h);'
    body = read + delete if read_before else delete + read
    source = joined_holder_program('consume(selected.child,a)')
    source = source.replace('main :: fn()',
                            'consume :: fn(p:ref Box,h:ref Holder){' + body + '}\nmain :: fn()')
    if read_before:
        expect_ok(source, tmp_path)
    else:
        expect_exit(source, tmp_path, 6, 'deleted')


@pytest.mark.parametrize('fresh', [False, True])
def test_saved_selected_child_join_retains_dependencies_until_replaced(tmp_path, fresh):
    operation = 'saved:=selected.child;if flag {saved=z};'
    if fresh:
        operation += 'saved=z;'
    operation += 'clear(a);if saved!=nil {io.println("{}",saved.value)}'
    if fresh:
        expect_ok(joined_holder_program(operation), tmp_path)
    else:
        expect_exit(joined_holder_program(operation), tmp_path, 6, 'deleted')


def test_record_copy_retains_saved_selected_child_dependencies(tmp_path):
    operation = '''record:=Holder{child:selected.child,sibling:nil};copy:=record;
clear(a);if copy.child!=nil {io.println("{}",copy.child.value)}'''
    expect_exit(joined_holder_program(operation), tmp_path, 6, 'deleted')
