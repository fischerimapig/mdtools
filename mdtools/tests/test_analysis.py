"""Actual service integration, I/O failures, snapshot consistency and identity."""
from hashlib import sha256
from pathlib import Path
import json
import os

import pytest

from mdtools.analysis import analyze_workspace
from mdtools.core.source import SourceSnapshot
from mdtools.spec.ir import ir_to_dict, render_ir_json

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / 'docs/spec/examples'


def project(root, body='::: {.requirement #REQ-A spec-version=1}\n日本語😀\n:::\n', defs=None):
    (root / 'doc.md').write_bytes(body.encode())
    config = root / 'mdtools.toml'
    config.write_text('version=1\n[[documents]]\nkind="markdown"\npath="doc.md"\n' +
                      ('[[definitions]]\nkind="spec"\npath="defs.json"\n' if defs else ''))
    if defs:
        (root / 'defs.json').write_text(defs)
    return config


@pytest.mark.parametrize('name,count', [('cancellation',3),('model-contract',4)])
def test_real_service_ir_and_determinism(name,count,capsys):
    config = EXAMPLES / name / 'mdtools.toml'
    a,b = analyze_workspace(config),analyze_workspace(config)
    assert a.completeness == 'complete'
    assert len(a.ir.resolved.inputs) == len(a.inputs)
    data = ir_to_dict(a.ir)
    assert len(data['requirements']) == count
    assert render_ir_json(a.ir) == render_ir_json(b.ir)
    assert all(c.status == 'not-run' and c.reason for c in a.resolved.checks.expressions)
    for source in a.report.sources:
        assert source.ref.snapshot == sha256(source.path.read_bytes()).hexdigest()
    for local in a.inputs:
        for r in local.requirements:
            for body in r.bodies:
                assert local.source.slice(body.span) == body.text
    assert all(e.state in ('read','analyzed') for e in a.manifest.entries)
    assert capsys.readouterr() == ('','')


@pytest.mark.parametrize('file', ['invalid.md','broken-model.md','unsupported.md'])
def test_recovery_and_unknown_version_keep_rejected(tmp_path,file):
    result = analyze_workspace(project(tmp_path,(EXAMPLES/'model-contract'/file).read_text()))
    assert result.completeness == 'partial'
    assert ir_to_dict(result.ir)['rejected']


@pytest.mark.parametrize('failure', ['io','utf8','execution'])
def test_failed_registered_input_cannot_hide_behind_complete_resolver(tmp_path,monkeypatch,failure):
    config = project(tmp_path,defs='{"version":1,"types":{},"variables":{},"constants":{}}')
    original = SourceSnapshot.from_path
    def read(path):
        if path.name == 'defs.json':
            if failure == 'io': raise PermissionError('denied')
            if failure == 'utf8': raise UnicodeError('invalid UTF-8')
        return original(path)
    monkeypatch.setattr(SourceSnapshot,'from_path',read)
    if failure == 'execution':
        monkeypatch.setattr('mdtools.analysis.load_definitions',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('failed')))
    result = analyze_workspace(config)
    assert result.resolved.completeness == 'complete'
    assert result.completeness == 'partial'
    assert result.ir.completeness == 'partial'
    assert len(result.inputs) == 1
    assert next(c for c in result.report.checks if c.check_id == 'spec.references').status == 'unknown'
    assert result.manifest.entries[-1].state == ('analysis-error' if failure == 'execution' else 'read-error')
    if failure != 'execution': assert result.manifest.entries[-1].source is None


@pytest.mark.parametrize('raw', [b'version=2',b'bad toml',b'\xff'])
def test_selection_failure_distinguishes_encoding(tmp_path,raw):
    config=tmp_path/'mdtools.toml';config.write_bytes(raw)
    result=analyze_workspace(config)
    assert result.completeness == 'unavailable' and result.ir is None
    if raw == b'\xff':
        assert not result.report.sources
        assert result.report.diagnostics[0].code == 'spec.read-error'
    else: assert result.report.diagnostics[0].code.startswith('workspace.')


