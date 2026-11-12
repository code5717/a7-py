"""Projected addresses retain writes and frame-owned returned-reference provenance.

These checks inspect final real-pipeline summaries. They do not establish native
execution or diagnose all dangling-reference uses.
"""
import pytest
from a7.ast_nodes import ASTNode, NodeKind
from a7.errors import TypeErrorType
from a7.parser import Parser
from a7.tokens import Tokenizer
from a7.passes.name_resolution import NameResolutionPass
from a7.passes.type_checker import TypeCheckingPass
from a7.passes.semantic_validator import SemanticValidationPass
from a7.passes.safety import SafetyProofPass


def analyze(source, expected_move=False):
    program = Parser(Tokenizer(source).tokenize()).parse()
    resolver = NameResolutionPass()
    symbols = resolver.analyze(program, "<location-summary>")
    assert not resolver.errors
    checker = TypeCheckingPass(symbols)
    node_types = checker.analyze(program, "<location-summary>")
    assert not checker.errors
    validator = SemanticValidationPass(symbols, node_types)
    validator.analyze(program, "<location-summary>")
    assert not validator.errors
    safety = SafetyProofPass(symbols, node_types)
    safety.analyze(program, "<location-summary>")
    if expected_move:
        assert safety.errors
        assert all(error.error_type == TypeErrorType.USE_AFTER_MOVE for error in safety.errors)
    else:
        assert not safety.errors
    return safety


