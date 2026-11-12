"""Guarded reference slots survive readonly loops without reviving dead storage."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
CASES = [('readonly_entry_guard',
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};j:usize=0;while j<3{observe(n);j+=1}}\n'
  'main::fn(){i:usize=1;wrap(i)}\n',
  0,
  None),
 ('readonly_nested_loops',
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};j:usize=0;while j<3{k:usize=0;while '
  'k<2{observe(n);k+=1};j+=1}}\n'
  'main::fn(){i:usize=1;wrap(i)}\n',
  0,
  None),
 ('readonly_after_loop',
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};j:usize=0;while j<3{observe(n);j+=1};observe(n)}\n'
  'main::fn(){i:usize=1;wrap(i)}\n',
  0,
  None),
 ('readonly_deferred_loop',
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};j:usize=0;while j<3{defer observe(n);j+=1}}\n'
  'main::fn(){i:usize=1;wrap(i)}\n',
  0,
  None),
 ('readonly_condition',
  'observe::fn(n:ref usize){}\n'
  'check::fn(n:ref usize) bool{observe(n);ret false}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};while check(n){observe(n)}}\n'
  'main::fn(){i:usize=1;wrap(i)}\n',
  0,
  None),
 ('global_alias_delete',
  'observe::fn(n:ref usize){}\n'
  'g:ref usize\n'
  'kill::fn(){del g}\n'
  'wrap::fn(n:ref usize,flag:bool){if n==nil{ret};while flag{kill();observe(n)}}\n'
  'main::fn(){g=new usize;if g==nil{ret};wrap(g,true)}\n',
  6,
  'cannot_dereference'),
 ('global_alias_transitive_delete',
  'observe::fn(n:ref usize){}\n'
  'g:ref usize\n'
  'kill::fn(){del g}\n'
  'relay::fn(){kill()}\n'
  'wrap::fn(n:ref usize,flag:bool){if n==nil{ret};while flag{relay();observe(n)}}\n'
  'main::fn(){g=new usize;if g==nil{ret};wrap(g,true)}\n',
  6,
  'cannot_dereference'),
 ('global_alias_deferred_delete',
  'observe::fn(n:ref usize){}\n'
  'g:ref usize\n'
  'kill::fn(){del g}\n'
  'wrap::fn(n:ref usize,flag:bool){if n==nil{ret};while flag{defer kill();observe(n)}}\n'
  'main::fn(){g=new usize;if g==nil{ret};wrap(g,true)}\n',
  6,
  'cannot_dereference'),
 ('global_alias_condition_delete',
  'observe::fn(n:ref usize){}\n'
  'g:ref usize\n'
  'check::fn() bool{del g;ret true}\n'
  'wrap::fn(n:ref usize,flag:bool){if n==nil{ret};while check(){observe(n)}}\n'
  'main::fn(){g=new usize;if g==nil{ret};wrap(g,true)}\n',
  6,
  'cannot_dereference'),
 ('global_alias_nested_delete',
  'observe::fn(n:ref usize){}\n'
  'g:ref usize\n'
  'kill::fn(){del g}\n'
  'wrap::fn(n:ref usize,flag:bool){if n==nil{ret};while flag{while flag{kill();observe(n)}}}\n'
  'main::fn(){g=new usize;if g==nil{ret};wrap(g,true)}\n',
  6,
  'cannot_dereference'),
 ('direct_local_rebind',
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize){if n==nil{ret};a:=n;j:usize=0;while j<3{a=nil;observe(a);j+=1}}\n'
  'main::fn(){i:usize=1;wrap(i)}\n',
  6,
  'cannot_dereference'),
 ('parameter_delete',
  'observe::fn(n:ref usize){}\n'
  'wrap::fn(n:ref usize,flag:bool){if n==nil{ret};while flag{del n;observe(n)}}\n'
  'main::fn(){i:usize=1;wrap(i,true)}\n',
  6,
  'use_after_move')]

@pytest.mark.parametrize("name,source,expected,code", CASES, ids=[case[0] for case in CASES])
def test_readonly_reference_loop(tmp_path, name, source, expected, code):
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
