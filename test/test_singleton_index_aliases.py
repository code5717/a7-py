"""Current singleton local indices preserve exact fixed-array reference identity."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
CASES=[('exact_zero_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=0;xs[i].child=q;del '
  'q;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('exact_zero_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=0;xs[i].child=q;del '
  'p;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('reassigned_one_distinct',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=0;i=1;xs[i].child=q;del '
  'q;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('reassigned_zero_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=1;i=0;xs[i].child=q;del '
  'q;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('saved_before_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];saved:=xs[0].child;i:usize=0;xs[i].child=q;del '
  'p;r:=saved;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('saved_before_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];saved:=xs[0].child;i:usize=0;xs[i].child=q;del '
  'q;r:=saved;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('nil_replacement',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=0;xs[i].child=nil;del '
  'p;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('repeated_delete',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=0;xs[i].child=q;del q;del '
  'xs[0].child}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('fresh_replacement',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=0;xs[i].child=new Box;del '
  'p;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('branch_same_zero_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=1;if '
  'a{i=0}else{i=0};xs[i].child=q;del q;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('sibling_distinct',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box,other:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p,other:p},Holder{child:q,other:q}];i:usize=0;xs[i].child=q;del '
  'q;r:=xs[0].other;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('sibling_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box,other:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p,other:p},Holder{child:q,other:q}];i:usize=0;xs[i].child=q;del '
  'p;r:=xs[0].other;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('variable_read_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=0;xs[i].child=q;del '
  'q;r:=xs[i].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('variable_delete_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=0;xs[i].child=q;del q;del '
  'xs[i].child}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('compound_to_one_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=0;i+=1;xs[i].child=q;del '
  'q;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('compound_to_zero_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=1;i-=1;xs[i].child=q;del '
  'q;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('index_copy_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];j:usize=0;i:=j;j=1;xs[i].child=q;del '
  'q;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('index_copy_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];j:usize=1;i:=j;j=0;xs[i].child=q;del '
  'q;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('branch_disagree_distinct',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=0;if '
  'a{i=1};xs[i].child=p;del q;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('shadow_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=1;if '
  'a{i:usize=0;v:=i};xs[i].child=q;del q;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('loop_reassign_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=0;while i<1{i+=1};if '
  'i>=2{ret};xs[i].child=q;del q;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('borrowed_index_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'borrow::fn(i:ref usize){}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=0;borrow(i);i=1;if '
  'i>=2{ret};xs[i].child=q;del q;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('uncertain_index_valid_distinct',
  'Box::struct{value:i32}\n'
  '\n'
  'run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]ref '
  'Box=[p,q];i:usize=0;if b{i=1};if a{xs[i]=p};del q;r:=xs[0];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true,true);run(true,false);run(false,true);run(false,false)}',
  0),
 ('loop_backedge_distinct',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=0;while i<2{if '
  'i==1{xs[i].child=q};i+=1};del q;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0)]

@pytest.mark.parametrize("name,source,expected", CASES, ids=[case[0] for case in CASES])
def test_singleton_index_aliases(tmp_path, name, source, expected):
    path = tmp_path / (name + ".a7")
    path.write_text(source)
    output = tmp_path / (name + ".zig")
    for mode in ("semantic", "compile"):
        argv = [sys.executable, str(ROOT / "main.py"), str(path), "--mode", mode, "--format", "json"]
        if mode == "compile":
            argv += ["--output", str(output)]
        result = subprocess.run(argv, capture_output=True, text=True)
        assert result.returncode == expected, result.stdout + result.stderr
        assert result.stderr == ""
        data = json.loads(result.stdout)
        if expected == 6:
            assert data["error"]["category"] == "semantic"
            line = next(i for i, value in enumerate(source.splitlines(), 1) if value.startswith("run::"))
            assert any(detail["code"] == "use_after_move" and detail["file"] == str(path)
                       and detail["span"]["start_line"] == line for detail in data["error"]["details"])
            assert not output.exists()
        else:
            assert data["status"] == "ok"
            if mode == "compile":
                assert "pub fn main" in output.read_text()


def test_singleton_out_of_bounds_remains_rejected(tmp_path):
    source = next(source for name, source, _ in CASES if name == "exact_zero_dead")
    path = tmp_path / "out_of_bounds.a7"
    path.write_text(source.replace("i:usize=0;", "i:usize=2;"))
    output = tmp_path / "out_of_bounds.zig"
    for mode in ("semantic", "compile"):
        args = [sys.executable, str(ROOT / "main.py"), str(path), "--mode", mode, "--format", "json"]
        if mode == "compile":
            args += ["--output", str(output)]
        result = subprocess.run(args, capture_output=True, text=True)
        assert result.returncode == 6, result.stdout + result.stderr
        assert result.stderr == ""
        details = json.loads(result.stdout)["error"]["details"]
        assert any("Index not proven in bounds" in detail["message"] for detail in details)
        assert not output.exists()
