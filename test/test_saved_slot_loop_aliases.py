"""Known scalar referents survive mutable array-cell invalidation at loops."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
CASES = [('ordinary_maybe_delete',
  'Box::struct{value:i32}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=p;while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('ordinary_single_trip',
  'Box::struct{value:i32}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=p;i:usize=0;while i<1{del p;i+=1};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('ordinary_zero_trip',
  'Box::struct{value:i32}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=p;while false{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('ordinary_distinct_delete',
  'Box::struct{value:i32}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=p;while flag{del q;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('ordinary_container_overwrite',
  'Box::struct{value:i32}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=p;while flag{xs[0]=q;del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('ordinary_fresh_saved',
  'Box::struct{value:i32}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=p;while flag{del p;r=new Box;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('ordinary_read_before',
  'Box::struct{value:i32}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=p;while flag{if r!=nil{v:=r.value};del p;break};}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('ordinary_empty_loop',
  'Box::struct{value:i32}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=p;while flag{break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('saved_maybe_delete',
  'Box::struct{value:i32}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('saved_single_trip',
  'Box::struct{value:i32}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];i:usize=0;while i<1{del p;i+=1};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('saved_zero_trip',
  'Box::struct{value:i32}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];while false{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('saved_distinct_delete',
  'Box::struct{value:i32}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];while flag{del q;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('saved_container_overwrite',
  'Box::struct{value:i32}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];while flag{xs[0]=q;del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('saved_fresh_saved',
  'Box::struct{value:i32}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];while flag{del p;r=new Box;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('saved_read_before',
  'Box::struct{value:i32}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];while flag{if r!=nil{v:=r.value};del p;break};}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('saved_empty_loop',
  'Box::struct{value:i32}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];while flag{break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('saved_distinct_slot',
  'Box::struct{value:i32}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[1];while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true)}\n',
  0),
 ('for_dead',
  'Box::struct{value:i32}\n'
  'kill::fn(p:ref Box){del p}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];for i:=0;i<1;i+=1{del p};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('for_distinct',
  'Box::struct{value:i32}\n'
  'kill::fn(p:ref Box){del p}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];for i:=0;i<1;i+=1{del q};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('collection_dead',
  'Box::struct{value:i32}\n'
  'kill::fn(p:ref Box){del p}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];values:[1]i32=[1];for value in values{del p};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('collection_distinct',
  'Box::struct{value:i32}\n'
  'kill::fn(p:ref Box){del p}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];values:[1]i32=[1];for value in values{del q};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('indexed_collection_dead',
  'Box::struct{value:i32}\n'
  'kill::fn(p:ref Box){del p}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];values:[1]i32=[1];for i,value in values{del p};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('copy_dead',
  'Box::struct{value:i32}\n'
  'kill::fn(p:ref Box){del p}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];s:=r;while flag{del p;break};r=s;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('fresh_before',
  'Box::struct{value:i32}\n'
  'kill::fn(p:ref Box){del p}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];r=new Box;while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('nil_before',
  'Box::struct{value:i32}\n'
  'kill::fn(p:ref Box){del p}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];r=nil;while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('continue_dead',
  'Box::struct{value:i32}\n'
  'kill::fn(p:ref Box){del p}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];i:usize=0;while i<1{del p;i+=1;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('continue_fresh',
  'Box::struct{value:i32}\n'
  'kill::fn(p:ref Box){del p}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];i:usize=0;while i<1{del p;r=new Box;i+=1;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('callee_dead',
  'Box::struct{value:i32}\n'
  'kill::fn(p:ref Box){del p}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];while flag{kill(p);break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('callee_distinct',
  'Box::struct{value:i32}\n'
  'kill::fn(p:ref Box){del p}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];while flag{kill(q);break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('saved_into_field_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];h:=Holder{child:r};while flag{del p;break};if '
  'h.child!=nil{v:=h.child.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('saved_into_field_distinct',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];h:=Holder{child:r};while flag{del q;break};if '
  'h.child!=nil{v:=h.child.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('nested_array_saved_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];grid:[1][2]ref Box=[[p,q]];r=grid[0][0];while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('nested_array_saved_distinct',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];grid:[1][2]ref Box=[[p,q]];r=grid[0][1];while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('branch_saved_distinct',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];if flag{r=q};while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('nil_in_loop',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];while flag{del p;r=nil;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('saved_nil_current',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];while flag{del p;r=nil;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  0),
 ('saved_nil_old_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];old:=r;while flag{del p;r=nil;break};if '
  'old!=nil{v:=old.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('saved_nil_partial',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];while flag{del p;if other{r=nil};break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('saved_nil_then_stale',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];while flag{del p;r=nil;r=p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('saved_stable_predicate',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  0),
 ('saved_assigned_predicate',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};flag=true;while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('saved_inverted_predicate',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};flag=!flag;while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('saved_borrowed_predicate',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};settrue(flag);while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('saved_distinct_predicate',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};while other{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('saved_shadow_predicate',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};if true{flag:=true;while flag{del '
  'p;break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('saved_backedge_predicate',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};while !flag{flag=true;continue};while '
  'flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('ordinary_nil_current',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;while flag{del p;r=nil;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  0),
 ('ordinary_nil_old_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;old:=r;while flag{del p;r=nil;break};if '
  'old!=nil{v:=old.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('ordinary_nil_partial',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;while flag{del p;if other{r=nil};break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('ordinary_nil_then_stale',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;while flag{del p;r=nil;r=p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('ordinary_stable_predicate',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;if flag{r=q};while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  0),
 ('ordinary_assigned_predicate',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;if flag{r=q};flag=true;while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('ordinary_inverted_predicate',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;if flag{r=q};flag=!flag;while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('ordinary_borrowed_predicate',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;if flag{r=q};settrue(flag);while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('ordinary_distinct_predicate',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;if flag{r=q};while other{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('ordinary_shadow_predicate',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;if flag{r=q};if true{flag:=true;while flag{del '
  'p;break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('ordinary_backedge_predicate',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;if flag{r=q};while !flag{flag=true;continue};while '
  'flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('saved_reinitialized_predicate',
  'Box::struct{value:i32}\n'
  'main::fn(){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[1];i:usize=0;while i<2{flag:=i==0;if flag{r=p};if !flag{del p};i+=1};if '
  'r!=nil{v:=r.value}}\n',
  6),
 ('ordinary_reinitialized_predicate',
  'Box::struct{value:i32}\n'
  'main::fn(){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=q;i:usize=0;while i<2{flag:=i==0;if flag{r=p};if !flag{del p};i+=1};if '
  'r!=nil{v:=r.value}}\n',
  6),
 ('shadow_live',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};if true{flag:=false;while flag{del '
  'q;break}};while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('shadow_live_ordinary',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;if flag{r=q};if true{flag:=false;while flag{del '
  'q;break}};while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('borrow_noop_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];settrue(flag);if flag{r=q};while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('borrow_noop_valid_ordinary',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;settrue(flag);if flag{r=q};while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('saved_setfalse_between',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};setfalse(flag);while !flag{del '
  'q;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('saved_branch_mutation_between',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};if other{flag=!flag};while flag{del '
  'p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('saved_branch_versions_before',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if other{flag=true}else{flag=false};if flag{r=q};while '
  'flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  0),
 ('saved_old_copy_after_mutation',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};old:=flag;flag=!flag;if old{r=q};while '
  'flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('saved_nested_loop_mutation',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};while other{while '
  'true{flag=true;break};break};while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('saved_setfalse_before',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];setfalse(flag);if !flag{r=q};while !flag{del '
  'p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  0),
 ('saved_constant_false_loop',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];shadow:=false;while shadow{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  0),
 ('ordinary_setfalse_between',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;if flag{r=q};setfalse(flag);while !flag{del q;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('ordinary_branch_mutation_between',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;if flag{r=q};if other{flag=!flag};while flag{del '
  'p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('ordinary_branch_versions_before',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;if other{flag=true}else{flag=false};if flag{r=q};while '
  'flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  0),
 ('ordinary_old_copy_after_mutation',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;if flag{r=q};old:=flag;flag=!flag;if old{r=q};while '
  'flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('ordinary_nested_loop_mutation',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;if flag{r=q};while other{while '
  'true{flag=true;break};break};while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('ordinary_setfalse_before',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;setfalse(flag);if !flag{r=q};while !flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  0),
 ('ordinary_constant_false_loop',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=p;shadow:=false;while shadow{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  0),
 ('copy_before_token_live',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];saved:=flag;if saved{r=q};while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('copy_before_token_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];saved:=flag;if saved{r=q};flag=!flag;while flag{del '
  'p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('copy_after_token_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};saved:=flag;flag=!flag;while saved{del '
  'q;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('loop_false_never_enter_live',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];flag=false;while flag{flag=true;del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('loop_false_then_mutate_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];flag=false;while true{flag=true;if flag{del '
  'p};break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('closure_read_live',
  'Box::struct{value:i32}\n'
  'global_flag:bool=false\n'
  'setglobal::fn(){global_flag=true}\n'
  'identity::fn(b:bool) bool{ret b}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];get::fn() bool{ret flag};if flag{r=q};while flag{del '
  'p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 7, 'semantic': 0}),
 ('closure_mutation_dead',
  'Box::struct{value:i32}\n'
  'global_flag:bool=false\n'
  'setglobal::fn(){global_flag=true}\n'
  'identity::fn(b:bool) bool{ret b}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];change::fn(){flag=true};if flag{r=q};change();while '
  'flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('closure_alias_borrow_dead',
  'Box::struct{value:i32}\n'
  'global_flag:bool=false\n'
  'setglobal::fn(){global_flag=true}\n'
  'identity::fn(b:bool) bool{ret b}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];set::fn(x:ref '
  'bool){x=true};change::fn(){setter:=set;setter(flag)};if flag{r=q};change();while flag{del '
  'p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('closure_read_called_live',
  'Box::struct{value:i32}\n'
  'global_flag:bool=false\n'
  'setglobal::fn(){global_flag=true}\n'
  'identity::fn(b:bool) bool{ret b}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];get::fn() bool{ret flag};if flag{r=q};get();while '
  'flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 7, 'semantic': 0}),
 ('for_init_mutates_dead',
  'Box::struct{value:i32}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'main::fn(){flag:=false;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];for flag=true;flag;flag=false{del p;break};if r!=nil{v:=r.value}}\n',
  6),
 ('condition_call_mutates_dead',
  'Box::struct{value:i32}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'main::fn(){flag:=false;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];while turn(flag){del p;break};if r!=nil{v:=r.value}}\n',
  6)]

@pytest.mark.parametrize("name,source,expected", CASES, ids=[x[0] for x in CASES])
def test_saved_slot_loop_aliases(tmp_path, name, source, expected):
    path = tmp_path / (name + ".a7")
    path.write_text(source)
    out = tmp_path / (name + ".zig")
    for mode in ("semantic", "compile"):
        mode_expected = expected[mode] if isinstance(expected, dict) else expected
        argv = [sys.executable, str(ROOT / "main.py"), str(path), "--mode", mode, "--format", "json"]
        if mode == "compile":
            argv += ["--output", str(out)]
        result = subprocess.run(argv, capture_output=True, text=True)
        assert result.returncode == mode_expected, result.stdout + result.stderr
        assert not result.stderr
        if mode_expected == 6:
            error = json.loads(result.stdout)["error"]
            assert error["category"] == "semantic"
            assert any(d["code"] == "use_after_move" and d["file"] == str(path) for d in error["details"])
            assert not out.exists()
        elif mode_expected == 7:
            error = json.loads(result.stdout)["error"]
            assert error["category"] == "codegen"
            assert "enclosing function" in error["message"]
            assert not out.exists()
        elif mode == "compile":
            assert "pub fn main" in out.read_text()
