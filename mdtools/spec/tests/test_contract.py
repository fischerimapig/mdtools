"""Contract/invariant tests; no future parser, loader or CLI is simulated."""

from dataclasses import FrozenInstanceError, replace
import json

import pytest

from mdtools.core.diagnostics import CheckResult, Diagnostic, DiagnosticLocation, RelatedLocation, report_to_dict
from mdtools.core.source import SourcePosition, SourceSnapshot, SourceSpan
from mdtools.spec.model import (
    Body, FieldSource, JsonObject, NodeKey, Reference,
)
from mdtools.spec.results import (
    LocalAnalysis, ReferenceResolution, ResolvedAnalysis, SpecGraph,
)
from mdtools.spec.tests.examples import (
    FIXTURES, checks, definition_results, fixture_result, origin, requirement,
)
from mdtools.workspace import load_workspace


@pytest.mark.parametrize('name,expected', json.loads((FIXTURES / 'expectations.json').read_text()).items())
def test_hand_authored_fixture_contract(name, expected):
    result = fixture_result(name)
    assert result.completeness == expected['completeness']
    assert [d.code for d in result.diagnostics] == ([expected['diagnostic']] if expected['diagnostic'] else [])
    if result.requirements:
        req, = result.requirements
        assert req.formalization == expected['formalization']
        assert [body.language for body in req.bodies] == expected['languages']
    else:
        assert expected['formalization'] is None
    assert all(c.status == 'not-run' for c in result.checks.expressions)
    assert result.checks.references.status == 'not-run'
    assert report_to_dict(result.report)['schema_version'] == 1


def test_no_formula_or_uses_validation_is_claimed_by_structural_success():
    result = fixture_result('unchecked.md')
    model = result.requirements[0].model
    assert result.checks.structure.status == 'passed'
    assert model.when.text == 'paid and ('  # Not even valid expression syntax.
    assert model.uses == ()  # M3 must diagnose missing identifiers, not M2.
    assert all(c.status == 'not-run' and c.reason for c in model.checks)
    with pytest.raises(ValueError, match='M2'):
        replace(model, checks=tuple(replace(c, status='passed') for c in model.checks))


def test_escaped_json_field_keeps_raw_token_and_decoded_value_separate():
    result = fixture_result('unchecked.md')
    must = result.requirements[0].model.must
    assert must.text == 'paid == true'
    assert result.source.slice(must.origin.location.span) == '"must": "\\u0070aid == true"'
    unavailable = origin(result.source, '/must', container=must.origin.container)
    conservative = replace(must, origin=unavailable)
    assert conservative.origin.location.kind == 'unmapped'
    assert conservative.origin.location.span is None
    assert conservative.origin.container is not None


def test_recovery_and_broken_formalization_never_become_complete_natural_only():
    recovered = fixture_result('invalid.md')
    assert recovered.requirements[0].key.name == 'REQ-RECOVER'
    assert recovered.rejected[0].text.startswith('::: {.requirement spec-version=1}')
    with pytest.raises(ValueError, match='complete'):
        replace(recovered, completeness='complete', checks=checks())
    broken = fixture_result('broken-model.md')
    req = broken.requirements[0]
    assert req.formalization == 'present' and req.model is None
    with pytest.raises(ValueError, match='broken formal model'):
        replace(req, structure=CheckResult('spec.structure', 'passed'))
    with pytest.raises(ValueError, match='natural-only'):
        replace(broken, requirements=(replace(req, formalization='natural-only'),))
    with pytest.raises(ValueError, match='diagnostic is missing'):
        replace(broken, diagnostics=())


