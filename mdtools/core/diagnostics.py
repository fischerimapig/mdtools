"""Shared immutable diagnostics and deterministic v1 text/JSON rendering.

No analysis, filesystem reads, exit-code policy, or backend/protocol dependencies.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Literal

from .source import SourceMapping, SourceRef, SourceSnapshot, SourceSpan

Severity = Literal["error", "warning", "info", "hint"]
Category = Literal["user", "unsupported", "unknown", "not-run", "tool-error"]
CheckStatus = Literal["not-run", "passed", "failed", "unknown", "unsupported", "error"]
SCHEMA_VERSION = 1
_IDENTIFIER = re.compile(r"[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+\Z")


def _text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    value.encode("utf-8")  # Reject lone surrogates before either renderer writes.


def _identifier(value: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError("identifier must be a lowercase dotted/hyphenated code")


def _tuple(value: tuple, cls: type) -> None:
    if not isinstance(value, tuple) or any(not isinstance(v, cls) for v in value):
        raise ValueError(f"expected a tuple of {cls.__name__}")


@dataclass(frozen=True)
class DiagnosticLocation:
    """Provenance metadata around an existing SourceSpan, never new coordinates.

    Only 'original' identifies a manuscript. Synthetic/unmapped spans, when
    available, identify the generated artifact. 'none' has no span or reason.
    """

    kind: Literal["original", "synthetic", "unmapped", "none"] = "none"
    span: SourceSpan | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.span is not None and not isinstance(self.span, SourceSpan):
            raise ValueError("location span must be a SourceSpan")
        if self.kind == "original":
            if self.span is None or self.reason is not None:
                raise ValueError("original location requires a span and no reason")
        elif self.kind in ("synthetic", "unmapped"):
            _text(self.reason, "location reason")
        elif self.kind != "none" or self.span is not None or self.reason is not None:
            raise ValueError("none location must have no span or reason")

    @classmethod
    def from_mapping(cls, mapping: SourceMapping) -> DiagnosticLocation:
        if mapping.original is not None:
            return cls("original", mapping.original)
        return cls(mapping.kind, mapping.generated, mapping.reason)


@dataclass(frozen=True)
class RelatedLocation:
    message: str
    location: DiagnosticLocation
    requirement_id: str | None = None

    def __post_init__(self) -> None:
        _text(self.message, "related message")
        if not isinstance(self.location, DiagnosticLocation):
            raise ValueError("related location requires DiagnosticLocation")
        if self.requirement_id is not None:
            _text(self.requirement_id, "requirement_id")


@dataclass(frozen=True)
class Evidence:
    """Producer-defined kind and human-readable fact/assumption, optionally located.

    Strings may contain JSON or counterexample details; core interprets no logic.
    """

    kind: str
    message: str
    location: DiagnosticLocation | None = None

    def __post_init__(self) -> None:
        _identifier(self.kind)
        _text(self.message, "evidence message")
        if self.location is not None and not isinstance(self.location, DiagnosticLocation):
            raise ValueError("evidence location requires DiagnosticLocation")


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: Severity
    category: Category
    message: str
    primary: DiagnosticLocation = field(default_factory=DiagnosticLocation)
    related: tuple[RelatedLocation, ...] = ()
    requirement_id: str | None = None
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.code)
        if self.severity not in ("error", "warning", "info", "hint"):
            raise ValueError("unknown severity")
        if self.category not in ("user", "unsupported", "unknown", "not-run", "tool-error"):
            raise ValueError("unknown diagnostic category")
        _text(self.message, "message")
        if not isinstance(self.primary, DiagnosticLocation):
            raise ValueError("primary requires DiagnosticLocation")
        _tuple(self.related, RelatedLocation)
        _tuple(self.evidence, Evidence)
        if self.requirement_id is not None:
            _text(self.requirement_id, "requirement_id")


@dataclass(frozen=True)
class CheckResult:
    """Explicit result for a producer-defined check/scope, independent of severity."""

    check_id: str
    status: CheckStatus
    reason: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.check_id)
        if self.status not in ("not-run", "passed", "failed", "unknown", "unsupported", "error"):
            raise ValueError("unknown check status")
        if self.status in ("not-run", "unknown", "unsupported", "error") or self.reason is not None:
            _text(self.reason, "check reason")


@dataclass(frozen=True)
class DiagnosticReport:
    diagnostics: tuple[Diagnostic, ...] = ()
    checks: tuple[CheckResult, ...] = ()
    sources: tuple[SourceSnapshot, ...] = ()

    def __post_init__(self) -> None:
        _tuple(self.diagnostics, Diagnostic)
        _tuple(self.checks, CheckResult)
        _tuple(self.sources, SourceSnapshot)
        if len({c.check_id for c in self.checks}) != len(self.checks):
            raise ValueError("check IDs must be unique within a report")
        sources = {s.ref: s for s in self.sources}
        if len(sources) != len(self.sources):
            raise ValueError("duplicate source snapshot")
        for source in self.sources:
            _text(source.uri, "source URI")
            if source.path is not None:
                _text(str(source.path), "source path")
        for diagnostic in self.diagnostics:
            locations = (diagnostic.primary, *(r.location for r in diagnostic.related),
                         *(e.location for e in diagnostic.evidence if e.location is not None))
            for location in locations:
                if location.span is not None:
                    source = sources.get(location.span.source)
                    if source is None:
                        raise ValueError("location snapshot is missing from report")
                    source.offsets(location.span)


def _source(ref: SourceRef) -> dict:
    result = {"uri": ref.uri, "snapshot": ref.snapshot}
    if ref.path is not None:
        result["path"] = str(ref.path)
    return result


def _location(location: DiagnosticLocation) -> dict:
    result = {"kind": location.kind}
    if location.span is not None:
        span = location.span
        result["span"] = {
            "source": _source(span.source),
            "start": {"line": span.start.line, "column": span.start.column},
            "end": {"line": span.end.line, "column": span.end.column},
        }
    if location.reason is not None:
        result["reason"] = location.reason
    return result


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _diagnostic(diagnostic: Diagnostic) -> dict:
    related = []
    for item in diagnostic.related:
        entry = {"message": item.message, "location": _location(item.location)}
        if item.requirement_id is not None:
            entry["requirement_id"] = item.requirement_id
        related.append(entry)
    evidence = []
    for item in diagnostic.evidence:
        entry = {"kind": item.kind, "message": item.message}
        if item.location is not None:
            entry["location"] = _location(item.location)
        evidence.append(entry)
    result = {
        "code": diagnostic.code, "severity": diagnostic.severity,
        "category": diagnostic.category, "message": diagnostic.message,
        "primary": _location(diagnostic.primary),
        "related": sorted(related, key=_canonical),
        "evidence": sorted(evidence, key=_canonical),
    }
    if diagnostic.requirement_id is not None:
        result["requirement_id"] = diagnostic.requirement_id
    return result


def _diagnostic_key(item: dict) -> tuple:
    location = item["primary"]
    span = location.get("span")
    return (
        span is None, span["source"]["uri"] if span else "",
        span["start"]["line"] if span else 0, span["start"]["column"] if span else 0,
        item["code"], item.get("requirement_id", ""), _canonical(item),
    )


def report_to_dict(report: DiagnosticReport) -> dict:
    """Fresh JSON-compatible v1 value; snapshot text remains in the report only."""
    checks = []
    for check in sorted(report.checks, key=lambda c: c.check_id):
        item = {"check_id": check.check_id, "status": check.status}
        if check.reason is not None:
            item["reason"] = check.reason
        checks.append(item)
    return {
        "schema_version": SCHEMA_VERSION,
        "sources": sorted((_source(s.ref) for s in report.sources), key=_canonical),
        "checks": checks,
        "diagnostics": sorted((_diagnostic(d) for d in report.diagnostics), key=_diagnostic_key),
    }


def render_json(report: DiagnosticReport) -> str:
    return json.dumps(report_to_dict(report), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _quote(value: str) -> str:
    # Keep Japanese/emoji readable, escape controls, separators and bidi controls.
    quoted = json.dumps(value, ensure_ascii=False)
    return "".join(f"\\u{ord(c):04x}" if (ord(c) < 32 or 127 <= ord(c) <= 159
                   or c in "\u2028\u2029\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")
                   else c for c in quoted)


def _text_location(item: dict) -> str:
    result = f"kind={item['kind']}"
    if "span" in item:
        span = item["span"]
        result += " " + _text_source(span["source"])
        a, b = span["start"], span["end"]
        result += f" range=[{a['line']}:{a['column']},{b['line']}:{b['column']})"
    if "reason" in item:
        result += f" reason={_quote(item['reason'])}"
    return result


def _text_source(item: dict) -> str:
    result = f"uri={_quote(item['uri'])} snapshot={_quote(item['snapshot'])}"
    if "path" in item:
        result += f" path={_quote(item['path'])}"
    return result


def render_text(report: DiagnosticReport) -> str:
    data = report_to_dict(report)
    lines = [f"diagnostics schema_version={SCHEMA_VERSION}"]
    for source in data["sources"]:
        lines.append("source " + _text_source(source))
    for check in data["checks"]:
        line = f"check {check['check_id']} status={check['status']}"
        if "reason" in check:
            line += f" reason={_quote(check['reason'])}"
        lines.append(line)
    lines.append(f"diagnostic_count={len(data['diagnostics'])}")
    for item in data["diagnostics"]:
        lines.append(f"{item['code']} severity={item['severity']} category={item['category']}"
                     f" message={_quote(item['message'])}")
        if "requirement_id" in item:
            lines.append("  requirement_id=" + _quote(item["requirement_id"]))
        lines.append("  primary " + _text_location(item["primary"]))
        for related in item["related"]:
            line = "  related message=" + _quote(related["message"])
            if "requirement_id" in related:
                line += " requirement_id=" + _quote(related["requirement_id"])
            lines.append(line + " " + _text_location(related["location"]))
        for evidence in item["evidence"]:
            line = f"  evidence {evidence['kind']} message={_quote(evidence['message'])}"
            if "location" in evidence:
                line += " " + _text_location(evidence["location"])
            lines.append(line)
    return "\n".join(lines) + "\n"
