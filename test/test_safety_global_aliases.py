import pytest
from conftest import expect_ok, expect_exit
HEADER='Box::struct{x:i32}\ng:ref Box\nh:ref Box\nset::fn(p:ref Box){g=p}\ndrop::fn(){del g}\n'
MAIN='main::fn(){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};'
CASES={
'saved_global':(6,'', 'set(p);saved:=g;drop();if saved!=nil{x:=saved.x}'),
'saved_global_distinct':(0,'', 'set(p);saved:=g;set(q);drop();if saved!=nil{x:=saved.x;del saved}'),
'argument_capture':(6,'replace::fn(p:ref Box) ref Box{g=p;ret p}\nconsume::fn(old:ref Box,newer:ref Box){del old}\n', 'set(p);if g!=nil{consume(g,replace(q))};x:=p.x'),
'argument_capture_distinct':(0,'replace::fn(p:ref Box) ref Box{g=p;ret p}\nconsume::fn(old:ref Box,newer:ref Box){del old}\n', 'set(p);if g!=nil{consume(g,replace(q))};x:=q.x;del q'),
'global_snapshot_after_args':(6,'replace::fn(p:ref Box) ref Box{g=p;ret p}\nconsume::fn(unused:ref Box){del g}\n', 'set(p);consume(replace(q));x:=q.x'),
'global_snapshot_keeps_old':(0,'replace::fn(p:ref Box) ref Box{g=p;ret p}\nconsume::fn(unused:ref Box){del g}\n', 'set(p);consume(replace(q));x:=p.x;del p'),
'conditional_no_store':(6,'maybe::fn(p:ref Box,flag:bool){if flag{g=p}}\n', 'set(p);maybe(q,false);drop();x:=p.x'),
'conditional_no_store_distinct':(0,'maybe::fn(p:ref Box,flag:bool){if flag{g=p}}\n', 'set(q);maybe(q,false);drop();x:=p.x;del p'),
'forward_delete':(6,'forward::fn(){drop()}\n', 'set(p);forward();x:=p.x'),
'deferred_delete':(6,'later::fn(){defer del g}\n', 'set(p);later();x:=p.x'),
'deferred_replacement':(0,'later::fn(){defer del g;g=new Box}\n', 'set(p);later();x:=p.x;del p;del q'),
'deferred_saved_delete':(6,'later::fn(){saved:=g;defer del saved;g=new Box}\n', 'set(p);later();x:=p.x'),
'distinct_globals':(0,'seth::fn(p:ref Box){h=p}\n', 'set(p);seth(q);drop();if h!=nil{x:=h.x;del h}'),
'distinct_global_deleted':(6,'seth::fn(p:ref Box){h=p}\n', 'set(p);seth(q);drop();x:=p.x'),
'local_shadow':(0,'shadow::fn(p:ref Box){g:=p;del g}\n', 'set(p);shadow(q);x:=p.x;del p'),
'local_shadow_deleted':(6,'shadow::fn(p:ref Box){g:=p;del g}\n', 'set(p);shadow(q);x:=q.x'),
'final_deleted_global':(6,'fresh_drop::fn(){g=new Box;del g}\n', 'fresh_drop();if g!=nil{x:=g.x}'),
'global_unallocated_entry':(6,'bad::fn(){drop();if g!=nil{x:=g.x}}\n', 'set(p);bad()'),
'forward_saved_return':(6,'old::fn() ref Box{saved:=g;g=new Box;ret saved}\nforward::fn() ref Box{ret old()}\n', 'set(p);saved:=forward();del p;if saved!=nil{x:=saved.x}'),
'parameter_global_distinct':(0,'kill_global::fn(unused:ref Box){del g}\n', 'set(q);kill_global(p);x:=p.x;del p'),
'parameter_global_alias':(6,'kill_global::fn(unused:ref Box){del g}\n', 'set(p);kill_global(p);x:=p.x'),
}
SOURCES={name:(expected,HEADER+extra+MAIN+body+'}') for name,(expected,extra,body) in CASES.items()}


@pytest.mark.parametrize("name", SOURCES)
def test_global_call_order_and_aliases(name, tmp_path):
    expected, source = SOURCES[name]
    if expected == 0:
        expect_ok(source, tmp_path)
    else:
        expect_exit(source, tmp_path, 6, "Use after move or delete")

GLOBAL_REPLACEMENTS = {'direct': (6, 'Box::struct{x:i32}\ng:ref Box\nset::fn(p:ref Box){g=p}\ndrop::fn(){del g}\nmain::fn(){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};set(p);drop();x:=p.x}'), 'distinct': (0, 'Box::struct{x:i32}\ng:ref Box\nset::fn(p:ref Box){g=p}\ndrop::fn(){del g}\nmain::fn(){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};set(q);drop();x:=p.x;del p}'), 'fresh_reassign': (0, 'Box::struct{x:i32}\ng:ref Box\nset::fn(p:ref Box){g=p}\nreplace::fn(){g=new Box}\ndrop::fn(){del g}\nmain::fn(){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};set(p);replace();drop();x:=p.x;del p;del q}'), 'fresh_store_then_delete': (0, 'Box::struct{x:i32}\ng:ref Box\nset::fn(p:ref Box){g=p}\nreplace_drop::fn(){g=new Box;del g}\nmain::fn(){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};set(p);replace_drop();x:=p.x;del p;del q}'), 'delete_then_fresh_store': (6, 'Box::struct{x:i32}\ng:ref Box\nset::fn(p:ref Box){g=p}\nrenew::fn(){del g;g=new Box}\nmain::fn(){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};set(p);renew();x:=p.x}'), 'delete_then_fresh_store_global_read': (0, 'Box::struct{x:i32}\ng:ref Box\nset::fn(p:ref Box){g=p}\nrenew::fn(){del g;g=new Box}\nmain::fn(){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};set(p);renew();if g!=nil{x:=g.x;del g};del q}'), 'returned_old_global': (6, 'Box::struct{x:i32}\ng:ref Box\nset::fn(p:ref Box){g=p}\nreplace::fn() ref Box{old:=g;g=new Box;ret old}\nmain::fn(){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};set(p);old:=replace();del p;if old!=nil{x:=old.x}}'), 'forwarded': (6, 'Box::struct{x:i32}\ng:ref Box\nset::fn(p:ref Box){g=p}\nforward::fn(p:ref Box){set(p)}\ndrop::fn(){del g}\nmain::fn(){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};forward(p);drop();x:=p.x}'), 'conditional_store': (6, 'Box::struct{x:i32}\ng:ref Box\nset::fn(p:ref Box,q:ref Box,flag:bool){g=if flag{p}else{q}}\ndrop::fn(){del g}\nmain::fn(){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};set(p,q,false);drop();x:=p.x}'), 'readonly': (0, 'Box::struct{x:i32}\ng:ref Box\nset::fn(p:ref Box){g=p}\nread::fn(){if g!=nil{x:=g.x}}\nmain::fn(){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};set(p);read();x:=p.x;del p;del q}')}

@pytest.mark.parametrize("name", GLOBAL_REPLACEMENTS)
def test_global_replacement_lifetime(name, tmp_path):
    expected, source = GLOBAL_REPLACEMENTS[name]
    if expected == 0:
        expect_ok(source, tmp_path)
    else:
        expect_exit(source, tmp_path, 6, "Use after move or delete")
