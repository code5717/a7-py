"""Readonly scalar borrows preserve counters; mutations invalidate them."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
CASES = [('original_empty_observer',
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;observe::fn(n:ref usize){};while flag{if other{if i==1{break}}else{if '
  'i==1{break}};del p;i+=1;observe(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('readonly_alias',
  'observe::fn(n:ref usize){}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;f:=observe;f(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('readonly_wrapper',
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize){observe(n)}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;wrap(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('readonly_loop',
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};j:usize=0;while j<3{observe(n);j+=1}}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;wrap(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('readonly_branch',
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize,b:bool){if b{observe(n)}else{observe(n)}}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;wrap(i,other)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('readonly_defer',
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize){defer observe(n)}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;wrap(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('readonly_ref_alias',
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize){a:=n;observe(a)}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;wrap(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('saved_callable_readonly',
  'observe::fn(n:ref usize) usize{ret 0}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;f:=observe;g:=f;f=reset;g(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('direct_reset',
  '\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;reset(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('compound_write',
  'advance::fn(n:ref usize){amount:usize=1;n+=amount}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;advance(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('forward_alias_mutation',
  'wrap::fn(n:ref usize){a:=n;reset(a)}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;wrap(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('nested_wrapper_mutation',
  'wrap::fn(n:ref usize){inner(n)}\n'
  'inner::fn(n:ref usize){reset(n)}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;wrap(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('conditional_mutator',
  'observe::fn(n:ref usize) usize{ret 0}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;f:=observe;if other{f=reset};f(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('unknown_callback',
  'invoke::fn(f:fn(ref usize)usize,n:ref usize){f(n)}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;invoke(reset,i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('reset_then_restore',
  '\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;reset(i);i=1};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('deferred_reset',
  '\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del p;i+=1;defer '
  'reset(i);continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('argument_mutation',
  'observe_value::fn(n:ref usize,v:usize){}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;observe_value(i,reset(i))};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('return_escape',
  'borrow::fn(n:ref usize) ref usize{ret n}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;a:=borrow(i);if a!=nil{zero:usize=0;a=zero}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('global_escape',
  'g:ref usize\n'
  'keep::fn(n:ref usize){g=n}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;keep(i);if g!=nil{zero:usize=0;g=zero}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('closure_reference_escape',
  'wrap::fn(n:ref usize){if n==nil{ret};mut::fn(){zero:usize=0;n=zero};mut()}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;wrap(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('two_actuals_same',
  'pair::fn(a:ref usize,b:ref usize){zero:usize=0;b=zero}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;pair(i,i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('third_trip',
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;observe::fn(n:ref usize){};while flag{if other{if i==2{break}}else{if '
  'i==2{break}};del p;i+=1;observe(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('old_alias',
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;observe::fn(n:ref usize){};while flag{if other{if i==1{break}}else{if '
  'i==1{break}};del p;i+=1;observe(i)};if p!=nil{v:=p.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('guarded_readonly',
  'Box::struct{value:i32}\n'
  'observe::fn(n:ref usize){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==1{break}}else{if i==2{break}};del p;if '
  'other{i=1}else{i=2};observe(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('nil_return_no_escape',
  'observe::fn(n:ref usize) ref usize{ret nil}\n'
  'wrap::fn(n:ref usize){observe(n)}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;wrap(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('scalar_return_no_escape',
  'observe::fn(n:ref usize) usize{ret 0}\n'
  'wrap::fn(n:ref usize){observe(n)}\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;wrap(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0)]

@pytest.mark.parametrize("name,source,expected", CASES, ids=[case[0] for case in CASES])
def test_borrowed_counter_proof(tmp_path, name, source, expected):
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
            assert any(item["code"] == "use_after_move" and item["file"] == str(path)
                       for item in data["error"]["details"])
        else:
            assert data["status"] == "ok"
        if mode == "compile" and expected == 0:
            assert "pub fn main" in output.read_text()
        else:
            assert not output.exists()
