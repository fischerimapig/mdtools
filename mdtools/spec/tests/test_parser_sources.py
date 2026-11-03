"""Original snapshots, multilingual fragments and Workspace selection."""

from hashlib import sha256
import json
import pytest
from mdtools.core.source import SourceSnapshot
from mdtools.core.source import SourcePosition
from mdtools.spec.parser import parse_requirements
from mdtools.workspace import load_workspace
from mdtools.workspace import snapshot_sources

from mdtools.spec.tests._parser_helpers import (
    MODEL, parse, fence, requirement, assert_provenance,
)


@pytest.mark.parametrize('newline', ['\n', '\r\n', '\r'])
def test_file_snapshot_unicode_escapes_and_every_field_are_exact(tmp_path, newline):
    model = {**MODEL, 'when': '日本語📚é\npaid', 'must': 'paid\t== true'}
    raw_json = json.dumps(model, ensure_ascii=False).replace('"paid"', '"\\u0070aid"')
    raw = requirement('説明📚é\n' + fence(raw_json)).replace('\n', newline)
    path = tmp_path / '日本語.md'
    path.write_bytes(raw.encode('utf-8'))
    source = SourceSnapshot.from_path(path)
    result = parse_requirements(source)
    assert result.completeness == 'complete'
    assert source.ref.path == path and source.ref.uri == path.as_uri()
    assert source.ref.snapshot == sha256(path.read_bytes()).hexdigest()
    req, = result.requirements
    assert req.bodies[0].text == '説明📚é' + newline
    assert req.bodies[0].span.start == SourcePosition(2, 1)
    assert source.position(raw.index('📚')) == SourcePosition(2, 3)
    for origin in req.model.fields:
        value = json.loads(source.slice(origin.location.span))
        key = origin.path[1:]
        assert value == (model['uses'][int(key.split('/')[1])] if key.startswith('uses/') else model[key])
    assert req.model.uses[0].name == 'paid'
    assert source.slice(req.model.uses[0].origin.location.span) == '"\\u0070aid"'
    assert req.model.when.text == model['when'] and req.model.must.text == model['must']
    assert_provenance(result)


def test_multilingual_and_interleaved_bodies_preserve_only_contiguous_raw_ranges():
    body = ('共通\n::: {lang=ja}\n日本語1\n:::\n' + fence()
            + '::: {lang=en}\nEnglish\n:::\n::: {lang=ja}\n日本語2\n:::\n末尾\n')
    result = parse(requirement(body))
    req, = result.requirements
    assert [b.language for b in req.bodies] == [None, 'ja', 'en', 'ja', None]
    assert [b.text for b in req.bodies] == ['共通\n', '日本語1\n', 'English\n', '日本語2\n', '末尾\n']
    assert len(result.nodes) == 2 and req.model is not None
    assert_provenance(result)


def test_workspace_sections_are_independent_originals_not_composed_or_filtered(tmp_path):
    first = requirement('::: {lang=ja}\n日本語\n:::\n', close=False)
    second = ':::\n' + requirement('::: {lang=en}\nEnglish []{.term id=unit}\n:::\n')
    (tmp_path / 'a.md').write_bytes(first.replace('\n', '\r\n').encode())
    (tmp_path / 'b.md').write_text(second)
    (tmp_path / 'canonical.md').write_text(requirement(attrs='.requirement #REQ-GENERATED spec-version=1'))
    (tmp_path / 'unused.md').write_text(requirement(attrs='.requirement #REQ-UNUSED spec-version=1'))
    hierarchy = {'sections': [{'title': title, 'file': name, 'order': i, 'children': []}
                              for i, (title, name) in enumerate([('A', 'a.md'), ('B', 'b.md')])]}
    (tmp_path / 'hierarchy.json').write_text(json.dumps(hierarchy))
    config = tmp_path / 'mdtools.toml'
    config.write_text('version=1\n[[documents]]\nkind="hierarchy"\npath="hierarchy.json"\ncanonical="canonical.md"\n')
    snapshots = snapshot_sources(load_workspace(config))
    assert [s.path.name for s in snapshots] == ['a.md', 'b.md']
    a, b = map(parse_requirements, snapshots)
    assert a.completeness == 'partial' and b.completeness == 'complete'
    assert a.requirements[0].bodies[0].text == '日本語\r\n'
    assert b.requirements[0].bodies[0].text == 'English []{.term id=unit}\n'
    assert a.diagnostics[0].primary.span.source.path == tmp_path / 'a.md'
    assert [a.requirements[0].key.name, b.requirements[0].key.name] == ['REQ-A', 'REQ-A']
    assert_provenance(a)
    assert_provenance(b)


def test_eof_and_source_changes_keep_exact_source_identity():
    raw = requirement().rstrip('\n')
    before = parse(raw)
    after = parse(raw.replace('説明', '変更'))
    assert before.requirements[0].span.end == SourcePosition(3, 4)
    assert before.source.ref.uri == after.source.ref.uri
    assert before.source.ref.snapshot != after.source.ref.snapshot
    assert before.requirements[0].key.name == after.requirements[0].key.name
    with pytest.raises(TypeError):
        parse_requirements(raw)


def test_escaped_attribute_reference_has_its_own_raw_token_range():
    result = parse(requirement(attrs='.requirement #REQ-A spec-version=1 refs="REQ-\\B REQ-B"'))
    req, = result.requirements
    assert [r.name for r in req.refs] == ['REQ-B', 'REQ-B']
    assert [result.source.slice(r.origin.location.span) for r in req.refs] == ['REQ-\\B', 'REQ-B']


def test_unicode_separators_do_not_renumber_source_lines():
    result = parse(requirement('A\u2028B\u0085C\n'))
    body = result.requirements[0].bodies[0]
    assert body.text == 'A\u2028B\u0085C\n'
    assert body.span.start == SourcePosition(2, 1) and body.span.end == SourcePosition(3, 1)