@pytest.mark.parametrize('newline', ['\n', '\r\n', '\r'])
def test_source_coordinates_and_stale_snapshot_are_validated(newline):
    raw = f'::: {{.requirement #REQ-UNICODE spec-version=1}}{newline}日本語📚é{newline}:::{newline}'
    source = SourceSnapshot('memory:unicode', raw)
    req = requirement(source, 'REQ-UNICODE', ((None, '日本語📚é' + newline),))
    result = LocalAnalysis(source, checks(), 'complete', (req,))
    assert result.source.slice(req.bodies[0].span) == '日本語📚é' + newline
    assert req.bodies[0].span.start == SourcePosition(2, 1)
    assert source.position(raw.index('é')) == SourcePosition(2, 5)
    with pytest.raises(ValueError, match='snapshot'):
        replace(result, source=SourceSnapshot(source.uri, raw + 'changed'))
    bad = SourceSpan(source.ref, SourcePosition(99, 1), SourcePosition(99, 2))
    with pytest.raises(ValueError):
        replace(result, requirements=(replace(req, span=bad, bodies=(Body(None, 'x', bad),)),))


def test_body_and_rejected_text_must_match_snapshot():
    result = fixture_result('natural-only.md')
    req = result.requirements[0]
    bad = replace(req, bodies=(replace(req.bodies[0], text='invented text'),))
    with pytest.raises(ValueError, match='raw text differs'):
        replace(result, requirements=(bad,))
    rejected = fixture_result('invalid.md')
    with pytest.raises(ValueError, match='raw text differs'):
        replace(rejected, rejected=(replace(rejected.rejected[0], text='lost raw input'),))


def test_field_precision_and_required_provenance():
    result = fixture_result('normal.md')
    req = result.requirements[0]
    with pytest.raises(ValueError, match='missing or duplicate'):
        replace(req, fields=req.fields[1:])
    with pytest.raises(ValueError, match='missing or duplicate'):
        replace(req, fields=(*req.fields, req.fields[0]))
    with pytest.raises(ValueError, match='outside its container'):
        FieldSource('/id', req.fields[0].location, result.source.span(0, 1))
    with pytest.raises(ValueError, match='pointer'):
        FieldSource('/bad~2path', DiagnosticLocation())
    assert FieldSource('/names/a~1b~0c', DiagnosticLocation()).path == '/names/a~1b~0c'
    default = fixture_result('natural-only.md').requirements[0].fields[-1]
    assert default.path == '/status' and default.location.kind == 'unmapped'


@pytest.mark.parametrize('changes', [
    {'minimum': True}, {'maximum': False}, {'minimum': 31}, {'value': True},
    {'value': -1}, {'value': 31}, {'value': '14'}, {'role': 'input'},
])
def test_integer_constant_boundaries_and_bool_are_not_int(changes):
    window = definition_results()[0].declarations[2]
    with pytest.raises(ValueError):
        replace(window, **changes)
    assert replace(window, value=0).value == 0
    assert replace(window, value=30).value == 30


@pytest.mark.parametrize('name', ['bool', 'int', 'true', 'false', 'not', 'and', 'or', 'has-dash'])
def test_variable_names_and_builtin_collisions(name):
    paid = definition_results()[0].declarations[1]
    with pytest.raises(ValueError):
        replace(paid, key=replace(paid.key, name=name))


def test_enum_and_deferred_named_type_constant():
    defs, _ = definition_results()
    enum, paid, window, initial = defs.declarations
    for values in ((), ('new', 'new'), ('',), ['new']):
        with pytest.raises(ValueError):
            replace(enum, values=values)
    assert initial.type_ref.name == 'OrderState'
    # Membership is checked after collecting all files in #38.
    assert replace(initial, value='not-a-member').value == 'not-a-member'
    with pytest.raises(ValueError):
        replace(initial, value=True)
    with pytest.raises(ValueError):
        replace(paid, role=None)
    with pytest.raises(ValueError):
        replace(paid, minimum=0)


def test_glossary_associations_keep_legacy_id_and_data_semantics():
    defs, glossary = definition_results()
    paid = defs.declarations[1]
    assert paid.glossary.name == glossary.glossary[0].key.name == 'paid label'
    assert defs.declarations[0].glossary.name == glossary.glossary[1].key.name
    # Link targets may be any glossary kind. They do not confer a spec type.
    assert glossary.glossary[1].kind == 'symbol'
    assert replace(glossary.glossary[0].key, name=' ').name == ' '
    with pytest.raises(FrozenInstanceError):
        glossary.glossary[0].kind = 'const'
    for data in ({'names': 'mutable'}, JsonObject((('id', 'duplicate'),))):
        with pytest.raises(ValueError):
            replace(glossary.glossary[0], data=data)
    for items in ((('x', []),), (('x', float('nan')),), (('x', 1), ('x', 2))):
        with pytest.raises(ValueError):
            JsonObject(items)


