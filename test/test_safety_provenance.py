import itertools
import random
from a7.passes.safety import AllocationGraph


def enumerate_small(graph, root):
    values = set()
    pending = [(root, ())]
    while pending:
        node, path = pending.pop()
        terminal, edges = graph.nodes[node]
        if terminal:
            values.add(path)
        pending.extend((child, path + (label,)) for label, child in edges)
    return values


def test_finite_set_operations_against_independent_word_sets():
    graph = AllocationGraph()
    rng = random.Random(907)
    roots, sets = [0, 1], [set(), {()}]
    operations = {'union': set.union, 'intersection': set.intersection, 'difference': set.difference}
    for _ in range(150):
        a, b = rng.randrange(len(roots)), rng.randrange(len(roots))
        operation = rng.choice([*operations, 'prefix'])
        if operation == 'prefix':
            label = rng.choice(['a', 'b', 'c'])
            root = graph.prefix(label, roots[a])
            expected = {(label,) + word for word in sets[a]}
        else:
            root = graph.combine(operation, roots[a], roots[b])
            expected = operations[operation](sets[a], sets[b])
        assert enumerate_small(graph, root) == expected
        assert graph.cardinality[root] == min(2, len(expected))
        roots.append(root)
        sets.append(expected)
    for a, b in itertools.product(range(len(roots)), repeat=2):
        if sets[a] == sets[b]:
            assert roots[a] == roots[b]


def test_fanout_keeps_shared_suffixes_and_distinct_invocations():
    graph = AllocationGraph()
    root = graph.atom(('new', 0))
    for depth in range(1, 65):
        root = graph.union([graph.prefix(('call', 2 * depth), root),
                            graph.prefix(('call', 2 * depth + 1), root)])
        if depth <= 8:
            assert len(enumerate_small(graph, root)) == 2 ** depth
        assert graph.cardinality[root] == 2
        # Alternatives double at each level; retained state follows source size.
        assert len(graph.nodes) <= 4 * depth + 4
    first = graph.prefix(('caller', 1), root)
    second = graph.prefix(('caller', 2), root)
    assert graph.combine('intersection', first, second) == 0
    assert graph.combine('difference', graph.union([first, second]), first) == second


def test_linear_factory_fanout_retains_compact_runtime_facts(tmp_path, monkeypatch):
    import a7.compile as compiler
    from a7.passes.safety import SafetyProofPass
    from conftest import expect_ok

    observed = []

    class Capture(SafetyProofPass):
        def analyze(self, *args, **kwargs):
            result = super().analyze(*args, **kwargs)
            observed.append((len(self.allocation_graph.nodes),
                             len(self.allocation_graph.combinations),
                             sum(len(fact.allocations) for fact in self.facts.by_node.values())))
            return result

    # Observe retained state at the completed safety-pass boundary. The real
    # compiler still checks and emits each valid program.
    monkeypatch.setattr(compiler, 'SafetyProofPass', Capture)
    for depth in [2, 4, 8, 32, 64]:
        source = 'Box::struct{value:i32}\nHolder::struct{child:ref Box}\n'
        for index in range(depth):
            source += (f'factory_{index}::fn(flag:bool) ref Holder{{'
                       f'if flag{{ret factory_{index + 1}(flag)}};ret factory_{index + 1}(flag)}}\n')
        source += f'factory_{depth}::fn(flag:bool) ref Holder{{ret new Holder}}\n'
        source += 'main::fn(){p:=factory_0(false);if p!=nil{if p.child!=nil{v:=p.child.value;del p.child};del p}}'
        expect_ok(source, tmp_path)
        nodes, queries, fact_handles = observed[-1]
        # The source adds two invocation alternatives per level. Retained
        # graph/query/fact state must follow source size, not the 2**depth paths.
        assert nodes <= 8 * depth + 16
        assert queries <= 16 * depth + 16
        assert fact_handles <= 8 * depth + 16


def test_partial_dead_fresh_return_keeps_its_lifetime_dependency(tmp_path):
    from conftest import expect_exit, expect_ok

    source = '''Box::struct{value:i32}
factory::fn(flag:bool) ref Box{
 a:=new Box;b:=new Box;c:=new Box
 defer del c
 ret if flag{a}else{b}
}
main::fn(){p:=factory(false);if p!=nil{v:=p.value;del p}}
'''
    expect_ok(source, tmp_path)
    expect_exit(source.replace('defer del c', 'defer del a'), tmp_path, 6, 'Use after move or delete')


def test_selected_factory_holder_keeps_tracked_child_and_missing_child_origins(tmp_path):
    from conftest import expect_exit, expect_ok

    source = '''Box::struct{value:i32}
Holder::struct{child:ref Box}
factory::fn() ref Holder{ret new Holder}
check::fn(flag:bool){
 a:=factory();if a==nil{ret};b:=factory();if b==nil{del a;ret}
 x:=new Box;if x==nil{del a;del b;ret}
 a.child=x
 p:=if flag{a}else{b}
 if p.child!=nil{saved:=p.child;v:=saved.value}
 del x;del a;del b
}
main::fn(){check(false)}
'''
    expect_ok(source, tmp_path)
    expect_exit(source.replace('v:=saved.value', 'del x;v:=saved.value'), tmp_path, 6, 'Use after move or delete')


def test_factory_choice_stored_and_returned_has_one_shared_origin_set(tmp_path):
    from conftest import expect_exit, expect_ok

    source = '''Box::struct{value:i32}
Holder::struct{child:ref Box}
factory::fn(h:ref Holder,flag:bool) ref Box{
 a:=new Box;b:=new Box;t:=if flag{a}else{b};h.child=t;ret t
}
main::fn(){h:=Holder{child:nil};p:=factory(h,false);if p==nil{ret};
 if h.child!=nil{v:=h.child.value};del p}
'''
    expect_ok(source, tmp_path)
    expect_exit(source.replace('if h.child!=nil{v:=h.child.value};del p',
                               'del p;if h.child!=nil{v:=h.child.value}'),
                tmp_path, 6, 'Use after move or delete')


def test_deep_shared_prefix_queries_do_not_use_python_recursion():
    import sys
    from conftest import low_recursion_limit

    graph = AllocationGraph()
    left, right = graph.atom(('new', 1)), graph.atom(('new', 2))
    previous = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(low_recursion_limit())
        for site in range(2001):
            left = graph.prefix(('call', site), left)
            right = graph.prefix(('call', site), right)
        combined = graph.union([left, right])
        assert graph.cardinality[combined] == 2
        assert graph.combine('intersection', left, right) == 0
        assert graph.combine('difference', combined, left) == right
        assert graph.combine('intersection', combined, left) == left
    finally:
        sys.setrecursionlimit(previous)
