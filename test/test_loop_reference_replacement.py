"""Loop replacement must preserve stale allocation aliases and exit paths."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = [('replaced',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'main :: fn() {\n'
  '    p := new Box\n'
  '    if p == nil { ret }\n'
  '    i := 0\n'
  '    while i < 2 {\n'
  '        if p == nil { ret }\n'
  '        del p\n'
  '        p = new Box\n'
  '        if p == nil { ret }\n'
  '        p.value = i\n'
  '        i += 1\n'
  '    }\n'
  '    if p == nil { ret }\n'
  '    io.println("{}", p.value)\n'
  '    del p\n'
  '}\n',
  0),
 ('deleted',
  'Box :: struct { value: i32 }\n'
  'main :: fn() {\n'
  '    p := new Box\n'
  '    if p == nil { ret }\n'
  '    i := 0\n'
  '    while i < 2 {\n'
  '        if p == nil { ret }\n'
  '        del p\n'
  '        p.value = i\n'
  '        i += 1\n'
  '    }\n'
  '}\n',
  6),
 ('local',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'main :: fn() {\n'
  '    i := 0\n'
  '    while i < 2 {\n'
  '        p := new Box\n'
  '        if p == nil { ret }\n'
  '        p.value = i\n'
  '        io.println("{}", p.value)\n'
  '        del p\n'
  '        i += 1\n'
  '    }\n'
  '}\n',
  0),
 ('straight',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'main :: fn() {\n'
  '    p := new Box\n'
  '    if p == nil { ret }\n'
  '    del p\n'
  '    p = new Box\n'
  '    if p == nil { ret }\n'
  '    p.value = 1\n'
  '    io.println("{}", p.value)\n'
  '    del p\n'
  '}\n',
  0),
 ('stale_alias',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'main :: fn() {\n'
  'p := new Box\n'
  'if p == nil { ret }\n'
  'p.value = 5\n'
  'i := 0\n'
  'old := p\n'
  'while i < 2 { if p == nil { ret }; del p\n'
  'p = new Box\n'
  'if p == nil { ret }\n'
  'p.value = i\n'
  'if old != nil { io.println("{}", old.value) }; i += 1 }\n'
  'if p == nil { ret }\n'
  'io.println("{}", p.value)\n'
  'del p\n'
  '}\n',
  6),
 ('missing_branch',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'main :: fn() {\n'
  'p := new Box\n'
  'if p == nil { ret }\n'
  'p.value = 5\n'
  'i := 0\n'
  'while i < 2 { if p == nil { ret }; del p\n'
  'if i == 0 { p = new Box\n'
  'if p == nil { ret }\n'
  'p.value = i\n'
  ' }\n'
  'i += 1 }\n'
  'if p == nil { ret }\n'
  'io.println("{}", p.value)\n'
  'del p\n'
  '}\n',
  6),
 ('continue_before',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'main :: fn() {\n'
  'p := new Box\n'
  'if p == nil { ret }\n'
  'p.value = 5\n'
  'i := 0\n'
  'while i < 2 { if p == nil { ret }; del p\n'
  'if i == 0 { i += 1; continue }\n'
  'p = new Box\n'
  'if p == nil { ret }\n'
  'p.value = i\n'
  'i += 1 }\n'
  'if p == nil { ret }\n'
  'io.println("{}", p.value)\n'
  'del p\n'
  '}\n',
  6),
 ('break_before',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'main :: fn() {\n'
  'p := new Box\n'
  'if p == nil { ret }\n'
  'p.value = 5\n'
  'i := 0\n'
  'while i < 2 { if p == nil { ret }; del p\n'
  'if i == 0 { break }\n'
  'p = new Box\n'
  'if p == nil { ret }\n'
  'p.value = i\n'
  'i += 1 }\n'
  'if p == nil { ret }\n'
  'io.println("{}", p.value)\n'
  'del p\n'
  '}\n',
  6),
 ('deferred_delete',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'main :: fn() {\n'
  'p := new Box\n'
  'if p == nil { ret }\n'
  'p.value = 5\n'
  'i := 0\n'
  'while i < 2 { if p == nil { ret }; del p\n'
  'p = new Box\n'
  'if p == nil { ret }\n'
  'p.value = i\n'
  'defer del p\n'
  'i += 1 }\n'
  'if p == nil { ret }\n'
  'io.println("{}", p.value)\n'
  'del p\n'
  '}\n',
  6),
 ('continue_after',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'main :: fn() {\n'
  'p := new Box\n'
  'if p == nil { ret }\n'
  'p.value = 5\n'
  'i := 0\n'
  'while i < 2 { if p == nil { ret }; del p\n'
  'p = new Box\n'
  'if p == nil { ret }\n'
  'p.value = i\n'
  'i += 1; continue }\n'
  'if p == nil { ret }\n'
  'io.println("{}", p.value)\n'
  'del p\n'
  '}\n',
  0),
 ('break_after',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'main :: fn() {\n'
  'p := new Box\n'
  'if p == nil { ret }\n'
  'p.value = 5\n'
  'i := 0\n'
  'while i < 2 { if p == nil { ret }; del p\n'
  'p = new Box\n'
  'if p == nil { ret }\n'
  'p.value = i\n'
  'break }\n'
  'if p == nil { ret }\n'
  'io.println("{}", p.value)\n'
  'del p\n'
  '}\n',
  0),
 ('conditional_replace',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'run :: fn(change: bool) {\n'
  'p := new Box\n'
  'if p == nil { ret }\n'
  'p.value = 5\n'
  'i := 0\n'
  'while i < 2 { if p == nil { ret }; if change { del p\n'
  'p = new Box\n'
  'if p == nil { ret }\n'
  'p.value = i\n'
  '}\n'
  'i += 1 }\n'
  'if p == nil { ret }\n'
  'io.println("{}", p.value)\n'
  'del p\n'
  '}\n'
  'main :: fn() { run(true); run(false) }\n',
  0),
 ('zero_trips',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'run :: fn(flag: bool) { p := new Box; if p == nil { ret }; p.value=7; i:=0; while i < 0 { del p; p=new '
  'Box; if p==nil {ret}; p.value=9; i+=1 };if p == nil { ret }; io.println("{}",p.value); del p }\n'
  'main :: fn(){run(false)}\n',
  0),
 ('old_alias_after_replacement',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'run :: fn(flag: bool) { p := new Box; if p == nil { ret }; p.value=7; i:=0; q:=p; while i<2 {del p;p=new '
  'Box;if p==nil {ret};p.value=i;i+=1}; if q!=nil {io.println("{}",q.value)};if p == nil { ret }; '
  'io.println("{}",p.value); del p }\n'
  'main :: fn(){run(false)}\n',
  6),
 ('new_alias_deleted',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'run :: fn(flag: bool) { p := new Box; if p == nil { ret }; p.value=7; i:=0; while i<2 {del p;p=new Box;if '
  'p==nil {ret};q:=p;del q;p.value=i;i+=1};if p == nil { ret }; io.println("{}",p.value); del p }\n'
  'main :: fn(){run(false)}\n',
  6),
 ('new_alias_before_delete',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'run :: fn(flag: bool) { p := new Box; if p == nil { ret }; p.value=7; i:=0; while i<2 {del p;p=new Box;if '
  'p==nil {ret};q:=p;p.value=i;io.println("{}",q.value);i+=1};if p == nil { ret }; io.println("{}",p.value); '
  'del p }\n'
  'main :: fn(){run(false)}\n',
  0),
 ('defer_old_alias',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'run :: fn(flag: bool) { p := new Box; if p == nil { ret }; p.value=7; i:=0; while i<2 {q:=p;defer del '
  'q;p=new Box;if p==nil {ret};p.value=i;i+=1};if p == nil { ret }; io.println("{}",p.value); del p }\n'
  'main :: fn(){run(false)}\n',
  0),
 ('defer_current_alias',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'run :: fn(flag: bool) { p := new Box; if p == nil { ret }; p.value=7; i:=0; while i<2 {del p;p=new Box;if '
  'p==nil {ret};q:=p;defer del q;p.value=i;i+=1};if p == nil { ret }; io.println("{}",p.value); del p }\n'
  'main :: fn(){run(false)}\n',
  6),
 ('nested_replacement',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'run :: fn(flag: bool) { p := new Box; if p == nil { ret }; p.value=7; i:=0; while i<2 {j:=0;while j<2 '
  '{del p;p=new Box;if p==nil {ret};p.value=j;j+=1};i+=1};if p == nil { ret }; io.println("{}",p.value); del '
  'p }\n'
  'main :: fn(){run(false)}\n',
  0),
 ('replacement_then_unsafe_branch',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'run :: fn(flag: bool) { p := new Box; if p == nil { ret }; p.value=7; i:=0; while i<2 {del p;p=new Box;if '
  'p==nil {ret};if flag {del p};i+=1};if p == nil { ret }; io.println("{}",p.value); del p }\n'
  'main :: fn(){run(false)}\n',
  6),
 ('shared_after_delete',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'run :: fn(n: i32) {\n'
  '    p := new Box\n'
  '    if p == nil { ret }\n'
  '    q := new Box\n'
  '    if q == nil { ret }\n'
  '    i := 0\n'
  '    while i < n {\n'
  '        if p == nil { ret }\n'
  '        del p\n'
  '        p = new Box\n'
  '        if p == nil { ret }\n'
  '        p.value = 7\n'
  '        q = new Box\n'
  '        if q == nil { ret }\n'
  '        del q\n'
  '        q = p\n'
  '        i += 1\n'
  '    }\n'
  '    if p == nil { ret }\n'
  '    if q == nil { ret }\n'
  '    del p\n'
  '    io.println("{}", q.value)\n'
  '}\n'
  'main :: fn() { run(2) }\n',
  6),
 ('shared_double_delete',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'run :: fn(n: i32) {\n'
  '    p := new Box\n'
  '    if p == nil { ret }\n'
  '    q := new Box\n'
  '    if q == nil { ret }\n'
  '    i := 0\n'
  '    while i < n {\n'
  '        if p == nil { ret }\n'
  '        del p\n'
  '        p = new Box\n'
  '        if p == nil { ret }\n'
  '        p.value = 7\n'
  '        q = new Box\n'
  '        if q == nil { ret }\n'
  '        del q\n'
  '        q = p\n'
  '        i += 1\n'
  '    }\n'
  '    if p == nil { ret }\n'
  '    if q == nil { ret }\n'
  '    del p\n'
  '    del q\n'
  '}\n'
  'main :: fn() { run(2) }\n',
  6),
 ('shared_before_delete',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'run :: fn(n: i32) {\n'
  '    p := new Box\n'
  '    if p == nil { ret }\n'
  '    q := new Box\n'
  '    if q == nil { ret }\n'
  '    i := 0\n'
  '    while i < n {\n'
  '        if p == nil { ret }\n'
  '        del p\n'
  '        p = new Box\n'
  '        if p == nil { ret }\n'
  '        p.value = 7\n'
  '        q = new Box\n'
  '        if q == nil { ret }\n'
  '        del q\n'
  '        q = p\n'
  '        i += 1\n'
  '    }\n'
  '    if p == nil { ret }\n'
  '    if q == nil { ret }\n'
  '    io.println("{}", q.value)\n'
  '    del p\n'
  '}\n'
  'main :: fn() { run(2) }\n',
  0),
 ('zero_trip_alias',
  'Box::struct{value:i32}\n'
  'main::fn(){p:=new Box;if p==nil{ret};q:=p;i:=0;while i<0 {if i==1{del p;p=new Box;if '
  'p==nil{ret}};i+=1};del p;if q!=nil{v:=q.value}}',
  6),
 ('conditional_alias',
  'Box::struct{value:i32}\n'
  'main::fn(){p:=new Box;if p==nil{ret};q:=p;i:=0;while i<2 {if i==1{del p;p=new Box;if '
  'p==nil{ret}};i+=1};del p;if q!=nil{v:=q.value}}',
  6),
 ('field_escape',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'main::fn(){p:=new Box;if p==nil{ret};r:=new Box;if r==nil{del p;ret};holder:=Holder{child:r};refs:[1]ref '
  'Box=[r];i:=0;while i<2{del p;p=new Box;if p==nil{ret};holder.child=p;i+=1};del p;q:=holder.child;if '
  'q!=nil{v:=q.value}}',
  6),
 ('aggregate_escape',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'main::fn(){p:=new Box;if p==nil{ret};r:=new Box;if r==nil{del p;ret};holder:=Holder{child:r};refs:[1]ref '
  'Box=[r];i:=0;while i<2{del p;p=new Box;if p==nil{ret};holder=Holder{child:p};i+=1};del '
  'p;q:=holder.child;if q!=nil{v:=q.value}}',
  6),
 ('array_escape',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'main::fn(){p:=new Box;if p==nil{ret};r:=new Box;if r==nil{del p;ret};holder:=Holder{child:r};refs:[1]ref '
  'Box=[r];i:=0;while i<2{del p;p=new Box;if p==nil{ret};refs[0]=p;i+=1};del p;q:=refs[0];if '
  'q!=nil{v:=q.value}}',
  6),
 ('scalar_field',
  'Box::struct{value:i32}\n'
  'main::fn(){p:=new Box;if p==nil{ret};holder:=Box{value:0};items:[1]i32=[0];i:=0;while i<2{del p;p=new '
  'Box;if p==nil{ret};p.value=i;holder.value=i;i+=1};if p==nil{ret};v:=p.value;del p}',
  0),
 ('scalar_aggregate',
  'Box::struct{value:i32}\n'
  'main::fn(){p:=new Box;if p==nil{ret};holder:=Box{value:0};items:[1]i32=[0];i:=0;while i<2{del p;p=new '
  'Box;if p==nil{ret};p.value=i;holder=Box{value:i};i+=1};if p==nil{ret};v:=p.value;del p}',
  0),
 ('scalar_array',
  'Box::struct{value:i32}\n'
  'main::fn(){p:=new Box;if p==nil{ret};holder:=Box{value:0};items:[1]i32=[0];i:=0;while i<2{del p;p=new '
  'Box;if p==nil{ret};p.value=i;items=[i];items[0]=i;i+=1};if p==nil{ret};v:=p.value;del p}',
  0),
 ('field_escape_then_fresh',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'main::fn(){p:=new Box;if p==nil{ret};r:=new Box;if r==nil{del p;ret};holder:=Holder{child:r};refs:[1]ref '
  'Box=[r];i:=0;while i<2{del p;p=new Box;if p==nil{ret};holder.child=p;del p;p=new Box;if '
  'p==nil{ret};i+=1};del p;q:=holder.child;if q!=nil{v:=q.value}}',
  6),
 ('aggregate_escape_then_fresh',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'main::fn(){p:=new Box;if p==nil{ret};r:=new Box;if r==nil{del p;ret};holder:=Holder{child:r};refs:[1]ref '
  'Box=[r];i:=0;while i<2{del p;p=new Box;if p==nil{ret};holder=Holder{child:p};del p;p=new Box;if '
  'p==nil{ret};i+=1};del p;q:=holder.child;if q!=nil{v:=q.value}}',
  6),
 ('array_escape_then_fresh',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'main::fn(){p:=new Box;if p==nil{ret};r:=new Box;if r==nil{del p;ret};holder:=Holder{child:r};refs:[1]ref '
  'Box=[r];i:=0;while i<2{del p;p=new Box;if p==nil{ret};refs[0]=p;del p;p=new Box;if p==nil{ret};i+=1};del '
  'p;q:=refs[0];if q!=nil{v:=q.value}}',
  6),
 ('prior_generation_alias',
  'Box::struct{value:i32}\n'
  'main::fn(){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if q==nil{ret};q.value=2;i:=0;while i<3{q=p;del '
  'p;p=new Box;if p==nil{ret};i+=1};if q!=nil{v:=q.value};del p}\n',
  6),
 ('branch_shared',
  'Box::struct{value:i32}\n'
  'main::fn(){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if q==nil{ret};q.value=2;i:=0;while i<3{del '
  'p;p=new Box;if p==nil{ret};if i==1{q=p};i+=1};del p;if q!=nil{v:=q.value}}\n',
  6),
 ('break_stale',
  'Box::struct{value:i32}\n'
  'main::fn(){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if q==nil{ret};q.value=2;i:=0;while i<3{q=p;del '
  'p;p=new Box;if p==nil{ret};break};if q!=nil{v:=q.value};del p}\n',
  6),
 ('break_live_alias',
  'Box::struct{value:i32}\n'
  'main::fn(){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if q==nil{ret};q.value=2;i:=0;while i<3{del '
  'p;p=new Box;if p==nil{ret};q=p;break};if q!=nil{v:=q.value};del p}\n',
  0),
 ('previous_live_generation',
  'Box::struct{value:i32}\n'
  'main::fn(){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if q==nil{ret};q.value=2;i:=0;while '
  'i<3{q=p;p=new Box;if p==nil{ret};i+=1};if q!=nil{v:=q.value};del p}\n',
  0),
 ('branch_live',
  'Box::struct{value:i32}\n'
  'main::fn(){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if q==nil{ret};q.value=2;i:=0;while i<3{del '
  'p;p=new Box;if p==nil{ret};if i==1{q=p};i+=1};if q!=nil{v:=q.value}}\n',
  6),
 ('break_stale_double_delete',
  'Box::struct{value:i32}\n'
  'main::fn(){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if q==nil{ret};q.value=2;i:=0;while i<3{q=p;del '
  'p;p=new Box;if p==nil{ret};break};del q;del p}\n',
  6),
 ('break_distinct_live',
  'Box::struct{value:i32}\n'
  'main::fn(){p:=new Box;if p==nil{ret};p.value=1;q:=new Box;if q==nil{ret};q.value=2;i:=0;while i<3{del '
  'p;p=new Box;if p==nil{ret};break};if q!=nil{v:=q.value};del p}\n',
  0),
 ('old_entry_alias_remains_live',
  'Box::struct{value:i32}\n'
  'main::fn(){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};r:=q;i:=0;while i<3{q=p;del p;p=new Box;if '
  'p==nil{ret};break};if r!=nil{v:=r.value};del p;del r}',
  0),
 ('former_allocation_live',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'main :: fn() {\n'
  '    p := new Box\n'
  '    if p == nil { ret }\n'
  '    q := new Box\n'
  '    if q == nil { ret }\n'
  '    q.value = 17\n'
  '    saved := q\n'
  '    i := 0\n'
  '    while i < 3 {\n'
  '        q = p\n'
  '        del p\n'
  '        p = new Box\n'
  '        if p == nil { ret }\n'
  '        break\n'
  '    }\n'
  '    if saved != nil { io.println("{}", saved.value) }\n'
  '    del saved\n'
  '    del p\n'
  '}\n',
  0),
 ('current_alias_dead',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'main :: fn() {\n'
  '    p := new Box\n'
  '    if p == nil { ret }\n'
  '    q := new Box\n'
  '    if q == nil { ret }\n'
  '    q.value = 17\n'
  '    saved := q\n'
  '    i := 0\n'
  '    while i < 3 {\n'
  '        q = p\n'
  '        del p\n'
  '        p = new Box\n'
  '        if p == nil { ret }\n'
  '        break\n'
  '    }\n'
  '    if saved != nil { io.println("{}", saved.value) }\n'
  '    if q != nil { io.println("{}", q.value) }\n'
  '    del p\n'
  '}\n',
  6),
 ('former_allocation_deleted',
  'io :: import "std/io"\n'
  'Box :: struct { value: i32 }\n'
  'main :: fn() {\n'
  '    p := new Box\n'
  '    if p == nil { ret }\n'
  '    q := new Box\n'
  '    if q == nil { ret }\n'
  '    q.value = 17\n'
  '    saved := q\n'
  '    i := 0\n'
  '    while i < 3 {\n'
  '        q = p\n'
  '        del p\n'
  '        p = new Box\n'
  '        if p == nil { ret }\n'
  '        break\n'
  '    }\n'
  '    del saved\n'
  '    if saved != nil { io.println("{}", saved.value) }\n'
  '    del p\n'
  '}\n',
  6),
 ('no_positive_projection',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'main::fn(){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};holder:=Holder{child:p};i:=0;while '
  'i<1{q=p;del p;break};if q!=nil{v:=q.value}}',
  6),
 ('field_delete_then_new',
  'Box::struct{value:i32}\n'
  'Holder::struct{child:ref Box}\n'
  'main::fn(){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};holder:=Holder{child:p};i:=0;while '
  'i<2{q=p;del holder.child;p=new Box;if p==nil{ret};break};if q!=nil{v:=q.value};del p}',
  6),
 ('single_iteration_dead_alias',
  'Box :: struct { value: i32 }\n'
  'main :: fn() {\n'
  ' p := new Box\n'
  ' if p == nil { ret }\n'
  ' q := new Box\n'
  ' if q == nil { ret }\n'
  ' i := 0\n'
  ' while i < 1 {\n'
  '  q = p\n'
  '  del p\n'
  '  i += 1\n'
  ' }\n'
  ' if q != nil { v := q.value }\n'
  '}\n',
  6),
 ('single_iteration_former_slot_live',
  'Box::struct{value:i32}\n'
  'main::fn(){p:=new Box;if p==nil{ret};q:=new Box;if q==nil{ret};saved:=q;i:=0;while i<1{q=p;del p;i+=1};if '
  'saved!=nil{v:=saved.value};del saved}',
  0)]

@pytest.mark.parametrize("name,source,expected", CASES, ids=[case[0] for case in CASES])
def test_loop_reference_replacement(tmp_path, name, source, expected):
    path = tmp_path / (name + ".a7")
    path.write_text(source)
    out = tmp_path / (name + ".zig")
    result = subprocess.run([sys.executable, str(ROOT / "main.py"), str(path), "--mode", "compile", "--format", "json", "--output", str(out)], capture_output=True, text=True)
    assert result.returncode == expected, result.stdout + result.stderr
    assert result.stderr == ""
    if expected:
        error = json.loads(result.stdout)["error"]
        assert error["category"] == "semantic"
        assert any(item["code"] == "use_after_move" and item["file"] == str(path) and item["span"]["start_line"] > 0 for item in error["details"])
        assert not out.exists()
    else:
        assert out.exists()
        assert "pub fn main" in out.read_text()
