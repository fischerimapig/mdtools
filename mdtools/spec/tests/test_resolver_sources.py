"""Real fixtures, immutable original snapshots, diagnostic locations and ID stability."""

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from mdtools.core.diagnostics import DiagnosticLocation, report_to_dict
from mdtools.core.source import SourceSnapshot, SourceSpan
from mdtools.diagnostics import read_definition_source
from mdtools.spec.loader import load_definitions
from mdtools.spec.model import walk_values
from mdtools.spec.parser import parse_requirements
from mdtools.spec.resolver import resolve_analyses
from mdtools.workspace import load_workspace, snapshot_sources
from ._loader_helpers import EXAMPLES
from ._resolver_helpers import definitions, manuscript, signature


def assert_sources(result):
    assert result.report.sources == tuple(local.source for local in result.inputs)
    snapshots = {source.ref: source for source in result.report.sources}
    for value in walk_values((result.graph, result.report)):
        if isinstance(value, SourceSpan):
            snapshots[value.source].offsets(value)
        elif isinstance(value, DiagnosticLocation) and value.kind == 'unmapped':
            assert value.reason and value.span is None
    for local in result.inputs:
        assert local.source.ref.snapshot == sha256(local.source.text.encode()).hexdigest()
        for rejected in local.rejected:
            assert local.source.slice(rejected.span) == rejected.text
        for requirement in local.requirements:
            for body in requirement.bodies:
                assert local.source.slice(body.span) == body.text
    schema = json.loads((EXAMPLES.parent / 'diagnostics-v1.schema.json').read_text())
    Draft202012Validator(schema).validate(report_to_dict(result.report))


@pytest.mark.parametrize('example', ['cancellation', 'model-contract'])
def test_workspace_real_parser_loader_fixture_join(example):
    workspace = load_workspace(EXAMPLES / example / 'mdtools.toml')
    locals = tuple(parse_requirements(source) for source in snapshot_sources(workspace)) + tuple(
        load_definitions(read_definition_source(item.path), kind=item.kind, format=item.path.suffix[1:])
        for item in workspace.definitions)
    result = resolve_analyses(locals)
    assert result.completeness == 'complete' and result.diagnostics == ()
    assert result.graph.nodes == tuple(key for local in locals for key in local.nodes)
    assert len(result.graph.edges) == sum(len(local.references) for local in locals)
    assert all(edge.status == 'resolved' for edge in result.graph.edges)
    assert 'paid' in result.registries['declaration']
    if example == 'cancellation':
        assert tuple(result.registries['requirement']) == ('REQ-CANCEL-ALLOW', 'REQ-CANCEL-DENY', 'REQ-CANCEL-GUIDANCE')
    else:
        assert 'paid label' in result.registries['glossary']
        unchecked = next(r for local in locals for r in local.requirements if r.key.name == 'REQ-UNCHECKED')
        assert unchecked.model.when.text == 'paid and ('
    assert_sources(result)


@pytest.mark.parametrize('filename', ['invalid.md', 'broken-model.md', 'unsupported.md'])
def test_real_recovery_and_unknown_version_remain_partial_with_all_local_evidence(filename):
    local = parse_requirements(SourceSnapshot.from_path(EXAMPLES / 'model-contract' / filename))
    result = resolve_analyses((local,))
    assert result.completeness == 'partial'
    assert result.checks.references.status == 'unknown'
    assert result.report.diagnostics == local.diagnostics
    assert result.inputs[0] is local and result.inputs[0].rejected
    assert_sources(result)


@pytest.mark.parametrize('filename,code', [('missing-glossary.json', 'spec.undefined-glossary'),
                                          ('duplicate-definitions.json', 'spec.duplicate-name')])
def test_real_missing_glossary_and_duplicate_definitions(filename, code):
    local = load_definitions(read_definition_source(EXAMPLES / 'model-contract' / filename), kind='spec', format='json')
    result = resolve_analyses((local,))
    assert result.completeness == 'partial' and result.checks.references.status == 'failed'
    assert code in [d.code for d in result.report.diagnostics]
    assert_sources(result)


