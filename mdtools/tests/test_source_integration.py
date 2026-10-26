"""Connect Workspace, scanning, compose and the unchanged distribution build."""

from pathlib import Path

import pytest

from mdsplit.compose import compose, compose_with_source_map
from mdsplit.decompose import decompose
from mdsplit.schema import DocumentTree, SectionNode
from mdtools.build_cli import main as build
from mdtools.core.mdscan import scan_md_lines
from mdtools.core.source import SourceMapBuilder, SourcePosition as P, SourceSnapshot, SourceSpan
from mdtools.workspace import WorkspaceError, load_workspace, snapshot_sources

REPO = Path(__file__).resolve().parents[2]


def settings(root, document):
    path = root / "mdtools.toml"
    path.write_text("version = 1\n" + document, encoding="utf-8")
    return path


def query_text(result, text, start=0):
    offset = result.artifact.text.index(text, start)
    return result.resolve(result.artifact.span(offset, offset + len(text)))


def test_workspace_distinguishes_identical_section_text_and_preserves_snapshot(tmp_path):
    for name in ("a.md", "b.md"):
        (tmp_path / name).write_bytes("同じ😀\r\n".encode())
    tree = DocumentTree("ignored.md", sections=[
        SectionNode("A", "a.md", 0), SectionNode("B", "b.md", 1),
    ])
    hierarchy = tmp_path / "hierarchy.json"
    tree.save(hierarchy)
    workspace = load_workspace(settings(tmp_path, '[[documents]]\nkind = "hierarchy"\n'
                                        'path = "hierarchy.json"\ncanonical = "out.md"\n'))
    originals = snapshot_sources(workspace)
    assert originals[0].ref.snapshot == originals[1].ref.snapshot
    assert originals[0].ref != originals[1].ref
    result = compose_with_source_map(hierarchy, artifact_uri=(tmp_path / "out.md").as_uri())
    assert result.artifact.text == compose(hierarchy)
    first, = query_text(result, "同じ😀")
    second, = query_text(result, "同じ😀", result.artifact.text.index("# B"))
    assert first.original == originals[0].span(0, 3)
    assert second.original == originals[1].span(0, 3)
    (tmp_path / "a.md").write_text("edited", encoding="utf-8")
    assert result.resolve(first.generated)[0] == first
    assert originals[0].slice(first.original) == "同じ😀"
    assert snapshot_sources(workspace)[0].ref != originals[0].ref


def test_single_original_scanner_keeps_front_matter_preamble_fence_and_eof_positions(tmp_path):
    text = "---\r\ntitle: 日本😀\r\n---\r\n\r\n前文\r\n# Heading\r\n```md\r\n# コード😀\r\n```\r\n終端"
    path = tmp_path / "doc.qmd"
    path.write_bytes(text.encode())
    workspace = load_workspace(settings(tmp_path, '[[documents]]\nkind = "markdown"\npath = "doc.qmd"\n'))
    source, = snapshot_sources(workspace)
    lines = list(scan_md_lines(source.text))
    assert lines[1].lineno == 2 and "日本😀" in lines[1].text
    assert lines[7].in_code_fence and "# コード😀" in lines[7].text
    assert source.slice(SourceSpan(source.ref, P(8, 3), P(8, 7))) == "コード😀"
    assert source.position(len(text)) == P(10, 3)
    assert source.slice(SourceSpan(source.ref, P(5, 1), P(5, 3))) == "前文"
    # Scanning is observational; raw CRLF text and its positions remain intact.
    assert source.text == text


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_compose_front_matter_preamble_fence_and_roundtrip(tmp_path, newline):
    text = ('---\ntitle: 日本😀\n---\n\n前文😀\n\n# 見出し\n\n'
            '```md\n# コード😀\n```\n\n## 子\n\n本文😀\n')
    original = tmp_path / "original.qmd"
    original.write_bytes(text.replace("\n", newline).encode())
    tree = decompose(original, tmp_path / "sections")
    hierarchy = tmp_path / "sections/hierarchy.json"
    # Exercise CRLF/CR in actual section inputs too; decompose reads universal newlines.
    for path in (tmp_path / "sections").rglob("*.md"):
        path.write_bytes(path.read_text(encoding="utf-8").replace("\n", newline).encode())
    result = compose_with_source_map(hierarchy, artifact_uri="memory:canonical")
    assert result.artifact.text == compose(hierarchy) == text
    for needle, file in [("前文😀", tree.metadata["preamble_file"]),
                         ("# コード😀", tree.sections[0].file),
                         ("本文😀", tree.sections[0].children[0].file)]:
        hit, = query_text(result, needle)
        source = SourceSnapshot.from_path(tmp_path / "sections" / file)
        assert hit.original.source == source.ref
        assert source.slice(hit.original) == needle
    assert query_text(result, "title: 日本😀")[0].kind == "synthetic"
    assert query_text(result, "# 見出し")[0].reason == "heading"
    # A cross-section query preserves original files and synthetic separators.
    hits = result.resolve(result.artifact.span())
    assert {h.original.source.path for h in hits if h.original} == {
        tmp_path / "sections" / tree.metadata["preamble_file"],
        tmp_path / "sections" / tree.sections[0].file,
        tmp_path / "sections" / tree.sections[0].children[0].file,
    }
    output = tmp_path / "build.md"
    assert build([str(hierarchy), "-o", str(output)]) == 0
    assert output.read_text(encoding="utf-8") == result.artifact.text
    again = tmp_path / "again.md"
    again.write_text(result.artifact.text, encoding="utf-8")
    decompose(again, tmp_path / "again")
    assert compose(tmp_path / "again/hierarchy.json") == text


