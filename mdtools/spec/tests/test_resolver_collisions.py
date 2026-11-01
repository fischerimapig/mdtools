"""Collisions remain failures independently of diagnostics already emitted locally."""

from dataclasses import replace

import pytest

from mdtools.core.diagnostics import DiagnosticLocation
from mdtools.spec.resolver import resolve_analyses
from ._resolver_helpers import definitions, manuscript


@pytest.mark.parametrize('namespace', ['requirement', 'model', 'declaration', 'glossary'])
def test_unreferenced_collisions_in_every_namespace_fail_references(namespace):
    if namespace == 'requirement':
        first, second = manuscript(), manuscript(uri='memory:second')
    elif namespace == 'model':
        first, second = manuscript(uses=[]), manuscript(name='REQ-B', uses=[], uri='memory:second')
    elif namespace == 'declaration':
        first, second = (definitions(variables={'v': {'type': 'bool', 'role': 'input'}}, uri=f'memory:{i}') for i in range(2))
    else:
        first, second = (definitions({'entries': [{'id': 'label', 'kind': 'term'}]}, kind='glossary', uri=f'memory:{i}') for i in range(2))
    result = resolve_analyses((first, second))
    assert result.completeness == 'partial' and result.checks.references.status == 'failed'
    assert result.checks.declarations.status == ('failed' if namespace in ('declaration', 'glossary') else 'passed')
    collision, = result.diagnostics
    assert collision.code == {'requirement': 'spec.duplicate-id', 'model': 'spec.duplicate-id',
                              'declaration': 'spec.duplicate-name', 'glossary': 'spec.duplicate-glossary'}[namespace]
    assert collision.primary.span.source == second.source.ref
    assert collision.related[0].location.span.source == first.source.ref
    with pytest.raises(ValueError):
        replace(result, checks=replace(result.checks, references=replace(result.checks.references, status='passed')))


def test_same_snapshot_requirement_and_model_collisions_retain_all_occurrences():
    from mdtools.core.source import SourceSnapshot
    from mdtools.spec.parser import parse_requirements
    raw = manuscript(uses=[]).source.text
    local = parse_requirements(SourceSnapshot('memory:duplicate', raw + raw))
    result = resolve_analyses((local,))
    assert len(result.registries['requirement']['REQ-A']) == 2
    assert len(result.registries['model']['MODEL-A']) == 2
    assert [d.code for d in result.diagnostics] == ['spec.duplicate-id', 'spec.duplicate-id']
    for diagnostic in result.diagnostics:
        assert diagnostic.primary.span.start > diagnostic.related[0].location.span.start


@pytest.mark.parametrize('kind', ['spec', 'glossary'])
def test_exact_locally_reported_pair_is_suppressed_but_failure_and_candidates_remain(kind):
    if kind == 'spec':
        raw = '{"version":1,"types":{},"variables":{"v":{"type":"bool","role":"input"},"v":{"type":"bool","role":"output"}},"constants":{}}'
    else:
        raw = {'entries': [{'id': 'v', 'kind': 'term'}, {'id': 'v', 'kind': 'symbol'}]}
    local = definitions(raw, kind=kind)
    result = resolve_analyses((local,))
    assert result.diagnostics == ()  # Both precise positions are already present.
    assert result.report.diagnostics == local.diagnostics
    assert result.checks.references.status == result.checks.declarations.status == 'failed'
    assert len(result.registries['declaration' if kind == 'spec' else 'glossary']['v']) == 2
    with pytest.raises(ValueError):
        replace(result, checks=replace(result.checks, declarations=replace(result.checks.declarations, status='passed')))


def test_same_code_for_a_different_collision_does_not_suppress_new_pair():
    local = definitions(types={'x': {'kind': 'enum', 'values': ['ok']}, 'y': {'kind': 'enum', 'values': ['ok']}},
                        constants={'x': {'type': 'bool', 'value': True}, 'y': {'type': 'bool', 'value': False}})
    first, second = [d for d in local.diagnostics if d.code == 'spec.duplicate-name']
    local = replace(local, diagnostics=(first,))
    result = resolve_analyses((local,))
    diagnostic, = result.diagnostics
    assert diagnostic.primary == second.primary
    assert diagnostic.related[0].location == second.related[0].location
    assert result.report.diagnostics == (first, diagnostic)


def test_in_file_and_cross_file_collisions_coexist_and_link_all_prior_other_snapshots():
    first = definitions(variables={'v': {'type': 'bool', 'role': 'input'}}, uri='memory:first')
    second = definitions(variables={'v': {'type': 'bool', 'role': 'output'}}, uri='memory:second')
    raw = '{"version":1,"types":{},"variables":{"v":{"type":"bool","role":"input"},"v":{"type":"bool","role":"output"}},"constants":{}}'
    third = definitions(raw, uri='memory:third')
    result = resolve_analyses((first, second, third))
    assert len(result.registries['declaration']['v']) == 4
    assert len(result.diagnostics) == 3  # second plus both occurrences in third.
    for diagnostic in result.diagnostics[1:]:
        assert diagnostic.primary.span.source == third.source.ref
        assert [r.location.span.source for r in diagnostic.related] == [first.source.ref, second.source.ref]
    assert result.report.diagnostics[:len(third.diagnostics)] == third.diagnostics


def test_unmapped_collision_cannot_be_proven_duplicate_and_uses_known_containers():
    local = definitions(types={'x': {'kind': 'enum', 'values': ['ok']}}, constants={'x': {'type': 'bool', 'value': True}})
    nodes = []
    for node in local.declarations:
        fields = tuple(replace(f, location=DiagnosticLocation('unmapped', reason='Exact name unavailable'))
                       if f.path == '/name' else f for f in node.fields)
        nodes.append(replace(node, fields=fields))
    local = replace(local, declarations=tuple(nodes))
    result = resolve_analyses((local,))
    diagnostic, = result.diagnostics
    assert diagnostic.primary.kind == 'unmapped' and diagnostic.primary.span is None and diagnostic.primary.reason
    assert len(diagnostic.related) == 3
    assert [r.location.kind for r in diagnostic.related] == ['original', 'unmapped', 'original']
    assert result.checks.references.status == 'failed'


def test_code_and_only_one_matching_location_do_not_prove_pair_was_reported():
    local = definitions(types={'x': {'kind': 'enum', 'values': ['ok']}}, constants={'x': {'type': 'bool', 'value': True}})
    diagnostic, = local.diagnostics
    local = replace(local, diagnostics=(replace(diagnostic, related=()),))
    result = resolve_analyses((local,))
    assert len(result.diagnostics) == 1 and len(result.diagnostics[0].related) == 1
