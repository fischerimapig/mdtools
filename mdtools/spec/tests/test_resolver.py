"""Collected-name resolution and declaration-value checks via public APIs."""

from dataclasses import replace

import pytest

from mdtools.spec.resolver import resolve_analyses
from ._resolver_helpers import definitions, manuscript, signature


def test_forward_references_across_inputs_and_namespaces_in_input_order():
    req = manuscript(refs=('REQ-B',), uses=['flag', 'choice'])
    other = manuscript(name='REQ-B', refs=('REQ-A',), uri='memory:other')
    const = definitions(constants={'choice': {'type': 'State', 'value': 'yes'}}, uri='memory:constants')
    types = definitions(types={'State': {'kind': 'enum', 'values': ['yes', 'no']}},
                        variables={'flag': {'type': 'bool', 'role': 'input'}}, uri='memory:types')
    result = resolve_analyses(iter((req, const, other, types)))
    assert result.inputs == (req, const, other, types)
    assert result.graph.nodes == tuple(key for item in result.inputs for key in item.nodes)
    assert len(result.graph.edges) == sum(len(item.references) for item in result.inputs)
    assert result.completeness == 'complete' and all(e.status == 'resolved' for e in result.graph.edges)
    assert signature(result) == signature(resolve_analyses(reversed(result.inputs)))
    assert all(e.status != 'pending' for e in result.graph.edges)
    assert all(c.status == 'not-run' and c.reason for c in result.checks.expressions)
    assert result.inputs[0].requirements[0].model.when.text == 'unexamined and ('


@pytest.mark.parametrize('type_kind', ['variable', 'constant'])
def test_single_declaration_wrong_kind_is_not_substituted(type_kind):
    non_type = {'type': 'bool', **({'role': 'input'} if type_kind == 'variable' else {'value': True})}
    members = {'types': {'Enum': {'kind': 'enum', 'values': ['ok']}},
               'variables': {'v': {'type': 'Target', 'role': 'input'}}}
    members.setdefault(type_kind + 's', {})['Target'] = non_type
    defs = definitions(**members)
    result = resolve_analyses((manuscript(uses=['Enum']), defs))
    wrong = [e for e in result.graph.edges if e.status == 'wrong-kind']
    assert [(e.reference.kind, e.reference.name) for e in wrong] == [('uses', 'Enum'), ('type', 'Target')]
    assert all(len(e.candidates) == 1 for e in wrong)
    assert result.checks.references.status == 'failed'
    assert result.checks.declarations.status == 'passed'  # No named constant membership was deferred.
    assert len([d for d in result.diagnostics if d.code == 'spec.wrong-reference-kind']) == 2


def test_undefined_references_and_glossary_use_distinct_codes_and_origins():
    req = manuscript(refs=('REQ-MISSING',), uses=['missing'])
    defs = definitions(variables={'v': {'type': 'Missing', 'role': 'input', 'glossary': 'missing label'}})
    result = resolve_analyses((req, defs))
    assert [e.status for e in result.graph.edges] == ['undefined'] * 4
    assert [d.code for d in result.diagnostics] == ['spec.undefined-reference'] * 3 + ['spec.undefined-glossary']
    assert [d.primary for d in result.diagnostics] == [e.reference.origin.location for e in result.graph.edges]
    assert [d.requirement_id for d in result.diagnostics[:2]] == ['REQ-A', 'REQ-A']


def test_other_namespaces_all_candidates_are_wrong_kind_even_if_multiple():
    req = manuscript(name='shared', uses=['shared'])
    other = manuscript(name='shared', uri='memory:other')
    glossary = definitions({'entries': [{'id': 'shared', 'kind': 'term'}]}, kind='glossary')
    result = resolve_analyses((req, other, glossary))
    edge, = result.graph.edges
    assert edge.status == 'wrong-kind'
    assert edge.candidates == (*req.nodes[:1], *other.nodes, *glossary.nodes)
    diagnostic = next(d for d in result.diagnostics if d.code == 'spec.wrong-reference-kind')
    assert len(diagnostic.related) == 3
    with pytest.raises(ValueError):
        replace(result, graph=replace(result.graph, edges=(replace(edge, candidates=edge.candidates[:1]),)))


@pytest.mark.parametrize('members', [
    {'types': {'x': {'kind': 'enum', 'values': ['ok']}}, 'constants': {'x': {'type': 'bool', 'value': True}}},
    {'types': {'x': {'kind': 'enum', 'values': ['ok']}}},
])
def test_ambiguity_before_declaration_kind_filter(members):
    first = definitions(**members)
    # For the second case both candidates are of the wrong kind for uses.
    inputs = (first,) if 'constants' in members else (first, definitions(uri='memory:second', **members))
    result = resolve_analyses((manuscript(uses=['x']), *inputs))
    edge = result.graph.edges[0]
    assert edge.status == 'ambiguous' and len(edge.candidates) == 2
    assert edge.candidates == tuple(d.key for item in inputs for d in item.declarations if d.key.name == 'x')
    assert result.registries['declaration']['x'] == edge.candidates
    with pytest.raises(ValueError):
        replace(result, graph=replace(result.graph, edges=(replace(edge, status='wrong-kind', candidates=edge.candidates[:1]),
                                                         *result.graph.edges[1:])))
    with pytest.raises(ValueError):
        replace(result, checks=replace(result.checks, declarations=replace(result.checks.declarations, status='passed')))


