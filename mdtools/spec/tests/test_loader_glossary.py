"""Display data preservation, glossary duplicates and legacy CLI compatibility."""

import json

import pytest

from glossary.cli import main
from glossary.loader import load as legacy_load
from mdtools.core.source import SourceSnapshot
from mdtools.spec.loader import load_definitions
from mdtools.spec.model import JsonObject
from ._loader_helpers import EXAMPLES, assert_provenance, load


def test_real_glossary_keeps_id_kind_and_display_data():
    result = load_definitions(SourceSnapshot.from_path(EXAMPLES / 'model-contract/glossary.json'),
                              kind='glossary', format='json')
    assert result.completeness == 'complete'
    assert [(entry.key.name, entry.kind) for entry in result.glossary] == [('paid label', 'term'), ('order-state', 'symbol')]
    names = dict(result.glossary[0].data.items)['names']
    assert dict(names.items) == {'ja': '支払い済み', 'en': 'Paid'}
    assert_provenance(result)


def test_arbitrary_glossary_display_data_is_not_spec_typed():
    result = load({'entries': [{'id': '  ', 'kind': 'const', 'value': '1 + 2', 'extra': [None, True, 1.25, {}],
                                 'names': {'ja': '値', 'en': 'Value'}}]}, kind='glossary')
    assert result.completeness == 'complete'
    assert dict(result.glossary[0].data.items)['value'] == '1 + 2'
    assert dict(result.glossary[0].data.items)['extra'] == (None, True, 1.25, JsonObject())
    assert not result.references and not result.declarations


@pytest.mark.parametrize('raw', ['{}', '{"entries":{}}', '{"entries":[],"unknown":1}',
                                  '{"entries":[1]}', '{"entries":[{"kind":"term"}]}',
                                  '{"entries":[{"id":"","kind":"term"}]}',
                                  '{"entries":[{"id":"a","kind":"other"}]}',
                                  '{"entries":[{"id":"a","kind":"term","names":{"en":"one","en":"two"}}]}'])
def test_invalid_glossary_has_diagnostic_and_raw_rejection(raw):
    result = load(raw, kind='glossary')
    assert result.completeness == 'partial' and not result.nodes
    assert result.checks.structure.status == 'failed'
    assert {d.code for d in result.diagnostics} == {'spec.invalid-glossary'}
    assert result.rejected


def test_glossary_duplicate_ids_and_bad_entry_recovery():
    result = load('{"entries":[{"id":"a","kind":"term","value":"first"},'
                  '{"id":"bad","id":"ambiguous","kind":"term"},'
                  '{"id":"a","kind":"symbol","value":"last"}]}', kind='glossary')
    assert [(entry.key.name, entry.kind) for entry in result.glossary] == [('a', 'term'), ('a', 'symbol')]
    assert len(result.rejected) == 1
    assert result.completeness == 'partial'
    assert {d.code for d in result.diagnostics} == {'spec.invalid-glossary', 'spec.duplicate-glossary'}
    assert all(d.related for d in result.diagnostics)


def test_json_yaml_glossary_equivalence_and_yaml_duplicates():
    raw = {'entries': [{'id': ' id ', 'kind': 'const', 'value': '2 + 2', 'extra': [None, True, 1.5]},
                       {'id': ' id ', 'kind': 'term', 'names': {'ja': '値'}}]}
    yaml = 'entries:\n - {id: " id ", kind: const, value: "2 + 2", extra: [null, true, 1.5]}\n - {id: " id ", kind: term, names: {ja: 値}}'
    results = [load(raw, kind='glossary'), load(yaml, kind='glossary', format='yaml')]
    assert [(e.key.name, e.kind, e.data) for e in results[0].glossary] == [(e.key.name, e.kind, e.data) for e in results[1].glossary]
    assert all(result.completeness == 'partial' and result.diagnostics[0].code == 'spec.duplicate-glossary'
               for result in results)
    duplicate = load('entries:\n - {id: a, kind: term, names: {ja: 一, ja: 二}}\n - {id: good, kind: term}',
                     kind='glossary', format='yaml')
    assert [node.name for node in duplicate.nodes] == ['good']
    assert duplicate.diagnostics[0].code == 'spec.invalid-glossary'
    assert duplicate.diagnostics[0].related and duplicate.rejected


def test_legacy_cli_overrides_warning_display_and_exit_codes_stay_compatible(tmp_path, capsys):
    paths = [tmp_path / 'first.json', tmp_path / 'second.json']
    for path, value in zip(paths, ('First', 'Last')):
        path.write_text(json.dumps({'entries': [{'id': 'same', 'kind': 'term', 'names': {'en': value}}]}))
    assert legacy_load(paths)['same'].data['names']['en'] == 'Last'
    assert 'overrides earlier definition' in capsys.readouterr().err
    assert main(['list', '-f', str(paths[0]), '-f', str(paths[1]), '--format', 'json']) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)[0]['names']['en'] == 'Last'
    assert 'overrides earlier definition' in captured.err
    paths[1].write_text('{"entries":[{"id":"same","kind":"term","names":{"en":"first","en":"last"}}]}')
    assert main(['list', '-f', str(paths[1]), '--format', 'json']) == 0
    assert json.loads(capsys.readouterr().out)[0]['names']['en'] == 'last'
    strict = load_definitions(SourceSnapshot.from_path(paths[1]), kind='glossary', format='json')
    assert strict.completeness == 'partial' and not strict.glossary