@pytest.mark.parametrize('newline', ['\n', '\r\n', '\r'])
def test_original_bytes_unicode_newlines_and_escaped_token_survive_resolution(tmp_path, newline):
    raw = r'''{
"version":1,"types":{"State":{"kind":"enum","values":["日本語📚é","a\nb"]}},
"variables":{"pa\u0069d":{"type":"\u0062ool","role":"input"}},
"constants":{"c":{"type":"State","value":"a\nabsent"}},"extra":"rejected📚"
}'''.replace('\n', newline)
    path = tmp_path / 'original.json'
    original_bytes = raw.encode()
    path.write_bytes(original_bytes)
    source = read_definition_source(path)
    local = load_definitions(source, kind='spec', format='json')
    req = manuscript(uses=['paid'])
    path.write_text('changed after collection')
    result = resolve_analyses((req, local))
    assert result.inputs[1].source is source
    assert source.text.encode() == original_bytes and source.ref.snapshot == sha256(original_bytes).hexdigest()
    assert source.path == path.resolve()
    assert result.graph.edges[0].candidates == (local.declarations[1].key,)
    assert result.graph.edges[1].builtin == 'bool'
    type_origin = result.graph.edges[1].reference.origin.location
    assert source.slice(type_origin.span) == r'"\u0062ool"'
    diagnostic, = result.diagnostics
    assert source.slice(diagnostic.primary.span) == r'"a\nabsent"'
    assert source.slice(diagnostic.related[1].location.span) == r'["日本語📚é","a\nb"]'
    assert_sources(result)


def test_unmapped_reference_has_reason_and_known_container_without_invented_token():
    local = manuscript(refs=('Missing',))
    requirement, = local.requirements
    ref, = requirement.refs
    origin = replace(ref.origin, location=DiagnosticLocation('unmapped', reason='Exact reference token unavailable'))
    local = replace(local, requirements=(replace(requirement, refs=(replace(ref, origin=origin),)),))
    result = resolve_analyses((local,))
    diagnostic, = result.diagnostics
    assert diagnostic.primary.kind == 'unmapped' and diagnostic.primary.span is None and diagnostic.primary.reason
    assert diagnostic.related[0].location.span == origin.container
    assert_sources(result)


def test_self_cycle_and_repeated_refs_preserve_each_explicit_reference_without_implicit_edges():
    a = manuscript(refs=('REQ-A', 'REQ-B', 'REQ-B'), heading='# Heading\n\n')
    b = manuscript(name='REQ-B', refs=('REQ-A',), uri='memory:b')
    result = resolve_analyses((a, b))
    assert result.completeness == 'complete' and result.diagnostics == ()
    assert len(result.graph.nodes) == 2 and len(result.graph.edges) == 4
    assert result.graph.edges[0].owner == result.graph.edges[0].candidates[0]
    assert result.graph.edges[1].reference.origin.path != result.graph.edges[2].reference.origin.path
    assert result.graph.edges[1].candidates == result.graph.edges[2].candidates


def test_movement_headings_and_source_order_preserve_semantic_ids_and_targets(tmp_path):
    a = manuscript(refs=('REQ-B',), uses=['paid'], heading='# Old title\n\n')
    b = manuscript(name='REQ-B', refs=('REQ-A',), uri='memory:b')
    defs = definitions(variables={'paid': {'type': 'bool', 'role': 'input'}})
    original = resolve_analyses((a, b, defs))
    moved = tmp_path / 'moved.md'
    moved.write_text('# Renamed heading\n\n' + b.source.text + '## New section\n\n' + a.source.text)
    reordered = parse_requirements(SourceSnapshot.from_path(moved))
    result = resolve_analyses((defs, reordered))
    assert result.completeness == 'complete' and signature(result) == signature(original)
    assert [key.name for key in result.graph.nodes] == ['paid', 'REQ-B', 'REQ-A', 'MODEL-A']
    old_key = original.registries['requirement']['REQ-A'][0]
    new_key = result.registries['requirement']['REQ-A'][0]
    assert old_key.name == new_key.name
    assert old_key.source != new_key.source and old_key.ordinal != new_key.ordinal
    assert new_key.source.path == moved.resolve()
    assert_sources(result)


def test_resolver_does_no_file_io_and_produces_no_output(monkeypatch, capsys):
    local = manuscript(uses=['paid'])
    defs = definitions(variables={'paid': {'type': 'bool', 'role': 'input'}})
    def forbidden(*args, **kwargs):
        raise AssertionError('Resolver performed I/O')
    with monkeypatch.context() as patch:
        patch.setattr('builtins.open', forbidden)
        patch.setattr('io.open', forbidden)
        patch.setattr('os.open', forbidden)
        patch.setattr('socket.socket', forbidden)
        result = resolve_analyses((local, defs))
        assert result.completeness == 'complete'
    assert capsys.readouterr() == ('', '')