def complete_example():
    normal = fixture_result('normal.md')
    defs, glossary = definition_results()
    enum, paid, window, initial = defs.declarations
    label, state_label = glossary.glossary
    edges = (
        ReferenceResolution(normal.requirements[0].model.key, normal.requirements[0].model.uses[0], 'resolved', (paid.key,)),
        ReferenceResolution(enum.key, enum.glossary, 'resolved', (state_label.key,)),
        ReferenceResolution(paid.key, paid.type_ref, 'resolved', builtin='bool'),
        ReferenceResolution(paid.key, paid.glossary, 'resolved', (label.key,)),
        ReferenceResolution(window.key, window.type_ref, 'resolved', builtin='int'),
        ReferenceResolution(initial.key, initial.type_ref, 'resolved', (enum.key,)),
        ReferenceResolution(initial.key, initial.glossary, 'resolved', (state_label.key,)),
    )
    inputs = (normal, defs, glossary)
    graph = SpecGraph(tuple(key for item in inputs for key in item.nodes), edges)
    return ResolvedAnalysis(inputs, graph, checks(references='passed'), 'complete')


def test_local_and_resolved_results_have_distinct_contracts():
    result = complete_example()
    assert len(result.graph.nodes) == 8
    assert len(result.graph.edges) == 7
    assert result.checks.references.status == 'passed'
    assert all(item.checks.references.status == 'not-run' for item in result.inputs)
    with pytest.raises(ValueError, match='defer'):
        replace(result.inputs[0], checks=checks(references='passed'))
    with pytest.raises(ValueError, match='every collected occurrence'):
        replace(result, graph=SpecGraph((), ()))
    with pytest.raises(ValueError, match='every explicit reference'):
        replace(result, graph=replace(result.graph, edges=result.graph.edges[1:]))


@pytest.mark.parametrize('status', ['pending', 'undefined', 'wrong-kind'])
def test_unresolved_states_never_pass_as_a_complete_graph(status):
    result = complete_example()
    edge = result.graph.edges[0]
    candidate = result.inputs[1].declarations[1].key
    replacement = replace(edge, status=status, candidates=(candidate,) if status == 'wrong-kind' else ())
    graph = replace(result.graph, edges=(replacement, *result.graph.edges[1:]))
    with pytest.raises(ValueError, match='unresolved'):
        replace(result, graph=graph)
    partial = replace(result, graph=graph, completeness='partial', checks=checks(references='failed'))
    assert partial.graph.edges[0].status == status


def test_name_collisions_retain_all_occurrences_and_both_diagnostic_locations():
    result = complete_example()
    defs = result.inputs[1]
    original = defs.declarations[1]
    second_source = SourceSnapshot('memory:second-definition', defs.source.text)
    # A separate original file, with explicit newly located provenance.
    from mdtools.spec.model import Declaration
    block = second_source.span()
    fields = tuple(origin(second_source, item.path, container=block) for item in original.fields)
    duplicate = Declaration(NodeKey('declaration', 'paid', second_source.ref, 0), block, fields, 'variable',
                            type_ref=Reference('type', 'bool', next(o for o in fields if o.path == '/type')), role='input',
                            glossary=Reference('glossary', 'paid label', next(o for o in fields if o.path == '/glossary')))
    duplicate_local = LocalAnalysis(second_source, checks(), 'complete', declarations=(duplicate,))
    edge = result.graph.edges[0]
    collision = replace(edge, status='ambiguous', candidates=(original.key, duplicate.key))
    graph = SpecGraph((*result.graph.nodes, duplicate.key),
                      (collision, *result.graph.edges[1:],
                       ReferenceResolution(duplicate.key, duplicate.type_ref, 'resolved', builtin='bool'),
                       ReferenceResolution(duplicate.key, duplicate.glossary, 'resolved', (result.inputs[2].glossary[0].key,))))
    diagnostic = Diagnostic('spec.duplicate-name', 'error', 'user', 'Duplicate paid declaration',
                            DiagnosticLocation('original', duplicate.span),
                            (RelatedLocation('Previous declaration', DiagnosticLocation('original', original.span)),))
    partial = ResolvedAnalysis((*result.inputs, duplicate_local), graph, checks(references='failed'), 'partial', (diagnostic,))
    assert len(partial.graph.edges[0].candidates) == 2
    assert len(partial.report.sources) == 4
    with pytest.raises(ValueError, match='hides a name collision'):
        replace(partial, graph=replace(graph, edges=(edge, *graph.edges[1:])))
    with pytest.raises(ValueError, match='complete'):
        replace(partial, completeness='complete', checks=checks(references='passed'))


