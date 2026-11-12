"""Saved callable values keep their target after source-slot reassignment."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
CASES=[('copied_noop_source_rebound_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};f:=noop;g:=f;f=get;saved:=flag;if saved{r=q};g();while '
  'flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 7},
  'use_after_move'),
 ('copied_mutator_source_rebound_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};f:=get;g:=f;f=noop;saved:=flag;if saved{r=q};g();while '
  'flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 6, 'compile': 6},
  'use_after_move'),
 ('direct_new_mutator_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;g:=f;f=get;saved:=flag;if '
  'saved{r=q};f();while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 6, 'compile': 6},
  'use_after_move'),
 ('direct_new_noop_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=get;g:=f;f=noop;saved:=flag;if '
  'saved{r=q};f();while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 7},
  'use_after_move'),
 ('two_saved_copies_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;g:=f;h:=g;f=get;g=get;saved:=flag;if '
  'saved{r=q};h();while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 7},
  'use_after_move'),
 ('copy_after_reassignment_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;g:=f;f=get;h:=f;saved:=flag;if '
  'saved{r=q};h();while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 6, 'compile': 6},
  'use_after_move'),
 ('same_target_branches_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=get;if '
  'other{f=noop}else{f=noop};g:=f;f=get;saved:=flag;if saved{r=q};g();while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 7},
  'use_after_move'),
 ('distinct_noops_branches_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=get;if '
  'other{f=noop}else{f=noop2};g:=f;f=get;saved:=flag;if saved{r=q};g();while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 7},
  'use_after_move'),
 ('noop_mutator_branch_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;if '
  'other{f=get};g:=f;f=noop;saved:=flag;if saved{r=q};g();while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 6, 'compile': 6},
  'use_after_move'),
 ('noop_mutator_before_both_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;if '
  'other{f=get};g:=f;f=noop;g();saved:=flag;if saved{r=q};while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 7},
  'use_after_move'),
 ('shadowed_callable_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;g:=f;if '
  'other{f:=get;f()};f=get;saved:=flag;if saved{r=q};g();while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 7},
  'use_after_move'),
 ('immutable_captured_callable_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;g:=f;wrapper::fn(){g()};saved:=flag;if '
  'saved{r=q};wrapper();while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 7},
  'use_after_move'),
 ('passed_by_value_ignored_valid',
  'ignore::fn(f:fn()){}\n'
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;g:=f;f=get;saved:=flag;if '
  'saved{r=q};ignore(g);g();while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 7},
  'use_after_move'),
 ('transitive_mutator_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};wrapper::fn(){get()};f:=wrapper;g:=f;f=noop;saved:=flag;if '
  'saved{r=q};g();while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 6, 'compile': 6},
  'use_after_move'),
 ('unknown_callback_dead',
  'invoke::fn(f:fn()){f()}\n'
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=get;g:=f;f=noop;saved:=flag;if '
  'saved{r=q};invoke(g);while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 6, 'compile': 6},
  'use_after_move'),
 ('argument_mutation_dead',
  'ignore_bool::fn(b:bool){}\n'
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;g:=f;f=get;saved:=flag;if '
  'saved{r=q};ignore_bool(turn(flag));g();while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 6, 'compile': 6},
  'use_after_move'),
 ('argument_mutation_before_valid',
  'ignore_bool::fn(b:bool){}\n'
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;g:=f;f=get;ignore_bool(turn(flag));g();saved:=flag;if '
  'saved{r=q};while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 7},
  'use_after_move'),
 ('zero_trip_assignment_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;while '
  'false{f=get};g:=f;f=get;saved:=flag;if saved{r=q};g();while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 7},
  'use_after_move'),
 ('loop_mutation_saved_copy_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;g:=f;while '
  'other{f=get;break};saved:=flag;if saved{r=q};g();while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 7},
  'use_after_move'),
 ('loop_mutation_current_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;while '
  'other{f=get;break};saved:=flag;if saved{r=q};f();while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 6, 'compile': 6},
  'use_after_move'),
 ('backedge_mutator_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;saved:=flag;if '
  'saved{r=q};i:usize=0;while i<2{f();f=get;i+=1};while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 6, 'compile': 6},
  'use_after_move'),
 ('defer_current_mutator_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;saved:=flag;if saved{r=q};if '
  'true{defer f();f=get};while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 6, 'compile': 6},
  'use_after_move'),
 ('defer_saved_noop_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;g:=f;saved:=flag;if saved{r=q};if '
  'true{defer g();f=get};while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 7},
  'use_after_move'),
 ('defer_current_noop_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=get;saved:=flag;if saved{r=q};if '
  'true{defer f();f=noop};while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 7},
  'use_after_move'),
 ('defer_continue_mutator_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;saved:=flag;if '
  'saved{r=q};i:usize=0;while i<1{defer f();f=get;i+=1;continue};while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 6, 'compile': 6},
  'use_after_move'),
 ('defer_continue_saved_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;g:=f;saved:=flag;if '
  'saved{r=q};i:usize=0;while i<1{defer g();f=get;i+=1;continue};while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 7},
  'use_after_move'),
 ('for_update_mutator_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;saved:=flag;if saved{r=q};for '
  'i:=cast(usize,0);i<2;i+=1{f();f=get;continue};while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 6, 'compile': 6},
  'use_after_move'),
 ('defer_return_saved_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};wrapper::fn(){f:=noop;g:=f;defer '
  'g();f=get;ret};saved:=flag;if saved{r=q};wrapper();while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 7},
  'use_after_move'),
 ('defer_return_current_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};wrapper::fn(){f:=noop;defer '
  'f();f=get;ret};saved:=flag;if saved{r=q};wrapper();while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 6, 'compile': 6},
  'use_after_move'),
 ('labeled_break_saved_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;g:=f;saved:=flag;if '
  'saved{r=q};@outer while other{while true{defer g();f=get;break outer}};while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 7},
  'use_after_move'),
 ('nil_literal_boundary',
  'access::fn(a:ref[4]i32,b:bool){if b{x:=a[0]}}\n'
  'main::fn(){v:=false;later::fn(){v=true};defer {later()};access(nil,v)}\n',
  {'semantic': 6, 'compile': 6},
  'cannot_dereference'),
 ('defer_before_both_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};noop2::fn(){};f:=noop;if true{defer '
  'f();f=get};saved:=flag;if saved{r=q};while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 7},
  'use_after_move')]

@pytest.mark.parametrize("name,source,expected,diagnostic",CASES,ids=[x[0] for x in CASES])
def test_saved_callable_copy(tmp_path,name,source,expected,diagnostic):
    path=tmp_path/(name+".a7")
    path.write_text(source)
    output=tmp_path/(name+".zig")
    for mode in ("semantic","compile"):
        args=[sys.executable,str(ROOT/"main.py"),str(path),"--mode",mode,"--format","json"]
        if mode=="compile":args += ["--output",str(output)]
        result=subprocess.run(args,capture_output=True,text=True)
        assert result.returncode==expected[mode],result.stdout+result.stderr
        assert not result.stderr
        data=json.loads(result.stdout)
        if expected[mode]==6:
            assert data["error"]["category"]=="semantic"
            assert any(item["code"]==diagnostic and item["file"]==str(path) for item in data["error"]["details"])
        elif expected[mode]==7:
            assert data["error"]["category"]=="codegen"
            assert "enclosing function" in data["error"]["message"]
        else:assert data["status"]=="ok"
        assert not output.exists()