CASES = [('formal_inline_projection_byref',
  'Inner::struct{count:usize;items:[2]usize}\n'
  'Outer::struct{inner:Inner;link:ref usize}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'write::fn(owner:ref Outer){if owner==nil{ret};reset(owner.inner.items[0])}\n'
  'main::fn(){local:Outer;write(local)}\n',
  'write',
  [0]),
 ('reference_field_crossing_unknown',
  'Inner::struct{count:usize;items:[2]usize}\n'
  'Outer::struct{inner:Inner;link:ref usize}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'write::fn(owner:ref Outer,other:ref usize){if owner==nil{ret};if '
  'owner.link==nil{ret};reset(owner.link)}\n'
  'main::fn(){}\n',
  'write',
  [0, 1]),
 ('global_inline_storage_unknown',
  'Inner::struct{count:usize;items:[2]usize}\n'
  'Outer::struct{inner:Inner;link:ref usize}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'global:Outer\n'
  'write::fn(other:ref usize){reset(global.inner.items[0])}\n'
  'main::fn(){}\n',
  'write',
  [0]),
 ('captured_inline_storage_unknown',
  'Inner::struct{count:usize;items:[2]usize}\n'
  'Outer::struct{inner:Inner;link:ref usize}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'outer::fn(other:ref usize){local:Outer;inner::fn(n:ref '
  'usize){reset(local.inner.items[0])};inner(other)}\n'
  'main::fn(){}\n',
  'outer',
  [0]),
 ('slice_storage_unknown',
  'Inner::struct{count:usize;items:[2]usize}\n'
  'Outer::struct{inner:Inner;link:ref usize}\n'
  'reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\n'
  'write::fn(xs:[]usize,other:ref usize){idx:usize=0;if idx<xs.len{reset(xs[idx])}}\n'
  'main::fn(){}\n',
  'write',
  [1]),
 ('conditional_fresh_and_unknown_receiver',
  'Cell::struct{count:usize}\n'
  'Holder::struct{child:ref Cell}\n'
  'write::fn(owner:ref Holder,other:ref usize,flag:bool){if owner==nil{ret};if '
  'owner.child==nil{ret};local:=new Cell;if local==nil{ret};(if '
  'flag{local}else{owner.child}).count=4;del local}\n'
  'main::fn(){}\n',
  'write',
  [0, 1])]

@pytest.mark.parametrize("name,source,function,writes", CASES, ids=[c[0] for c in CASES])
def test_projected_reference_writes(name, source, function, writes):
    safety = analyze(source)
    assert set(writes) <= safety.scalar_parameter_writes[function]


@pytest.mark.parametrize("helpers", [1, 2])
def test_returned_stack_element_keeps_frame_provenance(helpers):
    source = "borrow::fn(n:ref usize) ref usize{ret n}\n"
    if helpers == 2:
        source += "forward::fn(n:ref usize) ref usize{ret borrow(n)}\n"
    callee = "borrow" if helpers == 1 else "forward"
    source += f"bad::fn() ref usize{{buf:[2]usize;a:={callee}(buf[0]);ret a}}\nmain::fn(){{a:=bad()}}"
    safety = analyze(source)
    assert safety.scalar_returned_origins["borrow"] is not None
    assert len(safety.scalar_returned_origins["borrow"]) == 1
    if helpers == 2:
        assert safety.scalar_returned_origins["forward"] is not None
        assert len(safety.scalar_returned_origins["forward"]) == 1
    assert safety.scalar_returned_origins["bad"] is None


def test_local_returned_borrow_use_preserves_unrelated_counter():
    source = """Box::struct{value:i32}
borrow::fn(n:ref usize) ref usize{ret n}
forward::fn(n:ref usize) ref usize{ret borrow(n)}
reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}
run::fn(flag:bool){p:=new Box;if p==nil{ret};p.value=7;buf:[2]usize;i:usize=0
while flag{if i==1{break};del p;i+=1;a:=forward(buf[0]);if a!=nil{reset(a)}}
if !flag{del p}}
main::fn(){run(false);run(true)}"""
    safety = analyze(source)
    assert any(key.startswith("i#") for key in safety.scalar_eligible_keys)


def test_retained_stack_reference_keeps_nonempty_provenance():
    source = """g:ref usize
borrow::fn(n:ref usize) ref usize{ret n}
stash::fn(n:ref usize){g=n}
main::fn(){buf:[2]usize;a:=borrow(buf[0]);stash(a)}"""
    safety = analyze(source)
    assert safety.scalar_parameter_escapes["stash"] == {0}
    # The caller's resolved buf storage, not merely stash's formal, escapes.
    local_keys = {key for (_, name), key in safety.keys.items() if name == "buf"}
    assert len(local_keys) == 1
    local_key = next(iter(local_keys))
    assert any(token.startswith("\0storage:4:main:") and token.endswith(":" + local_key)
               for token in safety.scalar_escaped_keys)


@pytest.mark.parametrize("type_name,initial", [("i32", "0"), ("bool", "false")])
def test_non_counter_scalar_return_keeps_frame_provenance(type_name, initial):
    source = (f"borrow::fn(n:ref {type_name}) ref {type_name}{{ret n}}\n"
              f"forward::fn(n:ref {type_name}) ref {type_name}{{ret borrow(n)}}\n"
              f"bad::fn() ref {type_name}{{x:{type_name}={initial};a:=forward(x);ret a}}\n"
              "main::fn(){a:=bad()}")
    safety = analyze(source)
    assert safety.scalar_returned_origins["forward"] is not None
    assert len(safety.scalar_returned_origins["forward"]) == 1
    assert safety.scalar_returned_origins["bad"] is None


def test_local_enum_return_keeps_frame_provenance():
    source = """Phase::enum{First,Second}
borrow::fn(n:ref Phase) ref Phase{ret n}
forward::fn(n:ref Phase) ref Phase{ret borrow(n)}
bad::fn() ref Phase{state:=Phase.First;a:=forward(state);ret a}
main::fn(){a:=bad()}"""
    safety = analyze(source)
    assert safety.scalar_returned_origins["forward"] is not None
    assert len(safety.scalar_returned_origins["forward"]) == 1
    assert safety.scalar_returned_origins["bad"] is None




def test_handle_same_backed_slice_retains_backing_write():
    safety = analyze('reset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\nwrite::fn(xs:[]usize,other:ref usize){idx:usize=0;if idx<xs.len{reset(xs[idx])}}\nmain::fn(){a:[1]usize;a[0]=1;xs:=a[0..1];write(xs,a[0])}\n')
    assert 1 in safety.scalar_parameter_writes["write"]


@pytest.mark.parametrize("type_name,declaration", [
    ("string", 'state:="before"'),
    ("[]i32", "state:[]i32"),
    ("fn()", "state:=empty"),
])
def test_handle_slot_return_and_retention_keep_local_token(type_name, declaration):
    source = ("empty::fn(){}\n"
              f"g:ref {type_name}\n"
              f"borrow::fn(n:ref {type_name}) ref {type_name}{{ret n}}\n"
              f"forward::fn(n:ref {type_name}) ref {type_name}{{ret borrow(n)}}\n"
              f"stash::fn(n:ref {type_name}){{g=n}}\n"
              f"bad::fn() ref {type_name}{{{declaration};a:=forward(state);stash(a);ret a}}\n"
              "main::fn(){a:=bad()}")
    safety = analyze(source)
    assert safety.scalar_returned_origins["bad"] is None
    for helper in ("borrow", "forward"):
        function = safety.exact_effect_bodies[helper]
        assert safety.scalar_returned_origins[helper] == {safety._key(function.parameters[0])}
    assert safety.scalar_parameter_escapes["stash"] == {0}
    state_keys = {key for (_, name), key in safety.keys.items() if name == "state"}
    assert len(state_keys) == 1
    key = next(iter(state_keys))
    assert any(token.startswith("\0storage:3:bad:") and token.endswith(":" + key)
               for token in safety.scalar_escaped_keys)


def test_callback_replacement_and_invocation_have_distinct_effects():
    safety = analyze('Box::struct{value:i32}\nnoop::fn(n:ref usize){}\nreset::fn(n:ref usize){if n==nil{ret};zero:usize=0;n=zero}\nreplace::fn(state:ref fn(ref usize)){if state==nil{ret};state=reset}\nrun::fn(flag:bool){\n p:=new Box;if p==nil{ret};p.value=7\n state:=noop;i:usize=0\n while flag{if i==1{break};del p;i+=1;replace(state);state(i)}\n if !flag{del p}\n}\nmain::fn(){run(false);run(true)}\n', expected_move=True)
    counter_keys = {key for (_, name), key in safety.keys.items() if name == "i"}
    assert len(counter_keys) == 1
    counter = next(iter(counter_keys))
    calls = {}
    pending = [safety.exact_effect_bodies["run"].body]
    while pending:
        node = pending.pop()
        if node.kind == NodeKind.CALL and node.function.kind == NodeKind.IDENTIFIER:
            calls[node.function.name] = node
        for value in vars(node).values():
            if isinstance(value, ASTNode):
                pending.append(value)
            elif isinstance(value, list):
                pending.extend(item for item in value if isinstance(item, ASTNode))
    assert counter not in safety.scalar_call_writes[id(calls["replace"])]
    assert counter in safety.scalar_call_writes[id(calls["state"])]
