"""One-way orchestration: original index -> blocks -> owned inlines -> result."""
from __future__ import annotations

from dataclasses import replace

from mdtools.core.source import SourceSnapshot

from .blocks import parse_blocks
from .inline import parse_inlines
from .links import build_reference_lookup
from .model import (
    PROFILE, ByteRange, Coverage, DocumentParse, Limits, Notice, SourceIndex,
    validate_document, walk,
)


def _incomplete(coverage, missing):
    """Overlay disjoint inline owners on the block coverage partition."""
    if not missing:
        return coverage
    missing = sorted(missing, key=lambda item: item.span.start)
    points = sorted({p for item in (*coverage, *missing)
                     for p in (item.span.start, item.span.end)})
    original = gap = 0
    result = []
    for a, b in zip(points, points[1:]):
        while original + 1 < len(coverage) and coverage[original].span.end <= a:
            original += 1
        while gap < len(missing) and missing[gap].span.end <= a:
            gap += 1
        state = coverage[original]
        if gap < len(missing) and missing[gap].span.start <= a < missing[gap].span.end:
            state = missing[gap]
        if result and result[-1].state == state.state and result[-1].reason == state.reason:
            result[-1] = Coverage(ByteRange(result[-1].span.start, b), state.state, state.reason)
        else:
            result.append(Coverage(ByteRange(a, b), state.state, state.reason))
    return tuple(result)


def parse_document(source: SourceSnapshot, *, profile: str = PROFILE,
                   limits: Limits = Limits()) -> DocumentParse:
    """Parse one snapshot; never read a path or fall back to a legacy parser.

    Invalid API argument types raise. Engine/invariant exceptions are reported
    as failed with their reason and original source retained. Syntax notices
    and capacity limits are separate from specification validity.
    """
    if not isinstance(source, SourceSnapshot) or not isinstance(limits, Limits):
        raise TypeError("parse_document requires SourceSnapshot and Limits")
    if not isinstance(profile, str):
        raise TypeError("profile must be a string")
    index = SourceIndex(source)
    whole = ByteRange(0, index.byte_length)

    def unavailable(code, message, status="rejected"):
        return DocumentParse(index, (), (), (Notice(code, message, whole),),
                             (Coverage(whole, "unparsed", message),) if whole.end else (),
                             status, profile)

    if profile != PROFILE:
        return unavailable("document.profile", "Unknown prototype profile: " + profile)
    if index.byte_length > limits.max_bytes:
        return unavailable("document.limit.bytes", f"Input exceeds {limits.max_bytes} bytes")

    blocks, references, coverage, notices = (), (), (), []
    verified_blocks, verified_references = (), ()
    verified_notices = ()
    try:
        result = parse_blocks(index, limits)
        blocks, references = result.blocks, result.references
        reference_lookup = build_reference_lookup(references)
        coverage, notices = result.coverage, list(result.notices)
        status = result.status
        validate_document(DocumentParse(index, blocks, references, tuple(notices), coverage, status, profile))
        verified_blocks, verified_references = blocks, references
        verified_notices = tuple(notices)
        ordered = list(walk(blocks))
        remaining = limits.max_nodes - len(ordered)
        replacements = {}
        missing = []
        for node in ordered:
            if node.kind not in ("paragraph", "heading") or node.body.start == node.body.end:
                continue
            if remaining <= 0:
                message = "Document node budget exhausted before inline analysis"
                notices.append(Notice("document.limit.nodes", message, node.body))
                missing.append(Coverage(node.body, "unparsed", message))
                status = "partial"
                continue
            inline = parse_inlines(index, node.body, reference_lookup,
                                   replace(limits, max_nodes=remaining))
            remaining -= len(inline.inlines)
            replacements[id(node)] = replace(node, inlines=inline.inlines)
            notices.extend(inline.notices)
            if not inline.complete:
                missing.append(Coverage(node.body, "unparsed", "Inline analysis did not finish"))
                status = "partial"
        # Freeze enriched ancestors in postorder. Raw text and untouched leaves
        # are shared; there is only one persistent document tree.
        for node in reversed(ordered):
            changed = replacements.get(id(node), node)
            children = tuple(replacements.get(id(child), child) for child in node.children)
            if any(a is not b for a, b in zip(children, node.children)):
                changed = replace(changed, children=children)
            replacements[id(node)] = changed
        blocks = tuple(replacements[id(node)] for node in blocks)
        document = DocumentParse(index, blocks, references, tuple(notices),
                                 _incomplete(coverage, missing), status, profile)
        validate_document(document)
        return document
    except Exception as exc:
        # This is the explicit execution boundary, not a semantic recovery rule.
        # Keep available block structures, but make no coverage/success claim.
        message = f"{type(exc).__name__}: {exc}"
        return DocumentParse(index, verified_blocks, verified_references,
                             (*verified_notices, Notice("document.execution", message, whole)),
                             (Coverage(whole, "unparsed", message),) if whole.end else (),
                             "failed", profile)