def test_target_namespace_has_priority_over_same_name_elsewhere():
    req = manuscript(name='shared', refs=('shared',), uses=['shared'])
    defs = definitions(variables={'shared': {'type': 'bool', 'role': 'input'}})
    glossary = definitions({'entries': [{'id': 'shared', 'kind': 'symbol'}]}, kind='glossary', uri='memory:glossary')
    result = resolve_analyses((req, defs, glossary))
    assert result.completeness == 'complete'
    assert [e.candidates for e in result.graph.edges[:2]] == [(req.nodes[0],), (defs.nodes[0],)]


@pytest.mark.parametrize('builtin', ['bool', 'int'])
def test_builtins_precede_other_namespaces_and_do_not_apply_to_refs_or_glossary(builtin):
    req = manuscript(name=builtin, refs=(builtin,), uses=[builtin])
    glossary = definitions({'entries': [{'id': builtin, 'kind': 'term'}]}, kind='glossary', uri='memory:glossary')
    var = {'type': builtin, 'role': 'input', 'glossary': builtin}
    if builtin == 'int':
        var.update(min=0, max=1)
    defs = definitions(variables={'v': var})
    result = resolve_analyses((req, glossary, defs))
    refs, uses, type_ref, glossary_ref = result.graph.edges
    assert refs.status == glossary_ref.status == type_ref.status == 'resolved'
    assert refs.builtin is glossary_ref.builtin is None
    assert type_ref.builtin == uses.builtin == builtin
    assert uses.status == 'wrong-kind' and uses.candidates == ()
    assert builtin not in result.registries['declaration']
    diagnostic, = result.diagnostics
    assert diagnostic.code == 'spec.wrong-reference-kind' and diagnostic.related == ()
    assert diagnostic.evidence[0].kind == 'spec.builtin'


@pytest.mark.parametrize('value,expected', [('yes', 'complete'), ('no', 'partial')])
def test_named_enum_membership_is_checked_after_resolving_type(value, expected):
    const = definitions(constants={'c': {'type': 'State', 'value': value}}, uri='memory:const')
    enum = definitions(types={'State': {'kind': 'enum', 'values': ['yes']}}, uri='memory:enum')
    result = resolve_analyses((const, enum))
    assert const.completeness == 'complete' and result.completeness == expected
    assert result.checks.references.status == 'passed'
    if value == 'no':
        diagnostic, = result.diagnostics
        assert diagnostic.code == 'spec.invalid-definition'
        assert const.source.slice(diagnostic.primary.span) == '"no"'
        assert [enum.source.slice(r.location.span) for r in diagnostic.related] == ['"State"', '["yes"]']
        assert result.checks.declarations.status == 'failed'


@pytest.mark.parametrize('target', ['undefined', 'wrong-kind', 'ambiguous'])
def test_unresolved_constant_type_keeps_value_and_skipped_membership_reason(target):
    const = definitions(constants={'c': {'type': 'State', 'value': 'yes'}})
    if target == 'undefined':
        others = ()
    elif target == 'wrong-kind':
        others = (definitions(variables={'State': {'type': 'bool', 'role': 'input'}}, uri='memory:variable'),)
    else:
        others = tuple(definitions(types={'State': {'kind': 'enum', 'values': ['yes']}}, uri=f'memory:enum-{i}') for i in range(2))
    result = resolve_analyses((const, *others))
    edge = result.graph.edges[0]
    assert edge.status == target
    diagnostic = next(d for d in result.diagnostics if d.primary == edge.reference.origin.location)
    evidence, = diagnostic.evidence
    assert evidence.kind == 'spec.enum-membership' and 'not run' in evidence.message
    assert "'yes'" in evidence.message and const.source.slice(evidence.location.span) == '"yes"'
    assert 'not run' in result.checks.declarations.reason
    assert result.checks.declarations.status == ('failed' if target == 'ambiguous' else 'not-run')


def test_builtin_redefinition_rejected_locally_is_retained_without_fabricated_node():
    defs = definitions(variables={'bool': {'type': 'bool', 'role': 'input'}, 'ok': {'type': 'bool', 'role': 'input'}})
    result = resolve_analyses((manuscript(uses=['bool']), defs))
    assert [d.key.name for d in defs.declarations] == ['ok']
    assert result.report.diagnostics[:len(defs.diagnostics)] == defs.diagnostics
    assert result.inputs[1].rejected == defs.rejected
    assert result.graph.edges[0].builtin == 'bool' and result.graph.edges[0].status == 'wrong-kind'
    assert result.completeness == 'partial'
