"""CLI contracts through the real service, including whole-workspace failures."""
import json
from hashlib import sha256
from pathlib import Path
import subprocess
import sys

import pytest

from mdtools.analysis import analyze_workspace
from mdtools.core.diagnostics import render_text, report_to_dict
from mdtools.core.source import SourceSnapshot
from mdtools.main import main
from mdtools.spec.ir import ir_to_dict
from mdtools.tests.test_analysis import project

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / 'docs/spec/examples'


def invoke(capsys, argv, code=0):
    with pytest.raises(SystemExit) as exc:
        main(['spec', *argv])
    assert exc.value.code == code
    out, err = capsys.readouterr()
    assert err == ''
    assert out.endswith('\n')
    return json.loads(out)


@pytest.mark.parametrize('command', ['index', 'show'])
def test_real_service_once_and_api_identity(command, monkeypatch, capsys):
    import mdtools.spec_cli as cli
    original = cli.analyze_workspace
    calls = []
    def analyze(path):
        calls.append(path)
        return original(path)
    monkeypatch.setattr(cli, 'analyze_workspace', analyze)
    config = EXAMPLES / 'model-contract/mdtools.toml'
    args = [command] + (['REQ-NORMAL'] if command == 'show' else [])
    data = invoke(capsys, [*args, '--project', str(config), '--format', 'json'])
    assert calls == [str(config)]
    api = analyze_workspace(config)
    assert data['report'] == report_to_dict(api.report)
    assert data['schema_version'] == 1 and data['status'] == 'complete'
    if command == 'index':
        assert set(data) == {'schema_version', 'command', 'status', 'exit_code', 'result', 'report'}
        assert data['result'] == ir_to_dict(api.ir)
    else:
        assert data['query'] == {'requirement_id': 'REQ-NORMAL'}
        result = data['result']
        req, = result['requirements']
        assert req['bodies'][0]['text'] == '支払い済みなら処理を許可する。\n\n'
        assert req['status'] == 'active'
        assert req['key']['source']['snapshot'] == sha256((config.parent/'normal.md').read_bytes()).hexdigest()
        model, = result['models']
        assert model['when']['text'] == 'paid'
        assert model['must']['text'] == 'paid == true'
        assert [d['key']['name'] for d in result['declarations']] == ['paid']
        assert [g['key']['name'] for g in result['glossary']] == ['paid label']
        assert [(e['reference']['kind'], e['reference']['name'], e['status']) for e in result['references']] == [
            ('uses', 'paid', 'resolved'), ('type', 'bool', 'resolved'), ('glossary', 'paid label', 'resolved')]
        assert all(c['status'] == 'not-run' and c['reason'] for c in model['checks'])


@pytest.mark.parametrize('argv', [[], ['wat'], ['index'], ['show', '--project', 'missing'],
    ['index', '--project', 'missing', '--format', 'yaml'],
    ['show', 'bad id', '--project', 'missing'], ['show', '_bad', '--project', 'missing'],
    ['show', 'REQ-A', 'REQ-B', '--project', 'missing']])
def test_argument_errors_precede_analysis(argv, capsys, monkeypatch):
    def forbidden(*a):
        pytest.fail('arguments must be validated before analysis')
    monkeypatch.setattr('mdtools.spec_cli.analyze_workspace', forbidden)
    with pytest.raises(SystemExit) as exc:
        main(['spec', *argv])
    assert exc.value.code == 2
    out, err = capsys.readouterr()
    assert out == '' and err.startswith('usage: mdtools spec') and 'error:' in err


@pytest.mark.parametrize('args', [[], ['index'], ['show']])
def test_help(args, capsys):
    with pytest.raises(SystemExit) as exc:
        main(['spec', *args, '--help'])
    assert exc.value.code == 0
    out, err = capsys.readouterr()
    assert err == '' and 'usage: mdtools spec' in out and 'README 原典:' in out


@pytest.mark.parametrize('name', ['REQ-MISSING', 'MODEL-NORMAL', 'OrderState'])
def test_unknown_and_other_namespaces(name, capsys):
    data = invoke(capsys, ['show', name, '--project', str(EXAMPLES/'model-contract/mdtools.toml'), '--format', 'json'], 3)
    assert data['status'] == 'complete' and data['result'] is None
    assert data['query'] == {'requirement_id': name}
    diagnostic, = data['report']['diagnostics']
    assert diagnostic['code'] == 'spec.unknown-id' and diagnostic['primary'] == {'kind': 'none'}
    assert diagnostic['requirement_id'] == name
    assert all(c['status'] == 'passed' for c in data['report']['checks'] if c['check_id'] in ('spec.structure','spec.declarations','spec.references'))


