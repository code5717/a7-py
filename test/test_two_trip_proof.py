"""Terminal re-entry certificates preserve lifetime history and unsafe repeats."""
import json,pprint
from pathlib import Path
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
CASES = [('two_trip_single_delete_precision',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if i==1{break};del p;defer i+=1;continue};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('third_trip_repeat',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if i==3{break};if i==0{i+=1;continue};del p;defer '
  'i+=1;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('second_trip_repeat',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if i==2{break};del p;defer i+=1;continue};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('defer_reset_repeat',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if i==1{break};del p;defer i=0;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('ref_reset_repeat',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if i==1{z:=reset_zero(i)};if i==1{break};del p;defer '
  'i+=1;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('one_trip_equivalent',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{del p;i+=1;if i==1{break};continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('labeled_terminal_live',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;@outer while flag{if i==1{break outer};del p;defer i+=1;continue};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('for_update_terminal_live',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;for i=0;flag;i+=1{if i==1{break};del p;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('for_update_reset_dead',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;for i=0;flag;i=0{if i==1{break};del p;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('unsafe_reentry_prefix_read',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if i==1{v:=p.value;break};del p;defer i+=1;continue};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('deferred_reentry_delete',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{defer del p;if i==1{break};del p;defer i+=1;continue};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('wrong_inner_break',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{while true{if i==1{break};break};del p;defer i+=1;continue};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('unknown_initial_dead',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool,n:usize){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=n;while flag{if i==1{break};del p;defer i+=1;continue};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,0);run(true,2)}\n',
  6),
 ('wrapping_repeat_dead',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=18446744073709551615;while flag{if i==1{break};del p;defer i+=1;continue};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('postloop_old_alias_dead',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;i:usize=0;while '
  'flag{if i==1{break};del p;defer i+=1;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('header_call_reset_dead',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while reset_false(i) or flag{if i==1{break};del p;defer i+=1;continue};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('prefix_division_dead',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if i==1{z:=i-i;v:=1/z;break};del p;defer i+=1;continue};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('first_trip_all_break_live',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('literal_header_terminal_live',
  'Box::struct{value:i32}\n'
  'reset_zero::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'reset_false::fn(i:ref usize) bool{zero:usize=0;i=zero;ret false}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;if flag{while true{if i==1{break};del p;defer i+=1;continue}};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0)]

@pytest.mark.parametrize("name,source,expected", CASES, ids=[c[0] for c in CASES])
def test_two_trip_proof(tmp_path, name, source, expected):
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
