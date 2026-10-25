"""Real diagnostic generation -> both formats, with existing source/workspace APIs."""

import json
from pathlib import Path

import pytest

from mdtools.core.diagnostics import (
    CheckResult, Diagnostic, DiagnosticLocation, DiagnosticReport, RelatedLocation,
    render_json, render_text,
)
from mdtools.diagnostics import inspect_workspace
from mdtools.workspace import WorkspaceError, load_workspace, snapshot_sources
from mdsplit.compose import compose_with_source_map
from mdsplit.schema import DocumentTree, SectionNode

REPO = Path(__file__).resolve().parents[2]


def test_real_workspace_loading_and_missing_file_diagnostic(tmp_path):
    real = REPO / 'docs/spec/examples/cancellation/mdtools.toml'
    report = inspect_workspace(real)
    assert report.sources == snapshot_sources(load_workspace(real))
    assert report.diagnostics == ()
    assert report.checks == (CheckResult('workspace.sources', 'passed'),)
    assert 'workspace.sources status=passed' in render_text(report)
    assert 'spec' not in json.loads(render_json(report))['checks'][0]['check_id']
    settings = tmp_path / 'mdtools.toml'
    settings.write_text('version = 1\n[[documents]]\nkind = "markdown"\npath = "不在😀.md"\n')
    report = inspect_workspace(settings)
    diagnostic, = report.diagnostics
    assert diagnostic.code == 'workspace.missing-file'
    assert diagnostic.category == 'user'
    assert diagnostic.primary.kind == 'none'
    assert report.sources == ()
    data = json.loads(render_json(report))
    assert data['checks'][0]['status'] == 'failed'
    assert data['diagnostics'][0]['evidence'][0]['message'] == str(tmp_path / '不在😀.md')
    text = render_text(report)
    assert 'workspace.missing-file severity=error category=user' in text
    assert 'primary kind=none' in text and '不在😀.md' in text


@pytest.mark.parametrize('code,category,status', [
    ('workspace.read-error', 'tool-error', 'error'),
    ('workspace.unsupported-version', 'unsupported', 'unsupported'),
    ('workspace.changed-input', 'unknown', 'unknown'),
    ('workspace.invalid-source', 'user', 'failed'),
])
def test_workspace_adapter_classifies_errors_without_inventing_sources(tmp_path, monkeypatch, code, category, status):
    def fail(_):
        raise WorkspaceError(code, tmp_path / '原稿😀.md', '説明\n次行')
    monkeypatch.setattr('mdtools.diagnostics.load_workspace', fail)
    report = inspect_workspace(tmp_path / 'mdtools.toml')
    assert report.diagnostics[0].category == category
    assert report.checks[0].status == status
    assert report.diagnostics[0].primary == DiagnosticLocation()
    assert report.sources == ()
    assert json.loads(render_json(report))['diagnostics'][0]['code'] == code
    assert '\\n' in render_text(report)


def test_section_map_to_diagnostic_keeps_both_originals_and_generated_heading(tmp_path):
    for name in ('a.md', 'b.md'):
        (tmp_path / name).write_bytes('同じ本文😀\r\n'.encode())
    hierarchy = tmp_path / 'hierarchy.json'
    DocumentTree('canonical.md', sections=[SectionNode('A', 'a.md', 0), SectionNode('B', 'b.md', 1)]).save(hierarchy)
    mapped = compose_with_source_map(hierarchy, artifact_uri='memory:compose')
    originals = [m for m in mapped.resolve(mapped.artifact.span()) if m.kind == 'exact']
    a, b = (DiagnosticLocation.from_mapping(part) for part in originals)
    heading = DiagnosticLocation.from_mapping(mapped.mappings[0])
    diagnostic = Diagnostic('example.duplicate', 'warning', 'user', '同じ本文の例（意味検査ではない）', a,
                            (RelatedLocation('もう一つのsection', b), RelatedLocation('生成見出し', heading)))
    report = DiagnosticReport((diagnostic,), sources=(*mapped.inputs, mapped.artifact))
    primary = json.loads(render_json(report))['diagnostics'][0]['primary']['span']['source']
    assert primary['path'] == str(tmp_path / 'a.md')
    assert a.span.source != b.span.source
    assert a.span.source.snapshot == b.span.source.snapshot
    text = render_text(report)
    assert 'a.md' in text and 'b.md' in text
    assert 'kind=synthetic uri="memory:compose"' in text
    assert 'reason="heading"' in text
