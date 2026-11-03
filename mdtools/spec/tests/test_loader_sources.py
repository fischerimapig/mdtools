"""Original bytes, token provenance, failure reports and Workspace selection."""

from hashlib import sha256
import json

import pytest
from jsonschema import Draft202012Validator

from mdtools.core.diagnostics import render_json
from mdtools.core.source import SourceSnapshot
from mdtools.diagnostics import DefinitionReadError, read_definition_source
from mdtools.spec.loader import load_definitions
from mdtools.workspace import load_workspace
from ._loader_helpers import EXAMPLES, assert_provenance, document, load


@pytest.mark.parametrize('newline', ['\n', '\r\n', '\r'])
def test_json_unicode_escape_and_original_bytes(tmp_path, newline):
    raw = r'''{
  "version": 1,
  "types": {"State": {"kind":"enum","values":["日本語📚é","a\nb"]}},
  "variables": {"pa\u0069d": {"type":"\u0062ool","role":"input","glossary":"支払\u3044📚"}},
  "constants": {"value": {"type":"State","value":"a\nb"}}
}'''.replace('\n', newline)
    path = tmp_path / 'defs.json'
    path.write_bytes(raw.encode())
    source = read_definition_source(path)
    result = load_definitions(source, kind='spec', format='json')
    assert result.completeness == 'complete'
    assert source.text == raw and source.ref.snapshot == sha256(path.read_bytes()).hexdigest()
    assert source.path == path.resolve()
    paid = result.declarations[1]
    assert paid.key.name == 'paid' and paid.type_ref.name == 'bool' and paid.glossary.name == '支払い📚'
    fields = {field.path: field for field in paid.fields}
    for pointer, expected in [('/name', r'"pa\u0069d"'), ('/type', r'"\u0062ool"'),
                              ('/glossary', r'"支払\u3044📚"')]:
        assert source.slice(fields[pointer].location.span) == expected
    value = next(field for field in result.declarations[2].fields if field.path == '/value')
    assert source.slice(value.location.span) == r'"a\nb"'
    assert result.declarations[2].value == 'a\nb'
    assert_provenance(result)


@pytest.mark.parametrize('newline', ['\n', '\r\n', '\r'])
def test_yaml_quoted_and_block_scalar_source_tokens(newline):
    raw = '''entries:
  - id: "日本語📚"
    kind: term
    description:
      ja: |-
        一行目é
        二行目
      en: "line\\nnext"
'''.replace('\n', newline)
    result = load(raw, kind='glossary', format='yaml')
    assert result.completeness == 'complete'
    fields = {field.path: field for field in result.glossary[0].fields}
    block = result.source.slice(fields['/description/ja'].location.span)
    assert block.startswith('|-' + newline)
    assert '一行目é' in block and '二行目' in block
    assert result.source.slice(fields['/description/en'].location.span) == '"line\\nnext"'
    description = dict(dict(result.glossary[0].data.items)['description'].items)
    assert description == {'ja': '一行目é\n二行目', 'en': 'line\nnext'}


def test_json_pointer_escaping_and_nested_display_value_sources():
    result = load({'entries': [{'id': 'id', 'kind': 'term', 'a/b~c': {'ja': ['値📚']}}]}, kind='glossary')
    field = next(f for f in result.glossary[0].fields if f.path == '/a~1b~0c/ja/0')
    assert result.source.slice(field.location.span) == '"値📚"'


def test_workspace_registration_selects_definitions_without_scanning(tmp_path):
    (tmp_path / 'body.md').write_text('ordinary body')
    (tmp_path / 'defs.json').write_text(json.dumps(document(variables={'registered': {'type': 'bool', 'role': 'input'}})))
    (tmp_path / 'unregistered.json').write_text('invalid and must never be read')
    (tmp_path / 'canonical.md').write_text('invalid and must never be parsed')
    config = tmp_path / 'mdtools.toml'
    config.write_text('version = 1\ngenerated = ["canonical.md"]\n[[documents]]\nkind="markdown"\npath="body.md"\n[[definitions]]\nkind="spec"\npath="defs.json"\n')
    workspace = load_workspace(config)
    results = [load_definitions(read_definition_source(item.path), kind=item.kind, format=item.path.suffix[1:])
               for item in workspace.definitions]
    assert len(results) == 1 and results[0].completeness == 'complete'
    assert [d.key.name for d in results[0].declarations] == ['registered']
    for example in ('cancellation', 'model-contract'):
        workspace = load_workspace(EXAMPLES / example / 'mdtools.toml')
        results = [load_definitions(read_definition_source(item.path), kind=item.kind, format=item.path.suffix[1:])
                   for item in workspace.definitions]
        assert all(result.completeness == 'complete' for result in results)
        assert [result.source.path for result in results] == [item.path for item in workspace.definitions]


@pytest.mark.parametrize('failure', ['missing', 'invalid-utf8', 'directory'])
def test_read_failure_has_report_without_fake_snapshot(tmp_path, failure):
    path = tmp_path / 'source.json'
    if failure == 'invalid-utf8':
        path.write_bytes(b'\xff\xfe')
    elif failure == 'directory':
        path.mkdir()
    with pytest.raises(DefinitionReadError) as caught:
        read_definition_source(path)
    report = caught.value.report
    assert not report.sources
    assert report.diagnostics[0].code == 'spec.read-error'
    assert report.diagnostics[0].category == 'tool-error'
    assert report.diagnostics[0].primary.kind == 'none'
    assert report.diagnostics[0].evidence[0].message == str(path)
    assert report.checks[0].status == 'error'
    assert all(check.status == 'not-run' and check.reason for check in report.checks[1:])
    assert len(json.loads(render_json(report))['checks']) == 7


def test_structural_failure_keeps_valid_siblings_and_explicit_check_scope():
    result = load(document(variables={'bad': {}, 'good': {'type': 'bool', 'role': 'input'}}))
    assert result.checks.structure.status == 'failed'
    assert result.checks.declarations.status == 'passed'
    assert result.completeness == 'partial'
    assert [node.name for node in result.nodes] == ['good']
    assert_provenance(result)


def test_reports_conform_to_existing_common_diagnostic_schema(tmp_path, capsys):
    schema = json.loads((EXAMPLES.parent / 'diagnostics-v1.schema.json').read_text())
    validator = Draft202012Validator(schema)
    for result in (load(document()), load({'version': 2}), load('not JSON')):
        validator.validate(json.loads(render_json(result.report)))
    with pytest.raises(DefinitionReadError) as caught:
        read_definition_source(tmp_path / 'missing.json')
    validator.validate(json.loads(render_json(caught.value.report)))
    assert capsys.readouterr() == ('', '')
