"""Guarded counter facts preserve terminal lifetime proofs across disjoint paths."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
CASES=[('original',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if other{if i==1{break}}else{if i==2{break}};del p;if other{i=1;continue}else{i=2;continue}};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('local_predicate_valid',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,input:bool){other:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==2{break}};del p;if '
  'other{i=1;continue}else{i=2;continue}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('changed_predicate_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,input:bool){other:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==2{break}};del p;if '
  'other{i=1;other=false;continue}else{i=2;other=true;continue}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('refcall_predicate_dead',
  'Box::struct{value:i32}\n'
  'setfalse::fn(b:ref bool){b=false}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,input:bool){other:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==2{break}};del p;if '
  'other{i=1;setfalse(other);continue}else{i=2;continue}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('defer_reset_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if other{if i==1{break}}else{if i==2{break}};del p;if other{i=1;defer i=0;continue}else{i=2;defer '
  'i=0;continue}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('postloop_old_alias_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;i:usize=0;while flag{if '
  'other{if i==1{break}}else{if i==2{break}};del p;if other{i=1;continue}else{i=2;continue}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('equal_value_overlap_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if other{if i==1{break}}else{if i==1{break}};del p;if other{i=1;continue}else{i=1;continue}};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('unknown_predecessor_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool,n:usize){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==2{break}};del p;if '
  'other{i=1;continue}else{i=n;continue}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(false,true,0);run(true,false,0);run(true,true,0)}\n',
  6),
 ('possible_outcomes_overlap_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,input:bool){other:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}};del p;i=1;other=false;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('saved_boolean_version_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,input:bool){other:=input;saved:=other;other=!other;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};r:=p;if flag{r=q};i:usize=0;while flag{if saved{if i==1{break}}else{if i==2{break}};del p;if '
  'saved{i=1;continue}else{i=2;continue}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('changed_current_version_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,input:bool){other:=input;saved:=other;other=!other;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};r:=p;if flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==2{break}};del p;if '
  'saved{i=1;continue}else{i=2;continue}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('shadowed_boolean_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if other{if i==1{break}}else{if i==2{break}};del p;if '
  'other{i=1;other:=false;continue}else{i=2;other:=true;continue}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('two_guarded_operands_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;j:usize=3;while flag{if i==j{break};del p;if other{i=1;j=1;continue}else{i=2;j=2;continue}};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('self_add_guarded_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if other{if i==2{break}}else{if i==4{break}};del p;if other{i=1}else{i=2};i+=i;continue};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('self_sub_guarded_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=3;while '
  'flag{if i==0{break};del p;if other{i=1}else{i=2};i-=i;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('width_overflow_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if other{if i==1{break}}else{if i==2{break}};del p;if '
  'other{i=18446744073709551615;i+=1;continue}else{i=2;continue}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('for_guarded_update_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;for '
  'i=0;flag;i+=1{if other{if i==2{break}}else{if i==3{break}};del p;if other{i=1;continue}else{i=2;continue}};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('deferred_guarded_update_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if other{if i==2{break}}else{if i==3{break}};defer i+=1;del p;if other{i=1;continue}else{i=2;continue}};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('labeled_correlated_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;@outer while flag{if other{if i==1{break outer}}else{if i==2{break outer}};del p;if '
  'other{i=1;continue outer}else{i=2;continue outer}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('captured_predicate_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,input:bool){other:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};mut::fn(){other=false};i:usize=0;while flag{if other{if i==1{break}}else{if i==2{break}};del p;if '
  'other{i=1;mut();continue}else{i=2;continue}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('deferred_predicate_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,input:bool){other:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==2{break}};del p;if other{i=1;defer '
  'other=false;continue}else{i=2;continue}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('fresh_current_old_alias_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};old:=p;r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==2{break}};del p;p=new Box;if p==nil{ret};if '
  'other{i=1;continue}else{i=2;continue}};if old!=nil{v:=old.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('long_incrementing_recurrence_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if i>=1000000000000{break};del p;i+=1;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6)]

@pytest.mark.parametrize("name,source,expected", CASES, ids=[c[0] for c in CASES])
def test_correlated_counter_proof(tmp_path, name, source, expected):
    path=tmp_path/(name+".a7")
    path.write_text(source)
    out=tmp_path/(name+".zig")
    for mode in ("semantic", "compile"):
        argv=[sys.executable,str(ROOT/"main.py"),str(path),"--mode",mode,"--format","json"]
        if mode=="compile":
            argv += ["--output",str(out)]
        result=subprocess.run(argv,capture_output=True,text=True)
        assert result.returncode==expected, result.stdout+result.stderr
        assert not result.stderr
        if expected==6:
            error=json.loads(result.stdout)["error"]
            assert error["category"]=="semantic"
            assert any(d["code"]=="use_after_move" and d["file"]==str(path) for d in error["details"])
            assert not out.exists()
        elif mode=="compile":
            assert "pub fn main" in out.read_text()
