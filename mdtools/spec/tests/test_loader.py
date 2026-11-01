"""Definition fixture, shape, local declaration and recovery contracts."""

import pytest

from mdtools.core.source import SourceSnapshot
from mdtools.spec.loader import load_definitions
from ._loader_helpers import EXAMPLES, assert_provenance, document, load, meanings


def test_real_cancellation_and_model_contract_definitions():
    cancellation = load_definitions(SourceSnapshot.from_path(EXAMPLES / 'cancellation/definitions.json'),
                                    kind='spec', format='json')
    assert cancellation.completeness == 'complete'
    assert [d.key.name for d in cancellation.declarations] == ['paid', 'shipped', 'cancel_allowed', 'cancel_window_days']
    assert cancellation.declarations[-1].value == 14
    assert_provenance(cancellation)
    results = [load_definitions(SourceSnapshot.from_path(EXAMPLES / 'model-contract' / ('definitions.' + fmt)),
                                kind='spec', format=fmt) for fmt in ('json', 'yaml')]
    assert meanings(results[0]) == meanings(results[1])
    for result in results:
        assert result.completeness == 'complete'
        assert len(result.references) == 6
        assert_provenance(result)
    missing = load_definitions(SourceSnapshot.from_path(EXAMPLES / 'model-contract/missing-glossary.json'),
                               kind='spec', format='json')
    assert missing.completeness == 'complete' and not missing.diagnostics
    assert missing.references[-1][1].kind == 'glossary'


@pytest.mark.parametrize('raw', [[], None, {'version': True}, {'version': '1'}, {'version': 1.0},
                                  {'types': {}, 'variables': {}, 'constants': {}},
                                  document(types=[]), document(extra=1), {'version': 1}])
def test_invalid_document_shape(raw):
    result = load(raw)
    assert result.completeness == 'partial'
    assert result.checks.structure.status == 'failed'
    assert {d.code for d in result.diagnostics} == {'spec.invalid-definition'}
    assert result.rejected


def test_unknown_version_is_not_interpreted_as_v1():
    result = load({'version': 2, 'future': True, 'variables': {'okay': {'type': 'bool', 'role': 'input'}}})
    assert result.completeness == 'partial' and not result.nodes
    assert [d.code for d in result.diagnostics] == ['spec.unsupported-version']
    assert result.checks.structure.status == 'unsupported'
    assert result.checks.declarations.status == 'not-run'


@pytest.mark.parametrize('name,kind', [('bool', 'types'), ('int', 'variables'), ('true', 'constants'),
                                     ('and', 'variables'), ('bad-name', 'variables'), ('3Type', 'types')])
def test_invalid_or_reserved_names(name, kind):
    content = {'kind': 'enum', 'values': ['a']} if kind == 'types' else {'type': 'bool', 'value': True} if kind == 'constants' else {'type': 'bool', 'role': 'input'}
    result = load(document(**{kind: {name: content}}))
    assert not result.nodes and result.rejected
    assert result.checks.declarations.status == 'failed'


@pytest.mark.parametrize('kind,content', [
    ('types', {'kind': 'other', 'values': ['a']}),
    ('types', {'kind': 'enum', 'values': []}),
    ('types', {'kind': 'enum', 'values': ['a', 'a']}),
    ('types', {'kind': 'enum', 'values': ['', 1]}),
    ('variables', {'type': 'bool', 'role': 'other'}),
    ('variables', {'type': False, 'role': 'input'}),
    ('variables', {'type': 'bad type', 'role': 'input'}),
    ('variables', {'type': 'bool', 'role': 'input', 'min': 0}),
    ('variables', {'type': 'int', 'role': 'input', 'min': True, 'max': 2}),
    ('variables', {'type': 'int', 'role': 'input', 'min': 0, 'max': 1.0}),
    ('variables', {'type': 'int', 'role': 'input', 'min': 2, 'max': 1}),
    ('variables', {'type': 'int', 'role': 'input', 'max': 1}),
    ('constants', {'type': 'bool', 'value': 1}),
    ('constants', {'type': 'int', 'min': 0, 'max': 1, 'value': True}),
    ('constants', {'type': 'int', 'min': 0, 'max': 1, 'value': -1}),
    ('constants', {'type': 'int', 'min': 0, 'max': 1, 'value': 2}),
    ('constants', {'type': 'State', 'value': 1}),
    ('constants', {'type': 'State', 'value': None}),
    ('variables', {'type': 'bool', 'role': 'input', 'glossary': ''}),
])
def test_invalid_declaration_values(kind, content):
    result = load(document(**{kind: {'item': content}}))
    assert result.completeness == 'partial' and not result.nodes
    assert result.checks.declarations.status == 'failed'
    assert {d.code for d in result.diagnostics} == {'spec.invalid-definition'}
    assert len(result.rejected) == 1


