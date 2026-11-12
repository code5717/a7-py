"""Boolean value identity and conditional cleanup must compose."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
CASES=[('copied_complement',
  'Box::struct{value:i32}\n'
  'Holder::struct{ptr:ref Box}\n'
  'setfalse::fn(b:ref bool){b=false}\n'
  'set::fn(h:ref Holder,p:ref Box){h.ptr=p}\n'
  'factory::fn() ref Box{ret new Box}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};copy:=flag;if copy{del p};if '
  '!flag{del p}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('copied_loop_complement',
  'Box::struct{value:i32}\n'
  'Holder::struct{ptr:ref Box}\n'
  'setfalse::fn(b:ref bool){b=false}\n'
  'set::fn(h:ref Holder,p:ref Box){h.ptr=p}\n'
  'factory::fn() ref Box{ret new Box}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};copy:=flag;while copy{del p;break};if '
  '!flag{del p}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('copied_mutation_repeat',
  'Box::struct{value:i32}\n'
  'Holder::struct{ptr:ref Box}\n'
  'setfalse::fn(b:ref bool){b=false}\n'
  'set::fn(h:ref Holder,p:ref Box){h.ptr=p}\n'
  'factory::fn() ref Box{ret new Box}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};copy:=flag;if copy{del '
  'p};flag=false;if !flag{del p}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('copied_refborrow_repeat',
  'Box::struct{value:i32}\n'
  'Holder::struct{ptr:ref Box}\n'
  'setfalse::fn(b:ref bool){b=false}\n'
  'set::fn(h:ref Holder,p:ref Box){h.ptr=p}\n'
  'factory::fn() ref Box{ret new Box}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};copy:=flag;if copy{del '
  'p};setfalse(flag);if !flag{del p}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('readonly_capture_complement',
  'Box::struct{value:i32}\n'
  'Holder::struct{ptr:ref Box}\n'
  'setfalse::fn(b:ref bool){b=false}\n'
  'set::fn(h:ref Holder,p:ref Box){h.ptr=p}\n'
  'factory::fn() ref Box{ret new Box}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};get::fn() bool{ret '
  'flag};copy:=flag;get();if copy{del p};if !flag{del p}}\n'
  'main::fn(){run(false);run(true)}\n',
  {'semantic': 0, 'compile': 7}),
 ('capture_mutation_repeat',
  'Box::struct{value:i32}\n'
  'Holder::struct{ptr:ref Box}\n'
  'setfalse::fn(b:ref bool){b=false}\n'
  'set::fn(h:ref Holder,p:ref Box){h.ptr=p}\n'
  'factory::fn() ref Box{ret new Box}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};change::fn(){flag=false};if flag{del '
  'p};change();if !flag{del p}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('capture_refborrow_repeat',
  'Box::struct{value:i32}\n'
  'Holder::struct{ptr:ref Box}\n'
  'setfalse::fn(b:ref bool){b=false}\n'
  'set::fn(h:ref Holder,p:ref Box){h.ptr=p}\n'
  'factory::fn() ref Box{ret new Box}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};change::fn(){setfalse(flag)};if '
  'flag{del p};change();if !flag{del p}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('false_entry_complement',
  'Box::struct{value:i32}\n'
  'Holder::struct{ptr:ref Box}\n'
  'setfalse::fn(b:ref bool){b=false}\n'
  'set::fn(h:ref Holder,p:ref Box){h.ptr=p}\n'
  'factory::fn() ref Box{ret new Box}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};flag=false;while flag{del p;break};if '
  '!flag{del p}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('nested_entry_write_repeat',
  'Box::struct{value:i32}\n'
  'Holder::struct{ptr:ref Box}\n'
  'setfalse::fn(b:ref bool){b=false}\n'
  'set::fn(h:ref Holder,p:ref Box){h.ptr=p}\n'
  'factory::fn() ref Box{ret new Box}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};flag=false;while true{flag=true;while '
  'flag{del p;break};break};if flag{del p}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('fresh_callee_current',
  'Box::struct{value:i32}\n'
  'Holder::struct{ptr:ref Box}\n'
  'setfalse::fn(b:ref bool){b=false}\n'
  'set::fn(h:ref Holder,p:ref Box){h.ptr=p}\n'
  'factory::fn() ref Box{ret new Box}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};old:=p;h:=Holder{ptr:p};copy:=flag;if '
  'copy{del h.ptr};q:=factory();if q==nil{ret};set(h,q);if h.ptr!=nil{v:=h.ptr.value;del h.ptr};if '
  '!flag{del old}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('fresh_callee_old_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{ptr:ref Box}\n'
  'setfalse::fn(b:ref bool){b=false}\n'
  'set::fn(h:ref Holder,p:ref Box){h.ptr=p}\n'
  'factory::fn() ref Box{ret new Box}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};old:=p;h:=Holder{ptr:p};copy:=flag;if '
  'copy{del h.ptr};q:=factory();if q==nil{ret};set(h,q);if flag{if old!=nil{v:=old.value}}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('fresh_callee_old_complement',
  'Box::struct{value:i32}\n'
  'Holder::struct{ptr:ref Box}\n'
  'setfalse::fn(b:ref bool){b=false}\n'
  'set::fn(h:ref Holder,p:ref Box){h.ptr=p}\n'
  'factory::fn() ref Box{ret new Box}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};old:=p;h:=Holder{ptr:p};copy:=flag;if '
  'copy{del h.ptr};q:=factory();if q==nil{ret};set(h,q);if !flag{if old!=nil{v:=old.value};del '
  'old};if h.ptr!=nil{del h.ptr}}\n'
  'main::fn(){run(false);run(true)}\n',
  0)]

@pytest.mark.parametrize("name,source,expected", CASES, ids=[x[0] for x in CASES])
def test_alias_cleanup_integration(tmp_path, name, source, expected):
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
            assert any(d["code"] == "use_after_move" and d["file"] == str(path) for d in error["details"])
            assert not out.exists()
        elif mode_expected == 7:
            error = json.loads(result.stdout)["error"]
            assert error["category"] == "codegen"
            assert "enclosing function" in error["message"]
            assert not out.exists()
        elif mode == "compile":
            assert "pub fn main" in out.read_text()
