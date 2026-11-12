"""Initialized primitive stores retain alias proof and preserve expression effects."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
CASES = [('readonly_entry_loop',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};j:usize=0;while j<3{observe(n);j+=1}}\n'
  'run::fn(flag:bool,other:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' q:=new Box;if q==nil{del p;ret};q.value=17\n'
  ' r:=p\n'
  ' if flag{r=q}\n'
  ' i:usize=0\n'
  ' while flag{if other{if i==1{break}}else{if i==1{break}};del p;i+=1;wrap(i)}\n'
  ' if r!=nil{io.println("{}",r.value)}\n'
  ' if !flag{del p}\n'
  ' del q\n'
  '}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0,
  None),
 ('readonly_deferred_loop',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};j:usize=0;while j<3{defer observe(n);j+=1}}\n'
  'run::fn(flag:bool,other:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' q:=new Box;if q==nil{del p;ret};q.value=17\n'
  ' r:=p\n'
  ' if flag{r=q}\n'
  ' i:usize=0\n'
  ' while flag{if other{if i==1{break}}else{if i==1{break}};del p;i+=1;wrap(i)}\n'
  ' if r!=nil{io.println("{}",r.value)}\n'
  ' if !flag{del p}\n'
  ' del q\n'
  '}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0,
  None),
 ('returned_readonly',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'observe::fn(n:ref usize){}\n'
  'borrow::fn(n:ref usize) ref usize{ret n}\n'
  'run::fn(flag:bool,other:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' q:=new Box;if q==nil{del p;ret};q.value=17\n'
  ' r:=p\n'
  ' if flag{r=q}\n'
  ' i:usize=0\n'
  ' while flag{if other{if i==1{break}}else{if i==1{break}};del p;i+=1;a:=borrow(i);if '
  'a!=nil{observe(a)}}\n'
  ' if r!=nil{io.println("{}",r.value)}\n'
  ' if !flag{del p}\n'
  ' del q\n'
  '}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0,
  None),
 ('local_alias_entry_guard',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};a:=n;j:usize=0;while j<3{observe(a);j+=1}}\n'
  'run::fn(flag:bool,other:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' q:=new Box;if q==nil{del p;ret};q.value=17\n'
  ' r:=p\n'
  ' if flag{r=q}\n'
  ' i:usize=0\n'
  ' while flag{if other{if i==1{break}}else{if i==1{break}};del p;i+=1;wrap(i)}\n'
  ' if r!=nil{io.println("{}",r.value)}\n'
  ' if !flag{del p}\n'
  ' del q\n'
  '}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0,
  None),
 ('alias_overwrite_distinct',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'wrap::fn(n:ref usize,m:ref usize){a:=n;a=m;reset(a)}\n'
  'run::fn(flag:bool,other:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' q:=new Box;if q==nil{del p;ret};q.value=17\n'
  ' r:=p\n'
  ' if flag{r=q}\n'
  ' i:usize=0\n'
  ' while flag{if other{if i==1{break}}else{if i==1{break}};del p;i+=1;j:usize=0;wrap(i,j)}\n'
  ' if r!=nil{io.println("{}",r.value)}\n'
  ' if !flag{del p}\n'
  ' del q\n'
  '}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0,
  None),
 ('graph_lifo_rebind_before_reset',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'wrap::fn(n:ref usize,m:ref usize){a:=n;defer reset(a);defer a=m}\n'
  'run::fn(flag:bool,other:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' q:=new Box;if q==nil{del p;ret};q.value=17\n'
  ' r:=p\n'
  ' if flag{r=q}\n'
  ' i:usize=0\n'
  ' while flag{if other{if i==1{break}}else{if i==1{break}};del p;i+=1;j:usize=0;wrap(i,j)}\n'
  ' if r!=nil{io.println("{}",r.value)}\n'
  ' if !flag{del p}\n'
  ' del q\n'
  '}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0,
  None),
 ('graph_nested_return_readonly',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'observe::fn(n:ref usize){}\n'
  'borrow::fn(n:ref usize) ref usize{ret n}\n'
  'forward::fn(n:ref usize) ref usize{ret borrow(n)}\n'
  'run::fn(flag:bool,other:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' q:=new Box;if q==nil{del p;ret};q.value=17\n'
  ' r:=p\n'
  ' if flag{r=q}\n'
  ' i:usize=0\n'
  ' while flag{if other{if i==1{break}}else{if i==1{break}};del p;i+=1;a:=forward(i);if '
  'a!=nil{observe(a)}}\n'
  ' if r!=nil{io.println("{}",r.value)}\n'
  ' if !flag{del p}\n'
  ' del q\n'
  '}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0,
  None),
 ('stdlib_guarded_readonly_print',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'observe::fn(n:ref usize){}\n'
  'run::fn(flag:bool,other:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' q:=new Box;if q==nil{del p;ret};q.value=17\n'
  ' r:=p\n'
  ' if flag{r=q}\n'
  ' i:usize=0\n'
  ' while flag{if other{if i==1{break}}else{if i==2{break}};del p;if '
  'other{i=1}else{i=2};observe(i);io.println("counter {}",i)}\n'
  ' if r!=nil{io.println("{}",r.value)}\n'
  ' if !flag{del p}\n'
  ' del q\n'
  '}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0,
  None),
 ('stdlib_deferred_counter_print',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'run::fn(flag:bool,other:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' q:=new Box;if q==nil{del p;ret};q.value=17\n'
  ' r:=p\n'
  ' if flag{r=q}\n'
  ' i:usize=0\n'
  ' while flag{if other{if i==1{break}}else{if i==1{break}};del p;defer io.println("counter '
  '{}",i);defer i+=1;continue}\n'
  ' if r!=nil{io.println("{}",r.value)}\n'
  ' if !flag{del p}\n'
  ' del q\n'
  '}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0,
  None),
 ('rhs_call_mutates_counter',
  'Box::struct{value:i32}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'value::fn(n:ref usize) i32{reset(n);ret 7}\n'
  'index::fn(n:ref usize) usize{reset(n);ret 0}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' q:=new Box;if q==nil{del p;ret};q.value=17\n'
  ' i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;q.value=value(i)}\n'
  ' if !flag{del p};del q\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  6,
  (9, 32, 33)),
 ('fresh_stack_array_store_valid',
  'Box::struct{value:i32}\n'
  'observe::fn(n:ref usize){}\n'
  'borrow::fn(n:ref usize) ref usize{ret n}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' slots:[2]i32\n'
  ' i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;slots[0]=9;a:=borrow(i);if a!=nil{observe(a)}}\n'
  ' if !flag{del p}\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  0,
  None),
 ('local_stack_field_rhs_valid',
  'Box::struct{value:i32}\n'
  'observe::fn(n:ref usize){}\n'
  'borrow::fn(n:ref usize) ref usize{ret n}\n'
  'tick::fn(n:ref usize) bool{if n==nil{ret false};zero:usize=0;n=zero;ret true}\n'
  'rhs::fn() i32{ret 9}\n'
  'Cell::struct{value:i32}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' b:=new Box;if b==nil{del p;ret};b.value=17\n'
  ' slots:[2]i32;cell:Cell;lo:usize=0;hi:usize=1;j:usize=3;i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;cell.value=rhs();a:=borrow(i);if a!=nil{observe(a)}}\n'
  ' if !flag{del p};del b\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  0,
  None),
 ('index_effect_bounded_valid',
  'Box::struct{value:i32}\n'
  'observe::fn(n:ref usize){}\n'
  'borrow::fn(n:ref usize) ref usize{ret n}\n'
  'tick::fn(n:ref usize) bool{if n==nil{ret false};zero:usize=0;n=zero;ret true}\n'
  'rhs::fn() i32{ret 9}\n'
  'Cell::struct{value:i32}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' b:=new Box;if b==nil{del p;ret};b.value=17\n'
  ' slots:[2]i32;cell:Cell;lo:usize=0;hi:usize=1;j:usize=3;i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;slots[if tick(j){lo}else{hi}]=rhs();a:=borrow(i);if '
  'a!=nil{observe(a)}}\n'
  ' if !flag{del p};del b\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  0,
  None),
 ('index_effect_bounded_dead',
  'Box::struct{value:i32}\n'
  'observe::fn(n:ref usize){}\n'
  'borrow::fn(n:ref usize) ref usize{ret n}\n'
  'tick::fn(n:ref usize) bool{if n==nil{ret false};zero:usize=0;n=zero;ret true}\n'
  'rhs::fn() i32{ret 9}\n'
  'Cell::struct{value:i32}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' b:=new Box;if b==nil{del p;ret};b.value=17\n'
  ' slots:[2]i32;cell:Cell;lo:usize=0;hi:usize=1;j:usize=3;i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;slots[if tick(i){lo}else{hi}]=rhs();a:=borrow(i);if '
  'a!=nil{observe(a)}}\n'
  ' if !flag{del p};del b\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  6,
  (11, 32, 33)),
 ('conditional_base_effect_valid',
  'Box::struct{value:i32}\n'
  'observe::fn(n:ref usize){}\n'
  'borrow::fn(n:ref usize) ref usize{ret n}\n'
  'tick::fn(n:ref usize) bool{if n==nil{ret false};zero:usize=0;n=zero;ret true}\n'
  'rhs::fn() i32{ret 9}\n'
  'Cell::struct{value:i32}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' b:=new Box;if b==nil{del p;ret};b.value=17\n'
  ' slots:[2]i32;cell:Cell;lo:usize=0;hi:usize=1;j:usize=3;i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;if b!=nil{(if '
  'tick(j){b}else{b}).value=rhs()};a:=borrow(i);if a!=nil{observe(a)}}\n'
  ' if !flag{del p};del b\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  0,
  None),
 ('formal_inline_projection_byref',
  'Inner::struct{count:usize;items:[2]usize}\n'
  'Outer::struct{inner:Inner;link:ref usize}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'write::fn(owner:ref Outer){if owner==nil{ret};reset(owner.inner.items[0])}\n'
  'main::fn(){local:Outer;write(local)}\n',
  0,
  None),
 ('local_inline_projection_byref_valid',
  'Inner::struct{count:usize;items:[2]usize}\n'
  'Outer::struct{inner:Inner;link:ref usize}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'Box::struct{value:i32}\n'
  'observe::fn(n:ref usize){}\n'
  'borrow::fn(n:ref usize) ref usize{ret n}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' local:Outer;i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;reset(local.inner.items[0]);a:=borrow(i);if '
  'a!=nil{observe(a)}}\n'
  ' if !flag{del p}\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  0,
  None),
 ('primitive_sibling_beside_reference_valid',
  'Inner::struct{count:usize;items:[2]usize}\n'
  'Outer::struct{inner:Inner;link:ref usize}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'Box::struct{value:i32}\n'
  'observe::fn(n:ref usize){}\n'
  'borrow::fn(n:ref usize) ref usize{ret n}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' local:Outer;i:usize=0\n'
  ' while flag{if i==1{break};del '
  'p;i+=1;local.inner.count=4;reset(local.inner.count);a:=borrow(i);if a!=nil{observe(a)}}\n'
  ' if !flag{del p}\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  0,
  None),
 ('reference_field_crossing_unknown',
  'Inner::struct{count:usize;items:[2]usize}\n'
  'Outer::struct{inner:Inner;link:ref usize}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'write::fn(owner:ref Outer,other:ref usize){if owner==nil{ret};if '
  'owner.link==nil{ret};reset(owner.link)}\n'
  'main::fn(){}\n',
  0,
  None),
 ('global_inline_storage_unknown',
  'Inner::struct{count:usize;items:[2]usize}\n'
  'Outer::struct{inner:Inner;link:ref usize}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'global:Outer\n'
  'write::fn(other:ref usize){reset(global.inner.items[0])}\n'
  'main::fn(){}\n',
  0,
  None),
 ('captured_inline_storage_unknown',
  'Inner::struct{count:usize;items:[2]usize}\n'
  'Outer::struct{inner:Inner;link:ref usize}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'outer::fn(other:ref usize){local:Outer;inner::fn(n:ref '
  'usize){reset(local.inner.items[0])};inner(other)}\n'
  'main::fn(){}\n',
  {'semantic': 0, 'compile': 7},
  None),
 ('slice_storage_unknown',
  'Inner::struct{count:usize;items:[2]usize}\n'
  'Outer::struct{inner:Inner;link:ref usize}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'write::fn(xs:[]usize,other:ref usize){idx:usize=0;if idx<xs.len{reset(xs[idx])}}\n'
  'main::fn(){}\n',
  0,
  None),
 ('conditional_fresh_receivers_valid',
  'Box::struct{value:i32}\n'
  'observe::fn(n:ref usize){}\n'
  'borrow::fn(n:ref usize) ref usize{ret n}\n'
  'Cell::struct{count:usize}\n'
  'run::fn(flag:bool,other:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' left:=new Cell;if left==nil{del p;ret}\n'
  ' right:=new Cell;if right==nil{del left;del p;ret}\n'
  ' i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;(if other{left}else{right}).count=4;a:=borrow(i);if '
  'a!=nil{observe(a)}}\n'
  ' if !flag{del p};del left;del right\n'
  '}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0,
  None),
 ('conditional_fresh_and_unknown_receiver',
  'Cell::struct{count:usize}\n'
  'Holder::struct{child:ref Cell}\n'
  'write::fn(owner:ref Holder,other:ref usize,flag:bool){if owner==nil{ret};if '
  'owner.child==nil{ret};local:=new Cell;if local==nil{ret};(if '
  'flag{local}else{owner.child}).count=4;del local}\n'
  'main::fn(){}\n',
  0,
  None),
 ('independent_i32_mutation_valid',
  'Box::struct{value:i32}\n'
  'reset::fn(n:ref i32){if n==nil{ret};zero:i32=0;n=zero}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' x:i32=3;i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;reset(x)}\n'
  ' if !flag{del p}\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  0,
  None),
 ('independent_bool_mutation_valid',
  'Box::struct{value:i32}\n'
  'reset_x::fn(n:ref bool){if n==nil{ret};v:bool=false;n=v}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};p.value=7;x:bool=false;i:usize=0\n'
  'while flag{if i==1{break};del p;i+=1;reset_x(x)}\n'
  'if !flag{del p}}\n'
  'main::fn(){run(false);run(true)}\n',
  0,
  None),
 ('independent_enum_valid',
  'Phase::enum{First,Second}\n'
  'Box::struct{value:i32}\n'
  'advance::fn(state:ref Phase){if state==nil{ret};next:=Phase.Second;state=next}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' state:=Phase.First;i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;advance(state)}\n'
  ' if !flag{del p}\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  0,
  None)]

CASES += [('string_slot',
  'Box::struct{value:i32}\n'
  'advance::fn(state:ref string){if state==nil{ret};next:="after";state=next}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' state:="before";i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;advance(state)}\n'
  ' if !flag{del p}\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  0,
  None),
 ('slice_slot',
  'Box::struct{value:i32}\n'
  'advance::fn(state:ref []i32){if state==nil{ret};next:[]i32;state=next}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' state:[]i32;i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;advance(state)}\n'
  ' if !flag{del p}\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  0,
  None),
 ('function_slot',
  'first::fn(){}\n'
  'second::fn(){}\n'
  'Box::struct{value:i32}\n'
  'advance::fn(state:ref fn()){if state==nil{ret};state=second}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' state:=first;i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;advance(state)}\n'
  ' if !flag{del p}\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  0,
  None),
 ('same_backed_slice',
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'write::fn(xs:[]usize,other:ref usize){idx:usize=0;if idx<xs.len{reset(xs[idx])}}\n'
  'main::fn(){a:[1]usize;a[0]=1;xs:=a[0..1];write(xs,a[0])}\n',
  0,
  None),
 ('callback_reset_dead',
  'Box::struct{value:i32}\n'
  'noop::fn(n:ref usize){}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'replace::fn(state:ref fn(ref usize)){if state==nil{ret};state=reset}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' state:=noop;i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;replace(state);state(i)}\n'
  ' if !flag{del p}\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  6,
  (8, 32, 33)),
 ('forwarded_slot_reset_dead',
  'Box::struct{value:i32}\n'
  'noop::fn(n:ref usize){}\n'
  'reset::fn(n:ref usize){if n==nil{ret};z:usize=0;n=z}\n'
  'forward::fn(state:ref fn(ref usize)) ref fn(ref usize){ret state}\n'
  'replace::fn(state:ref fn(ref usize)){if state==nil{ret};state=reset}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' state:=noop;i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;replace(forward(state));state(i)}\n'
  ' if !flag{del p}\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  6,
  (9, 32, 33)),
 ('retained_slot_reset_dead',
  'Box::struct{value:i32}\n'
  'saved:ref fn(ref usize)\n'
  'noop::fn(n:ref usize){}\n'
  'reset::fn(n:ref usize){if n==nil{ret};z:usize=0;n=z}\n'
  'remember::fn(state:ref fn(ref usize)){saved=state}\n'
  'replace_saved::fn(){if saved==nil{ret};saved=reset}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' state:=noop;i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;remember(state);replace_saved();state(i)}\n'
  ' if !flag{del p}\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  6,
  (10, 32, 33)),
 ('aggregate_slot_unknown_callback_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{callback:fn(ref usize)}\n'
  'noop::fn(n:ref usize){}\n'
  'reset::fn(n:ref usize){if n==nil{ret};z:usize=0;n=z}\n'
  'replace::fn(state:ref fn(ref usize)){if state==nil{ret};state=reset}\n'
  'invoke::fn(callback:fn(ref usize),n:ref usize){callback(n)}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' holder:=Holder{callback:noop};i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;replace(holder.callback);invoke(holder.callback,i)}\n'
  ' if !flag{del p}\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  6,
  (10, 32, 33)),
 ('wrapper_string_slot',
  'Box::struct{value:i32}\n'
  'advance::fn(state:ref string){if state==nil{ret};next:="after";state=next}\n'
  'forward::fn(state:ref string){advance(state)}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' state:="before";i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;forward(state)}\n'
  ' if !flag{del p}\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  0,
  None),
 ('deferred_string_slot',
  'Box::struct{value:i32}\n'
  'advance::fn(state:ref string){if state==nil{ret};next:="after";state=next}\n'
  'forward::fn(state:ref string){defer advance(state)}\n'
  'run::fn(flag:bool){\n'
  ' p:=new Box;if p==nil{ret};p.value=7\n'
  ' state:="before";i:usize=0\n'
  ' while flag{if i==1{break};del p;i+=1;forward(state)}\n'
  ' if !flag{del p}\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  0,
  None)]

@pytest.mark.parametrize("name,source,expected,span", CASES, ids=[case[0] for case in CASES])
def test_primitive_place_stores(tmp_path, name, source, expected, span):
    path = tmp_path / (name + ".a7")
    path.write_text(source)
    for mode in ("semantic", "compile"):
        output = tmp_path / (name + ".zig")
        argv = [sys.executable, str(ROOT / "main.py"), str(path), "--mode", mode, "--format", "json"]
        if mode == "compile":
            argv += ["--output", str(output)]
        result = subprocess.run(argv, capture_output=True, text=True)
        required = expected[mode] if isinstance(expected, dict) else expected
        assert result.returncode == required, result.stdout + result.stderr
        assert not result.stderr
        data = json.loads(result.stdout)
        if required == 7:
            assert data["error"]["category"] == "codegen"
            assert len(data["error"]["details"]) == 1
            detail = data["error"]["details"][0]
            assert detail["type"] == "CodegenError"
            assert detail["file"] == str(path)
            assert detail["message"] == (
                "Zig backend: nested function 'inner' uses 'local' from the enclosing function; "
                "pass it as a parameter")
            assert detail["span"] == {"start_line": 4, "start_column": 40,
                                      "end_line": 4, "end_column": 45, "length": 5}
        elif required == 6:
            assert data["error"]["category"] == "semantic"
            assert data["error"]["details"]
            assert all(item["code"] == "use_after_move" and item["file"] == str(path)
                       and (item["span"]["start_line"], item["span"]["start_column"],
                            item["span"]["end_column"]) == span
                       for item in data["error"]["details"]), data
        else:
            assert data["status"] == "ok"
        assert output.exists() == (mode == "compile" and required == 0)