@pytest.mark.parametrize('raw,code,diagnostic', [
    (b'bad toml', 1, 'workspace.invalid-config'), (b'version=2', 1, 'workspace.unsupported-version'),
    (b'\xff', 4, 'spec.read-error')])
def test_selection_failures(raw, code, diagnostic, tmp_path, capsys):
    config = tmp_path/'mdtools.toml'; config.write_bytes(raw)
    data = invoke(capsys, ['show', 'REQ-A', '--project', str(config), '--format', 'json'], code)
    assert data['result'] is None and data['status'] == 'unavailable'
    assert data['query']['requirement_id'] == 'REQ-A'
    assert [d['code'] for d in data['report']['diagnostics']] == [diagnostic]
    assert all(c['status'] == 'not-run' and c['reason'] for c in data['report']['checks'] if c['check_id'].startswith('spec.'))


@pytest.mark.parametrize('file', ['invalid.md', 'broken-model.md', 'unsupported.md'])
@pytest.mark.parametrize('command', ['index', 'show'])
def test_invalid_originals_keep_partial(file, command, tmp_path, capsys):
    config = project(tmp_path, (EXAMPLES/'model-contract'/file).read_text())
    name = 'REQ-RECOVER' if file == 'invalid.md' else 'REQ-BROKEN'
    # Select the retained requirement if present, so a broken model is not lost.
    api = analyze_workspace(config)
    if api.inputs[0].requirements:
        name = api.inputs[0].requirements[0].key.name
    args = [command] + ([name] if command == 'show' else [])
    data = invoke(capsys, [*args, '--project', str(config), '--format', 'json'], 1)
    assert data['status'] == 'partial'
    assert data['report']['diagnostics']
    if command == 'index' or file == 'broken-model.md':
        assert data['result']['rejected']
    if command == 'show' and file == 'broken-model.md':
        req, = data['result']['requirements']
        assert req['formalization'] == 'present' and req['structure']['status'] == 'failed'


@pytest.mark.parametrize('failure', ['io', 'utf8', 'execution', 'dependency', 'invalid', 'combined'])
@pytest.mark.parametrize('name', ['REQ-A', 'REQ-ABSENT'])
def test_whole_workspace_failure_priority(failure, name, tmp_path, monkeypatch, capsys):
    config = project(tmp_path)
    (tmp_path/'defs.yaml').write_text('version: 1\ntypes: {}\nvariables: {}\nconstants: {}\n')
    config.write_text(config.read_text() + '[[definitions]]\nkind="spec"\npath="defs.yaml"\n')
    if failure in ('dependency', 'combined'):
        import builtins
        original_import = builtins.__import__
        def blocked(module, *a, **kw):
            if module == 'yaml':
                raise ImportError('PyYAML unavailable')
            return original_import(module, *a, **kw)
        monkeypatch.setattr(builtins, '__import__', blocked)
    if failure in ('io', 'utf8', 'combined'):
        original_read = SourceSnapshot.from_path
        def read(path):
            if path.name == ('doc.md' if failure == 'combined' else 'defs.yaml'):
                raise (UnicodeError('invalid UTF-8') if failure == 'utf8' else PermissionError('denied'))
            return original_read(path)
        monkeypatch.setattr(SourceSnapshot, 'from_path', read)
    if failure == 'execution':
        def broken(*a, **kw):
            raise RuntimeError('loader failed')
        monkeypatch.setattr('mdtools.analysis.load_definitions', broken)
    if failure in ('invalid', 'combined'):
        (tmp_path/'bad.md').write_text('::: {.requirement spec-version=1}\nbad\n:::\n')
        config.write_text(config.read_text() + '[[documents]]\nkind="markdown"\npath="bad.md"\n')
    code = 5 if failure == 'dependency' else 1 if failure == 'invalid' else 4
    data = invoke(capsys, ['show', name, '--project', str(config), '--format', 'json'], code)
    assert data['status'] in ('partial', 'unavailable')
    if failure != 'combined' and name == 'REQ-A':
        assert data['result']['requirements'][0]['bodies'][0]['text'] == '日本語😀\n'
    if name == 'REQ-ABSENT':
        assert data['result'] is None
    assert data['report']['diagnostics']
    if failure == 'combined':
        codes = {d['code'] for d in data['report']['diagnostics']}
        assert {'spec.read-error', 'spec.missing-dependency', 'spec.invalid-requirement'} <= codes


