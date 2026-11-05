"""Source-preserving, specification-agnostic prototype result contract.

Ranges are original UTF-8 byte boundaries. Python cursors remain code points;
the index converts them without rescanning the source prefix. No normalized
text, rendered text, or duplicate tree is stored.
"""
from __future__ import annotations

from array import array
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
import re

from mdtools.core.source import SourceSnapshot, SourceSpan

PROFILE = "mdtools-document-prototype-v0"
MODEL_VERSION = 0


@dataclass(frozen=True, order=True)
class ByteRange:
    start: int
    end: int

    def __post_init__(self):
        if (type(self.start) is not int or type(self.end) is not int
                or not 0 <= self.start <= self.end):
            raise ValueError("invalid half-open byte range")


@dataclass(frozen=True)
class Line:
    start: int
    content_end: int
    end: int


class SourceIndex:
    """One snapshot, one UTF-8 boundary table, original line boundaries."""

    def __init__(self, source: SourceSnapshot):
        if not isinstance(source, SourceSnapshot):
            raise TypeError("SourceIndex requires SourceSnapshot")
        self.source = source
        offsets = array("Q", [0])
        total = 0
        for char in source.text:
            total += len(char.encode("utf-8"))
            offsets.append(total)
        self._bytes = offsets
        self.byte_length = total
        lines = []
        start = 0
        for match in re.finditer(r"\r\n|\r|\n", source.text):
            lines.append(Line(start, match.start(), match.end()))
            start = match.end()
        if start < len(source.text):
            lines.append(Line(start, len(source.text), len(source.text)))
        self.lines = tuple(lines)

    def byte_range(self, start: int, end: int) -> ByteRange:
        if (type(start) is not int or type(end) is not int
                or not 0 <= start <= end <= len(self.source.text)):
            raise ValueError("code point offsets outside snapshot")
        return ByteRange(self._bytes[start], self._bytes[end])

    def cp_offset(self, byte: int) -> int:
        if type(byte) is not int or not 0 <= byte <= self.byte_length:
            raise ValueError("byte offset outside snapshot")
        pos = bisect_left(self._bytes, byte)
        if self._bytes[pos] != byte:
            raise ValueError("offset inside UTF-8 character")
        return pos

    def offsets(self, span: ByteRange) -> tuple[int, int]:
        return self.cp_offset(span.start), self.cp_offset(span.end)

    def slice(self, span: ByteRange) -> str:
        start, end = self.offsets(span)
        return self.source.text[start:end]

    def span(self, span: ByteRange) -> SourceSpan:
        # SourceSnapshot rejects a boundary inside CRLF; never round it.
        return self.source.span(*self.offsets(span))


@dataclass(frozen=True)
class Limits:
    max_bytes: int = 4 * 1024 * 1024
    max_nodes: int = 200_000
    max_depth: int = 64
    max_inline_chars: int = 2 * 1024 * 1024

    def __post_init__(self):
        if any(type(n) is not int or n < 1 for n in (
                self.max_bytes, self.max_nodes, self.max_depth, self.max_inline_chars)):
            raise ValueError("limits must be positive integers")


@dataclass(frozen=True)
class Attribute:
    kind: str
    name: str
    value: str
    span: ByteRange
    value_span: ByteRange


@dataclass(frozen=True)
class Inline:
    kind: str
    span: ByteRange
    target: ByteRange | None = None
    title: ByteRange | None = None
    reference: str | None = None


@dataclass(frozen=True)
class ReferenceDefinition:
    label: str
    span: ByteRange
    destination: ByteRange
    title: ByteRange | None = None


@dataclass(frozen=True)
class Node:
    kind: str
    span: ByteRange
    body: ByteRange
    header: ByteRange | None = None
    closing: ByteRange | None = None
    children: tuple[Node, ...] = ()
    attributes: tuple[Attribute, ...] = ()
    info: str = ""
    info_span: ByteRange | None = None
    marker: str = ""
    closure: str = "none"
    valid: bool = True
    inlines: tuple[Inline, ...] = ()


@dataclass(frozen=True)
class Notice:
    code: str
    message: str
    span: ByteRange


@dataclass(frozen=True)
class Coverage:
    span: ByteRange
    state: str  # recognized, unsupported, unparsed
    reason: str | None = None


@dataclass(frozen=True)
class BlockResult:
    blocks: tuple[Node, ...]
    references: tuple[ReferenceDefinition, ...] = ()
    notices: tuple[Notice, ...] = ()
    coverage: tuple[Coverage, ...] = ()
    status: str = "complete"