@pytest.mark.parametrize('content', [None, {}, {'type': 'bool'}, {'type': 'bool', 'role': 'input', 'extra': 1}])
def test_bad_record_recovers_at_next_complete_declaration(content):
    result = load(document(variables={'broken': content, 'good': {'type': 'bool', 'role': 'output'}}))
    assert [key.name for key in result.nodes] == ['good']
    assert result.completeness == 'partial'
    assert result.checks.structure.status == 'failed'
    assert len(result.rejected) == 1


def test_integer_boundaries_named_type_deferred_and_source_order():
    result = load({'version': 1, 'constants': {
        'low': {'type': 'int', 'min': -2, 'max': 2, 'value': -2},
        'high': {'type': 'int', 'min': -2, 'max': 2, 'value': 2},
        'single': {'type': 'int', 'min': 0, 'max': 0, 'value': 0},
        'huge': {'type': 'int', 'min': -(2**100), 'max': 2**100, 'value': 2**100},
        'later': {'type': 'OtherFile', 'value': 'not-validated-yet'},
        'truth': {'type': 'bool', 'value': False},
    }, 'variables': {}, 'types': {'local': {'kind': 'enum', 'values': ['x']}}})
    assert result.completeness == 'complete'
    assert [d.key.name for d in result.declarations] == ['low', 'high', 'single', 'huge', 'later', 'truth', 'local']
    assert result.references[-2][1].name == 'OtherFile'


def test_duplicate_fixture_retains_both_candidates_and_both_locations():
    result = load_definitions(SourceSnapshot.from_path(EXAMPLES / 'model-contract/duplicate-definitions.json'),
                              kind='spec', format='json')
    assert [d.role for d in result.declarations] == ['input', 'output']
    assert [d.key.name for d in result.declarations] == ['duplicate', 'duplicate']
    assert len(set(d.key for d in result.declarations)) == 2
    assert result.completeness == 'partial'
    for diagnostic in result.diagnostics:
        assert diagnostic.related
        assert diagnostic.primary.span != diagnostic.related[0].location.span
    assert_provenance(result)


def test_duplicate_groups_and_cross_category_names_do_not_disappear():
    result = load('{"version":1,"types":{},"variables":{"same":{"type":"bool","role":"input"}},'
                  '"variables":{"same":{"type":"bool","role":"output"}},'
                  '"constants":{"same":{"type":"bool","value":true}}}')
    assert [d.kind for d in result.declarations] == ['variable', 'variable', 'constant']
    assert {d.code for d in result.diagnostics} == {'spec.invalid-definition', 'spec.duplicate-name'}


def test_escaped_duplicate_field_rejects_only_ambiguous_declaration():
    result = load(r'{"version":1,"types":{},"variables":{"bad":{"type":"bool","ty\u0070e":"int","role":"input"},"good":{"type":"bool","role":"output"}},"constants":{}}')
    assert [d.key.name for d in result.declarations] == ['good']
    assert 'ty\\u0070e' in result.rejected[0].text
    assert result.diagnostics[0].related


@pytest.mark.parametrize('raw', ['{"version":1,', '{"version":1,"version":2}', '{"version":NaN}',
                                  '{"version":1} trailing', r'{"version":1,"\ud800":null}'])
def test_broken_document_does_not_guess_a_recovery(raw):
    result = load(raw)
    assert not result.nodes and result.completeness == 'partial'
    assert result.rejected[0].text == raw


def test_api_misuse_is_not_a_source_diagnostic():
    with pytest.raises(TypeError):
        load_definitions('text', kind='spec', format='json')
    with pytest.raises(ValueError):
        load_definitions(SourceSnapshot('memory:bad', '{}'), kind='spec', format='toml')


def test_duplicate_keys_inside_unknown_fields_are_still_diagnosed():
    result = load('{"version":1,"types":{},"variables":{},"constants":{},"future":{"a":1,"a":2}}')
    assert len(result.diagnostics) == 2
    duplicate = next(d for d in result.diagnostics if d.related)
    assert result.source.slice(duplicate.primary.span) == '"a"'
    assert result.source.slice(duplicate.related[0].location.span) == '"a"'
    assert '"future"' in result.rejected[0].text


@pytest.mark.parametrize('raw', ['[' * 2000 + '0' + ']' * 2000, '{"version":' + '1' * 5000 + '}'])
def test_parser_capacity_is_unsupported_not_misreported_as_invalid(raw):
    result = load(raw)
    assert result.completeness == 'partial'
    assert [d.code for d in result.diagnostics] == ['spec.unsupported-syntax']
    assert result.checks.structure.status == 'unsupported'
    assert result.rejected[0].text == raw
