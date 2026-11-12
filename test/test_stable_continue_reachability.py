"""Loop summary scalar reachability preserves live aliases and real backedges."""
import json,pprint
from pathlib import Path
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
CASES = [('original_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{del p;i+=1;if '
  'i==1{break};continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('break_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('counter_then_break_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{del p;i+=1;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('literal_break_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{del p;i+=1;if '
  'true{break};continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('implicit_backedge_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{del p;i+=1;if '
  'i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('counter_header_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while i<1{if flag{del '
  'p};i+=1};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('delete_after_test_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{i+=1;if i==1{del '
  'p;break};continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('real_repeat_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{del p;i+=1;if '
  'i==2{break};continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('continue_mutation_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while i<2{i+=1;if '
  'i==1{settrue(flag);continue};if flag{del p};break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('unknown_initial_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=n;while flag{del p;i+=1;if '
  'i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  6),
 ('conditional_increment_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{del p;if '
  'other{i+=1};if i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  6),
 ('missing_increment_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{del p;if '
  'i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  6),
 ('wrap_boundary_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=18446744073709551615;while '
  'flag{del p;i+=1;if i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  6),
 ('ref_mutation_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{del '
  'p;i+=1;reset(i);if i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  6),
 ('continue_before_break_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{del p;i+=1;if '
  'other{continue};if i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  6),
 ('nested_break_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{del p;i+=1;while '
  'true{if i==1{break}}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  6),
 ('labeled_break_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;@outer while flag{del '
  'p;i+=1;while true{if i==1{break outer};break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  0),
 ('for_update_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;for i=0;flag;i=0{del p;i+=1;if '
  'other{continue};if i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  6),
 ('defer_continue_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{defer i=0;del '
  'p;i+=1;if other{continue};if i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  6),
 ('defer_break_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{defer i=0;del '
  'p;i+=1;if i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  0),
 ('matching_join_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{del p;if '
  'other{i=1}else{i=1};if i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  0),
 ('conflicting_join_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{del p;if '
  'other{i=1}else{i=0};if i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  6),
 ('reassignment_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{del p;i+=1;i=0;if '
  'i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  6),
 ('literal_copy_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;j:usize=1;while flag{del '
  'p;i=j;if i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  0),
 ('subtract_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=2;while flag{del p;i-=1;if '
  'i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  0),
 ('fresh_local_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{del '
  'p;j:usize=0;j+=1;if j==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  0),
 ('old_alias_exit_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;r=p;while flag{del p;i+=1;if '
  'i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  6),
 ('for_init_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=9;for i=0;flag;i+=1{del p;i+=1;if '
  'i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  0),
 ('call_alias_mutation_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;f:=reset;while flag{del '
  'p;i+=1;f(i);if i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  6),
 ('labeled_continue_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;@outer while flag{del '
  'p;i+=1;while true{if other{continue outer};break};if i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  6),
 ('shadow_local_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{del p;if '
  'other{i:usize=7;i+=1};i+=1;if i==1{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  0),
 ('nested_local_repeat_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize){zero:usize=0;i=zero}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool,other:bool,n:usize){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]ref Box=[p,q];r:=xs[0];if flag{r=q};i:usize=0;while flag{del p;while '
  'true{j:usize=0;j+=1;if j==1{break}};i+=1;if i==2{break}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false,0);run(true,false,0);run(true,true,1)}\n',
  6)]

@pytest.mark.parametrize("name,source,expected", CASES, ids=[c[0] for c in CASES])
def test_stable_continue_reachability(tmp_path, name, source, expected):
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