def test_dependency_precedes_invalid_and_unknown(tmp_path, monkeypatch, capsys):
    config = project(tmp_path, '::: {.requirement spec-version=1}\nbad\n:::\n')
    (tmp_path/'defs.yaml').write_text('version: 1\n')
    config.write_text(config.read_text()+'[[definitions]]\nkind="spec"\npath="defs.yaml"\n')
    import builtins
    original = builtins.__import__
    def blocked(name, *a, **kw):
        if name == 'yaml': raise ImportError('no yaml')
        return original(name, *a, **kw)
    monkeypatch.setattr(builtins, '__import__', blocked)
    data = invoke(capsys, ['show', 'REQ-A', '--project', str(config), '--format', 'json'], 5)
    assert data['status'] == 'partial'


def test_type_closure_and_cyclic_refs(tmp_path, capsys):
    raw = '''::: {.requirement #REQ-A spec-version=1 refs="REQ-B"}
A
```mdspec
{"version":1,"id":"MODEL-A","kind":"constraint","uses":["initial"],"when":"true","must":"true"}
```
:::
::: {.requirement #REQ-B spec-version=1 refs="REQ-A"}
B must not be expanded
:::
'''
    config = project(tmp_path, raw, (EXAMPLES/'model-contract/definitions.json').read_text())
    (tmp_path/'glossary.json').write_text((EXAMPLES/'model-contract/glossary.json').read_text())
    config.write_text(config.read_text()+'[[definitions]]\nkind="glossary"\npath="glossary.json"\n')
    data = invoke(capsys, ['show','REQ-A','--project',str(config),'--format','json'])
    result = data['result']
    assert [r['key']['name'] for r in result['requirements']] == ['REQ-A']
    assert [d['key']['name'] for d in result['declarations']] == ['OrderState', 'initial']
    assert [g['key']['name'] for g in result['glossary']] == ['order-state']
    assert result['references'][0]['candidates'][0]['name'] == 'REQ-B'
    assert result['declarations'][1]['value'] == 'new'
    assert result['declarations'][0]['values'] == ['new', 'paid']


def test_collisions_preserve_occurrences_and_candidates(tmp_path, capsys):
    raw = ('::: {.requirement #REQ-A spec-version=1 refs="REQ-A"}\nfirst\n:::\n'
           '::: {.requirement #REQ-A spec-version=1}\nsecond\n:::\n')
    config = project(tmp_path, raw)
    data = invoke(capsys, ['show','REQ-A','--project',str(config),'--format','json'], 1)
    reqs = data['result']['requirements']
    assert [r['bodies'][0]['text'] for r in reqs] == ['first\n', 'second\n']
    edge, = data['result']['references']
    assert edge['status'] == 'ambiguous'
    assert edge['candidates'] == [r['key'] for r in reqs]
    assert [k['ordinal'] for k in edge['candidates']] == [0, 1]
    assert data['status'] == 'partial'


@pytest.mark.parametrize('name,body', [('REQ-MULTILINGUAL','Show the processing status.'), ('REQ-NATURAL','利用者に処理状況を表示する。'), ('REQ-UNCHECKED','paid and (')])
def test_text_preserves_content_and_whole_report(name, body, capsys):
    config = EXAMPLES/'model-contract/mdtools.toml'
    with pytest.raises(SystemExit) as exc:
        main(['spec','show',name,'--project',str(config)])
    assert exc.value.code == 0
    out, err = capsys.readouterr()
    assert err == '' and body in out and name in out
    assert render_text(analyze_workspace(config).report) in out
    assert 'spec.logic status=not-run' in out and 'source' in out
    if name == 'REQ-NATURAL': assert 'natural-only' in out
    if name == 'REQ-MULTILINGUAL': assert '処理状況を表示する。📚' in out