@pytest.mark.parametrize('alias', ['workspace.md', 'symlink.md', 'hardlink.md'])
@pytest.mark.parametrize('role,code', [
    ('body', 'workspace.duplicate-input'),
    ('generated', 'workspace.generated-input'),
])
def test_config_alias_registration_returns_unavailable_with_one_snapshot(tmp_path, alias, role, code):
    config = tmp_path / 'workspace.md'
    text = ('version=1\n' + (f'generated=["{alias}"]\n' if role == 'generated' else '')
            + '[[documents]]\nkind="markdown"\n'
            + f'path="{alias if role == "body" else "doc.md"}"\n')
    config.write_text(text, encoding='utf-8')
    (tmp_path / 'doc.md').write_text('本文\n', encoding='utf-8')
    (tmp_path / 'symlink.md').symlink_to(config)
    os.link(config, tmp_path / 'hardlink.md')

    result = analyze_workspace(config)

    assert result.completeness == 'unavailable'
    assert result.workspace is result.resolved is result.ir is None
    assert result.inputs == ()
    diagnostic, = result.report.diagnostics
    assert (diagnostic.code, diagnostic.category, diagnostic.severity) == (code, 'user', 'error')
    checks = {c.check_id: c for c in result.report.checks}
    assert checks['workspace.sources'].status == 'failed'
    for name in ('spec.structure', 'spec.declarations', 'spec.references'):
        assert checks[name].status == 'not-run'
        assert checks[name].reason == 'Workspace selection did not complete'
    snapshot, = result.report.sources
    assert snapshot.path == config
    assert snapshot.text == text
    assert snapshot.ref.snapshot == sha256(text.encode('utf-8')).hexdigest()
    entry, = result.manifest.entries
    assert (entry.role, entry.path, entry.state, entry.source) == ('workspace', config, 'read', snapshot.ref)


def test_config_and_hierarchy_are_the_snapshots_used_for_selection(tmp_path,monkeypatch):
    config=project(tmp_path)
    hierarchy=tmp_path/'hierarchy.json'
    hierarchy.write_text(json.dumps({'sections':[{'title':'A','file':'doc.md','order':0}]}))
    config.write_text('version=1\n[[documents]]\nkind="hierarchy"\npath="hierarchy.json"\ncanonical="out.md"\n')
    old={p:p.read_bytes() for p in (config,hierarchy)}
    original=SourceSnapshot.from_path
    def read(path):
        source=original(path)
        if path in old: path.write_text('changed after read')
        return source
    monkeypatch.setattr(SourceSnapshot,'from_path',read)
    result=analyze_workspace(config)
    assert result.completeness == 'complete'
    assert [r.key.name for i in result.inputs for r in i.requirements] == ['REQ-A']
    for e in result.manifest.entries[:2]:
        assert e.source.snapshot == sha256(old[e.path]).hexdigest()
    assert len(result.report.sources)==3


def test_missing_yaml_dependency_mixed_with_good_input(tmp_path,monkeypatch):
    config=project(tmp_path)
    (tmp_path/'defs.yaml').write_text('version: 1\ntypes: {}\nvariables: {}\nconstants: {}\n')
    config.write_text(config.read_text()+'[[definitions]]\nkind="spec"\npath="defs.yaml"\n')
    import builtins
    original=builtins.__import__
    def blocked(name,*a,**k):
        if name=='yaml': raise ImportError('no yaml')
        return original(name,*a,**k)
    monkeypatch.setattr(builtins,'__import__',blocked)
    result=analyze_workspace(config)
    assert result.completeness=='partial'
    assert result.inputs[-1].completeness=='unavailable'
    assert result.inputs[-1].rejected
    assert any(d.code=='spec.missing-dependency' for d in result.report.diagnostics)


