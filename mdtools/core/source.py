"""Immutable source snapshots and conservative generated-text provenance.

Coordinates are 1-based Unicode code points, with half-open spans. Protocol
encodings (including LSP) belong in adapters, not in this module.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

_NEWLINE = re.compile(r"\r\n|\r|\n")


@dataclass(frozen=True, order=True)
class SourcePosition:
    line: int
    column: int

    def __post_init__(self) -> None:
        if any(type(v) is not int or v < 1 for v in (self.line, self.column)):
            raise ValueError("line and column must be positive integers")


@dataclass(frozen=True)
class SourceRef:
    uri: str
    snapshot: str  # SHA-256 of the exact UTF-8 text, before newline normalization
    path: Path | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.uri, str) or not urlsplit(self.uri).scheme:
            raise ValueError("source URI must be absolute")
        if not isinstance(self.snapshot, str) or not re.fullmatch(r"[0-9a-f]{64}", self.snapshot):
            raise ValueError("snapshot must be a lowercase SHA-256 digest")
        if self.path is not None:
            if not isinstance(self.path, Path) or not self.path.is_absolute():
                raise ValueError("source path must be absolute")
            if self.path.as_uri() != self.uri:
                raise ValueError("source path and URI disagree")


@dataclass(frozen=True)
class SourceSpan:
    source: SourceRef
    start: SourcePosition
    end: SourcePosition

    def __post_init__(self) -> None:
        if not isinstance(self.source, SourceRef):
            raise ValueError("span requires a SourceRef")
        if not isinstance(self.start, SourcePosition) or not isinstance(self.end, SourcePosition):
            raise ValueError("span requires SourcePosition endpoints")
        if self.end < self.start:
            raise ValueError("span end precedes start")


@dataclass(frozen=True)
class SourceSnapshot:
    """Exact UTF-8 text in memory; no implicit rereads or currentness claim.

    LF, CRLF and lone CR are line endings, never columns. There is no position
    between CR and LF. EOF is the end column, or (last line + 1, 1) after a
    trailing newline. Empty text has the single position (1, 1).
    """

    uri: str
    text: str
    path: Path | None = field(default=None, compare=False)
    ref: SourceRef = field(init=False)
    _starts: tuple[int, ...] = field(init=False, repr=False, compare=False)
    _ends: tuple[int, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        digest = sha256(self.text.encode("utf-8")).hexdigest()
        object.__setattr__(self, "ref", SourceRef(self.uri, digest, self.path))
        breaks = list(_NEWLINE.finditer(self.text))
        object.__setattr__(self, "_starts", (0, *(m.end() for m in breaks)))
        object.__setattr__(self, "_ends", (*(m.start() for m in breaks), len(self.text)))

    @classmethod
    def from_path(cls, path: str | Path) -> SourceSnapshot:
        path = Path(path).resolve()
        return cls(path.as_uri(), path.read_bytes().decode("utf-8"), path)

    def offset(self, position: SourcePosition) -> int:
        """Convert to a Python string offset, validating against this snapshot."""
        if not isinstance(position, SourcePosition) or position.line > len(self._starts):
            raise ValueError("position outside snapshot")
        index = position.line - 1
        offset = self._starts[index] + position.column - 1
        if offset > self._ends[index]:
            raise ValueError("column outside line")
        return offset

    def position(self, offset: int) -> SourcePosition:
        if type(offset) is not int or not 0 <= offset <= len(self.text):
            raise ValueError("offset outside snapshot")
        index = bisect_right(self._starts, offset) - 1
        if offset > self._ends[index]:
            raise ValueError("offset inside CRLF")
        return SourcePosition(index + 1, offset - self._starts[index] + 1)

    def span(self, start: int = 0, end: int | None = None) -> SourceSpan:
        return SourceSpan(self.ref, self.position(start),
                          self.position(len(self.text) if end is None else end))

    def offsets(self, span: SourceSpan) -> tuple[int, int]:
        if not isinstance(span, SourceSpan) or span.source != self.ref:
            raise ValueError("span belongs to a different source/snapshot")
        return self.offset(span.start), self.offset(span.end)

    def slice(self, span: SourceSpan) -> str:
        start, end = self.offsets(span)
        return self.text[start:end]


MappingKind = Literal["exact", "newline", "synthetic", "unmapped"]


@dataclass(frozen=True)
class SourceMapping:
    generated: SourceSpan
    kind: MappingKind
    original: SourceSpan | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.generated, SourceSpan):
            raise ValueError("mapping requires a generated SourceSpan")
        if self.kind not in ("exact", "newline", "synthetic", "unmapped"):
            raise ValueError("unknown mapping kind")
        if self.kind in ("exact", "newline"):
            if not isinstance(self.original, SourceSpan) or self.reason is not None:
                raise ValueError("copied text requires an original span and no reason")
        elif self.original is not None or not isinstance(self.reason, str) or not self.reason:
            raise ValueError("synthetic/unmapped text requires a reason and no original span")


@dataclass(frozen=True)
class SourceMap:
    """A complete map for one artifact snapshot, with immutable input snapshots.

    resolve() splits ranges at provenance boundaries. It never invents one
    original range for a query crossing files or synthetic/unmapped text.
    """

    artifact: SourceSnapshot
    inputs: tuple[SourceSnapshot, ...]
    mappings: tuple[SourceMapping, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.inputs, tuple) or not isinstance(self.mappings, tuple):
            raise ValueError("source map collections must be tuples")
        inputs = {s.ref: s for s in self.inputs}
        cursor = 0
        for mapping in self.mappings:
            start, end = self.artifact.offsets(mapping.generated)
            if start != cursor or end <= start:
                raise ValueError("mappings must cover the artifact without gaps or overlaps")
            cursor = end
            if mapping.original is not None:
                source = inputs.get(mapping.original.source)
                if source is None:
                    raise ValueError("original snapshot is missing")
                original = source.slice(mapping.original)
                generated = self.artifact.text[start:end]
                if mapping.kind == "exact" and original != generated:
                    raise ValueError("exact mapping text differs")
                if mapping.kind == "newline" and not (generated == "\n" and original in ("\r", "\r\n")):
                    raise ValueError("newline mapping must normalize one CR/CRLF to LF")
        if cursor != len(self.artifact.text):
            raise ValueError("mappings do not cover the artifact")

    def resolve(self, span: SourceSpan) -> tuple[SourceMapping, ...]:
        start, end = self.artifact.offsets(span)
        result = []
        inputs = {s.ref: s for s in self.inputs}
        for mapping in self.mappings:
            left, right = self.artifact.offsets(mapping.generated)
            if start == end:
                # Right affinity at a boundary; EOF belongs to the final segment.
                if not (left <= start < right or start == right == len(self.artifact.text)):
                    continue
                a = b = start
            else:
                a, b = max(start, left), min(end, right)
                if a >= b:
                    continue
            original = None
            if mapping.original is not None:
                source = inputs[mapping.original.source]
                origin_start, origin_end = source.offsets(mapping.original)
                if mapping.kind == "newline":
                    oa = origin_start if a == left else origin_end
                    ob = origin_start if b == left else origin_end
                else:
                    oa, ob = origin_start + a - left, origin_start + b - left
                original = source.span(oa, ob)
            result.append(SourceMapping(self.artifact.span(a, b), mapping.kind, original, mapping.reason))
        if not result:  # The only valid no-segment query is an empty artifact.
            result.append(SourceMapping(span, "unmapped", reason="empty-artifact"))
        return tuple(result)


class SourceMapBuilder:
    """Record text as it is emitted, rather than infer provenance by diffing."""

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._entries: list[tuple[int, int, MappingKind, SourceSpan | None, str | None]] = []
        self._inputs: dict[SourceRef, SourceSnapshot] = {}
        self._length = 0

    def _append(self, text: str, kind: MappingKind, original: SourceSpan | None,
                reason: str | None) -> None:
        if text:
            self._entries.append((self._length, self._length + len(text), kind, original, reason))
            self._parts.append(text)
            self._length += len(text)

    def add_source(self, source: SourceSnapshot, *, normalize_newlines: bool = False) -> None:
        self._inputs[source.ref] = source  # Include even empty referenced inputs.
        cursor = 0
        if normalize_newlines:
            for match in re.finditer(r"\r\n|\r", source.text):
                self._append(source.text[cursor:match.start()], "exact",
                             source.span(cursor, match.start()), None)
                self._append("\n", "newline", source.span(match.start(), match.end()), None)
                cursor = match.end()
        self._append(source.text[cursor:], "exact", source.span(cursor), None)

    def add_synthetic(self, text: str, reason: str) -> None:
        if not isinstance(reason, str) or not reason:
            raise ValueError("synthetic text requires a reason")
        self._append(text, "synthetic", None, reason)

    def add_unmapped(self, text: str, reason: str) -> None:
        if not isinstance(reason, str) or not reason:
            raise ValueError("unmapped text requires a reason")
        self._append(text, "unmapped", None, reason)

    def build(self, uri: str, *, path: Path | None = None) -> SourceMap:
        artifact = SourceSnapshot(uri, "".join(self._parts), path)
        mappings = tuple(SourceMapping(artifact.span(a, b), kind, original, reason)
                         for a, b, kind, original, reason in self._entries)
        return SourceMap(artifact, tuple(self._inputs.values()), mappings)
