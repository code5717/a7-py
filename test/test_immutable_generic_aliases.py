import pytest
from conftest import compile_program, failure_text

CASES = [('direct_bad',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'check::fn(flag:bool){a:i8=0;x:=bad(a)}\n'
  'main::fn(){check(false)}',
  6),
 ('direct_safe',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'check::fn(flag:bool){a:i8=0;x:=safe(a)}\n'
  'main::fn(){check(false)}',
  0),
 ('immutable_bad',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'check::fn(flag:bool){a:i8=0;f:=bad;x:=f(a)}\n'
  'main::fn(){check(false)}',
  6),
 ('immutable_safe',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'check::fn(flag:bool){a:i8=0;f:=safe;x:=f(a)}\n'
  'main::fn(){check(false)}',
  0),
 ('copied_bad',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'check::fn(flag:bool){a:i8=0;f:=bad;g:=f;h:=g;x:=h(a)}\n'
  'main::fn(){check(false)}',
  6),
 ('copied_safe',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'check::fn(flag:bool){a:i8=0;f:=safe;g:=f;h:=g;x:=h(a)}\n'
  'main::fn(){check(false)}',
  0),
 ('const_bad',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'check::fn(flag:bool){a:i8=0;f::bad;x:=f(a)}\n'
  'main::fn(){check(false)}',
  6),
 ('saved_bad_other_copy_mutated',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'check::fn(flag:bool){a:i8=0;f:=bad;saved:=f;changed:=f;changed=safe;x:=saved(a)}\n'
  'main::fn(){check(false)}',
  6),
 ('saved_safe_other_copy_mutated',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'check::fn(flag:bool){a:i8=0;f:=safe;saved:=f;changed:=f;changed=bad;x:=saved(a)}\n'
  'main::fn(){check(false)}',
  0),
 ('lexical_inner_safe',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'check::fn(flag:bool){a:i8=0;f:=bad;{f:=safe;g:=f;x:=g(a)}}\n'
  'main::fn(){check(false)}',
  0),
 ('lexical_outer_bad',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'check::fn(flag:bool){a:i8=0;f:=bad;{f:=safe;x:=f(a)};x:=f(a)}\n'
  'main::fn(){check(false)}',
  6),
 ('immutable_defer_bad',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'check::fn(flag:bool){a:i8=0;f:=bad;defer f(a)}\n'
  'main::fn(){check(false)}',
  6),
 ('immutable_in_loop_bad',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'check::fn(flag:bool){a:i8=0;f:=bad;i:usize=0;while i<2{x:=f(a);i+=1}}\n'
  'main::fn(){check(false)}',
  6),
 ('immutable_in_branch_bad',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'check::fn(flag:bool){a:i8=0;f:=bad;if flag{x:=f(a)}}\n'
  'main::fn(){check(false)}',
  6),
 ('malformed_call',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'check::fn(flag:bool){a:i8=0;f:=bad;x:=f(a,a)}\n'
  'main::fn(){check(false)}',
  6),
 ('two_types_safe_False',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'main::fn(){f:=safe;a:i8=0;x:=f(a);b:i16=0;y:=f(b)}',
  0),
 ('forward_safe_False',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'forward::fn(x:$U)$U{f:=safe;g:=f;ret g(x)}\n'
  'main::fn(){a:i8=0;x:=forward(a);b:i16=0;y:=forward(b)}',
  0),
 ('two_types_safe_True',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'main::fn(){f:=safe;b:i16=0;y:=f(b);a:i8=0;x:=f(a)}',
  0),
 ('forward_safe_True',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'forward::fn(x:$U)$U{f:=safe;g:=f;ret g(x)}\n'
  'main::fn(){b:i16=0;y:=forward(b);a:i8=0;x:=forward(a)}',
  0),
 ('two_types_bad_False',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'main::fn(){f:=bad;a:i8=0;x:=f(a);b:i16=0;y:=f(b)}',
  6),
 ('forward_bad_False',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'forward::fn(x:$U)$U{f:=bad;g:=f;ret g(x)}\n'
  'main::fn(){a:i8=0;x:=forward(a);b:i16=0;y:=forward(b)}',
  6),
 ('two_types_bad_True',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'main::fn(){f:=bad;b:i16=0;y:=f(b);a:i8=0;x:=f(a)}',
  6),
 ('forward_bad_True',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'forward::fn(x:$U)$U{f:=bad;g:=f;ret g(x)}\n'
  'main::fn(){b:i16=0;y:=forward(b);a:i8=0;x:=forward(a)}',
  6),
 ('wide_only',
  'safe::fn(x:$T)$T{z:$T=1;ret z}\n'
  'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
  'main::fn(){f:=bad;a:i16=0;x:=f(a)}',
  0),
 ('unbound_return', 'make::fn(x:$T)$U{ret x}\nmain::fn(){f:=make;x:=f(1)}', 6),
 ('callback_local_alias',
  'apply::fn(f:fn($T)$T,x:$T)$T{g:=f;ret g(x)}\n'
  'small::fn(x:i8)i8{ret x}\n'
  'main::fn(){a:i8=0;x:=apply(small,a)}',
  0)]