@dataclass(frozen=True)
class InlineResult:
    inlines: tuple[Inline, ...]
    notices: tuple[Notice, ...] = ()
    complete: bool = True


@dataclass(frozen=True)
class DocumentParse:
    index: SourceIndex
    blocks: tuple[Node, ...]
    references: tuple[ReferenceDefinition, ...]
    notices: tuple[Notice, ...]
    coverage: tuple[Coverage, ...]
    status: str
    profile: str = PROFILE
    model_version: int = MODEL_VERSION

    @property
    def source(self) -> SourceSnapshot:
        return self.index.source

    def slice(self, span: ByteRange) -> str:
        return self.index.slice(span)


def walk(blocks: tuple[Node, ...]):
    """Preorder without Python recursion."""
    pending = list(reversed(blocks))
    while pending:
        node = pending.pop()
        yield node
        pending.extend(reversed(node.children))


def validate_document(document: DocumentParse) -> None:
    """Check ownership, original boundaries and complete coverage partition.

    A failed invariant is a programming error, never repaired by searching raw
    text. The parser's outer boundary converts it to an explicit failed result.
    """
    index = document.index
    whole = ByteRange(0, index.byte_length)

    def within(inner, outer):
        if not outer.start <= inner.start <= inner.end <= outer.end:
            raise ValueError("range escapes its owner")
        index.span(inner)

    pending = [(document.blocks, whole)]
    gaps = []
    while pending:
        siblings, owner = pending.pop()
        cursor = owner.start
        for node in siblings:
            within(node.span, owner)
            if node.span.start < cursor:
                raise ValueError("siblings overlap or are out of order")
            if node.span.start > cursor:
                gaps.append(ByteRange(cursor, node.span.start))
            cursor = node.span.end
            within(node.body, node.span)
            for span in (node.header, node.closing, node.info_span):
                if span is not None:
                    within(span, node.span)
            if node.kind == "div" and node.header is not None:
                if node.header.start != node.span.start or node.header.end != node.body.start:
                    raise ValueError("Div header/body do not form a partition")
                if node.closing is not None:
                    if node.body.end != node.closing.start or node.closing.end != node.span.end:
                        raise ValueError("Div body/closing do not form a partition")
                elif node.body.end != node.span.end:
                    raise ValueError("Unclosed Div body must reach its end")
            for attr in node.attributes:
                within(attr.span, node.header or node.span)
                within(attr.value_span, attr.span)
            inline_end = node.body.start
            for item in node.inlines:
                within(item.span, node.body)
                if item.span.start < inline_end:
                    raise ValueError("inline ranges overlap")
                inline_end = item.span.end
                # A resolved reference's destination/title belongs to its
                # definition, not the usage; only inline targets are local.
                for span in (item.target, item.title):
                    if span is not None:
                        within(span, whole if item.reference is not None else item.span)
            if node.kind == "div" or node.children:
                pending.append((node.children, node.body))
        if cursor < owner.end:
            gaps.append(ByteRange(cursor, owner.end))
    cursor = 0
    for item in document.coverage:
        within(item.span, whole)
        if item.span.start != cursor or item.span.end <= cursor:
            raise ValueError("coverage must partition original bytes")
        if item.state not in ("recognized", "unsupported", "unparsed"):
            raise ValueError("unknown coverage state")
        if item.state != "recognized" and not item.reason:
            raise ValueError("incomplete coverage requires reason")
        cursor = item.span.end
    if cursor != whole.end:
        raise ValueError("coverage does not reach EOF")
    starts = [c.span.start for c in document.coverage]
    for gap in gaps:
        cursor = gap.start
        i = max(0, bisect_right(starts, cursor) - 1)
        while cursor < gap.end:
            item = document.coverage[i]
            if item.state == "recognized":
                raise ValueError("recognized source bytes have no structural owner")
            cursor = min(gap.end, item.span.end)
            i += 1
    for ref in document.references:
        within(ref.span, whole)
        within(ref.destination, ref.span)
        if ref.title is not None:
            within(ref.title, ref.span)
    for notice in document.notices:
        within(notice.span, whole)
    if document.status not in ("complete", "partial", "rejected", "failed"):
        raise ValueError("unknown parse status")
    if document.status == "complete" and any(c.state != "recognized" for c in document.coverage):
        raise ValueError("incomplete coverage cannot be complete")
