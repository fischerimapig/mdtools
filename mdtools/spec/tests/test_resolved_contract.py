"""Supplied resolved-value invariants, separate from resolver execution tests."""

from dataclasses import replace

import pytest

from mdtools.spec.model import Reference
from mdtools.spec.results import ReferenceResolution, SpecGraph
from mdtools.spec.tests.examples import checks, definition_results
from mdtools.spec.tests.test_contract import complete_example


@pytest.mark.parametrize('name', ['bool', 'int'])
@pytest.mark.parametrize('kind,status,allowed', [
    ('type', 'resolved', True), ('uses', 'wrong-kind', True),
    ('type', 'wrong-kind', False), ('uses', 'resolved', False),
    ('refs', 'resolved', False), ('glossary', 'wrong-kind', False),
    ('type', 'undefined', False), ('uses', 'pending', False),
    ('type', 'ambiguous', False),
])
def test_builtin_representation(name, kind, status, allowed):
    local = definition_results()[0]
    declaration = local.declarations[1]
    ref = Reference(kind, name, declaration.type_ref.origin)
    if allowed:
        edge = ReferenceResolution(declaration.key, ref, status, builtin=name)
        assert edge.candidates == () and edge.builtin == name
    else:
        with pytest.raises(ValueError):
            ReferenceResolution(declaration.key, ref, status, builtin=name)


def test_builtin_requires_matching_name_and_no_candidate():
    result = complete_example()
    edge = result.graph.edges[2]
    same_name = replace(result.graph.nodes[0], name=edge.reference.name)
    for updates in ({'builtin': 'int'}, {'candidates': (same_name,)}):
        with pytest.raises(ValueError):
            replace(edge, **updates)


@pytest.mark.parametrize('status', ['undefined', 'wrong-kind'])
def test_nonpending_edge_cannot_hide_available_target(status):
    result = complete_example()
    edge = result.graph.edges[0]
    bad = replace(edge, status=status, candidates=edge.candidates if status == 'wrong-kind' else ())
    with pytest.raises(ValueError):
        replace(result, graph=replace(result.graph, edges=(bad, *result.graph.edges[1:])),
                checks=checks(references='failed'), completeness='partial')


def test_reference_pass_cannot_hide_partial_input_or_pending_edge():
    result = complete_example()
    partial = replace(result.inputs[0], checks=checks('unknown'), completeness='partial')
    with pytest.raises(ValueError):
        replace(result, inputs=(partial, *result.inputs[1:]), checks=checks('unknown', references='passed'),
                completeness='partial')
    edge = replace(result.graph.edges[0], status='pending', candidates=())
    with pytest.raises(ValueError):
        replace(result, graph=replace(result.graph, edges=(edge, *result.graph.edges[1:])),
                checks=checks('not-run', references='passed'), completeness='partial')


def test_declaration_pass_cannot_hide_local_incompletion():
    result = complete_example()
    local = replace(result.inputs[1], checks=checks(declarations='not-run'), completeness='partial')
    with pytest.raises(ValueError):
        replace(result, inputs=(result.inputs[0], local, result.inputs[2]),
                checks=checks(references='unknown'), completeness='partial')


def test_declaration_pass_requires_resolved_named_constant_type_and_membership():
    result = complete_example()
    defs = result.inputs[1]
    constant = defs.declarations[-1]
    # Local validation deliberately accepts a string outside a named enum.
    bad = replace(defs, declarations=(*defs.declarations[:-1], replace(constant, value='absent')))
    with pytest.raises(ValueError):
        replace(result, inputs=(result.inputs[0], bad, result.inputs[2]))
    pending = replace(result.graph.edges[5], status='pending', candidates=())
    with pytest.raises(ValueError):
        replace(result, graph=replace(result.graph, edges=(*result.graph.edges[:5], pending, result.graph.edges[6])),
                checks=checks(references='not-run'), completeness='partial')


def test_registries_are_derived_and_deeply_read_only():
    result = complete_example()
    registries = result.registries
    assert tuple(registries) == ('requirement', 'model', 'declaration', 'glossary')
    assert registries['declaration']['paid'] == (result.inputs[1].declarations[1].key,)
    assert 'bool' not in registries['declaration']
    with pytest.raises(TypeError):
        registries['declaration'] = {}
    with pytest.raises(TypeError):
        registries['declaration']['paid'] = ()
    assert result.registries == registries
    reordered = replace(result, graph=replace(result.graph, nodes=tuple(reversed(result.graph.nodes))))
    assert tuple(reordered.registries['declaration']) == ('initial', 'window', 'paid', 'OrderState')


def test_empty_complete_graph_cannot_claim_resolution_was_executed():
    from mdtools.spec.results import ResolvedAnalysis
    with pytest.raises(ValueError):
        ResolvedAnalysis((), SpecGraph((), ()), checks(references='passed'), 'complete')
