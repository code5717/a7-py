"""All feasible pure Boolean prefix paths must terminate before lifetime reuse."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
CASES=[('original',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if other{if i==1{break}}else{if i==1{break}};del p;defer i+=1;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('minimal_both_exit',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if other{if i==1{break}}else{if i==1{break}};del p;i+=1};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('one_branch_continues',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if other{if i==1{break}}else{if i==2{break}};del p;i+=1};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('risky_prefix_read',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if other{if i==1{v:=p.value;break}}else{if i==1{break}};del p;i+=1};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('deferred_prefix_delete',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if other{if i==1{defer del p;break}}else{if i==1{break}};del p;i+=1};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('equal_backedge_values',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if other{if i==1{break}}else{if i==1{break}};del p;if other{i=1;continue}else{i=1;continue}};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('nested_labeled_terminals_corrected',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;@outer while flag{if other{if i==1{break outer}}else{if i==1{break outer}};del p;i+=1};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('inner_break_only',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if other{if i==1{while true{break}}}else{if i==1{break}};del p;i+=1};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('effectful_condition',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if reset(i,other){if i==1{break}}else{if i==1{break}};del p;i+=1};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('shared_continuation_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if other{if i==1{break}};if i==1{break};del p;i+=1};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('missing_else_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if other{if i==1{break}};del p;i+=1};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('early_break_unreachable_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if other{if i==1{break}}else{if i==1{break}};if i==1{v:=p.value};del p;i+=1};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('postloop_alias_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;i:usize=0;while flag{if '
  'other{if i==1{break}}else{if i==1{break}};del p;i+=1};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('borrowed_condition_boundary',
  'Box::struct{value:i32}\n'
  'touch::fn(b:ref bool){b=true}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};choice:=other;touch(choice);i:usize=0;while flag{if choice{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('zero_initialized_condition_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};choice:bool;i:usize=0;while flag{if choice{if i==1{break}}else{if i==1{break}};del p;i+=1};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('for_update_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;for '
  'i=0;flag;i+=1{if other{if i==1{break}}else{if i==1{break}};del p;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('for_reset_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;for '
  'i=0;flag;i=0{if other{if i==1{break}}else{if i==1{break}};del p;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('nested_unknown_branches_live',
  'Box::struct{value:i32}\n'
  'reset::fn(i:ref usize,other:bool) bool{zero:usize=0;i=zero;ret other}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if flag{r=q};i:usize=0;while '
  'flag{if other{if other{if other{if other{if other{if other{if other{if other{if i==1{break}}else{if '
  'i==1{break}}}else{if i==1{break}}}else{if i==1{break}}}else{if i==1{break}}}else{if i==1{break}}}else{if '
  'i==1{break}}}else{if i==1{break}}}else{if i==1{break}};del p;i+=1};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0)]

@pytest.mark.parametrize("name,source,expected", CASES, ids=[c[0] for c in CASES])
def test_terminal_prefix_branches(tmp_path, name, source, expected):
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
