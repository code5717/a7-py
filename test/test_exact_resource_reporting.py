"""Resource reporting preserves failed evaluation and initializer ownership."""
from fractions import Fraction

import pytest

import a7.passes.type_checker as checker
from a7.ast_nodes import ASTNode
from a7.exact_constants import (
    ExactArithmeticError, ExactBudget, ExactPolicy, ExactResourceCategory,
    ExactResourceError,
)
from a7.symbol_table import SymbolTable
from conftest import expect_exit, expect_ok, parse_program


@pytest.mark.parametrize('size', [4, 16, 64])
def test_array_cache_failure_reports_first_owned_error(monkeypatch, tmp_path, size):
    source = f'main::fn(){{ a:[{size}]i32=[' + ','.join(['1'] * size) + '] }\n'
    expect_ok(source, tmp_path)
    events, passes = [], []
    report = checker.TypeCheckingPass._report_exact_error
    analyze = checker.TypeCheckingPass.analyze

    def record(self, error, span):
        events.append((error, span))
        return report(self, error, span)

    def keep_tree(self, program, filename='<unknown>'):
        passes.append((self, program))
        return analyze(self, program, filename)

    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(retained_bytes=132)))
    monkeypatch.setattr(checker.TypeCheckingPass, '_report_exact_error', record)
    monkeypatch.setattr(checker.TypeCheckingPass, 'analyze', keep_tree)
    result = expect_exit(source, tmp_path, 6, 'retained payload')
    assert len(result.failure.details) == 1
    first = result.failure.details[0]
    column = 27 if size == 4 else 28
    assert first == {
        'type': 'SemanticError', 'code': None,
        'message': 'Exact constant resource limit: retained payload exceeds 132 bytes',
        'hint': None, 'file': str(tmp_path / 'main.a7'),
        'span': {'start_line': 1, 'start_column': column, 'end_line': 1,
                 'end_column': column + 1, 'length': 1},
    }
    assert first['span']['start_line'] == events[0][1].start_line
    assert first['span']['start_column'] == events[0][1].start_column
    owner = events[0][0].initializer_owner
    assert len(events) > 1
    assert {(error.initializer_owner, error.category) for error, _ in events} == {
        (owner, ExactResourceCategory.RETAINED_PAYLOAD)}
    # Assert the actual ownership graph, including the revisited length node.
    instance, program = passes[-1]
    nodes, work = [], [program]
    seen = set()
    while work:
        node = work.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        nodes.append(node)
        for value in vars(node).values():
            if isinstance(value, ASTNode):
                work.append(value)
            elif isinstance(value, list):
                work.extend(child for child in value if isinstance(child, ASTNode))
    declaration = next(node for node in nodes if node.name == 'a')
    assert owner == id(declaration)
    assert all(instance.exact_budget.owners[id(node)] == owner
               for node in nodes if getattr(node, 'exact_failed', False))
    assert any(getattr(node, 'exact_failed', False) for node in nodes)
    assert instance.exact_budget.payload <= 132
    assert instance.exact_budget.policy.retained_bytes == 132
    accounting = (instance.exact_budget.total, instance.exact_budget.payload,
                  sorted(instance.exact_budget.initializers.values()),
                  sorted(instance.exact_budget.retained.values()))
    failed = sorted((node.span.start_line, node.span.start_column)
                    for node in nodes if getattr(node, 'exact_failed', False))
    # Restore the former publication behavior only. Evaluation and accounting
    # still run through the same compiler, so this isolates presentation effects.
    monkeypatch.setattr(checker.TypeCheckingPass, '_report_exact_error',
                        lambda self, error, span: self.add_error(str(error), span))
    unsuppressed = expect_exit(source, tmp_path, 6, 'retained payload')
    assert len(unsuppressed.failure.details) == size - 1
    assert unsuppressed.failure.details[0] == first
    other, program = passes[-1]
    assert (other.exact_budget.total, other.exact_budget.payload,
            sorted(other.exact_budget.initializers.values()),
            sorted(other.exact_budget.retained.values())) == accounting
    work, seen, other_failed = [program], set(), []
    while work:
        node = work.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if getattr(node, 'exact_failed', False):
            other_failed.append((node.span.start_line, node.span.start_column))
        for value in vars(node).values():
            if isinstance(value, ASTNode):
                work.append(value)
            elif isinstance(value, list):
                work.extend(child for child in value if isinstance(child, ASTNode))
    assert sorted(other_failed) == failed


def test_separate_initializers_and_nonresource_error_survive(monkeypatch, tmp_path):
    monkeypatch.setattr(checker, 'ExactBudget', lambda: ExactBudget(ExactPolicy(retained_bytes=132)))
    result = expect_exit('main::fn(){\n a:[4]i32=[1,1,1,1]\n b:[4]i32=[1,1,1,1]\n bad:bool="wrong"\n}\n',
                         tmp_path, 6, 'retained payload')
    resource = [error for error in result.failure.details if 'retained payload' in error['message']]
    assert len(resource) == 2
    assert {error['span']['start_line'] for error in resource} == {2, 3}
    assert any('retained payload' not in error['message'] and error['span']['start_line'] == 4
               for error in result.failure.details)


def test_structured_reporting_preserves_categories_unknown_errors_and_reset():
    instance = checker.TypeCheckingPass(SymbolTable())
    span = parse_program('X::1\n').declarations[0].span
    for category in (ExactResourceCategory.RETAINED_PAYLOAD, ExactResourceCategory.COMPONENT_BITS):
        error = ExactResourceError('same message', category=category, initializer_owner=17)
        instance._report_exact_error(error, span)
        instance._report_exact_error(error, span)
    assert len(instance.errors) == 2
    for error in (ExactResourceError('unclassified'), ExactArithmeticError('division by zero')):
        instance._report_exact_error(error, span)
        instance._report_exact_error(error, span)
    assert len(instance.errors) == 6
    instance.analyze(parse_program(''), 'again.a7')
    analysis_errors = tuple(instance.errors)
    repeated = ExactResourceError('same message',
        category=ExactResourceCategory.RETAINED_PAYLOAD, initializer_owner=17)
    instance._report_exact_error(repeated, span)
    instance._report_exact_error(repeated, span)
    assert tuple(instance.errors[:-1]) == analysis_errors
    assert len(instance.errors) == len(analysis_errors) + 1
    assert instance.errors[-1].message == 'same message'


def test_exception_captures_owner_without_changing_failed_charge():
    budget = ExactBudget(ExactPolicy(initializer_credits=1, retained_bytes=66))
    first, second = object(), object()
    budget.bind(first).charge(1, 'accepted')
    with pytest.raises(ExactResourceError) as failure:
        budget.charge(1, 'rejected')
    budget.bind(second)
    assert failure.value.initializer_owner == id(first)
    assert failure.value.category is ExactResourceCategory.INITIALIZER_WORK
    assert budget.total == 1 and budget.initializers == {id(first): 1}
    budget.retain(('binding', 1), (Fraction(1), False))
    with pytest.raises(ExactResourceError) as failure:
        budget.retain(('binding', 2), (Fraction(1), False))
    assert failure.value.initializer_owner == id(second)
    assert failure.value.category is ExactResourceCategory.RETAINED_PAYLOAD
    assert budget.payload == 66 and budget.retained == {('binding', 1): 66}
