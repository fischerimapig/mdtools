"""Library build behavior and errors, without CLI argument/stream handling."""

import json
from pathlib import Path

import pytest

from glossary.loader import GlossaryError
from glossary.resolver import ResolveError
from mdsplit.schema import DocumentTree, SectionNode
from mdtools.build import build_document


def test_build_from_sections_preserves_stage_order_and_rereads(tmp_path):
    section = tmp_path / 'body.md'
    section.write_bytes(b'::: {lang=en}\r\nHello []{.term id=unit}\r\n:::\r\n::: {lang=ja}\r\n[]{.term id=ja_only}\r\n:::\r\n')
    hierarchy = tmp_path / 'hierarchy.json'
    DocumentTree('source.qmd', sections=[SectionNode('Title', 'body.md', 0)]).save(hierarchy)
    defs = tmp_path / 'defs.json'
    defs.write_text(json.dumps({'entries': [{'id': 'unit', 'kind': 'term', 'names': {'en': 'Unit'}}]}))
    work = tmp_path / 'work'
    result = build_document(hierarchy, lang='en', defs=[defs], work_dir=work, suffix='.qmd')
    assert result == '# Title\nHello Unit\n'
    assert sorted(p.name for p in work.iterdir()) == ['01-compose.qmd', '02-langfilter.qmd', '03-glossary.qmd']
    assert 'id=ja_only' in (work / '01-compose.qmd').read_text()
    assert '[]{.term id=unit}' in (work / '02-langfilter.qmd').read_text()
    assert (work / '03-glossary.qmd').read_text() == result


def test_build_keeps_compose_reread_at_issue31_boundary(tmp_path):
    # #31 remains a map-only failure; do not switch build to the map API.
    hierarchy = tmp_path / 'hierarchy.json'
    DocumentTree('source.md', metadata={'front_matter': '---\rtitle: example\r---\r'},
                 sections=[SectionNode('Title', 'body.md', 0)]).save(hierarchy)
    (tmp_path / 'body.md').write_bytes('日本語\r\n'.encode())
    work = tmp_path / 'work'
    result = build_document(hierarchy, work_dir=work)
    assert (work / '01-compose.md').read_bytes() == '---\rtitle: example\r---\r\n# Title\n日本語\n'.encode()
    assert result == '---\ntitle: example\n---\n# Title\n日本語\n'


@pytest.mark.parametrize('text', ['', '本文😀\r\n', '::: {lang=en}\nEnglish\n:::\n'])
def test_build_text_input_does_not_read_stdin_or_write_final_output(text, tmp_path, capsys):
    assert build_document(input_text=text, work_dir=tmp_path) == text
    assert list(tmp_path.iterdir()) == []
    assert capsys.readouterr() == ('', '')


@pytest.mark.parametrize('filename,source_type', [('renamed.JSON', 'auto'), ('sections.data', 'sections')])
def test_build_hierarchy_selection_and_base_level(filename, source_type, tmp_path):
    hierarchy = tmp_path / filename
    DocumentTree('source.md', sections=[SectionNode('Title', 'absent.md', 0)]).save(hierarchy)
    assert build_document(hierarchy, source_type=source_type, base_level=2) == '## Title'
    assert build_document(hierarchy, source_type='markdown') == hierarchy.read_text()


@pytest.mark.parametrize('kwargs,match', [
    ({}, 'exactly one'),
    ({'input_path': 'x', 'input_text': ''}, 'exactly one'),
    ({'input_text': '', 'base_level': 2}, '--base-level'),
    ({'input_text': '', 'keep_lang_fences': True}, '--keep-lang-fences'),
    ({'input_text': '', 'defs': ['defs.json']}, '-f/--defs'),
    ({'input_text': '', 'source_type': 'unknown'}, 'source_type'),
    ({'input_text': '', 'lang': 'unknown'}, 'lang'),
    ({'input_text': '', 'on_missing': 'unknown'}, 'on_missing'),
])
def test_build_rejects_invalid_requests(kwargs, match):
    with pytest.raises(ValueError, match=match):
        build_document(**kwargs)


def test_build_exposes_errors_to_the_host(tmp_path):
    with pytest.raises(OSError):
        build_document(tmp_path / 'missing.md')
    with pytest.raises(GlossaryError):
        build_document(input_text='', lang='en', defs=[tmp_path / 'missing.json'])
    defs = tmp_path / 'defs.json'
    defs.write_text('{"entries": []}')
    with pytest.raises(ResolveError):
        build_document(input_text='[]{.term id=absent}', lang='en', defs=[defs])


def test_build_temporary_stages_are_cleaned_after_success_and_failure(tmp_path, monkeypatch):
    from mdtools import build
    real_temporary_directory = build.tempfile.TemporaryDirectory
    locations = []

    def temporary_directory(**kwargs):
        directory = real_temporary_directory(dir=tmp_path, **kwargs)
        locations.append(Path(directory.name))
        return directory

    monkeypatch.setattr(build.tempfile, 'TemporaryDirectory', temporary_directory)
    assert build_document(input_text='::: {lang=en}\nHello\n:::\n', lang='en') == 'Hello\n'
    with pytest.raises(GlossaryError):
        build_document(input_text='', lang='en', defs=[tmp_path / 'missing.json'])
    assert len(locations) == 2
    assert all(not directory.exists() for directory in locations)


def test_lazy_input_is_read_once_after_work_directory_setup(tmp_path, capsys):
    work = tmp_path / 'work'
    reads = []

    def read_input():
        assert work.is_dir()
        reads.append(True)
        return '::: {lang=ja}\n日本語\n:::\n'

    assert build_document(read_input=read_input, work_dir=work, lang='ja', keep_lang_fences=True) == '::: {lang=ja}\n日本語\n:::\n'
    assert reads == [True]
    assert capsys.readouterr() == ('', '')
