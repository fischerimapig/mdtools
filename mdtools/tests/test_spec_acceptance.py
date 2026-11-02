"""M2 acceptance: original files -> real service -> process CLI; no producer mocks."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from jsonschema import Draft202012Validator

from mdtools.analysis import analyze_workspace
from mdtools.core.diagnostics import report_to_dict
from mdtools.spec.ir import ir_to_dict
from mdtools.spec.tests.test_ir import validator  # Reuse the public-schema fixture.

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / 'docs/spec/examples'


def cli(config, command='index', name=None, *, code=0, format='json', bare=False):
    args = [sys.executable, *(['-E', '-S'] if bare else []), '-c',
            'from mdtools.main import main; main()', 'spec', command]
    if name is not None:
        args.append(name)
    p = subprocess.run([*args, '--project', str(config), '--format', format],
                       cwd=REPO, capture_output=True, text=True, timeout=15)
    assert p.returncode == code, p.stderr + p.stdout
    assert p.stderr == ''
    assert p.stdout.endswith('\n')
    return (json.loads(p.stdout) if format == 'json' else p.stdout), p.stdout


@pytest.fixture
def workspace(tmp_path):
    for name in ('m2-acceptance', 'model-contract'):
        shutil.copytree(EXAMPLES / name, tmp_path / name)
    return tmp_path / 'm2-acceptance/mdtools.toml'


def source(path):
    return dict(uri=path.as_uri(), path=str(path), snapshot=sha256(path.read_bytes()).hexdigest())


def key(path, namespace, name, ordinal=0):
    return dict(namespace=namespace, name=name, source=source(path), ordinal=ordinal)


def wire_schemas(data, validator):
    # Schema conformance is separate from the literal content assertions below.
    Draft202012Validator(json.loads((REPO / 'docs/spec/diagnostics-v1.schema.json').read_text())).validate(data['report'])
    if data['command'] == 'index' and data['result'] is not None:
        validator.validate(data['result'])


def not_run(checks):
    assert {c['check_id']: c['status'] for c in checks if c['check_id'] in (
        'spec.expression-syntax', 'spec.expression-types', 'spec.expression-uses', 'spec.logic')} == {
        'spec.expression-syntax': 'not-run', 'spec.expression-types': 'not-run',
        'spec.expression-uses': 'not-run', 'spec.logic': 'not-run'}
    assert all(c.get('reason') for c in checks if c['status'] == 'not-run')


def test_originals_service_cli_content_and_determinism(workspace, validator):
    root = workspace.parent.parent
    sections = workspace.parent / 'manual_sections'
    (workspace.parent / 'unused.md').write_text('::: {.requirement #REQ-UNUSED spec-version=1}\nunused\n:::\n')
    a = analyze_workspace(workspace)
    data, raw = cli(workspace)
    assert cli(workspace)[1] == raw
    assert data['status'] == 'complete'
    assert data['result'] == ir_to_dict(a.ir)
    assert data['report'] == report_to_dict(a.report)
    ir = data['result']
    expected = [key(sections/'section.md', 'requirement', 'REQ-SECTION'),
                key(sections/'detail.md', 'requirement', 'REQ-DETAIL'),
                key(root/'model-contract/normal.md', 'requirement', 'REQ-NORMAL')]
    assert [r['key'] for r in ir['requirements']] == expected
    assert [[(b['language'], b['text']) for b in r['bodies']] for r in ir['requirements']] == [
        [('ja', '状態を表示する。📚\n'), ('en', 'Show the state.\n')],
        [(None, '利用者へ案内する。\n')], [(None, '支払い済みなら処理を許可する。\n\n')]]
    assert [r['formalization'] for r in ir['requirements']] == ['present', 'natural-only', 'present']
    model = ir['models'][0]
    assert ir['requirements'][0]['model'] == key(sections/'section.md', 'model', 'MODEL-SECTION', 1)
    assert [u['name'] for u in model['uses']] == ['paid', 'initial']
    assert (model['when']['text'], model['must']['text']) == ('paid', 'initial == "new"')
    assert ir['requirements'][0]['bodies'][0]['span'] == dict(
        source=source(sections/'section.md'), start=dict(line=3,column=1), end=dict(line=4,column=1))
    # Every registered original has one acquisition; canonical/generated/unused are absent.
    assert [(e['role'], Path(e['path']).relative_to(root).as_posix()) for e in ir['manifest']['entries']] == [
        ('workspace','m2-acceptance/mdtools.toml'), ('hierarchy','m2-acceptance/manual_sections/hierarchy.json'),
        ('body','m2-acceptance/examples.md'), ('body','m2-acceptance/manual_sections/intro.md'),
        ('body','m2-acceptance/manual_sections/section.md'), ('body','m2-acceptance/manual_sections/detail.md'),
        ('body','model-contract/normal.md'), ('spec','model-contract/definitions.json'), ('glossary','model-contract/glossary.json')]
    assert len(a.report.sources) == 9
    for s in a.report.sources:
        assert s.ref.snapshot == sha256(s.path.read_bytes()).hexdigest()
    assert [(e['owner']['name'], e['reference']['name'], e['status'], [k['name'] for k in e['candidates']])
            for e in ir['references'] if e['reference']['kind'] == 'refs'] == [
        ('REQ-SECTION','REQ-DETAIL','resolved',['REQ-DETAIL']),
        ('REQ-DETAIL','REQ-DETAIL','resolved',['REQ-DETAIL']),
        ('REQ-DETAIL','REQ-SECTION','resolved',['REQ-SECTION'])]
    detail, _ = cli(workspace, 'show', 'REQ-SECTION')
    assert [r['key'] for r in detail['result']['requirements']] == expected[:1]
    assert [d['key']['name'] for d in detail['result']['declarations']] == ['OrderState','paid','initial']
    assert [g['key']['name'] for g in detail['result']['glossary']] == ['paid label','order-state']
    assert detail['result']['declarations'][-1]['value'] == 'new'
    text, _ = cli(workspace, 'show', 'REQ-SECTION', format='text')
    assert '状態を表示する。📚' in text and 'Show the state.' in text
    assert 'spec.logic status=not-run' in text
    not_run(data['report']['checks'])
    not_run(model['checks'])
    wire_schemas(data, validator)
    wire_schemas(detail, validator)


@pytest.mark.parametrize('bad', [None, 'json', 'duplicate', 'unclosed', 'version', 'reserved'])
def test_zero_requirements_and_rejected_syntax(workspace, bad, validator):
    if bad is None:
        body = (workspace.parent/'examples.md').read_text()
    else:
        models = {'json':'{', 'duplicate':'{"version":1,"version":1}', 'reserved':'{}'}
        body = ('::: {.requirement #REQ-BAD spec-version='+('2' if bad == 'version' else '1')+'}\n本文\n')
        if bad in models:
            body += '```mdspec'+(' extra' if bad == 'reserved' else '')+'\n'+models[bad]+'\n```\n'
        if bad != 'unclosed':
            body += ':::\n'
    (workspace.parent/'only.md').write_text(body)
    workspace.write_text('version=1\n[[documents]]\nkind="markdown"\npath="only.md"\n')
    data, raw = cli(workspace, code=1 if bad else 0)
    assert cli(workspace, code=1 if bad else 0)[1] == raw
    assert data['status'] == ('partial' if bad else 'complete')
    ir = data['result']
    if bad:
        assert data['report']['diagnostics']
        expected_code = {'json': 'spec.invalid-model', 'duplicate': 'spec.invalid-model',
                         'unclosed': 'spec.invalid-requirement', 'version': 'spec.unsupported-version',
                         'reserved': 'spec.invalid-model'}[bad]
        assert expected_code in {d['code'] for d in data['report']['diagnostics']}
        if bad == 'unclosed':
            assert ir['requirements'][0]['structure']['status'] == 'failed'
            assert ir['requirements'][0]['bodies'][0]['text'] == '本文\n'
        else:
            assert ir['rejected']
        assert all(r['text'] in body for r in ir['rejected'])
        if bad == 'json':
            assert [r['text'] for r in ir['rejected']] == ['```mdspec\n{\n```\n']
        assert all(d['primary']['span']['source'] == source(workspace.parent/'only.md') for d in data['report']['diagnostics'])
    else:
        assert ir['requirements'] == ir['models'] == ir['rejected'] == []
        assert data['report']['diagnostics'] == []
    wire_schemas(data, validator)


def test_collisions_undefined_and_show_global_failure(workspace, validator):
    root = workspace.parent.parent
    duplicate = root/'model-contract/duplicate.md'
    duplicate.write_text('::: {.requirement #REQ-NORMAL spec-version=1 refs="REQ-NORMAL ABSENT"}\n重複\n```mdspec\n{"version":1,"id":"MODEL-DUP","kind":"constraint","uses":["paid","missing"],"when":"true","must":"true"}\n```\n:::\n')
    defs = root/'model-contract/second.json'
    defs.write_text('{"version":1,"types":{},"variables":{"paid":{"type":"MissingType","role":"output","glossary":"missing label"}},"constants":{}}')
    workspace.write_text(workspace.read_text()+'\n[[documents]]\nkind="markdown"\npath="model-contract/duplicate.md"\n[[definitions]]\nkind="spec"\npath="model-contract/second.json"\n')
    data, raw = cli(workspace, code=1)
    assert cli(workspace, code=1)[1] == raw
    ir = data['result']
    assert data['status'] == 'partial'
    candidates = [key(root/'model-contract/normal.md','requirement','REQ-NORMAL'),key(duplicate,'requirement','REQ-NORMAL')]
    edge = next(e for e in ir['references'] if e['reference']['name'] == 'REQ-NORMAL')
    assert edge['status'] == 'ambiguous' and edge['candidates'] == candidates
    paid = [d for d in ir['declarations'] if d['key']['name'] == 'paid']
    assert [d['role'] for d in paid] == ['input','output']
    assert next(e for e in ir['references'] if e['reference']['name']=='paid')['candidates'] == [
        key(root/'model-contract/definitions.json','declaration','paid',1),key(defs,'declaration','paid')]
    assert {(e['reference']['kind'], e['reference']['name']) for e in ir['references'] if e['status']=='undefined'} == {
        ('refs','ABSENT'),('uses','missing'),('type','MissingType'),('glossary','missing label')}
    diagnostics = data['report']['diagnostics']
    for code, primary, related in (
        ('spec.duplicate-id', duplicate, root/'model-contract/normal.md'),
        ('spec.duplicate-name', defs, root/'model-contract/definitions.json')):
        d = next(d for d in diagnostics if d['code']==code)
        assert d['primary']['kind']=='original' and d['related']
        assert d['primary']['span']['source'] == source(primary)
        assert any(r['location']['span']['source'] == source(related) for r in d['related'])
        assert all(r['location']['kind']=='original' for r in d['related'])
    selected, _ = cli(workspace, 'show','REQ-DETAIL',code=1)
    assert selected['status']=='partial' and selected['report']==data['report']
    assert [r['key']['name'] for r in selected['result']['requirements']]==['REQ-DETAIL']
    text, _ = cli(workspace,'show','REQ-DETAIL',code=1,format='text')
    assert 'spec.duplicate-name' in text and '"partial"' in text
    wire_schemas(data, validator)


def test_move_heading_and_registration_order(workspace):
    before, _ = cli(workspace)
    sections = workspace.parent/'manual_sections'
    old = sections/'section.md'; moved = sections/'moved.md'
    old.rename(moved)
    hpath = sections/'hierarchy.json'
    h = json.loads(hpath.read_text()); children = h['sections'][0]['children']
    children[0].update(file='moved.md',title='変更した見出し',order=2)
    hpath.write_text(json.dumps(h,ensure_ascii=False))
    moved_only, _ = cli(workspace)
    assert moved_only['result']['requirements'][-1]['key']['name']=='REQ-NORMAL'
    moved_req = next(r for r in moved_only['result']['requirements'] if r['key']['name']=='REQ-SECTION')
    assert moved_req['key']['source']==source(moved)
    assert moved_req['key']['source']['snapshot']==before['result']['requirements'][0]['key']['source']['snapshot']
    moved.write_text('追加説明\n'+moved.read_text())
    text=workspace.read_text()
    block='[[documents]]\nkind = "markdown"\npath = "model-contract/normal.md"\n'
    workspace.write_text(text.replace(block,'').replace('[[documents]]',block+'\n[[documents]]',1))
    after, _ = cli(workspace)
    assert [r['key']['name'] for r in after['result']['requirements']]==['REQ-NORMAL','REQ-DETAIL','REQ-SECTION']
    req=after['result']['requirements'][-1]
    assert req['bodies'][0]['span']['start']==dict(line=4,column=1)
    assert req['key']['source']==source(moved)
    assert req['key']['source']['snapshot']!=moved_req['key']['source']['snapshot']
    semantic=lambda ir: sorted((e['owner']['name'],e['reference']['kind'],e['reference']['name'],tuple(k['name'] for k in e['candidates'])) for e in ir['references'])
    assert semantic(before['result'])==semantic(after['result'])
    for name in ('mdtools.toml','hierarchy.json'):
        find=lambda data: next(e['source']['snapshot'] for e in data['result']['manifest']['entries'] if Path(e['path']).name==name)
        assert find(before)!=find(after)


def test_cancellation_handoff(validator):
    config=EXAMPLES/'cancellation/mdtools.toml'
    data,_=cli(config)
    models=data['result']['models']
    assert [(m['key']['name'],m['when']['text'],m['must']['text'],[u['name'] for u in m['uses']]) for m in models]==[
        ('MODEL-CANCEL-ALLOW','paid and not shipped','cancel_allowed == true',['paid','shipped','cancel_allowed']),
        ('MODEL-CANCEL-DENY','paid','cancel_allowed == false',['paid','cancel_allowed'])]
    for m,file,line in zip(models,('cancel-allow.md','cancel-deny.md'),(19,13),strict=True):
        assert m['must']['origin']['location']['span']['source']==source(config.parent/file)
        assert m['must']['origin']['location']['span']['start']==dict(line=line,column=11)
        not_run(m['checks'])
    assert [(d['key']['name'],d.get('role'),d.get('value')) for d in data['result']['declarations']]==[
        ('paid','input',None),('shipped','input',None),('cancel_allowed','output',None),('cancel_window_days',None,14)]
    not_run(data['report']['checks'])
    wire_schemas(data,validator)


def test_real_yaml_presence_and_absence(workspace, validator):
    normal,_=cli(workspace,bare=True)
    assert normal['status']=='complete'
    workspace.write_text(workspace.read_text().replace('definitions.json','definitions.yaml'))
    installed,_=cli(workspace)
    assert installed['status']=='complete'
    assert [(d['key']['name'],d.get('value')) for d in installed['result']['declarations']]==[
        ('OrderState',None),('paid',None),('window',14),('initial','new')]
    missing,_=cli(workspace,code=5,bare=True)
    assert missing['status']=='partial'
    assert [r['key']['name'] for r in missing['result']['requirements']]==['REQ-SECTION','REQ-DETAIL','REQ-NORMAL']
    assert any(d['code']=='spec.missing-dependency' and 'PyYAML' in str(d) for d in missing['report']['diagnostics'])
    assert missing['result']['rejected']
    selected,_=cli(workspace,'show','REQ-DETAIL',code=5,bare=True)
    assert selected['report']==missing['report']
    wire_schemas(missing,validator)
