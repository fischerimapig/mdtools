"""Dependency direction, slice-only projection and explicit failure boundaries."""
import ast
from pathlib import Path
import subprocess
import sys

import pytest

from mdtools.core.source import SourceSnapshot
from experiments.document_parser import parser
from experiments.document_parser.model import Limits
from experiments.document_parser.projection import summary_dict

ROOT = Path(__file__).resolve().parents[3]
PROTOTYPE = ROOT / 'experiments/document_parser'


def imports(path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ''


def test_dependency_direction():
    """Prevent prototype imports of spec/Workspace/CLI/external parsers and production imports of experiments."""
    allowed = sys.stdlib_module_names
    local = {p.stem for p in PROTOTYPE.glob('*.py')}
    for path in PROTOTYPE.glob('*.py'):
        for module in imports(path):
            assert (module.split('.')[0] in allowed or module in local
                    or module in {'mdtools.core.source','mdtools.core.pandoc'}), (path,module)
    for package in ('mdtools','mdsplit','langfilter','mdhtml_rewrite','glossary'):
        for path in (ROOT/package).rglob('*.py'):
            assert not any(module == 'experiments' or module.startswith('experiments.') for module in imports(path)), path


def test_python_without_site_packages():
    """Run the parsing/projection entry under python -S to expose accidental installed parser dependencies."""
    script = '''
import sys
from mdtools.core.source import SourceSnapshot
from experiments.document_parser.parser import parse_document
from experiments.document_parser.projection import summary_dict
result = summary_dict(parse_document(SourceSnapshot('memory:isolated', 'ordinary text')))
assert result['status'] == 'complete' and result['candidates'] == []
assert not any(name.startswith('mdtools.spec') for name in sys.modules)
'''
    completed = subprocess.run([sys.executable,'-S','-c',script], cwd=ROOT, capture_output=True,text=True)
    assert completed.returncode == 0, completed.stderr


def test_projection_only_reads_owned_slices():
    """Project multilingual and model candidates without access to source.text or a scanner."""
    document = parser.parse_document(SourceSnapshot('memory:guard',
        '::: {.requirement #REQ-X spec-version=1}\n::: {lang=ja}\n本文\n:::\n```mdspec\n{}\n```\n:::\n'))
    class SliceOnlyDocument:
        def __init__(self):
            self.blocks = document.blocks
            self.status = document.status
            self.calls = []
        def slice(self, span):
            self.calls.append(span)
            return document.slice(span)
        def __getattr__(self, name):
            raise AssertionError('Projection escaped structure/slice facade: '+name)
    facade = SliceOnlyDocument()
    result = summary_dict(facade)
    assert result['candidates'][0]['id'] == 'REQ-X'
    assert result['candidates'][0]['bodies'][0]['text'] == '本文\n'
    assert result['candidates'][0]['mdspec'][0]['direct'] is True
    assert facade.calls
    assert set(imports(PROTOTYPE/'projection.py')) <= {'__future__','dataclasses','model'}
    tree = ast.parse((PROTOTYPE/'projection.py').read_text())
    assert not any(isinstance(node,ast.Attribute)
                   and isinstance(node.value,ast.Name)
                   and node.value.id == 'document'
                   and node.attr in {'text','source','index'}
                   for node in ast.walk(tree))


@pytest.mark.parametrize('text', ['', 'ordinary text\n'])
def test_successful_zero_candidates(text):
    """Accept true empty/ordinary zero-candidate input only as complete recognized structure."""
    document = parser.parse_document(SourceSnapshot('memory:zero',text))
    assert document.status == 'complete'
    assert all(item.state == 'recognized' for item in document.coverage)
    assert summary_dict(document)['candidates'] == []


@pytest.mark.parametrize('mode', ['profile','bytes','nodes','inline','engine'])
def test_incomplete_zero_is_explicit(mode,monkeypatch):
    """Keep rejected, limited and engine-failed zero results distinct from successful absence."""
    source = SourceSnapshot('memory:failure', 'ordinary text\n\nmore text\n')
    kwargs = {}
    if mode == 'profile':
        kwargs['profile'] = 'unknown'
    elif mode == 'bytes':
        kwargs['limits'] = Limits(max_bytes=1)
    elif mode == 'nodes':
        kwargs['limits'] = Limits(max_nodes=1)
    elif mode == 'inline':
        kwargs['limits'] = Limits(max_inline_chars=1)
    else:
        def broken(*args):
            raise RuntimeError('sentinel engine failure')
        monkeypatch.setattr(parser,'parse_blocks',broken)
    document = parser.parse_document(source,**kwargs)
    assert document.source is source
    assert document.status == {'profile':'rejected','bytes':'rejected','nodes':'partial','inline':'partial','engine':'failed'}[mode]
    assert document.notices
    assert any(c.state == 'unparsed' for c in document.coverage)
    if mode == 'engine':
        assert 'sentinel engine failure' in document.notices[-1].message
    result = summary_dict(document)
    assert result['status'] == document.status
    assert result['candidates'] == []
    assert set(result['semantic_checks'].values()) == {'not-run'}
