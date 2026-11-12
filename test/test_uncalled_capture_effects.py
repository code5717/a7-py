"""Captured Boolean mutations invalidate versions when their call executes."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
CASES=[('uncalled_mutator_capture_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};saved:=flag;if saved{r=q};while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 7, 'semantic': 0}),
 ('no_capture_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];saved:=flag;if saved{r=q};while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 0, 'semantic': 0}),
 ('readonly_capture_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn() bool{ret flag};saved:=flag;if saved{r=q};while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 7, 'semantic': 0}),
 ('called_mutator_stale_alias',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};saved:=flag;if saved{r=q};get();while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('called_before_both_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};get();saved:=flag;if saved{r=q};while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 7, 'semantic': 0}),
 ('uncalled_refborrow_capture_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){settrue(flag)};saved:=flag;if saved{r=q};while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 7, 'semantic': 0}),
 ('alias_before_both_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};f:=get;f();saved:=flag;if saved{r=q};while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 7, 'semantic': 0}),
 ('alias_between_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};f:=get;saved:=flag;if saved{r=q};f();while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('two_alias_before_both_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};f:=get;g:=f;g();saved:=flag;if saved{r=q};while flag{del '
  'p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 7, 'semantic': 0}),
 ('two_alias_between_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};f:=get;g:=f;saved:=flag;if saved{r=q};g();while flag{del '
  'p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('transitive_before_both_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};outer::fn(){get()};outer();saved:=flag;if saved{r=q};while '
  'flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 7, 'semantic': 0}),
 ('transitive_between_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};outer::fn(){get()};saved:=flag;if saved{r=q};outer();while '
  'flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('refborrow_before_both_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){settrue(flag)};get();saved:=flag;if saved{r=q};while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 7, 'semantic': 0}),
 ('refborrow_between_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){settrue(flag)};saved:=flag;if saved{r=q};get();while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('conditional_call_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};saved:=flag;if saved{r=q};if other{get()};while flag{del '
  'p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('deferred_call_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};saved:=flag;if saved{r=q};if true{defer get()};while flag{del '
  'p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('loop_call_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};saved:=flag;if saved{r=q};while other{get();break};while flag{del '
  'p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('mutable_alias_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};noop::fn(){};f:=noop;f=get;saved:=flag;if saved{r=q};f();while '
  'flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('callback_dead',
  'invoke::fn(f:fn()){f()}\n'
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};saved:=flag;if saved{r=q};invoke(get);while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('callback_before_both_valid',
  'invoke::fn(f:fn()){f()}\n'
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};invoke(get);saved:=flag;if saved{r=q};while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 7, 'semantic': 0}),
 ('same_spelling_distinct_binding_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};other_scope::fn(){flag:=false;change::fn(){flag=true};change()};saved:=flag;if '
  'saved{r=q};other_scope();while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 7, 'semantic': 0}),
 ('alias_distinct_binding_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};other_scope::fn(){flag:=false;change::fn(){flag=true};change()};saved:=flag;if '
  'saved{r=q};f:=other_scope;f();while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 7, 'semantic': 0}),
 ('argument_mutation_old_copy_dead',
  'pick::fn(first:bool,second:bool) bool{ret second}\n'
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn() bool{flag=true;ret true};saved:=flag;if '
  'saved{r=q};ignored:=pick(saved,get());while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 6, 'semantic': 6}),
 ('argument_mutation_before_both_valid',
  'pick::fn(first:bool,second:bool) bool{ret second}\n'
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn() bool{flag=true;ret true};ignored:=pick(get(),flag);saved:=flag;if '
  'saved{r=q};while flag{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 7, 'semantic': 0}),
 ('deferred_capture_nil_argument_boundary',
  'access::fn(a:ref[4]i32,b:bool){if b{x:=a[0]}}\n'
  'main::fn(){v:=false;later::fn(){v=true};defer {later()};access(nil,v)}\n',
  {'compile': 6, 'semantic': 6}),
 ('captured_literal_true_copy_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=true;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};saved:=flag;if saved{r=q};while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 7, 'semantic': 0}),
 ('captured_literal_false_copy_valid',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'turn::fn(flag:ref bool) bool{flag=true;ret true}\n'
  'run::fn(input:bool,other:bool){flag:=false;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];get::fn(){flag=true};saved:=flag;if saved{r=q};while flag{del p;break};if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  {'compile': 7, 'semantic': 0})]

@pytest.mark.parametrize("name,source,expected", CASES, ids=[x[0] for x in CASES])
def test_uncalled_capture_effects(tmp_path, name, source, expected):
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
            expected_code = "cannot_dereference" if name == "deferred_capture_nil_argument_boundary" else "use_after_move"
            assert any(d["code"] == expected_code and d["file"] == str(path) for d in error["details"])
            assert not out.exists()
        elif mode_expected == 7:
            error = json.loads(result.stdout)["error"]
            assert error["category"] == "codegen"
            assert "enclosing function" in error["message"]
            assert not out.exists()
        elif mode == "compile":
            assert "pub fn main" in out.read_text()
