"""Wire schema, pure conversion, provenance, and incomplete-value rejection."""
from copy import deepcopy
from dataclasses import replace
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
    entry=ir.manifest.entries[-1]
    bad=replace(entry,state='read-error',source=None,reason='not read')
    with pytest.raises(ValueError):
        build_spec_ir(ir.resolved,replace(ir.manifest,entries=(*ir.manifest.entries[:-1],bad)),
                      report=ir.report,completeness='complete')


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
