"""File ownership precedes whole-program lowering."""
from conftest import expect_ok, expect_exit

def write_modules(tmp_path, modules):
    for name, text in modules.items():
        path = tmp_path / (name + '.a7')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

def test_distinct_nominal_types(tmp_path):
    write_modules(tmp_path, {'a':'Point::struct{x:i32}\nvalue::fn()i32{ret 7}', 'b':'Point::struct{x:i32}\nvalue::fn()i32{ret 9}'})
    expect_ok('a::import "a"\nb::import "b"\nmain::fn(){x:=a.value();y:=b.value();p:=a.Point{x:1};q:=b.Point{x:2}}',tmp_path)
    expect_exit('a::import "a"\nb::import "b"\nmain::fn(){p:a.Point=b.Point{x:2}}',tmp_path,6,'mismatch')

def test_generic_type(tmp_path):
    write_modules(tmp_path, {'a':'Box($T)::struct{value:$T}\nidentity::fn(x:$T)$T{ret x}'})
    expect_ok('a::import "a"\nmain::fn(){p:a.Box(i32)=a.Box(i32){value:7};x:=a.identity(p.value)}',tmp_path)
    expect_exit('a::import "a"\nmain::fn(){p:a.Box(i32)=a.Box(i32){value:"bad"}}',tmp_path,6,'mismatch')

def test_private_origin(tmp_path):
    write_modules(tmp_path, {'a':'_value::fn()i32{ret 7}', 'b':'a::import "a"\nvalue::fn()i32{ret a._value()}'})
    r=expect_exit('b::import "b"\nmain::fn(){x:=b.value()}',tmp_path,6,'Private declaration')
    assert any(d.get('file')==str(tmp_path/'b.a7') for d in r.failure.details)

def test_deletion(tmp_path):
    write_modules(tmp_path, {'a':'Box::struct{x:i32}\ndrop::fn(p:ref Box){del p}'})
    expect_exit('a::import "a"\nmain::fn(){p:=new a.Box;if p==nil{ret};q:=p;a.drop(p);x:=q.x}',tmp_path,6,'Use after move or delete')

def test_private_siblings(tmp_path):
    write_modules(tmp_path, {'a':'_work::fn(x:i32)i32{ret x}\nkeep::fn(x:i32)i32{ret _work(x)}', 'b':'_work::fn(x:i32)i32{ret x+1}\nother::fn(x:i32)i32{ret _work(x)}'})
    expect_ok('a::import "a"\nb::import "b"\nmain::fn(){x:=a.keep(3);y:=b.other(4)}',tmp_path)

def test_recursion(tmp_path):
    write_modules(tmp_path, {'a':'left::fn(){right()}\nright::fn(){left()}'})
    expect_exit('a::import "a"\nmain::fn(){a.left()}',tmp_path,6,'recurs')

def test_stdlib_scopes(tmp_path):
    write_modules(tmp_path, {'a':'s::import "std/io"\nshow::fn(){s.println("ok")}', 'b':'s::import "std/math"\nroot::fn()f64{ret s.sqrt(4.0)}'})
    expect_ok('a::import "a"\nb::import "b"\nmain::fn(){a.show();x:=b.root()}',tmp_path)

def test_constants(tmp_path):
    write_modules(tmp_path, {'a':'N::7\nget::fn()i32{ret N}', 'b':'a::import "a"\nN::a.N+1'})
    expect_ok('a::import "a"\nb::import "b"\nmain::fn(){x:=a.N;y:=b.N}',tmp_path)

def test_imported_alias_keeps_its_declaration_scope(tmp_path):
    write_modules(tmp_path, {'a':'Local::struct{x:i32}\nValue::ref Local\nmake::fn()Value{ret nil}'})
    expect_ok('a::import "a"\nLocal::string\nmain::fn(){v:a.Value=a.make()}',tmp_path)
    expect_exit('a::import "a"\nLocal::string\nmain::fn(){v:a.Value="bad"}',tmp_path,6,'mismatch')

def test_enum_and_union_qualified_construction(tmp_path):
    write_modules(tmp_path, {'a':'Color::enum{red,blue}\nOutcome::union(tag){ok:i32,bad:string}'})
    expect_ok('a::import "a"\nmain::fn(){c:a.Color=a.Color.red;r:a.Outcome=a.Outcome{ok:7}}',tmp_path)

def test_global_reference_mutation_reaches_saved_alias(tmp_path):
    write_modules(tmp_path, {'a':'Box::struct{x:i32}\ng:ref Box\nset::fn(p:ref Box){g=p}\ndrop::fn(){del g}'})
    expect_exit('a::import "a"\nmain::fn(){p:=new a.Box;if p==nil{ret};a.set(p);a.drop();x:=p.x}',tmp_path,6,'Use after move or delete')

def test_imported_function_values_keep_definition_identity(tmp_path):
    write_modules(tmp_path, {'a':'value::fn()i32{ret 1}','b':'value::fn()i32{ret 2}'})
    expect_ok('a::import "a"\nb::import "b"\nmain::fn(){f:=a.value;g:=b.value;x:=f();y:=g()}',tmp_path)

def test_deep_alias_dependency_uses_target_file_scope(tmp_path):
    write_modules(tmp_path, {'a':'b::import "b"\nA::ref b.B','b':'Local::struct{x:i32}\nB::ref Local'})
    expect_ok('a::import "a"\nLocal::string\nmain::fn(){v:a.A=nil}',tmp_path)

def test_imported_by_value_record_cycle_is_rejected(tmp_path):
    write_modules(tmp_path, {'a':'A::struct{b:B}\nB::struct{a:A}'})
    expect_exit('a::import "a"\nmain::fn(){}',tmp_path,6,'infinite size')


def test_qualified_constants_supply_array_lengths_and_initializers(tmp_path):
    write_modules(tmp_path, {'a':'N::2', 'b':'a::import "a"\nN::a.N+1'})
    expect_ok('b::import "b"\na::import "a"\nmain::fn(){x:[b.N]i8=[1,2,3];y:[a.N]i8=[4,5]}',tmp_path)


def test_qualified_global_variable_assignment_is_mutable(tmp_path):
    write_modules(tmp_path, {'a':'count:i32=0'})
    expect_ok('a::import "a"\nmain::fn(){a.count=7;x:=a.count}',tmp_path)


def test_qualified_type_is_not_a_runtime_value(tmp_path):
    write_modules(tmp_path, {'a':'Point::struct{x:i32}'})
    expect_exit('a::import "a"\nmain::fn(){x:=a.Point}',tmp_path,6,'Not a value')


def test_qualified_enum_and_constant_patterns(tmp_path):
    write_modules(tmp_path, {'a':'Color::enum{red,blue}\nN::2'})
    expect_ok('a::import "a"\nmain::fn(){c:=a.Color.red;match c{case a.Color.red:{} case a.Color.blue:{}};match 2{case a.N:{} else:{}}}',tmp_path)


def test_reserved_top_level_names_do_not_broaden_local_rule(tmp_path):
    expect_exit('__io::import "std/io"\nmain::fn(){}',tmp_path,6,'reserved for the compiler')
    expect_ok('main::fn(){__local::fn()i32{ret 7};x:=__local()}',tmp_path)
