"""Mutually exclusive cleanup preserves allocation deaths on feasible paths."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
CASES=[('complementary_delete',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};while flag{del '
  'p;break};if !flag{del p};del q}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('same_condition_delete',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};while flag{del '
  'p;break};if flag{del p};del q}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('mutated_condition_delete',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};while flag{del '
  'p;break};flag=false;if !flag{del p};del q}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('nil_cleared',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};while flag{del '
  'p;p=nil;break};if p!=nil{del p};del q}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('complementary_read',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};old:=p;while '
  'flag{del p;break};if !flag{if old!=nil{v:=old.value};del p};del q}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('same_condition_read',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};old:=p;while '
  'flag{del p;break};if flag{if old!=nil{v:=old.value}};del q}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('if_complementary_delete',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};if flag{del '
  'p};if !flag{del p};del q}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('if_same_delete',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};if flag{del '
  'p};if flag{del p};del q}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('distinct_cleanup',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};while flag{del '
  'p;break};if !flag{del q}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('original_correlated_distinct',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool){\n'
  'flag:=input\n'
  'p:=new Box;if p==nil{ret};p.value=7\n'
  'q:=new Box;if q==nil{del p;ret};q.value=17\n'
  'xs:[2]ref Box=[p,q]\n'
  'r:=xs[0]\n'
  'if flag{r=q}\n'
  'while flag{del p;break}\n'
  'if r!=nil{io.println("{}",r.value)}\n'
  'if !flag{del p};del q\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('original_nil_current',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool){\n'
  'flag:=input\n'
  'p:=new Box;if p==nil{ret};p.value=7\n'
  'q:=new Box;if q==nil{del p;ret};q.value=17\n'
  'xs:[2]ref Box=[p,q]\n'
  'r:=xs[0]\n'
  'while flag{del p;r=nil;break}\n'
  'if r!=nil{io.println("{}",r.value)}else{io.println("{}",0)}\n'
  'if !flag{del p};del q\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('original_shadow_false',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool){\n'
  'flag:=input\n'
  'p:=new Box;if p==nil{ret};p.value=7\n'
  'q:=new Box;if q==nil{del p;ret};q.value=17\n'
  'xs:[2]ref Box=[p,q]\n'
  'r:=xs[0]\n'
  'if flag{r=q}\n'
  'if true{flag:=false;while flag{del q;break}}\n'
  'while flag{del p;break}\n'
  'if r!=nil{io.println("{}",r.value)}\n'
  'if !flag{del p};del q\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('original_mutation_before',
  'io::import "std/io"\n'
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'run::fn(input:bool){\n'
  'flag:=input\n'
  'p:=new Box;if p==nil{ret};p.value=7\n'
  'q:=new Box;if q==nil{del p;ret};q.value=17\n'
  'xs:[2]ref Box=[p,q]\n'
  'r:=xs[0]\n'
  'settrue(flag)\n'
  'if flag{r=q}\n'
  'while flag{del p;break}\n'
  'if r!=nil{io.println("{}",r.value)}\n'
  'if !flag{del p};del q\n'
  '}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('negation',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};if '
  '!!flag{del p};if !flag{del p};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('within_branch_repeat',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};if '
  'flag{del p;del p};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('ref_mutation',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};if '
  'flag{del p};setfalse(flag);if !flag{del p};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('different_flag',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};if '
  'flag{del p};if other{del p};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('shadowed_flag_repeat',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};if '
  'flag{del p};if true{flag:=false;if !flag{del p}};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('complementary_alias_delete',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del '
  'p;ret};old:=p;if flag{del p};if !flag{del old};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('same_alias_delete',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del '
  'p;ret};old:=p;if flag{del p};if flag{del old};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('nested_complementary',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};if '
  'flag{if other{del p}else{del p}};if !flag{del p};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('nested_partial_repeat',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};if '
  'flag{if other{del p}};if flag{del p};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('return_path',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};if '
  'flag{del p;del q;ret};del p;del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('return_saved_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del '
  'p;ret};old:=p;if flag{del p;del q;ret};del p;if old!=nil{v:=old.value};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('break_exit',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del '
  'p;ret};while flag{if other{del p;break};del p;break};if !flag{del p};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('continue_nil',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del '
  'p;ret};i:usize=0;while i<1{del p;p=nil;i+=1;continue};if p!=nil{del p};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('defer_same_repeat',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};if '
  'flag{defer del p;del p};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('defer_complementary',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};if '
  'flag{defer del p};if !flag{del p};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('nil_saved_dead',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del '
  'p;ret};old:=p;while flag{del p;p=nil;break};if flag{if old!=nil{v:=old.value}};if p!=nil{del p};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('branch_clear_preserves_old',
  'Box::struct{value:i32}\n'
  'settrue::fn(flag:ref bool){flag=true}\n'
  'setfalse::fn(flag:ref bool){flag=false}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del '
  'p;ret};old:=p;if flag{del p;p=nil};if flag{if old!=nil{v:=old.value}};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6)]

CASES.extend([('entry_mutation_repeat',
  'Box::struct{value:i32}\n'
  'Holder::struct{left:ref Box,right:ref Box}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};if '
  'flag{del p;flag=false};if !flag{del p};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('defer_mutation_repeat',
  'Box::struct{value:i32}\n'
  'Holder::struct{left:ref Box,right:ref Box}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del p;ret};if '
  'flag{defer del p;flag=false};if !flag{del p};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('defer_continue_complement',
  'Box::struct{value:i32}\n'
  'Holder::struct{left:ref Box,right:ref Box}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del '
  'p;ret};i:usize=0;while i<1{if flag{defer del p};i+=1;continue};if !flag{del p};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('defer_continue_repeat',
  'Box::struct{value:i32}\n'
  'Holder::struct{left:ref Box,right:ref Box}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del '
  'p;ret};i:usize=0;while i<1{if flag{defer del p};i+=1;continue};if flag{del p};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('fresh_current_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{left:ref Box,right:ref Box}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del '
  'p;ret};old:=p;if flag{del p;p=new Box};if p!=nil{v:=p.value};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('fresh_old_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{left:ref Box,right:ref Box}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del '
  'p;ret};old:=p;if flag{del p;p=new Box};if flag{if old!=nil{v:=old.value}};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('fresh_old_complement_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{left:ref Box,right:ref Box}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del '
  'p;ret};old:=p;if flag{del p;p=new Box};if !flag{if old!=nil{v:=old.value}};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('sibling_fields_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{left:ref Box,right:ref Box}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del '
  'p;ret};h:=Holder{left:p,right:q};if flag{del h.left};if !flag{del h.right}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('sibling_shared_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{left:ref Box,right:ref Box}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del '
  'p;ret};h:=Holder{left:p,right:p};old:=h.left;if flag{del h.left};if !flag{del h.right};if '
  'old!=nil{v:=old.value};del q}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  6),
 ('selected_holder_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{left:ref Box,right:ref Box}\n'
  'run::fn(input:bool,other:bool){flag:=input;p:=new Box;if p==nil{ret};q:=new Box;if q==nil{del '
  'p;ret};a:=new Holder;if a==nil{ret};b:=new Holder;if '
  'b==nil{ret};a.left=p;a.right=q;b.left=q;b.right=p;h:=a;if flag{h=b};if h!=nil{if flag{del h.left};if '
  '!flag{del h.left}}}\n'
  'main::fn(){run(false,false);run(false,true);run(true,false);run(true,true)}\n',
  0),
 ('unknown_parameter_complement',
  'Box::struct{value:i32}\n'
  'cleanup::fn(p:ref Box,flag:bool){if p==nil{ret};if flag{del p};if !flag{del p}}\n'
  'main::fn(){p:=new Box;if p==nil{ret};cleanup(p,true)}\n',
  0),
 ('unknown_parameter_repeat',
  'Box::struct{value:i32}\n'
  'cleanup::fn(p:ref Box,flag:bool){if p==nil{ret};if flag{del p};if flag{del p}}\n'
  'main::fn(){p:=new Box;if p==nil{ret};cleanup(p,true)}\n',
  6)])

@pytest.mark.parametrize("name,source,expected",CASES,ids=[x[0] for x in CASES])
def test_conditional_cleanup(tmp_path,name,source,expected):
    path=tmp_path/(name+".a7");path.write_text(source);output=tmp_path/(name+".zig")
    for mode in ("semantic","compile"):
        argv=[sys.executable,str(ROOT/"main.py"),str(path),"--mode",mode,"--format","json"]
        if mode=="compile":argv += ["--output",str(output)]
        result=subprocess.run(argv,capture_output=True,text=True)
        assert result.returncode==expected,result.stdout+result.stderr
        assert result.stderr==""
        data=json.loads(result.stdout)
        if expected==6:
            assert data["error"]["category"]=="semantic"
            assert any(d["code"]=="use_after_move" and d["file"]==str(path) and d["span"]["start_line"]>0 for d in data["error"]["details"])
            assert not output.exists()
        else:
            assert data["status"]=="ok"
            if mode=="compile":assert "pub fn main" in output.read_text()
