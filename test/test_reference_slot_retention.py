"""Stable local reference slots survive rebinding of unrelated global slots."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
CASES = [('local_alias_entry_guard',
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};a:=n;j:usize=0;while j<3{observe(a);j+=1}}\n'
  'main::fn(){i:usize=1;wrap(i)}\n',
  0,
  None),
 ('global_rebind_valid',
  'observe::fn(n:ref usize){}\n'
  'g:ref usize\n'
  'rebind::fn(){g=nil}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};j:usize=0;while j<3{rebind();observe(n);j+=1}}\n'
  'main::fn(){g=new usize;if g==nil{ret};wrap(g)}\n',
  0,
  None),
 ('global_rebind_reference_rhs',
  'observe::fn(n:ref usize){}\n'
  'g:ref usize\n'
  'h:ref usize\n'
  'rebind::fn(){g=h}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};j:usize=0;while j<3{rebind();observe(n);j+=1}}\n'
  'main::fn(){g=new usize;if g==nil{ret};wrap(g)}\n',
  0,
  None),
 ('global_rebind_fresh_rhs',
  'observe::fn(n:ref usize){}\n'
  'g:ref usize\n'
  'rebind::fn(){g=new usize}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};j:usize=0;while j<3{rebind();observe(n);j+=1}}\n'
  'main::fn(){g=new usize;if g==nil{ret};wrap(g)}\n',
  0,
  None),
 ('local_copy_unrelated_global_rebind',
  'observe::fn(n:ref usize){}\n'
  'g:ref usize\n'
  'rebind::fn(){g=nil}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};a:=n;j:usize=0;while j<3{rebind();observe(a);j+=1}}\n'
  'main::fn(){g=new usize;if g==nil{ret};wrap(g)}\n',
  0,
  None),
 ('global_rebind_rhs_deletes',
  'observe::fn(n:ref usize){}\n'
  'g:ref usize\n'
  'make::fn() ref usize{del g;ret nil}\n'
  'rebind::fn(){g=make()}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};j:usize=0;while j<3{rebind();observe(n);j+=1}}\n'
  'main::fn(){g=new usize;if g==nil{ret};wrap(g)}\n',
  6,
  'use_after_move'),
 ('global_delete_then_fresh',
  'observe::fn(n:ref usize){}\n'
  'g:ref usize\n'
  'rebind::fn(){del g;g=new usize}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};j:usize=0;while j<3{rebind();observe(n);j+=1}}\n'
  'main::fn(){g=new usize;if g==nil{ret};wrap(g)}\n',
  6,
  'use_after_move'),
 ('captured_local_nil',
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};a:=n;clear::fn(){a=nil};j:usize=0;while '
  'j<3{clear();observe(a);j+=1}}\n'
  'main::fn(){i:usize=1;wrap(i)}\n',
  6,
  'cannot_dereference'),
 ('deferred_captured_local_nil',
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};a:=n;clear::fn(){a=nil};j:usize=0;while j<3{defer '
  'clear();observe(a);j+=1}}\n'
  'main::fn(){i:usize=1;wrap(i)}\n',
  6,
  'cannot_dereference'),
 ('deferred_local_nil',
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};a:=n;j:usize=0;while j<3{defer {a=nil};observe(a);j+=1}}\n'
  'main::fn(){i:usize=1;wrap(i)}\n',
  6,
  'cannot_dereference'),
 ('sibling_parameter_delete',
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize,m:ref usize,flag:bool){if n==nil{ret};if m==nil{ret};while flag{del '
  'm;observe(n)}}\n'
  'main::fn(){p:=new usize;if p==nil{ret};wrap(p,p,true)}\n',
  6,
  'use_after_move'),
 ('selected_allocation_delete',
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize,m:ref usize,choose:bool,flag:bool){if n==nil{ret};if m==nil{ret};a:=n;if '
  'choose{a=m};if a==nil{ret};while flag{del n;observe(a)}}\n'
  'main::fn(){p:=new usize;if p==nil{ret};q:=new usize;if q==nil{ret};wrap(p,q,false,true)}\n',
  6,
  'use_after_move'),
 ('unknown_global_deleter',
  'observe::fn(n:ref usize){}\n'
  'g:ref usize\n'
  'kill::fn(){del g}\n'
  'wrap::fn(n:ref usize,f:fn(),flag:bool){if n==nil{ret};while flag{f();observe(n)}}\n'
  'main::fn(){g=new usize;if g==nil{ret};wrap(g,kill,true)}\n',
  6,
  'cannot_dereference')]

@pytest.mark.parametrize("name,source,expected,code", CASES, ids=[case[0] for case in CASES])
def test_reference_slot_retention(tmp_path, name, source, expected, code):
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
