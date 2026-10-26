"""Coordinate and provenance contracts, independent of document processing."""

from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from pathlib import Path

import pytest

from mdtools.core.source import (
    SourceMap, SourceMapBuilder, SourceMapping, SourcePosition as P,
    SourceRef, SourceSnapshot, SourceSpan,
)


def snapshot(text):
    return SourceSnapshot("memory:original", text)


@pytest.mark.parametrize("text,positions", [
    ("", [(1, 1)]),
    ("日本😀e\u0301", [(1, i) for i in range(1, 7)]),
    ("a\nb\n", [(1, 1), (1, 2), (2, 1), (2, 2), (3, 1)]),
    ("a\r\nb\r\n", [(1, 1), (1, 2), None, (2, 1), (2, 2), None, (3, 1)]),
    ("a\rb", [(1, 1), (1, 2), (2, 1), (2, 2)]),
    ("\r\n\n\r", [(1, 1), None, (2, 1), (3, 1), (4, 1)]),
])
def test_all_boundaries_and_roundtrip(text, positions):
    source = snapshot(text)
    assert len(positions) == len(text) + 1
    for offset, expected in enumerate(positions):
        if expected is None:
            with pytest.raises(ValueError, match="CRLF"):
                source.position(offset)
        else:
            assert source.position(offset) == P(*expected)
            assert source.offset(P(*expected)) == offset


@pytest.mark.parametrize("line,column", [(0, 1), (1, 0), (-1, 1), (True, 1), (1, False), (1.0, 2), (1, "2")])
def test_invalid_coordinate_values(line, column):
    with pytest.raises(ValueError):
        P(line, column)


@pytest.mark.parametrize("position", [P(1, 3), P(2, 3), P(3, 1)])
def test_outside_snapshot_position(position):
    with pytest.raises(ValueError):
        snapshot("a\r\nb").offset(position)


@pytest.mark.parametrize("offset", [-1, 4, True, 1.0, "1"])
def test_outside_snapshot_offset(offset):
    with pytest.raises(ValueError):
        snapshot("a\nb").position(offset)


def test_span_validation_and_half_open_slicing():
    source = snapshot("日本😀\r\n次")
    span = SourceSpan(source.ref, P(1, 2), P(1, 4))
    assert source.slice(span) == "本😀"
    assert source.slice(SourceSpan(source.ref, P(1, 4), P(2, 1))) == "\r\n"
    assert source.slice(source.span(len(source.text))) == ""
    with pytest.raises(ValueError, match="precedes"):
        SourceSpan(source.ref, P(2, 1), P(1, 1))
    with pytest.raises(ValueError):
        source.slice(SourceSpan(source.ref, P(1, 1), P(9, 1)))
    with pytest.raises(ValueError, match="different"):
        source.slice(snapshot("changed").span())
    with pytest.raises(ValueError):
        source.span(2, 1)


def test_snapshot_preserves_bytes_identity_and_old_ranges_after_edit(tmp_path):
    path = tmp_path / "原稿 😀.md"
    raw = "日本😀\r\n".encode()
    path.write_bytes(raw)
    old = SourceSnapshot.from_path(path)
    assert old.text.encode() == raw
    assert old.ref.snapshot == sha256(raw).hexdigest()
    assert old.ref.uri == path.as_uri()
    assert old.ref.path == path
    assert old.ref == SourceRef(old.uri, old.ref.snapshot)
    path.write_text("日本😀\n", encoding="utf-8")
    new = SourceSnapshot.from_path(path)
    assert old.ref != new.ref  # Newline-only edits change snapshot identity too.
    assert old.slice(old.span()) == "日本😀\r\n"
    with pytest.raises(ValueError):
        new.slice(old.span())
    with pytest.raises(FrozenInstanceError):
        old.text = "changed"
    moved = SourceSnapshot("memory:moved", old.text)
    assert moved.ref.snapshot == old.ref.snapshot and moved.ref != old.ref


def test_file_symlink_is_resolved_and_invalid_utf8_is_rejected(tmp_path):
    original = tmp_path / "source.md"
    original.write_bytes(b"text")
    link = tmp_path / "link.md"
    link.symlink_to(original)
    assert SourceSnapshot.from_path(link) == SourceSnapshot.from_path(original)
    original.write_bytes(b"\xff")
    with pytest.raises(UnicodeError):
        SourceSnapshot.from_path(original)


