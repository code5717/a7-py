"""Fresh conditional replacements preserve current sharing and old alias death."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
CASES = [('valid',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'run :: fn(change: bool) {\n'
  '    p := new Box\n'
  '    if p == nil { ret }\n'
  '    p.value = 7\n'
  '    \n'
  '    if change {\n'
  '        del p\n'
  '        p = new Box\n'
  '        if p == nil { ret }\n'
  '        p.value = 9\n'
  '    }\n'
  '    if p == nil { ret }\n'
  '    io.println("{}", p.value)\n'
  '}\n'
  'main :: fn() { run(true); run(false) }\n',
  0),
 ('deleted',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'run :: fn(change: bool) {\n'
  '    p := new Box\n'
  '    if p == nil { ret }\n'
  '    p.value = 7\n'
  '    \n'
  '    if change {\n'
  '        del p\n'
  '        \n'
  '    }\n'
  '    if p == nil { ret }\n'
  '    io.println("{}", p.value)\n'
  '}\n'
  'main :: fn() { run(true); run(false) }\n',
  6),
 ('stale_alias',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'run :: fn(change: bool) {\n'
  '    p := new Box\n'
  '    if p == nil { ret }\n'
  '    p.value = 7\n'
  '    old := p\n'
  '    if change {\n'
  '        del p\n'
  '        p = new Box\n'
  '        if p == nil { ret }\n'
  '        p.value = 9\n'
  '    }\n'
  '    if old == nil { ret }\n'
  '    io.println("{}", old.value)\n'
  '}\n'
  'main :: fn() { run(true); run(false) }\n',
  6),
 ('swapped_distinct',
  'Box::struct{value:i32}\n'
  'run::fn(change:bool){p:=new Box;if p==nil{ret};p.value=7;q:=new Box;if '
  'q==nil{ret};q.value=17;if change{tmp:=p;p=q;q=tmp};del p;if q!=nil{v:=q.value};del q}\n'
  'main::fn(){run(true);run(false)}',
  0),
 ('shared_on_one_branch',
  'Box::struct{value:i32}\n'
  'run::fn(change:bool){p:=new Box;if p==nil{ret};p.value=7;q:=new Box;if '
  'q==nil{ret};q.value=17;if change{q=p};del p;if q!=nil{v:=q.value}}\n'
  'main::fn(){run(true);run(false)}',
  6),
 ('alias_after_join',
  'Box::struct{value:i32}\n'
  'run::fn(change:bool){p:=new Box;if p==nil{ret};p.value=7;q:=new Box;if '
  'q==nil{ret};q.value=17;if change{del p;p=new Box;if p==nil{ret}};q=p;del p;if '
  'q!=nil{v:=q.value}}\n'
  'main::fn(){run(true);run(false)}',
  6),
 ('former_slot',
  'Box::struct{value:i32}\n'
  'run::fn(change:bool){p:=new Box;if p==nil{ret};p.value=7;q:=new Box;if '
  'q==nil{ret};q.value=17;saved:=q;if change{q=p;del p;p=new Box;if p==nil{ret}};if '
  'saved!=nil{v:=saved.value};del saved}\n'
  'main::fn(){run(true);run(false)}',
  0),
 ('former_slot_deleted',
  'Box::struct{value:i32}\n'
  'run::fn(change:bool){p:=new Box;if p==nil{ret};p.value=7;q:=new Box;if '
  'q==nil{ret};q.value=17;saved:=q;if change{q=p;del p;p=new Box;if p==nil{ret}};del saved;if '
  'saved!=nil{v:=saved.value}}\n'
  'main::fn(){run(true);run(false)}',
  6),
 ('nested_valid',
  'Box::struct{value:i32}\n'
  'run::fn(change:bool){p:=new Box;if p==nil{ret};p.value=7;q:=new Box;if '
  'q==nil{ret};q.value=17;if change{del p;if q!=nil{p=new Box;if p==nil{ret}}else{ret}};if '
  'p!=nil{v:=p.value}}\n'
  'main::fn(){run(true);run(false)}',
  0),
 ('return_after_delete',
  'Box::struct{value:i32}\n'
  'run::fn(change:bool){p:=new Box;if p==nil{ret};p.value=7;q:=new Box;if '
  'q==nil{ret};q.value=17;if change{del p;ret};if p!=nil{v:=p.value}}\n'
  'main::fn(){run(true);run(false)}',
  0),
 ('defer_old',
  'Box::struct{value:i32}\n'
  'run::fn(change:bool){p:=new Box;if p==nil{ret};p.value=7;q:=new Box;if '
  'q==nil{ret};q.value=17;if change{old:=p;defer del old;p=new Box;if p==nil{ret}};if '
  'p!=nil{v:=p.value}}\n'
  'main::fn(){run(true);run(false)}',
  0),
 ('defer_current',
  'Box::struct{value:i32}\n'
  'run::fn(change:bool){p:=new Box;if p==nil{ret};p.value=7;q:=new Box;if '
  'q==nil{ret};q.value=17;if change{p=new Box;if p==nil{ret};defer del p};if p!=nil{v:=p.value}}\n'
  'main::fn(){run(true);run(false)}',
  6)]

CASES += [
    ("canonical_field_replaced", """
