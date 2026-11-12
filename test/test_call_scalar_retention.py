"""Ordinary calls preserve only counters inaccessible to every callee."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
CASES = [('conditional_source_write_loop_saved_noop',
  'Box::struct{value:i32}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};r:=p;get::fn(){flag=true};noop::fn(){};f:=noop;g:=f;saved:=flag;if '
  'saved{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};if other{f=get};g();del '
  'p;defer i+=1;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 7, 'semantic': 0}),
 ('deferred_saved_noop_unknown_prefix',
  'Box::struct{value:i32}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};r:=p;get::fn(){flag=true};noop::fn(){};f:=noop;g:=f;saved:=flag;if '
  'saved{r=q};i:usize=0;while flag{if other{if i==1{break}}else{if i==1{break}};defer g();f=get;del '
  'p;defer i+=1;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 7, 'semantic': 0}),
 ('ordinary_noop_retains_counter',
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==1{break}}else{if i==1{break}};del p;i+=1;noop()};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 0, 'semantic': 0}),
 ('direct_ref_reset',
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==1{break}}else{if i==1{break}};del p;i+=1;reset(i)};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('aliased_ref_reset',
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;f:=reset;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;f(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('nested_capture_reset',
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;inner::fn(){i=0};outer::fn(){inner()};while flag{if other{if i==1{break}}else{if '
  'i==1{break}};del p;i+=1;outer()};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('forward_capture_reset',
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;outer::fn(){inner()};inner::fn(){i=0};while flag{if other{if i==1{break}}else{if '
  'i==1{break}};del p;i+=1;outer()};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('callback_capture_reset',
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;inner::fn(){i=0};cb:=inner;while flag{if other{if i==1{break}}else{if '
  'i==1{break}};del p;i+=1;cb()};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('mutating_argument',
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;sink(reset(i))};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('defer_reset_after_increment',
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==1{break}}else{if i==1{break}};del p;defer reset(i);defer '
  'i+=1;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('defer_increment_after_noop',
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==1{break}}else{if i==1{break}};del p;defer i+=1;defer '
  'noop();continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 0, 'semantic': 0}),
 ('defer_noop_after_increment',
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==1{break}}else{if i==1{break}};del p;defer noop();defer '
  'i+=1;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 0, 'semantic': 0}),
 ('shadowed_counter_reset',
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==1{break}}else{if i==1{break}};del p;i+=1;if '
  'other{i:usize=0;reset(i)};noop()};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 0, 'semantic': 0}),
 ('third_trip_repeat_delete',
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==2{break}}else{if i==2{break}};del p;i+=1;noop()};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('old_alias_after_loop',
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==1{break}}else{if i==1{break}};del p;i+=1;noop()};if '
  'p!=nil{v:=p.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('different_counter_cases_retained',
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==1{break}}else{if i==2{break}};del p;if '
  'other{i=1}else{i=2};noop()};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 0, 'semantic': 0}),
 ('borrowed_but_unmodified_compatibility',
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;observe::fn(n:ref usize){};while flag{if other{if i==1{break}}else{if '
  'i==1{break}};del p;i+=1;observe(i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 0, 'semantic': 0}),
 ('stdlib_print_valid',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;io.println("{}",i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 0, 'semantic': 0}),
 ('stdlib_mutating_argument',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;io.println("{}",reset(i))};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('stdlib_guarded_counter_valid',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==1{break}}else{if i==2{break}};del p;if '
  'other{i=1}else{i=2};io.println("{}",i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 0, 'semantic': 0}),
 ('stdlib_deferred_print_valid',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==1{break}}else{if i==1{break}};del p;defer '
  'io.println("{}",i);defer i+=1;continue};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 0, 'semantic': 0}),
 ('stdlib_read_line_unrelated_valid',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};buf:[8]u8;i:usize=0;;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;io.read_line(buf[0..])};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 0, 'semantic': 0}),
 ('stdlib_old_alias_dead',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;io.println("{}",i)};if p!=nil{v:=p.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('stdlib_third_trip_dead',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==2{break}}else{if i==2{break}};del '
  'p;i+=1;io.println("{}",i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('borrowed_guarded_then_stdlib_valid',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'observe::fn(n:ref usize){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==1{break}}else{if i==2{break}};del p;if '
  'other{i=1}else{i=2};observe(i);io.println("{}",i)};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 0, 'compile': 0}),
 ('stdlib_nested_reset_argument_dead',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'noop::fn(){}\n'
  'reset::fn(i:ref usize) usize{zero:usize=0;i=zero;ret zero}\n'
  'sink::fn(n:usize){}\n'
  'identity::fn(n:usize) usize{ret n}\n'
  'run::fn(flag:bool,other:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=p;if '
  'flag{r=q};i:usize=0;;while flag{if other{if i==1{break}}else{if i==1{break}};del '
  'p;i+=1;io.println("{}",identity(reset(i)))};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'semantic': 6, 'compile': 6})]

@pytest.mark.parametrize("name,source,expected", CASES, ids=[case[0] for case in CASES])
def test_call_scalar_retention(tmp_path, name, source, expected):
    path = tmp_path / (name + ".a7")
    path.write_text(source)
    for mode in ("semantic", "compile"):
        output = tmp_path / (name + ".zig")
        argv = [sys.executable, str(ROOT / "main.py"), str(path), "--mode", mode, "--format", "json"]
        if mode == "compile":
            argv += ["--output", str(output)]
        result = subprocess.run(argv, capture_output=True, text=True)
        assert result.returncode == expected[mode], result.stdout + result.stderr
        assert not result.stderr
        data = json.loads(result.stdout)
        if expected[mode] == 6:
            assert data["error"]["category"] == "semantic"
            assert any(item["code"] == "use_after_move" and item["file"] == str(path)
                       for item in data["error"]["details"])
        elif expected[mode] == 7:
            assert data["error"]["category"] == "codegen"
            assert "enclosing function" in data["error"]["message"]
        else:
            assert data["status"] == "ok"
        if mode == "compile" and expected[mode] == 0:
            assert "pub fn main" in output.read_text()
        else:
            assert not output.exists()