@pytest.mark.parametrize('name,source,expected', CASES, ids=[row[0] for row in CASES])
def test_immutable_alias_keeps_declaration_obligations(name,source,expected,tmp_path):
    result = compile_program(source,tmp_path)
    assert int(result.exit_code) == expected, failure_text(result)
    if expected == 6:
        assert any(text in failure_text(result) for text in ('Initializer', 'Expected 1 arguments', "Could not infer generic parameter '$U'")), failure_text(result)


from conftest import expect_ok

def test_immutable_alias_preserves_shared_ast_and_type_identity(tmp_path, monkeypatch):
    from a7.passes.type_checker import TypeCheckingPass
    from a7.ast_nodes import ASTNode

    original = TypeCheckingPass._record_immutable_generic_alias_calls
    observed = []

    def observe(checker, program):
        # Observe the registration boundary after ordinary type checking.
        pending = [program]
        nodes = {}
        while pending:
            node = pending.pop()
            if id(node) in nodes:
                continue
            nodes[id(node)] = (node, dict(vars(node)))
            for value in vars(node).values():
                if isinstance(value, ASTNode):
                    pending.append(value)
                elif isinstance(value, list):
                    pending.extend(child for child in value if isinstance(child, ASTNode))
        before_types = dict(checker.node_types)
        original(checker, program)
        assert checker.node_types.keys() == before_types.keys()
        assert all(checker.node_types[key] is value for key, value in before_types.items())
        for node, attributes in nodes.values():
            assert vars(node).keys() == attributes.keys()
            assert all(vars(node)[key] is value for key, value in attributes.items())
        observed.append(True)

    monkeypatch.setattr(TypeCheckingPass, "_record_immutable_generic_alias_calls", observe)
    for reverse in (False, True):
        calls = ["a:i8=0;x:=forward(a)", "b:i16=0;y:=forward(b)"]
        if reverse:
            calls.reverse()
        expect_ok("safe::fn(a:$T)$T{z:$T=1;ret z}\n"
                  "forward::fn(a:$U)$U{f:=safe;ret f(a)}\n"
                  "main::fn(){" + ";".join(calls) + "}", tmp_path)
    assert observed == [True, True]


def test_deep_callable_snapshots_use_worklists(tmp_path):
    import sys
    source = "safe::fn(x:$T)$T{ret x}\nmain::fn(){a:i8=0;alias_0:=safe;"
    source += ";".join(f"alias_{i}:=alias_{i-1}" for i in range(1,81))
    source += ";x:=alias_80(a)}"
    saved = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(100)
        expect_ok(source,tmp_path)
    finally:
        sys.setrecursionlimit(saved)

@pytest.mark.parametrize('body', [
    'f:=bad;f=safe;a:i8=0;x:=f(a)',
    'f:=bad;set(f);a:i8=0;x:=f(a)',
])
def test_written_or_borrowed_alias_is_not_bound_to_initializer(body, tmp_path):
    expect_ok('safe::fn(x:$T)$T{z:$T=1;ret z}\n'
              'bad::fn(x:$T)$T{z:$T=300;ret z}\n'
              'set::fn(f:ref fn($T)$T){f=safe}\n'
              'main::fn(){' + body + '}', tmp_path)


def test_shadow_initializer_uses_outer_declaration(tmp_path):
    result = compile_program('bad::fn(x:$T)$T{z:$T=300;ret z}\n'
                             'main::fn(){a:i8=0;f:=bad;{f:=f;x:=f(a)}}', tmp_path)
    assert int(result.exit_code) == 6
    assert 'Initializer' in failure_text(result)