Box::struct{value:i32}
Holder::struct{child:ref Box}
run::fn(change:bool){
 p:=new Box;if p==nil{ret}
 h:=new Holder;if h==nil{ret};h.child=p;alias:=h
 if change{del h.child;h.child=new Box;if h.child==nil{ret}}
 if alias.child!=nil{v:=alias.child.value}
}
main::fn(){run(true);run(false)}
""", 0),
    ("canonical_field_saved_old", """
Box::struct{value:i32}
Holder::struct{child:ref Box}
run::fn(change:bool){
 p:=new Box;if p==nil{ret}
 h:=new Holder;if h==nil{ret};h.child=p;old:=h.child
 if change{del h.child;h.child=new Box;if h.child==nil{ret}}
 if old!=nil{v:=old.value}
}
main::fn(){run(true);run(false)}
""", 6),
    ("canonical_field_alias_delete", """
Box::struct{value:i32}
Holder::struct{child:ref Box}
run::fn(change:bool){
 p:=new Box;if p==nil{ret}
 h:=new Holder;if h==nil{ret};h.child=p;alias:=h
 if change{del h.child;h.child=new Box;if h.child==nil{ret}}
 q:=alias.child;if q==nil{ret};del h.child;v:=q.value
}
main::fn(){run(true);run(false)}
""", 6),
    ("callee_delete_replaced", """
Box::struct{value:i32}
kill::fn(x:ref Box){del x}
run::fn(change:bool){p:=new Box;if p==nil{ret};
 if change{kill(p);p=new Box;if p==nil{ret}}
 if p!=nil{v:=p.value}
}
main::fn(){run(true);run(false)}
""", 0),
    ("callee_delete_old_alias", """
Box::struct{value:i32}
kill::fn(x:ref Box){del x}
run::fn(change:bool){p:=new Box;if p==nil{ret};old:=p;
 if change{kill(p);p=new Box;if p==nil{ret}}
 if old!=nil{v:=old.value}
}
main::fn(){run(true);run(false)}
""", 6),
    ("two_nested_fresh_arms", """
Box::struct{value:i32}
run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};
 if a{del p;if b{p=new Box}else{p=new Box};if p==nil{ret}}
 if p!=nil{v:=p.value}
}
main::fn(){run(true,true);run(true,false);run(false,true)}
""", 0),
    ("nested_missing_replacement", """
Box::struct{value:i32}
run::fn(a:bool,b:bool){p:=new Box;if p==nil{ret};
 if a{del p;if b{p=new Box;if p==nil{ret}}}
 if p!=nil{v:=p.value}
}
main::fn(){run(true,true);run(true,false);run(false,true)}
""", 6),
]

@pytest.mark.parametrize("name,source,expected", CASES, ids=[x[0] for x in CASES])
def test_conditional_reference_replacement(tmp_path, name, source, expected):
    path = tmp_path / (name + ".a7")
    path.write_text(source)
    output = tmp_path / (name + ".zig")
    run = subprocess.run([sys.executable, str(ROOT / "main.py"), str(path), "--mode", "compile", "--format", "json", "--output", str(output)], capture_output=True, text=True)
    assert run.returncode == expected, run.stdout + run.stderr
    assert run.stderr == ""
    if expected == 6:
        error = json.loads(run.stdout)["error"]
        assert error["category"] == "semantic"
        assert any(item["code"] == "use_after_move" and item["file"] == str(path) and item["span"]["start_line"] > 0 for item in error["details"])
        assert not output.exists()
    else:
        assert "pub fn main" in output.read_text()