def test_compose_missing_empty_whitespace_ties_override_and_metadata_only(tmp_path):
    (tmp_path / "empty.md").write_text("", encoding="utf-8")
    (tmp_path / "pre.md").write_text(" \r\n", encoding="utf-8")
    tree = DocumentTree("ignored.md", metadata={"preamble_file": "pre.md"}, sections=[
        SectionNode("B", "missing.md", 1),
        SectionNode("A", "empty.md", 0, children=[SectionNode("Child", "empty.md", 0)]),
        SectionNode("C", "empty.md", 1),
    ])
    hierarchy = tmp_path / "hierarchy.json"
    tree.save(hierarchy)
    result = compose_with_source_map(hierarchy, artifact_uri="memory:canonical", base_level=2)
    assert result.artifact.text == compose(hierarchy, base_level=2) == "## A\n\n### Child\n\n## B\n## C\n"
    assert {s.path for s in result.inputs} == {hierarchy, tmp_path / "empty.md", tmp_path / "pre.md"}
    assert all(h.original is None for h in result.resolve(result.artifact.span()))
    tree.sections = []
    tree.metadata = {"front_matter": "---\ntitle: metadata\n---"}
    tree.save(hierarchy)
    result = compose_with_source_map(hierarchy, artifact_uri="memory:metadata")
    assert result.artifact.text == compose(hierarchy)
    assert result.resolve(result.artifact.span())[0].reason == "hierarchy-front-matter"
    tree.metadata = {}
    tree.save(hierarchy)
    empty = compose_with_source_map(hierarchy, artifact_uri="memory:empty")
    assert empty.artifact.text == compose(hierarchy) == ""
    assert empty.resolve(empty.artifact.span())[0].kind == "unmapped"


def test_transformed_build_output_cannot_use_compose_map(tmp_path):
    (tmp_path / "body.md").write_text("::: {lang=en}\nEnglish\n:::\n::: {lang=ja}\n日本語\n:::\n", encoding="utf-8")
    hierarchy = tmp_path / "hierarchy.json"
    DocumentTree("ignored", sections=[SectionNode("Title", "body.md", 0)]).save(hierarchy)
    composed = compose_with_source_map(hierarchy, artifact_uri="memory:compose-stage")
    output = tmp_path / "en.md"
    assert build([str(hierarchy), "--lang", "en", "-o", str(output)]) == 0
    filtered = SourceSnapshot.from_path(output)
    assert "日本語" not in filtered.text and "English" in filtered.text
    with pytest.raises(ValueError, match="different"):
        composed.resolve(filtered.span())
    builder = SourceMapBuilder()
    builder.add_unmapped(filtered.text, "langfilter source mapping is unsupported")
    assert builder.build(filtered.uri).resolve(filtered.span())[0].kind == "unmapped"


def test_real_contract_map_matches_canonical_and_originals():
    hierarchy = REPO / "docs/spec/contract-v1_sections/hierarchy.json"
    result = compose_with_source_map(hierarchy, artifact_uri="memory:contract")
    assert result.artifact.text == (REPO / "docs/spec/contract-v1.md").read_text(encoding="utf-8")
    for mapping in result.mappings:
        if mapping.original:
            source = next(s for s in result.inputs if s.ref == mapping.original.source)
            assert source.slice(mapping.original) == result.artifact.slice(mapping.generated)


def test_workspace_snapshot_revalidates_registration_and_bad_encoding(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text("original", encoding="utf-8")
    config = settings(tmp_path, '[[documents]]\nkind = "markdown"\npath = "doc.md"\n')
    workspace = load_workspace(config)
    doc.write_bytes(b"\xff")
    with pytest.raises(WorkspaceError) as error:
        snapshot_sources(workspace)
    assert error.value.code == "workspace.invalid-source"
    other = tmp_path / "other.md"
    other.write_text("new document", encoding="utf-8")
    config.write_text(config.read_text().replace("doc.md", "other.md"), encoding="utf-8")
    with pytest.raises(WorkspaceError) as error:
        snapshot_sources(workspace)
    assert error.value.code == "workspace.changed-input"


def test_workspace_snapshots_wrap_content_io_and_reject_retargeted_symlinks(tmp_path, monkeypatch):
    doc = tmp_path / "doc.md"
    doc.write_text("original", encoding="utf-8")
    config = settings(tmp_path, '[[documents]]\nkind = "markdown"\npath = "doc.md"\n')
    workspace = load_workspace(config)
    read_bytes = Path.read_bytes

    def denied(path):
        if path == doc:
            raise PermissionError("source read denied")
        return read_bytes(path)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", denied)
        with pytest.raises(WorkspaceError) as error:
            snapshot_sources(workspace)
        assert error.value.code == "workspace.read-error"
    other = tmp_path / "other.md"
    other.write_text("replacement", encoding="utf-8")
    doc.unlink()
    doc.symlink_to(other)
    with pytest.raises(WorkspaceError) as error:
        snapshot_sources(workspace)
    assert error.value.code == "workspace.changed-input"
