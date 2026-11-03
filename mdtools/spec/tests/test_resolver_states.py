"""Aggregation, absence of available input, and API boundaries."""

from dataclasses import replace
from itertools import combinations

import pytest

from mdtools.core.diagnostics import CheckResult
from mdtools.core.source import SourceSnapshot
from mdtools.spec.parser import parse_requirements
from mdtools.spec.resolver import resolve_analyses
from ._resolver_helpers import definitions, manuscript


def unavailable(uri='memory:unavailable'):
    local = parse_requirements(SourceSnapshot(uri, ''))
    checks = replace(local.checks,
                     structure=CheckResult('spec.structure', 'unsupported', 'Input dependency unavailable'),
                     declarations=CheckResult('spec.declarations', 'not-run', 'No declarations examined'))
    return replace(local, completeness='unavailable', checks=checks)


def test_api_checks_iterable_elements_and_duplicate_source_refs():
    for inputs in ([None], [manuscript(), 'bad'], 'bad', None):
        with pytest.raises(TypeError):
            resolve_analyses(inputs)
    local = manuscript()
    with pytest.raises(ValueError, match='duplicate source'):
        resolve_analyses((local, local))
    with pytest.raises(ValueError, match='duplicate source'):
        resolve_analyses((local, replace(local)))
    # A changed snapshot at the same URI is a distinct SourceRef.
    changed = manuscript(name='REQ-B')
    assert local.source.uri == changed.source.uri and local.source.ref != changed.source.ref
    assert resolve_analyses((local, changed)).completeness == 'complete'


def test_no_inputs_and_all_unavailable_keep_reasoned_not_run_references():
    for inputs in ((), (unavailable(),), (unavailable(), unavailable('memory:other'))):
        result = resolve_analyses(inputs)
        assert result.completeness == 'unavailable'
        assert result.graph.nodes == result.graph.edges == ()
        assert result.checks.references.status == 'not-run' and result.checks.references.reason
        assert all(check.status == 'not-run' and check.reason for check in result.checks.expressions)
        assert tuple(result.registries) == ('requirement', 'model', 'declaration', 'glossary')
        assert all(not space for space in result.registries.values())
        assert result.report.sources == tuple(local.source for local in inputs)


def test_empty_readable_input_is_complete_but_rejected_or_mixed_input_is_partial():
    empty = parse_requirements(SourceSnapshot('memory:empty', 'ordinary text\n'))
    good = resolve_analyses((empty,))
    assert good.graph.nodes == () and good.completeness == 'complete'
    assert good.checks.references.status == 'passed'  # Local not-run is not aggregated.
    bad = definitions({'version': 2, 'types': {}, 'variables': {}, 'constants': {}})
    result = resolve_analyses((bad,))
    assert result.graph.nodes == () and result.completeness == 'partial'
    assert result.checks.structure.status == 'unsupported'
    assert result.checks.declarations.status == 'not-run'
    assert result.checks.references.status == 'unknown'
    assert result.inputs[0].rejected == bad.rejected
    mixed = resolve_analyses((empty, unavailable()))
    assert mixed.graph.nodes == () and mixed.completeness == 'partial'
    assert mixed.checks.references.status == 'unknown'


def test_invalid_reference_takes_precedence_over_incomplete_input():
    partial = definitions(variables={'bad': {'role': 'input'}, 'ok': {'type': 'bool', 'role': 'input'}})
    req = manuscript(uses=['missing', 'ok'])
    result = resolve_analyses((req, partial))
    assert result.checks.references.status == 'failed'
    assert [e.status for e in result.graph.edges[:2]] == ['undefined', 'resolved']
    # A rejected name never supplies a candidate, even if its name was readable.
    rejected = resolve_analyses((manuscript(uses=['bad']), partial))
    assert rejected.graph.edges[0].status == 'undefined'


@pytest.mark.parametrize('stronger,weaker', list(combinations(
    ['error', 'failed', 'unsupported', 'unknown', 'not-run', 'passed'], 2)))
def test_aggregation_priority_and_all_reasons_are_retained(stronger, weaker):
    locals = []
    for i, status in enumerate((weaker, stronger)):
        local = manuscript(name=f'REQ-{i}', uri=f'memory:{i}')
        checks = replace(local.checks, structure=CheckResult('spec.structure', status, f'structure-{status}'),
                         declarations=CheckResult('spec.declarations', status, f'declarations-{status}'))
        locals.append(replace(local, checks=checks, completeness='complete' if status == 'passed' else 'partial'))
    result = resolve_analyses(locals)
    for name in ('structure', 'declarations'):
        check = getattr(result.checks, name)
        assert check.status == stronger
        assert f'{name}-{stronger}' in check.reason and f'{name}-{weaker}' in check.reason
    assert result.checks.references.status == 'unknown'


def test_failed_local_declarations_do_not_erase_skipped_constant_membership():
    defs = definitions(variables={'bad': {'type': 'bool', 'role': 'invalid'}},
                       constants={'c': {'type': 'Missing', 'value': 'x'}})
    result = resolve_analyses((defs,))
    assert result.checks.declarations.status == 'failed'
    assert 'not run' in result.checks.declarations.reason
    assert 'definition diagnostics' in result.checks.declarations.reason
    assert any(e.kind == 'spec.enum-membership' for d in result.diagnostics for e in d.evidence)
