"""Safe YAML capabilities, scalar policy and optional dependency boundary."""

import builtins

import pytest

from ._loader_helpers import EXAMPLES, load


@pytest.mark.parametrize('raw', [
    'version: 1\ntypes: {}\nvariables: {a: &shared {type: bool, role: input}}\nconstants: {}',
    'version: 1\ntypes: {}\nvariables: {a: *missing}\nconstants: {}',
    'version: 1\ntypes: {}\nvariables: {a: {<<: {type: bool}, role: input}}\nconstants: {}',
    'version: !!int 1\ntypes: {}\nvariables: {}\nconstants: {}',
    '!!python/object/apply:os.system ["never execute"]',
    'version: 1\ntypes: {}\nvariables: {}\nconstants: {}\n---\n{}',
    '%YAML 1.1\n---\nversion: 1\ntypes: {}\nvariables: {}\nconstants: {}',
])
def test_unsupported_yaml_rejects_whole_document(raw):
    result = load(raw, format='yaml')
    assert result.completeness == 'partial' and not result.nodes
    assert result.checks.structure.status == 'unsupported'
    assert result.checks.declarations.status == 'not-run'
    assert [d.code for d in result.diagnostics] == ['spec.unsupported-syntax']
    assert result.rejected[0].text == raw


def test_unsupported_fixture_and_syntax_error_are_distinct():
    result = load((EXAMPLES / 'model-contract/unsupported.yaml').read_text(), format='yaml')
    assert result.diagnostics[0].code == 'spec.unsupported-syntax'
    result = load('version: [unterminated', format='yaml')
    assert result.diagnostics[0].code == 'spec.invalid-definition'
    assert result.checks.structure.status == 'failed'


def test_yaml_duplicate_names_and_duplicate_record_fields_recover():
    result = load('''version: 1
types: {}
variables:
  item: {type: bool, role: input}
  item: {type: bool, role: output}
  bad: {type: bool, type: int, role: input}
constants: {}
''', format='yaml')
    assert [d.role for d in result.declarations] == ['input', 'output']
    assert len(result.rejected) == 1 and result.rejected[0].text.startswith('bad:')
    assert {d.code for d in result.diagnostics} == {'spec.invalid-definition', 'spec.duplicate-name'}
    assert all(d.related for d in result.diagnostics)


def test_yaml_scalar_policy_preserves_display_strings_and_json_values():
    result = load('''entries:
  - id: " id "
    kind: term
    yes_text: yes
    date_text: 2026-11-01
    hex_text: 0x10
    zero_text: 01
    true_text: "true"
    true_value: true
    false_value: false
    null_value: null
    omitted:
    decimal: -12
    float: 1.5e2
    block: |-
      first
      second
    folded: >-
      first
      second
    nested: [{"<<": "literal"}, [1, 2]]
''', kind='glossary', format='yaml')
    assert result.completeness == 'complete'
    entry = result.glossary[0]
    assert entry.key.name == ' id '
    data = dict(entry.data.items)
    assert [data[k] for k in ('yes_text', 'date_text', 'hex_text', 'zero_text', 'true_text')] == ['yes', '2026-11-01', '0x10', '01', 'true']
    assert data['true_value'] is True and data['false_value'] is False
    assert data['null_value'] is None and data['omitted'] is None
    assert data['decimal'] == -12 and data['float'] == 150.0
    assert data['block'] == 'first\nsecond'
    assert data['folded'] == 'first second'


@pytest.mark.parametrize('literal', ['yes', 'True', '"true"', '1'])
def test_yaml_does_not_guess_bool_constant(literal):
    result = load(f'version: 1\ntypes: {{}}\nvariables: {{}}\nconstants:\n  item: {{type: bool, value: {literal}}}', format='yaml')
    assert result.checks.declarations.status == 'failed' and not result.nodes


@pytest.mark.parametrize('literal', ['true', '01', '+1', '0x10', '1.0', '"1"'])
def test_yaml_requires_json_decimal_integer(literal):
    result = load(f'version: 1\ntypes: {{}}\nvariables: {{}}\nconstants:\n  item: {{type: int, min: 0, max: 10, value: {literal}}}', format='yaml')
    assert result.checks.declarations.status == 'failed' and not result.nodes


@pytest.mark.parametrize('raw', ['', 'entries: []', 'entries:\n - {id: a, kind: term, data: {1: wrong}}',
                                  'entries:\n - {id: a, kind: term, data: {? [x, y]: wrong}}'])
def test_yaml_empty_or_non_string_mapping_keys(raw):
    result = load(raw, kind='glossary', format='yml')
    assert result.completeness == ('complete' if raw == 'entries: []' else 'partial')


def test_missing_yaml_dependency_does_not_affect_json(monkeypatch):
    original = builtins.__import__

    def import_without_yaml(name, *args, **kwargs):
        if name == 'yaml':
            raise ModuleNotFoundError('simulated missing yaml')
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', import_without_yaml)
    json_result = load({'version': 1, 'types': {}, 'variables': {}, 'constants': {}})
    assert json_result.completeness == 'complete'
    result = load('version: 1', format='yaml')
    assert result.completeness == 'unavailable'
    assert result.checks.structure.status == 'unsupported'
    assert result.checks.declarations.status == 'not-run'
    assert [d.code for d in result.diagnostics] == ['spec.missing-dependency']
    assert result.diagnostics[0].evidence[0].message == 'PyYAML'
    assert result.diagnostics[0].primary.kind == 'unmapped'
    assert result.diagnostics[0].primary.span is None
    assert result.source.slice(result.diagnostics[0].related[0].location.span) == 'version: 1'
    assert result.rejected[0].text == 'version: 1'


def test_quoted_yaml_duplicate_keys_compare_decoded_values():
    result = load('version: 1\ntypes: {}\nvariables: {paid: {type: bool, role: input}, "pa\\u0069d": {type: bool, role: output}}\nconstants: {}', format='yaml')
    assert [d.key.name for d in result.declarations] == ['paid', 'paid']
    assert result.diagnostics[0].related


@pytest.mark.parametrize('raw', ['entries: [{id: "\\uD800", kind: term}]',
                                  'entries: [{id: a, kind: const, value: 1e999}]'])
def test_invalid_yaml_scalars_are_source_diagnostics(raw):
    result = load(raw, kind='glossary', format='yaml')
    assert result.completeness == 'partial' and not result.nodes
    assert result.diagnostics[0].code == 'spec.invalid-glossary'