@pytest.mark.parametrize("uri,digest,path", [
    ("relative.md", "a" * 64, None), ("memory:x", "bad", None),
    ("memory:x", "a" * 64, "relative.md"),
    ("memory:x", "a" * 64, Path("relative.md")),
    ("memory:x", "a" * 64, Path("/different.md")),
])
def test_invalid_ref(uri, digest, path):
    with pytest.raises(ValueError):
        SourceRef(uri, digest, path)


def test_map_splits_files_and_synthetic_text_and_normalizes_newlines():
    a = SourceSnapshot("memory:a", "日本😀\r\n次")
    b = SourceSnapshot("memory:b", "日本😀")
    builder = SourceMapBuilder()
    builder.add_synthetic("# Title\n", "heading")
    builder.add_source(a, normalize_newlines=True)
    builder.add_synthetic("\n", "separator")
    builder.add_source(b)
    result = builder.build("memory:composed")
    assert result.artifact.text == "# Title\n日本😀\n次\n日本😀"
    hits = result.resolve(result.artifact.span())
    assert [h.kind for h in hits] == ["synthetic", "exact", "newline", "exact", "synthetic", "exact"]
    assert [h.original.source.uri for h in hits if h.original] == ["memory:a"] * 3 + ["memory:b"]
    newline = hits[2]
    assert a.slice(newline.original) == "\r\n"
    assert result.artifact.slice(newline.generated) == "\n"
    assert result.resolve(result.artifact.span(10, 11))[0].original == a.span(2, 3)
    assert result.resolve(result.artifact.span(len(result.artifact.text)))[0].original == b.span(3)
    # A point at a generated separator must not be attributed to adjacent text.
    separator = hits[4].generated
    assert result.resolve(SourceSpan(result.artifact.ref, separator.start, separator.start))[0].kind == "synthetic"
    with pytest.raises(ValueError):
        result.resolve(SourceSnapshot("memory:composed", "new output").span())


def test_unmapped_transform_cannot_claim_precise_origins_and_empty_artifact_is_explicit():
    builder = SourceMapBuilder()
    builder.add_unmapped("translated", "langfilter mapping unavailable")
    result = builder.build("memory:filtered")
    hit, = result.resolve(result.artifact.span(1, 4))
    assert hit.original is None and hit.kind == "unmapped" and "langfilter" in hit.reason
    empty = SourceMapBuilder().build("memory:empty")
    assert empty.resolve(empty.artifact.span())[0].kind == "unmapped"
    for add in (builder.add_synthetic, builder.add_unmapped):
        with pytest.raises(ValueError):
            add("text", "")


def test_map_rejects_gaps_overlaps_wrong_snapshots_and_false_exact_claims():
    source = snapshot("abc")
    builder = SourceMapBuilder()
    builder.add_source(source)
    result = builder.build("memory:out")
    entry, = result.mappings
    for entries in (
        (), (replace(entry, generated=result.artifact.span(1)),), (entry, entry),
        (replace(entry, generated=source.span()),),
        (replace(entry, original=source.span(1)),),
        (replace(entry, kind="newline"),),
    ):
        with pytest.raises(ValueError):
            SourceMap(result.artifact, result.inputs, entries)
    with pytest.raises(ValueError):
        SourceMap(result.artifact, (), result.mappings)
    with pytest.raises(ValueError):
        SourceMapping(entry.generated, "synthetic", source.span(), "heading")
    with pytest.raises(ValueError):
        SourceMapping(entry.generated, "exact")


def test_raw_crlf_copy_and_normalized_newline_boundary_queries():
    source = snapshot("a\r\nb\rc")
    builder = SourceMapBuilder()
    builder.add_source(source)
    raw = builder.build("memory:raw")
    assert raw.resolve(raw.artifact.span())[0].original == source.span()
    builder = SourceMapBuilder()
    builder.add_source(source, normalize_newlines=True)
    normalized = builder.build("memory:normalized")
    for start, end in [(0, 1), (1, 2), (2, 2), (3, 4), (5, 5)]:
        hits = normalized.resolve(normalized.artifact.span(start, end))
        assert len(hits) == 1
        hit, = hits
        assert source.slice(hit.original).replace("\r\n", "\n").replace("\r", "\n") == normalized.artifact.slice(hit.generated)