def test_namespaces_do_not_substitute_for_each_other():
    result = complete_example()
    edge = result.graph.edges[0]
    wrong_namespace = replace(result.inputs[2].glossary[0].key, name='paid')
    with pytest.raises(ValueError, match='namespaces'):
        replace(edge, candidates=(wrong_namespace,))
    wrong_kind = replace(result.inputs[1].declarations[0], key=replace(result.inputs[1].declarations[0].key, name='paid'))
    local = replace(result.inputs[1], declarations=(wrong_kind, *result.inputs[1].declarations[1:]))
    with pytest.raises(ValueError, match='wrong kind'):
        # Isolate the declaration kind invariant without triggering a collision.
        local = replace(local, declarations=(wrong_kind,))
        ref = edge.reference
        graph = SpecGraph((*result.inputs[0].nodes, wrong_kind.key), (
            replace(edge, candidates=(wrong_kind.key,)),
            ReferenceResolution(wrong_kind.key, wrong_kind.glossary, 'undefined'),
        ))
        ResolvedAnalysis((result.inputs[0], local), graph, checks(references='failed'), 'partial')


def test_self_reference_and_cycles_are_legal_graph_values():
    result = fixture_result('natural-only.md')
    req = result.requirements[0]
    field = origin(result.source, '/refs', container=req.span)
    ref = Reference('refs', req.key.name, replace(field, path='/refs/0'))
    req = replace(req, fields=(*req.fields, field), refs=(ref,))
    local = replace(result, requirements=(req,))
    edge = ReferenceResolution(req.key, ref, 'resolved', (req.key,))
    graph = SpecGraph(local.nodes, (edge,))
    resolved = ResolvedAnalysis((local,), graph, checks(references='passed'), 'complete')
    assert resolved.graph.edges[0].owner == resolved.graph.edges[0].candidates[0]
    assert resolved.checks.expressions[-1].status == 'not-run'


def test_repeated_refs_and_two_node_cycle_retain_distinct_occurrences():
    source = SourceSnapshot('memory:refs', 'A\nB\n')
    a_span, b_span = source.span(0, 2), source.span(2, 4)
    def req(name, ordinal, target, block, raw, count):
        fields = tuple(origin(source, path, container=block) for path in ('/id', '/spec-version', '/status', '/refs'))
        refs = tuple(Reference('refs', target, origin(source, f'/refs/{i}', container=block)) for i in range(count))
        from mdtools.spec.model import Requirement
        return Requirement(NodeKey('requirement', name, source.ref, ordinal), block, fields,
                           (Body(None, raw, block),), CheckResult('spec.structure', 'passed'), 'natural-only', refs=refs)
    a = req('A', 0, 'B', a_span, 'A\n', 2)
    b = req('B', 1, 'A', b_span, 'B\n', 1)
    local = LocalAnalysis(source, checks(), 'complete', (a, b))
    edges = (*[ReferenceResolution(a.key, ref, 'resolved', (b.key,)) for ref in a.refs],
             ReferenceResolution(b.key, b.refs[0], 'resolved', (a.key,)))
    resolved = ResolvedAnalysis((local,), SpecGraph(local.nodes, edges), checks(references='passed'), 'complete')
    assert len(resolved.graph.edges) == 3
    assert a.refs[0].name == a.refs[1].name
    assert a.refs[0].origin.path != a.refs[1].origin.path


