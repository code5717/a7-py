"""Conditioned literal slots retain referents without inventing missing facts.

Unknown-write and loop-marker acceptances pin compatibility, not native safety.
"""
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
CASES = [('shared_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[2]ref Box=[p,q];if a{xs[1]=xs[0]};del xs[0];r:=xs[1];if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('fresh_old_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[2]ref Box=[p,q];r:=xs[0];if a{del xs[0];xs[0]=new Box;if '
  'xs[0]==nil{ret}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('one_branch_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[2]ref Box=[p,q];if a{del xs[0]};r:=xs[0];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  6),
 ('swap_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[2]ref Box=[p,q];if a{t:=xs[0];xs[0]=xs[1];xs[1]=t};del '
  'xs[0];r:=xs[1];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  0),
 ('fresh_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[2]ref Box=[p,q];if a{del xs[0];xs[0]=new Box;if '
  'xs[0]==nil{ret}};r:=xs[0];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  0),
 ('reassigned_distinct_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[2]ref Box=[p,q];if a{xs[1]=xs[0]};xs[1]=new Box;if '
  'xs[1]==nil{ret};del xs[0];r:=xs[1];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}\n',
  0),
 ('repeated_delete',
  'Box::struct{value:i32}\n'
  '\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];if a{xs[1]=xs[0]};del xs[0];del xs[1]}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}',
  6),
 ('postjoin_alias',
  'Box::struct{value:i32}\n'
  '\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];if a{xs[1]=xs[0]};r:=xs[1];del xs[0];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}',
  6),
 ('before_delete',
  'Box::struct{value:i32}\n'
  '\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];if a{xs[1]=xs[0]};r:=xs[1];if r!=nil{v:=r.value};del xs[0]}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}',
  0),
 ('nested_dead',
  'Box::struct{value:i32}\n'
  '\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];if a{if b{xs[1]=xs[0]}};del xs[0];r:=xs[1];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}',
  6),
 ('nested_fresh',
  'Box::struct{value:i32}\n'
  '\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];if a{del xs[0];if b{xs[0]=new Box}else{xs[0]=new Box};if xs[0]==nil{ret}};r:=xs[0];if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}',
  0),
 ('terminating_delete',
  'Box::struct{value:i32}\n'
  '\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];if a{del xs[0];ret};r:=xs[0];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}',
  0),
 ('copy_old_dead',
  'Box::struct{value:i32}\n'
  '\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];copy:=xs;if a{xs[0]=q};del p;r:=copy[0];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}',
  6),
 ('copy_independent',
  'Box::struct{value:i32}\n'
  '\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];copy:=xs;if a{xs[0]=q}else{xs[0]=q};del p;r:=xs[0];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}',
  0),
 ('nested_array_dead',
  'Box::struct{value:i32}\n'
  '\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];grid:[2][2]ref Box=[[p,q],[q,q]];grid[0][0]=p;grid[1][0]=q;if '
  'a{grid[1][0]=grid[0][0]};del grid[0][0];r:=grid[1][0];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}',
  6),
 ('nested_array_distinct',
  'Box::struct{value:i32}\n'
  '\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];grid:[2][2]ref Box=[[p,q],[q,q]];grid[0][0]=p;grid[1][0]=q;if a{grid[0][0]=q};del '
  'p;r:=grid[1][0];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}',
  0),
 ('unknown_write_compatibility',
  'Box::struct{value:i32}\n'
  '\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];i:usize=0;if a{xs[i]=q};del p;r:=xs[0];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}',
  6),
 ('loop_marker',
  'Box::struct{value:i32}\n'
  'mutate::fn(xs:ref [2]ref Box,value:ref Box){xs=[value,value]}\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];if a{xs[1]=q};while b{del p;break};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(false,false)}\n',
  6),
 ('borrow_marker',
  'Box::struct{value:i32}\n'
  'mutate::fn(xs:ref [2]ref Box,value:ref Box){xs=[value,value]}\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];r:=xs[0];if a{xs[1]=q};mutate(xs,q);del p;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(false,false)}\n',
  6)]

@pytest.mark.parametrize("name,source,expected", CASES, ids=[x[0] for x in CASES])
def test_conditional_array_aliases(tmp_path, name, source, expected):
    path = tmp_path / (name + ".a7")
    path.write_text(source)
    out = tmp_path / (name + ".zig")
    for mode in ("semantic", "compile"):
        args = [sys.executable, str(ROOT / "main.py"), str(path), "--mode", mode, "--format", "json"]
        if mode == "compile":
            args += ["--output", str(out)]
        result = subprocess.run(args, capture_output=True, text=True)
        assert result.returncode == expected, result.stdout + result.stderr
        assert result.stderr == ""
        if expected == 6:
            error = json.loads(result.stdout)["error"]
            assert error["category"] == "semantic"
            assert any(d["code"] == "use_after_move" and d["file"] == str(path) and d["span"]["start_line"] == 3 for d in error["details"])
            assert not out.exists()
        elif mode == "compile":
            assert "pub fn main" in out.read_text()