def test_text_glossary_keys_preserve_path_boundaries(tmp_path, capsys):
    config = project(tmp_path)
    payload = {
        'a.b': 'flat', 'a': {'b': 'nested'}, 'line\nbreak': 'newline',
        '': 'empty', 'quote"\\': 'quoted', '[0]': 'key', 'items': ['item'],
        '0': 'numeric', '日本語': 'unicode', 'Normal_09': 'ordinary',
        '_name': 'underscore', 'a-b': 'hyphen',
    }
    (tmp_path/'glossary.json').write_text(json.dumps({
        'entries': [{'id': 'label', 'kind': 'term', **payload}],
    }), encoding='utf-8')
    config.write_text(config.read_text()+'[[definitions]]\nkind="glossary"\npath="glossary.json"\n')

    data = invoke(capsys, ['index', '--project', str(config), '--format', 'json'])
    assert data['status'] == 'complete' and data['exit_code'] == 0
    assert data['result']['glossary'][0]['data'] == payload

    with pytest.raises(SystemExit) as exc:
        main(['spec', 'index', '--project', str(config), '--format', 'text'])
    assert exc.value.code == 0
    out, err = capsys.readouterr()
    assert err == ''
    assert [line for line in out.splitlines() if line.startswith('result.glossary.[0].data.')] == [
        'result.glossary.[0].data.["a.b"] = "flat"',
        'result.glossary.[0].data.a.b = "nested"',
        r'result.glossary.[0].data.["line\nbreak"] = "newline"',
        'result.glossary.[0].data.[""] = "empty"',
        r'result.glossary.[0].data.["quote\"\\"] = "quoted"',
        'result.glossary.[0].data.["[0]"] = "key"',
        'result.glossary.[0].data.items.[0] = "item"',
        'result.glossary.[0].data.["0"] = "numeric"',
        'result.glossary.[0].data.["日本語"] = "unicode"',
        'result.glossary.[0].data.Normal_09 = "ordinary"',
        'result.glossary.[0].data._name = "underscore"',
        'result.glossary.[0].data.["a-b"] = "hyphen"',
    ]


def test_standard_library_only_dispatch():
    script = 'from mdtools.main import main; main()'
    process = subprocess.run([sys.executable, '-S', '-c', script, 'spec','index','--project',str(EXAMPLES/'model-contract/mdtools.toml'),'--format','json'], cwd=REPO, capture_output=True, text=True)
    assert process.returncode == 0 and process.stderr == ''
    assert json.loads(process.stdout)['status'] == 'complete'


def test_ambiguous_uses_keeps_all_declaration_candidates(tmp_path, capsys):
    raw = '::: {.requirement #REQ-A spec-version=1}\nA\n```mdspec\n{"version":1,"id":"MODEL-A","kind":"constraint","uses":["paid"],"when":"paid","must":"true"}\n```\n:::\n'
    config = project(tmp_path, raw, '{"version":1,"types":{},"variables":{"paid":{"type":"bool","role":"input"}},"constants":{}}')
    (tmp_path/'second.json').write_text('{"version":1,"types":{},"variables":{"paid":{"type":"int","min":0,"max":4,"role":"output"}},"constants":{}}')
    config.write_text(config.read_text()+'[[definitions]]\nkind="spec"\npath="second.json"\n')
    data = invoke(capsys, ['show','REQ-A','--project',str(config),'--format','json'], 1)
    result = data['result']
    assert [(d['key']['name'], d['role'], d['type_ref']['name']) for d in result['declarations']] == [('paid','input','bool'),('paid','output','int')]
    edge = result['references'][0]
    assert edge['status'] == 'ambiguous'
    assert edge['candidates'] == [d['key'] for d in result['declarations']]
    assert [e['builtin'] for e in result['references'][1:]] == ['bool', 'int']


def test_adapter_failure_keeps_completed_analysis_and_query(monkeypatch, capsys):
    def broken(*a):
        raise RuntimeError('conversion failed')
    monkeypatch.setattr('mdtools.spec_cli.ir_to_dict', broken)
    data = invoke(capsys, ['show','REQ-NORMAL','--project',str(EXAMPLES/'model-contract/mdtools.toml'),'--format','json'], 4)
    assert data['status'] == 'complete' and data['result'] is None
    assert data['query'] == {'requirement_id':'REQ-NORMAL'}
    assert data['report']['sources']
    diagnostic, = data['report']['diagnostics']
    assert diagnostic['code'] == 'spec.execution-error' and diagnostic['category'] == 'tool-error'


def test_text_index_partial_retains_rejected_and_global_diagnostic(tmp_path, capsys):
    config = project(tmp_path, (EXAMPLES/'model-contract/broken-model.md').read_text())
    with pytest.raises(SystemExit) as exc:
        main(['spec','index','--project',str(config)])
    assert exc.value.code == 1
    out, err = capsys.readouterr()
    assert err == ''
    assert '"partial"' in out and 'result.rejected.' in out
    assert 'formalization = "present"' in out
    assert render_text(analyze_workspace(config).report) in out