def test_input_and_graph_order_do_not_change_resolved_targets_or_diagnostic_json():
    result = complete_example()
    reordered = replace(result, inputs=tuple(reversed(result.inputs)),
                        graph=SpecGraph(tuple(reversed(result.graph.nodes)), tuple(reversed(result.graph.edges))))
    assert {(e.owner, e.reference, e.candidates, e.builtin) for e in result.graph.edges} == {
        (e.owner, e.reference, e.candidates, e.builtin) for e in reordered.graph.edges}
    assert report_to_dict(result.report) == report_to_dict(reordered.report)


def test_missing_snapshot_and_out_of_bounds_provenance_are_rejected():
    result = fixture_result('invalid.md')
    old = result.rejected[0]
    other = SourceSnapshot('memory:unregistered', old.text)
    with pytest.raises(ValueError, match='snapshot is missing'):
        replace(result, rejected=(replace(old, span=other.span()),))
    bad = SourceSpan(result.source.ref, SourcePosition(99, 1), SourcePosition(99, 2))
    with pytest.raises(ValueError, match='outside snapshot'):
        replace(result, rejected=(replace(old, span=bad),))


def test_glossary_undefined_diagnostic_and_unavailable_result():
    defs, _ = definition_results()
    declaration = defs.declarations[1]
    missing = Diagnostic('spec.undefined-glossary', 'error', 'user', 'No glossary target',
                         declaration.glossary.origin.location)
    assert missing.primary.span.source == defs.source.ref
    unavailable = ResolvedAnalysis((), SpecGraph((), ()), checks('error', 'not-run'), 'unavailable', (
        Diagnostic('spec.read-error', 'error', 'tool-error', 'Could not read input'),))
    assert unavailable.report.sources == ()
    assert unavailable.completeness == 'unavailable'
    with pytest.raises(ValueError, match='unavailable'):
        replace(defs, completeness='unavailable', checks=checks('error'))


def test_fixture_workspace_and_equivalent_yaml_are_usable_inputs():
    workspace = load_workspace(FIXTURES / 'mdtools.toml')
    assert [path.name for path in workspace.analysis_files] == [
        'normal.md', 'natural-only.md', 'multilingual.md', 'unchecked.md']
    import yaml
    # Fixture equivalence only; this is deliberately NOT the future strict loader.
    assert yaml.safe_load((FIXTURES / 'definitions.yaml').read_text()) == json.loads((FIXTURES / 'definitions.json').read_text())


@pytest.mark.parametrize('filename,command,status,exit_code,code', [
    ('cli-show-unknown.json', 'show', 'complete', 3, 'spec.unknown-id'),
    ('cli-index-missing-yaml.json', 'index', 'unavailable', 5, 'spec.missing-dependency'),
])
def test_future_cli_envelope_examples_reuse_m1_diagnostic_schema(filename, command, status, exit_code, code):
    from jsonschema import Draft202012Validator
    envelope = json.loads((FIXTURES / filename).read_text())
    schema = json.loads((FIXTURES.parents[1] / 'diagnostics-v1.schema.json').read_text())
    Draft202012Validator(schema).validate(envelope['report'])
    assert set(envelope) == {'schema_version', 'command', 'status', 'exit_code', 'result', 'report'}
    assert (envelope['schema_version'], envelope['command'], envelope['status'], envelope['exit_code']) == (1, command, status, exit_code)
    assert envelope['result'] is None
    assert envelope['report']['diagnostics'][0]['code'] == code
    m3 = [c for c in envelope['report']['checks'] if c['check_id'].startswith('spec.expression-') or c['check_id'] == 'spec.logic']
    assert len(m3) == 4 and all(c['status'] == 'not-run' and c['reason'] for c in m3)
