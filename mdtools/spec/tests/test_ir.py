"""Wire schema, pure conversion, provenance, and incomplete-value rejection."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from mdtools.analysis import analyze_workspace
from mdtools.spec.ir import build_spec_ir, ir_to_dict, render_ir_json

REPO=Path(__file__).resolve().parents[3]


@pytest.fixture(scope='module')
def validator():
    base=REPO/'docs/spec'
    diagnostic=json.loads((base/'diagnostics-v1.schema.json').read_text())
    schema=json.loads((base/'spec-ir-v1.schema.json').read_text())
    Draft202012Validator.check_schema(schema)
    registry=Registry().with_resource('diagnostics-v1.schema.json',Resource.from_contents(diagnostic))
    return Draft202012Validator(schema,registry=registry)


@pytest.mark.parametrize('name',['cancellation','model-contract'])
def test_service_json_schema_and_snapshot_sources(validator,name):
    result=analyze_workspace(REPO/'docs/spec/examples'/name/'mdtools.toml')
    data=ir_to_dict(result.ir)
    validator.validate(data)
    assert json.loads(render_ir_json(result.ir))==data
    assert data['report']['schema_version']==1
    assert data['resolution']['scope']=='collected-inputs'
    assert all(c['status']=='not-run' and c['reason'] for m in data['models'] for c in m['checks'])
    assert data['nodes']==[dict(namespace=k.namespace,name=k.name,source=dict(uri=k.source.uri,snapshot=k.source.snapshot,path=str(k.source.path)),ordinal=k.ordinal) for k in result.resolved.graph.nodes]


def _expected_source(path):
    # Expected provenance comes from original bytes, not parser/IR values.
    return {'uri': path.as_uri(), 'snapshot': sha256(path.read_bytes()).hexdigest(), 'path': str(path)}


def _expected_key(path, namespace, name, ordinal=0):
    return {'namespace': namespace, 'name': name, 'source': _expected_source(path), 'ordinal': ordinal}


def test_service_json_preserves_bodies_model_links_and_expression_tokens():
    base = REPO / 'docs/spec/examples/model-contract'
    data = json.loads(render_ir_json(analyze_workspace(base / 'mdtools.toml').ir))
    assert data['completeness'] == 'complete'
    assert data['resolution']['completeness'] == 'complete'
    requirements = data['requirements']
    assert [r['key'] for r in requirements] == [
        _expected_key(base / 'normal.md', 'requirement', 'REQ-NORMAL'),
        _expected_key(base / 'natural-only.md', 'requirement', 'REQ-NATURAL'),
        _expected_key(base / 'multilingual.md', 'requirement', 'REQ-MULTILINGUAL'),
        _expected_key(base / 'unchecked.md', 'requirement', 'REQ-UNCHECKED'),
    ]
    assert [[(b['language'], b['text']) for b in r['bodies']] for r in requirements] == [
        [(None, '支払い済みなら処理を許可する。\n\n')],
        [(None, '利用者に処理状況を表示する。\n')],
        [('ja', '処理状況を表示する。📚\n'), ('en', 'Show the processing status.\n')],
        [(None, '式はM3で検査する。\n\n')],
    ]
    assert [r['formalization'] for r in requirements] == ['present', 'natural-only', 'natural-only', 'present']
    expected_models = [
        _expected_key(base / 'normal.md', 'model', 'MODEL-NORMAL', 1),
        _expected_key(base / 'unchecked.md', 'model', 'MODEL-UNCHECKED', 1),
    ]
    assert [requirements[0]['model'], requirements[3]['model']] == expected_models
    assert 'model' not in requirements[1] and 'model' not in requirements[2]
    assert [m['key'] for m in data['models']] == expected_models

    expected_expressions = [
        ('normal.md', [('when', 'paid', '"paid"', 10),
                       ('must', 'paid == true', '"paid == true"', 11)]),
        ('unchecked.md', [('when', 'paid and (', '"paid and ("', 10),
                          ('must', 'paid == true', '"\\u0070aid == true"', 11)]),
    ]
    for model, (filename, expressions) in zip(data['models'], expected_expressions, strict=True):
        path = base / filename
        for field, text, token, line in expressions:
            expression = model[field]
            assert expression['text'] == text
            assert expression['origin']['path'] == '/' + field
            # Columns cover the quoted source token, including any JSON escape.
            assert expression['origin']['location'] == {
                'kind': 'original',
                'span': {'source': _expected_source(path),
                         'start': {'line': line, 'column': 11},
                         'end': {'line': line, 'column': 11 + len(token)}},
            }
            assert path.read_text(encoding='utf-8').splitlines()[line - 1][10:10 + len(token)] == token


def test_service_json_preserves_builtins_and_nested_glossary_values(tmp_path):
    (tmp_path / 'doc.md').write_text('::: {.requirement #REQ-A spec-version=1}\n本文\n:::\n', encoding='utf-8')
    definitions = tmp_path / 'defs.json'
    definitions.write_text('''{
      "version": 1, "types": {}, "variables": {},
      "constants": {
        "disabled": {"type": "bool", "value": false},
        "zero": {"type": "int", "min": 0, "max": 2, "value": 0}
      }
    }''', encoding='utf-8')
    glossary = tmp_path / 'glossary.json'
    glossary.write_text('''{"entries": [{"id": "display", "kind": "term",
      "names": {"ja": "表示", "en": "Display"},
      "extra": {"nothing": null, "enabled": false, "count": 0, "label": "",
                "items": [null, false, 0, "", {"nested": ["値", [], {}]}]}
    }]}''', encoding='utf-8')
    config = tmp_path / 'mdtools.toml'
    config.write_text('version=1\n[[documents]]\nkind="markdown"\npath="doc.md"\n'
                      '[[definitions]]\nkind="spec"\npath="defs.json"\n'
                      '[[definitions]]\nkind="glossary"\npath="glossary.json"\n', encoding='utf-8')

    data = json.loads(render_ir_json(analyze_workspace(config).ir))

    assert data['completeness'] == 'complete'
    disabled = _expected_key(definitions, 'declaration', 'disabled')
    zero = _expected_key(definitions, 'declaration', 'zero', 1)
    display = _expected_key(glossary, 'glossary', 'display')
    assert data['nodes'] == [_expected_key(tmp_path / 'doc.md', 'requirement', 'REQ-A'), disabled, zero, display]
    assert [(e['owner'], e['reference']['kind'], e['reference']['name'], e['status'], e['builtin'], e['candidates'])
            for e in data['references']] == [
        (disabled, 'type', 'bool', 'resolved', 'bool', []),
        (zero, 'type', 'int', 'resolved', 'int', []),
    ]
    assert [(d['key'], d['value']) for d in data['declarations']] == [(disabled, False), (zero, 0)]
    assert [type(d['value']) for d in data['declarations']] == [bool, int]
    assert [(g['key'], g['kind'], g['data']) for g in data['glossary']] == [
        (display, 'term', {
            'names': {'ja': '表示', 'en': 'Display'},
            'extra': {'nothing': None, 'enabled': False, 'count': 0, 'label': '',
                      'items': [None, False, 0, '', {'nested': ['値', [], {}]}]},
        }),
    ]
    extra = data['glossary'][0]['data']['extra']
    assert type(extra['enabled']) is bool and type(extra['count']) is int
    assert [type(value) for value in extra['items']] == [type(None), bool, int, str, dict]


def test_service_json_preserves_all_ambiguous_occurrences_and_candidate_order(tmp_path):
    # Registration order differs from filename order; two occurrences share a snapshot.
    (tmp_path / 'z-first.md').write_text(
        '::: {.requirement #REQ-DUP spec-version=1}\nfirst\n:::\n'
        '::: {.requirement #REQ-DUP spec-version=1}\nsecond\n:::\n', encoding='utf-8')
    (tmp_path / 'a-second.md').write_text(
        '::: {.requirement #REQ-DUP spec-version=1}\nthird\n:::\n', encoding='utf-8')
    (tmp_path / 'ref.md').write_text(
        '::: {.requirement #REQ-REF spec-version=1 refs="REQ-DUP"}\nreference\n:::\n', encoding='utf-8')
    config = tmp_path / 'mdtools.toml'
    config.write_text('version=1\n' + ''.join(
        f'[[documents]]\nkind="markdown"\npath="{name}"\n'
        for name in ('z-first.md', 'a-second.md', 'ref.md')), encoding='utf-8')

    data = json.loads(render_ir_json(analyze_workspace(config).ir))

    assert data['completeness'] == data['resolution']['completeness'] == 'partial'
    candidates = [
        _expected_key(tmp_path / 'z-first.md', 'requirement', 'REQ-DUP'),
        _expected_key(tmp_path / 'z-first.md', 'requirement', 'REQ-DUP', 1),
        _expected_key(tmp_path / 'a-second.md', 'requirement', 'REQ-DUP'),
    ]
    owner = _expected_key(tmp_path / 'ref.md', 'requirement', 'REQ-REF')
    assert data['nodes'] == [*candidates, owner]
    assert [r['key'] for r in data['requirements']] == [*candidates, owner]
    assert [[(b['language'], b['text']) for b in r['bodies']] for r in data['requirements']] == [
        [(None, 'first\n')], [(None, 'second\n')], [(None, 'third\n')], [(None, 'reference\n')],
    ]
    edge, = data['references']
    assert edge['owner'] == owner
    assert edge['reference']['kind'] == 'refs' and edge['reference']['name'] == 'REQ-DUP'
    assert edge['status'] == 'ambiguous'
    assert edge['candidates'] == candidates
    assert 'builtin' not in edge


@pytest.mark.parametrize('path,value',[
    (('schema_version',),2),
    (('contract','version'),False),
    (('completeness',),'valid'),
    (('nodes',0,'ordinal'),-1),
    (('nodes',0,'source','snapshot'),'a'*64+'\n'),
    (('models',0,'checks',0,'status'),'passed'),
    (('manifest','consistency'),'atomic'),
    (('references',0,'status'),'success'),
    (('report','schema_version'),2),
])
def test_schema_rejects_bad_values(validator,path,value):
    data=ir_to_dict(analyze_workspace(REPO/'docs/spec/examples/cancellation/mdtools.toml').ir)
    item=data
    for key in path[:-1]: item=item[key]
    item[path[-1]]=value
    with pytest.raises(ValidationError): validator.validate(data)


def test_pure_serialization_no_io_and_fresh_values(monkeypatch):
    ir=analyze_workspace(REPO/'docs/spec/examples/model-contract/mdtools.toml').ir
    expected=render_ir_json(ir)
    def forbidden(*a,**k): raise AssertionError('unexpected I/O')
    monkeypatch.setattr(Path,'read_bytes',forbidden)
    monkeypatch.setattr(Path,'read_text',forbidden)
    data=ir_to_dict(ir); data['requirements'].clear()
    assert render_ir_json(ir)==expected


def test_complete_constructor_rejects_missing_registered_input():
    ir=analyze_workspace(REPO/'docs/spec/examples/cancellation/mdtools.toml').ir
    for index in (0, len(ir.manifest.entries)-1):
        entries=list(ir.manifest.entries)
        entries[index]=replace(entries[index],state='read-error',source=None,reason='not read')
        with pytest.raises(ValueError):
            build_spec_ir(ir.resolved,replace(ir.manifest,entries=tuple(entries)),
                          report=ir.report,completeness='complete')
    with pytest.raises(ValueError):
        build_spec_ir(ir.resolved,ir.manifest,report=ir.report,completeness='partial')


def test_committed_generated_example(validator):
    import runpy
    base=REPO/'docs/spec/examples/model-contract'
    expected=runpy.run_path(str(base/'ir-example.py'))['example_json']()
    assert (base/'spec-ir-v1.json').read_text()==expected
    validator.validate(json.loads(expected))


def test_partial_and_unavailable_schema(validator,tmp_path,monkeypatch):
    from mdtools.tests.test_analysis import project
    from mdtools.core.source import SourceSnapshot
    config=project(tmp_path,'::: {.requirement #BAD spec-version=2}\nunknown\n:::\n')
    validator.validate(ir_to_dict(analyze_workspace(config).ir))
    original=SourceSnapshot.from_path
    def fail(path):
        if path.name=='doc.md': raise PermissionError('unreadable')
        return original(path)
    monkeypatch.setattr(SourceSnapshot,'from_path',fail)
    result=analyze_workspace(config)
    assert result.completeness=='unavailable'
    validator.validate(ir_to_dict(result.ir))
