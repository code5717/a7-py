"""Nested aggregate constructors preserve reference identities at literal cells."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
CASES = [('direct_dead',
  'Box::struct{value:i32}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;grid:[2][2]ref Box=[[p,q],[q,q]];del p;r:=grid[0][0];if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('direct_distinct',
  'Box::struct{value:i32}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;grid:[2][2]ref Box=[[p,q],[q,q]];del p;r:=grid[1][0];if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('slot_dead',
  'Box::struct{value:i32}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;grid:[2][2]ref Box=[[p,q],[q,q]];r:=grid[0][0];del grid[0][0];if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('slot_distinct',
  'Box::struct{value:i32}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;grid:[2][2]ref Box=[[p,q],[q,q]];r:=grid[1][0];del grid[0][0];if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('branch_dead',
  'Box::struct{value:i32}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;grid:[2][2]ref Box=[[p,q],[q,q]];if a{grid[1][0]=grid[0][0]};del '
  'grid[0][0];r:=grid[1][0];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('branch_distinct',
  'Box::struct{value:i32}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;grid:[2][2]ref Box=[[p,q],[q,q]];if a{grid[0][0]=q};del '
  'p;r:=grid[1][0];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('before_delete',
  'Box::struct{value:i32}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;grid:[2][2]ref Box=[[p,q],[q,q]];r:=grid[0][0];if r!=nil{v:=r.value};del '
  'p}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('double_delete',
  'Box::struct{value:i32}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;grid:[2][2]ref Box=[[p,q],[q,q]];del grid[1][0];del grid[1][1]}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('struct_conditional_saved_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[2]Holder=[Holder{child:p},Holder{child:q}];r:=xs[0].child;if '
  'a{xs[0].child=q};del p;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('struct_conditional_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[2]Holder=[Holder{child:p},Holder{child:q}];if '
  'a{xs[0].child=q}else{xs[0].child=q};del p;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('struct_element_saved_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[2]Holder=[Holder{child:p},Holder{child:q}];r:=xs[0].child;xs[0]=Holder{child:q};del '
  'p;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('struct_element_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[2]Holder=[Holder{child:p},Holder{child:q}];xs[0]=Holder{child:q};del '
  'p;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('struct_row_saved_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[1][1]Holder=[[Holder{child:p}]];r:=xs[0][0].child;xs[0]=[Holder{child:q}];del '
  'p;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('struct_row_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[1][1]Holder=[[Holder{child:p}]];xs[0]=[Holder{child:q}];del '
  'p;r:=xs[0][0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('struct_field_saved_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[2]Holder=[Holder{child:p},Holder{child:q}];r:=xs[0].child;xs[0].child=q;del '
  'p;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('struct_field_overwrite_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[2]Holder=[Holder{child:p},Holder{child:q}];xs[0].child=q;del '
  'p;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('struct_copy_saved_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[2]Holder=[Holder{child:p},Holder{child:q}];copy:=xs[0];xs[0].child=q;del '
  'p;r:=copy.child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('struct_copy_independent',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[2]Holder=[Holder{child:p},Holder{child:q}];copy:=xs[0];copy.child=q;del '
  'p;r:=copy.child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('struct_shared_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[2]Holder=[Holder{child:p},Holder{child:p}];del '
  'xs[0].child;r:=xs[1].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('struct_delete_distinct',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[2]Holder=[Holder{child:p},Holder{child:q}];del '
  'xs[0].child;r:=xs[1].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('three_dimensions_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;cube:[1][1][2]ref Box=[[[p,q]]];del p;r:=cube[0][0][0];if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('three_dimensions_distinct',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;cube:[1][1][2]ref Box=[[[p,q]]];del p;r:=cube[0][0][1];if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('struct_array_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[2]Holder=[Holder{child:p},Holder{child:q}];del p;r:=xs[0].child;if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('struct_array_distinct',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;xs:[2]Holder=[Holder{child:p},Holder{child:q}];del p;r:=xs[1].child;if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('array_struct_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;g:=Grid{cells:[[p,q],[q,q]]};del p;r:=g.cells[0][0];if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('array_struct_distinct',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;g:=Grid{cells:[[p,q],[q,q]]};del p;r:=g.cells[1][0];if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('row_copy_saved_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;row:[2]ref Box=[p,q];grid:[1][2]ref Box=[row];row[0]=q;del '
  'p;r:=grid[0][0];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('row_copy_independent',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;row:[2]ref Box=[p,q];grid:[1][2]ref Box=[row];grid[0][0]=q;del '
  'p;r:=grid[0][0];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('row_overwrite_saved_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;grid:[2][2]ref Box=[[p,q],[q,q]];r:=grid[0][0];grid[0]=[q,q];del p;if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('row_overwrite_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;grid:[2][2]ref Box=[[p,q],[q,q]];grid[0]=[q,q];del p;r:=grid[0][0];if '
  'r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('fresh_saved_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;grid:[1][1]ref Box=[[p]];r:=grid[0][0];del p;grid[0][0]=new Box;if '
  'grid[0][0]==nil{ret};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('fresh_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;grid:[1][1]ref Box=[[p]];del p;grid[0][0]=new Box;if '
  'grid[0][0]==nil{ret};r:=grid[0][0];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0),
 ('condition_old_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;grid:[1][1]ref Box=[[p]];r:=grid[0][0];if a{del p;grid[0][0]=new Box;if '
  'grid[0][0]==nil{ret}};if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  6),
 ('condition_fresh_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Grid::struct{cells:[2][2]ref Box}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if '
  'q==nil{ret};q.value=2;grid:[1][1]ref Box=[[p]];if a{del p;grid[0][0]=new Box;if '
  'grid[0][0]==nil{ret}};r:=grid[0][0];if r!=nil{v:=r.value}}\n'
  'main::fn(){run(true);run(false)}\n',
  0)]

# Unknown indexed writes discard obsolete exact-cell identities.
CASES.append(("dynamic_field_live", 'Box::struct{value:i32}\nHolder::struct{child:ref Box}\nWrap::struct{cells:[2]Holder}\nrun::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=0;xs[i].child=q;del p;r:=xs[0].child;if r!=nil{v:=r.value}}\nmain::fn(){run(false);run(true)}\n', 0))

CASES.extend([('dynamic_whole_element_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];i:usize=0;xs[i]=Holder{child:q};del '
  'p;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('dynamic_saved_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p},Holder{child:q}];saved:=xs[0].child;i:usize=0;xs[i].child=q;del '
  'p;r:=saved;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('dynamic_nested_field_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[1][2]Holder=[[Holder{child:p},Holder{child:q}]];i:usize=0;xs[0][i].child=q;del '
  'p;r:=xs[0][0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('dynamic_nested_row_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[1][2]Holder=[[Holder{child:p},Holder{child:q}]];i:usize=0;xs[i]=[Holder{child:q},Holder{child:q}];del '
  'p;r:=xs[0][0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('dynamic_wrapped_field_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};w:=Wrap{cells:[Holder{child:p},Holder{child:q}]};i:usize=0;w.cells[i].child=q;del '
  'p;r:=w.cells[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('dynamic_ref_holder_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};w:=new Wrap;if '
  'w==nil{ret};w.cells=[Holder{child:p},Holder{child:q}];i:usize=0;w.cells[i].child=q;del '
  'p;r:=w.cells[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0)])

CASES.extend([('dynamic_unrelated_scalar_assign_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box,count:i32}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p,count:0},Holder{child:q,count:0}];i:usize=0;xs[i].count=7;del '
  'p;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('dynamic_unrelated_scalar_assign_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box,count:i32}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p,count:0},Holder{child:q,count:0}];i:usize=0;xs[i].count=7;del '
  'q;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('dynamic_unrelated_scalar_compound_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box,count:i32}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p,count:0},Holder{child:q,count:0}];i:usize=0;xs[i].count+=1;del '
  'p;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('dynamic_unrelated_scalar_compound_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box,count:i32}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p,count:0},Holder{child:q,count:0}];i:usize=0;xs[i].count+=1;del '
  'q;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('dynamic_sibling_ref_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box,other:ref Box,count:i32}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p,other:q,count:0},Holder{child:q,other:q,count:0}];i:usize=0;xs[i].other=q;del '
  'p;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('dynamic_sibling_ref_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box,other:ref Box,count:i32}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[2]Holder=[Holder{child:p,other:q,count:0},Holder{child:q,other:q,count:0}];i:usize=0;xs[i].other=q;del '
  'q;r:=xs[0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0),
 ('dynamic_nested_sibling_dead',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box,other:ref Box,count:i32}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[1][2]Holder=[[Holder{child:p,other:q,count:0},Holder{child:q,other:q,count:0}]];i:usize=0;xs[0][i].other=q;del '
  'p;r:=xs[0][0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  6),
 ('dynamic_nested_sibling_live',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box,other:ref Box,count:i32}\n'
  'Wrap::struct{cells:[2]Holder}\n'
  'run::fn(a:bool){p:=new Box;if p==nil{ret};q:=new Box;if '
  'q==nil{ret};xs:[1][2]Holder=[[Holder{child:p,other:q,count:0},Holder{child:q,other:q,count:0}]];i:usize=0;xs[0][i].other=q;del '
  'q;r:=xs[0][0].child;if r!=nil{v:=r.value}}\n'
  'main::fn(){run(false);run(true)}\n',
  0)])

@pytest.mark.parametrize("name,source,expected", CASES, ids=[case[0] for case in CASES])
def test_nested_array_initializer_aliases(tmp_path, name, source, expected):
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
