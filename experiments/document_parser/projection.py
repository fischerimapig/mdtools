"""Review-only requirement candidates from Document; no specification checks.

No regex/scanner and no access to the entire manuscript are needed. Consumers
read only the explicit ranges of attributes, body leaves and code fences.
"""
from __future__ import annotations

from dataclasses import dataclass

from .model import ByteRange, DocumentParse, Node, walk


@dataclass(frozen=True)
class BodySummary:
    language: str | None
    span: ByteRange
    text: str


@dataclass(frozen=True)
class ModelSummary:
    span: ByteRange
    body: ByteRange
    info: str
    direct: bool
    closure: str


@dataclass(frozen=True)
class RequirementSummary:
    id: str | None
    ids: tuple[str, ...]
    span: ByteRange
    header_valid: bool
    closure: str
    bodies: tuple[BodySummary, ...]
    mdspec: tuple[ModelSummary, ...]


@dataclass(frozen=True)
class ReviewSummary:
    status: str
    candidates: tuple[RequirementSummary, ...]


def _candidate(document: DocumentParse, node: Node) -> bool:
    if node.kind != "div":
        return False
    for attr in node.attributes:
        if attr.kind == "class" and attr.value == "requirement":
            return True
        if attr.kind == "invalid":
            raw = document.slice(attr.span)
            suffix = raw.removeprefix(".requirement")
            if suffix != raw and (not suffix or not (suffix[0].isascii()
                    and (suffix[0].isalnum() or suffix[0] in "_.-"))):
                return True
    return False


def summarize_requirements(document: DocumentParse) -> ReviewSummary:
    """Keep every candidate occurrence, including ambiguous/malformed headers.

    This does not reject unknown specification versions, validate IDs or JSON,
    resolve references, or classify LocalAnalysis/Graph/IR completeness.
    """
    candidates = []
    for node in walk(document.blocks):
        if not _candidate(document, node):
            continue
        ids = tuple(a.value for a in node.attributes if a.kind == "id")
        body_ranges = []
        models = []
        pending = [(child, None, True) for child in reversed(node.children)]
        while pending:
            child, language, direct = pending.pop()
            if child.kind == "div":
                if _candidate(document, child):
                    # It has its own candidate, without duplicating its body.
                    continue
                langs = [a for a in child.attributes if a.name == "lang"
                         and a.kind in ("attribute", "invalid")]
                if langs:
                    language = (langs[0].value if len(langs) == 1
                                and langs[0].kind == "attribute" else "<ambiguous>")
                pending.extend((nested, language, False) for nested in reversed(child.children))
            elif child.kind == "code_fence" and child.info.startswith("mdspec"):
                models.append(ModelSummary(child.span, child.body, child.info, direct, child.closure))
            else:
                if (body_ranges and body_ranges[-1][0] == language
                        and body_ranges[-1][1].end == child.span.start):
                    previous = body_ranges[-1][1]
                    body_ranges[-1] = (language, ByteRange(previous.start, child.span.end))
                else:
                    body_ranges.append((language, child.span))
        bodies = []
        for language, span in body_ranges:
            text = document.slice(span)
            if text.strip():
                bodies.append(BodySummary(language, span, text))
        candidates.append(RequirementSummary(ids[0] if len(ids) == 1 else None, ids,
                          node.span, node.valid, node.closure, tuple(bodies), tuple(models)))
    return ReviewSummary(document.status, tuple(candidates))


def summary_dict(document: DocumentParse) -> dict:
    """Portable review wire format, explicitly not SpecIR."""
    summary = summarize_requirements(document)

    def span(value):
        return [value.start, value.end]

    return {
        "status": summary.status,
        "semantic_checks": {name: "not-run" for name in (
            "json", "references", "expressions", "requirement_validation")},
        "candidates": [
            {"id": c.id, "ids": list(c.ids), "span": span(c.span),
             "header_valid": c.header_valid, "closure": c.closure,
             "bodies": [{"language": b.language, "span": span(b.span), "text": b.text}
                        for b in c.bodies],
             "mdspec": [{"span": span(m.span), "body": span(m.body), "info": m.info,
                         "direct": m.direct, "closure": m.closure} for m in c.mdspec]}
            for c in summary.candidates],
    }