def test_order_move_heading_and_unregistered_files(tmp_path):
    config=project(tmp_path)
    a=analyze_workspace(config)
    (tmp_path/'unused.md').write_text('::: {.requirement #NO spec-version=1}\nNo\n:::\n')
    (tmp_path/'doc.md').rename(tmp_path/'moved.md')
    config.write_text(config.read_text().replace('doc.md','moved.md'))
    (tmp_path/'moved.md').write_text('# New heading\n'+(tmp_path/'moved.md').read_text())
    b=analyze_workspace(config)
    ar,br=a.inputs[0].requirements[0],b.inputs[0].requirements[0]
    assert ar.key.name==br.key.name and ar.key.source!=br.key.source
    assert len(b.ir.resolved.graph.nodes)==1


@pytest.mark.parametrize('refs,defs,code',[
 ('REQ-MISSING',None,'spec.undefined-reference'),
 ('paid','{"version":1,"types":{},"variables":{"paid":{"type":"bool","role":"input"}},"constants":{}}','spec.wrong-reference-kind'),
 ('REQ-A',None,'spec.ambiguous-reference'),
])
def test_bad_references_never_complete(tmp_path,refs,defs,code):
    body=f'::: {{.requirement #REQ-A spec-version=1 refs="{refs}"}}\n本文\n:::\n'
    if code=='spec.ambiguous-reference': body+='::: {.requirement #REQ-A spec-version=1}\n重複\n:::\n'
    result=analyze_workspace(project(tmp_path,body,defs))
    assert result.completeness=='partial'
    assert any(d.code==code for d in result.report.diagnostics)
    if code=='spec.ambiguous-reference':
        assert len(result.resolved.graph.nodes)==2
        assert len(result.resolved.graph.edges[0].candidates)==2


@pytest.mark.parametrize('newline',['\n','\r\n','\r'])
def test_unicode_escapes_and_original_coordinates(tmp_path,newline):
    raw='::: {.requirement #REQ-A spec-version=1}\n本文😀 é\n```mdspec\n{"version":1,"id":"MODEL-A","kind":"constraint","uses":[],"when":"\\u0061 + )","must":"true"}\n```\n:::\n'
    result=analyze_workspace(project(tmp_path,raw.replace('\n',newline)))
    assert result.completeness=='complete'
    local=result.inputs[0]; model=local.requirements[0].model
    assert model.when.text=='a + )'
    assert local.source.slice(model.when.origin.location.span)=='"\\u0061 + )"'
    assert all(c.status=='not-run' for c in model.checks)


def test_resolver_failure_retains_actual_locals_without_ir(tmp_path,monkeypatch):
    monkeypatch.setattr('mdtools.analysis.resolve_analyses',lambda *a: (_ for _ in ()).throw(RuntimeError('resolver failed')))
    result=analyze_workspace(project(tmp_path))
    assert result.inputs and result.ir is None and result.resolved is None
    assert result.completeness=='partial'
    assert any(d.code=='spec.execution-error' for d in result.report.diagnostics)


def test_document_order_changes_presentation_but_keeps_semantic_ids(tmp_path):
    config=project(tmp_path)
    (tmp_path/'second.md').write_text('::: {.requirement #REQ-B spec-version=1}\nB\n:::\n')
    first='[[documents]]\nkind="markdown"\npath="doc.md"\n'
    second='[[documents]]\nkind="markdown"\npath="second.md"\n'
    config.write_text('version=1\n'+first+second)
    a=analyze_workspace(config)
    config.write_text('version=1\n'+second+first)
    b=analyze_workspace(config)
    assert [k.name for k in a.resolved.graph.nodes]==['REQ-A','REQ-B']
    assert [k.name for k in b.resolved.graph.nodes]==['REQ-B','REQ-A']
    assert set(a.resolved.graph.nodes)==set(b.resolved.graph.nodes)
    assert a.manifest.entries[0].source!=b.manifest.entries[0].source


def test_actual_invalid_utf8_body_has_no_snapshot(tmp_path):
    config=project(tmp_path)
    (tmp_path/'doc.md').write_bytes(b'\xff')
    result=analyze_workspace(config)
    assert result.completeness=='unavailable'
    assert result.inputs==()
    assert len(result.report.sources)==1  # config only
    assert result.manifest.entries[-1].source is None
    assert result.report.diagnostics[0].category=='tool-error'
