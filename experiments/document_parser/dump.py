"""Review serialization; never used as a parser-to-projection transport."""
from __future__ import annotations

from .model import DocumentParse


def document_dict(document: DocumentParse, *, trace: bool = False) -> dict:
    index = document.index

    def location(span):
        if span is None:
            return None
        origin = index.span(span)
        value = {"bytes": [span.start, span.end],
                 "start": [origin.start.line, origin.start.column],
                 "end": [origin.end.line, origin.end.column]}
        if trace:
            value["raw"] = document.slice(span)
        return value

    rows = []
    pending = [(n, None) for n in reversed(document.blocks)]
    while pending:
        node, parent = pending.pop()
        ordinal = len(rows)
        rows.append({
            "node": ordinal, "parent": parent, "kind": node.kind,
            "span": location(node.span), "header": location(node.header),
            "body": location(node.body), "closing": location(node.closing),
            "closure": node.closure, "header_valid": node.valid,
            "marker": node.marker, "info": node.info, "info_span": location(node.info_span),
            "attributes": [{"kind": a.kind, "name": a.name, "value": a.value,
                            "span": location(a.span), "value_span": location(a.value_span)}
                           for a in node.attributes],
            "inlines": [{"kind": i.kind, "span": location(i.span),
                         "target": location(i.target), "title": location(i.title),
                         "reference": i.reference} for i in node.inlines],
        })
        pending.extend((child, ordinal) for child in reversed(node.children))
    return {
        "source": {"uri": document.source.ref.uri, "snapshot": document.source.ref.snapshot,
                   "bytes": index.byte_length},
        "profile": document.profile, "model_version": document.model_version,
        "status": document.status,
        "coverage": [{"span": location(c.span), "state": c.state, "reason": c.reason}
                     for c in document.coverage],
        "notices": [{"code": n.code, "message": n.message, "span": location(n.span)}
                    for n in document.notices],
        "references": [{"label": r.label, "span": location(r.span),
                        "destination": location(r.destination), "title": location(r.title)}
                       for r in document.references],
        "nodes": rows,
    }
