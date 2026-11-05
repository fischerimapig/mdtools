"""Independent source coordinates and document ownership contracts."""
from dataclasses import replace

import pytest

from mdtools.core.source import SourcePosition, SourceSnapshot
from experiments.document_parser.model import (
    ByteRange, Coverage, DocumentParse, Node, SourceIndex, validate_document,
)


@pytest.mark.parametrize('text,cp_bytes,positions', [
    ('a\n📚e\u0301', [0, 1, 2, 6, 7, 9], [(1,1),(1,2),(2,1),(2,2),(2,3),(2,4)]),
    ('a\r\n界\rZ\n', [0,1,2,3,6,7,8,9], [(1,1),(1,2),None,(2,1),(2,2),(3,1),(3,2),(4,1)]),
    ('\u2028😀', [0,3,7], [(1,1),(1,2),(1,3)]),
    ('', [0], [(1,1)]),
])
def test_independent_original_coordinates(text, cp_bytes, positions):
    """Detect normalization, UTF-16 counting, Unicode line splitting and EOF coordinate errors."""
    source = SourceSnapshot('memory:coordinates', text)
    index = SourceIndex(source)
    assert index.source is source
    assert index.byte_length == cp_bytes[-1]
    for cp, byte in enumerate(cp_bytes):
        assert index.byte_range(cp, cp) == ByteRange(byte, byte)
        assert index.cp_offset(byte) == cp
        if positions[cp] is None:
            with pytest.raises(ValueError):
                index.span(ByteRange(byte, byte))
        else:
            original = index.span(ByteRange(byte, byte))
            assert original.source is source.ref
            assert original.start == original.end == SourcePosition(*positions[cp])
    assert index.slice(ByteRange(0, cp_bytes[-1])) == text


def test_reject_boundaries_without_rounding():
    """Reject UTF-8 interior bytes and CRLF interior SourceSpan positions instead of rounding."""
    index = SourceIndex(SourceSnapshot('memory:bounds', 'é\r\nX'))
    for byte in (-1, 1, 6):
        with pytest.raises(ValueError):
            index.cp_offset(byte)
    with pytest.raises(ValueError):
        index.slice(ByteRange(0, 1))
    # CRLF interior is an actual UTF-8 boundary but has no SourcePosition.
    assert index.cp_offset(3) == 2
    with pytest.raises(ValueError):
        index.span(ByteRange(3, 3))
    assert index.slice(ByteRange(2, 4)) == '\r\n'
    assert index.span(ByteRange(2, 4)).end == SourcePosition(2, 1)


def test_snapshot_identity_is_not_uri_identity():
    """Retain the exact snapshot and distinguish edits at the same source URI."""
    first = SourceSnapshot('memory:same-uri', 'é')
    changed = SourceSnapshot('memory:same-uri', 'e')
    assert first.ref.uri == changed.ref.uri
    assert first.ref.snapshot != changed.ref.snapshot
    assert SourceIndex(first).span(ByteRange(0,2)).source is first.ref


def base_document():
    index = SourceIndex(SourceSnapshot('memory:ownership', 'abcdef'))
    leaf = Node('paragraph', ByteRange(1,3), ByteRange(1,3))
    owner = Node('div', ByteRange(0,4), ByteRange(1,3), children=(leaf,))
    sibling = Node('paragraph', ByteRange(4,6), ByteRange(4,6))
    return DocumentParse(index, (owner,sibling), (), (), (Coverage(ByteRange(0,6),'recognized'),), 'complete')


@pytest.mark.parametrize('fault', ['parent-escape','sibling-overlap','coverage-gap','coverage-overlap','coverage-eof'])
def test_document_partition_and_ownership(fault):
    """Reject escaped children, overlapping siblings and incomplete or overlapping coverage partitions."""
    document = base_document()
    validate_document(document)
    owner, sibling = document.blocks
    if fault == 'parent-escape':
        owner = replace(owner, children=(Node('paragraph', ByteRange(1,4), ByteRange(1,4)),))
        document = replace(document, blocks=(owner,sibling))
    elif fault == 'sibling-overlap':
        document = replace(document, blocks=(owner, replace(sibling,span=ByteRange(3,6),body=ByteRange(3,6))))
    else:
        spans = {'coverage-gap': [(0,2),(3,6)], 'coverage-overlap': [(0,4),(3,6)], 'coverage-eof':[(0,5)]}[fault]
        document = replace(document, coverage=tuple(Coverage(ByteRange(a,b),'recognized') for a,b in spans))
    with pytest.raises(ValueError):
        validate_document(document)
