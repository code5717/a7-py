"""Alias versions and returned references preserve the caller storage identity."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
CASES = [('actual_snapshot_before_later_argument',
  'Box::struct{value:i32}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'observe::fn(n:ref usize){}\n'
  'g:ref usize\n'
  'switch::fn(m:ref usize) usize{g=m;ret 0}\n'
  'first::fn(a:ref usize,x:usize){reset(a)}\n'
  'wrap::fn(n:ref usize,m:ref usize){g=n;if g==nil{ret};first(g,switch(m))}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};i:usize=0;while flag{if i==1{break};del '
  'p;i+=1;j:usize=0;wrap(i,j)};if !flag{del p}}\n'
  'main::fn(){run(false);run(true)}\n',
  6,
  'use_after_move'),
 ('callee_snapshot_before_arguments',
  'Box::struct{value:i32}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'observe::fn(n:ref usize){}\n'
  'write::fn(n:ref usize,x:usize){reset(n)}\n'
  'quiet::fn(n:ref usize,x:usize){}\n'
  'wrap::fn(n:ref usize,m:ref usize){f:=write;change::fn() usize{f=quiet;ret 0};f(n,change())}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};i:usize=0;while flag{if i==1{break};del '
  'p;i+=1;j:usize=0;wrap(i,j)};if !flag{del p}}\n'
  'main::fn(){run(false);run(true)}\n',
  6,
  'use_after_move'),
 ('return_snapshot_before_defer',
  'Box::struct{value:i32}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'observe::fn(n:ref usize){}\n'
  'pick::fn(n:ref usize,m:ref usize) ref usize{a:=n;defer a=m;ret a}\n'
  'wrap::fn(n:ref usize,m:ref usize){a:=pick(n,m);if a!=nil{reset(a)}}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};i:usize=0;while flag{if i==1{break};del '
  'p;i+=1;j:usize=0;wrap(i,j)};if !flag{del p}}\n'
  'main::fn(){run(false);run(true)}\n',
  6,
  'use_after_move'),
 ('lifo_rebind_before_reset_valid',
  'Box::struct{value:i32}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize,m:ref usize){a:=n;defer reset(a);defer a=m}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};i:usize=0;while flag{if i==1{break};del '
  'p;i+=1;j:usize=0;wrap(i,j)};if !flag{del p}}\n'
  'main::fn(){run(false);run(true)}\n',
  0,
  None),
 ('lifo_reset_before_rebind_dead',
  'Box::struct{value:i32}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize,m:ref usize){a:=n;defer a=m;defer reset(a)}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};i:usize=0;while flag{if i==1{break};del '
  'p;i+=1;j:usize=0;wrap(i,j)};if !flag{del p}}\n'
  'main::fn(){run(false);run(true)}\n',
  6,
  'use_after_move'),
 ('same_actual_formal_alias',
  'Box::struct{value:i32}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'observe::fn(n:ref usize){}\n'
  'second::fn(n:ref usize,m:ref usize){a:=n;a=m;reset(a)}\n'
  'wrap::fn(n:ref usize,m:ref usize){second(n,n)}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};i:usize=0;while flag{if i==1{break};del '
  'p;i+=1;j:usize=0;wrap(i,j)};if !flag{del p}}\n'
  'main::fn(){run(false);run(true)}\n',
  6,
  'use_after_move'),
 ('returned_and_globally_retained',
  'Box::struct{value:i32}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'observe::fn(n:ref usize){}\n'
  'g:ref usize\n'
  'retain::fn(n:ref usize) ref usize{g=n;ret n}\n'
  'mutate::fn(){if g!=nil{reset(g)}}\n'
  'wrap::fn(n:ref usize,m:ref usize){a:=retain(n);if a!=nil{observe(a)};mutate()}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};i:usize=0;while flag{if i==1{break};del '
  'p;i+=1;j:usize=0;wrap(i,j)};if !flag{del p}}\n'
  'main::fn(){run(false);run(true)}\n',
  6,
  'use_after_move'),
 ('nested_return_forward_readonly',
  'Box::struct{value:i32}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'observe::fn(n:ref usize){}\n'
  'borrow::fn(n:ref usize) ref usize{ret n}\n'
  'forward::fn(n:ref usize) ref usize{ret borrow(n)}\n'
  'wrap::fn(n:ref usize,m:ref usize){a:=forward(n);if a!=nil{observe(a)}}\n'
  'run::fn(flag:bool){p:=new Box;if p==nil{ret};i:usize=0;while flag{if i==1{break};del '
  'p;i+=1;j:usize=0;wrap(i,j)};if !flag{del p}}\n'
  'main::fn(){run(false);run(true)}\n',
  0,
  None),
 ('alias_overwrite_valid',
  'wrap::fn(n:ref usize,m:ref usize){a:=n;a=m;reset(a)}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;j:usize=0;wrap(i,j)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0,
  None),
 ('returned_reference_readonly_valid',
  'observe::fn(n:ref usize){}\n'
  'borrow::fn(n:ref usize) ref usize{ret n}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;a:=borrow(i);if a!=nil{observe(a)}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0,
  None)]

@pytest.mark.parametrize("name,source,expected,code", CASES, ids=[case[0] for case in CASES])
def test_borrowed_alias_graph(tmp_path, name, source, expected, code):
    path = tmp_path / (name + ".a7")
    path.write_text(source)
    for mode in ("semantic", "compile"):
        output = tmp_path / (name + ".zig")
        argv = [sys.executable, str(ROOT / "main.py"), str(path), "--mode", mode, "--format", "json"]
        if mode == "compile":
            argv += ["--output", str(output)]
        result = subprocess.run(argv, capture_output=True, text=True)
        assert result.returncode == expected, result.stdout + result.stderr
        assert not result.stderr
        data = json.loads(result.stdout)
        if expected == 6:
            assert data["error"]["category"] == "semantic"
            assert any(item["code"] == code and item["file"] == str(path)
                       for item in data["error"]["details"]), data
        else:
            assert data["status"] == "ok"
        if mode == "compile" and expected == 0:
            assert "pub fn main" in output.read_text()
        else:
            assert not output.exists()
