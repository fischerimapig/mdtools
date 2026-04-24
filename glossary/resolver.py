"""Marker resolver for glossary.

Parses Pandoc bracketed spans (``[label]{.term id=unit}``) and
``.glossary`` fenced divs, substituting them with content from the
loaded :class:`Entry` registry. Code fences are skipped; ``{lang=...}``
fenced divs are passed through untouched (they belong to langfilter).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


from .loader import Entry
from mdtools.core.mdscan import (
    join_lines_preserving_trailing_newline,
    scan_md_lines_from_list,
    split_text_preserving_trailing_newline,
)


# ── Regex patterns ─────────────────────────────────────────────────

# Pandoc bracketed span:  [label]{.class key=value key="value"}
SPAN_RE = re.compile(r"\[([^\[\]]*)\]\{([^{}]+)\}")

# Glossary fenced div (block-level only, whole line):
#   ::: {.glossary filter=term format=dl}
GLOSSARY_OPEN_RE = re.compile(r"^:::\s*\{\s*\.glossary\b([^}]*)\}\s*$")
FENCE_CLOSE_RE = re.compile(r"^:::\s*$")

# Attribute tokens inside span/div braces
ATTR_KV_RE = re.compile(r'(\w+)\s*=\s*("([^"]*)"|(\S+))')
ATTR_CLASS_RE = re.compile(r"\.(\S+)")


MARKER_CLASSES = frozenset({"term", "const", "symbol"})


# ── Attribute parsing ─────────────────────────────────────────────


@dataclass
class Attrs:
    classes: list[str]
    kv: dict[str, str]

    @property
    def marker_class(self) -> str | None:
        for cls in self.classes:
            if cls in MARKER_CLASSES:
                return cls
        return None


def parse_attrs(s: str) -> Attrs:
    """Parse the inside of ``{...}`` in a Pandoc span or fenced div."""
    classes = ATTR_CLASS_RE.findall(s)
    kv: dict[str, str] = {}
    for m in ATTR_KV_RE.finditer(s):
        key = m.group(1)
        value = m.group(3) if m.group(3) is not None else m.group(4)
        kv[key] = value
    return Attrs(classes=classes, kv=kv)


# ── Resolution of one marker to text ──────────────────────────────


class ResolveError(Exception):
    """Raised when a marker cannot be resolved."""


def _get_name(entry: Entry, lang: str) -> str | None:
    names = entry.get("names")
    if isinstance(names, dict):
        v = names.get(lang)
        if isinstance(v, str):
            return v
    return None


def _get_description(entry: Entry, lang: str) -> str | None:
    desc = entry.get("description")
    if isinstance(desc, dict):
        v = desc.get(lang)
        if isinstance(v, str):
            return v
    return None


def _format_value(v: object) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def resolve_marker(
    entry: Entry, attrs: Attrs, lang: str, label: str = ""
) -> str:
    """Render a single marker to its replacement text.

    ``label`` (the text inside ``[...]``) overrides the default rendering
    when non-empty, matching Pandoc's behaviour where the bracketed text
    is preserved.
    """
    if label:
        return label

    field = attrs.kv.get("field")

    if entry.kind == "term":
        if field is None or field == "name":
            v = _get_name(entry, lang)
            if v is None:
                raise ResolveError(
                    f"term '{entry.id}' has no names.{lang}"
                )
            return v
        if field == "description":
            v = _get_description(entry, lang)
            if v is None:
                raise ResolveError(
                    f"term '{entry.id}' has no description.{lang}"
                )
            return v
        if field == "abbr":
            v = entry.get("abbr")
            if not isinstance(v, str):
                raise ResolveError(f"term '{entry.id}' has no abbr")
            return v
        if field == "id":
            return entry.id
        raise ResolveError(
            f"term '{entry.id}' does not support field '{field}'"
        )

    if entry.kind == "const":
        if field is None or field == "value":
            v = entry.get("value")
            if v is None:
                raise ResolveError(f"const '{entry.id}' has no value")
            return _format_value(v)
        if field == "description":
            v = _get_description(entry, lang)
            if v is None:
                raise ResolveError(
                    f"const '{entry.id}' has no description.{lang}"
                )
            return v
        if field == "id":
            return entry.id
        raise ResolveError(
            f"const '{entry.id}' does not support field '{field}'"
        )

    if entry.kind == "symbol":
        if field is None or field == "id":
            return entry.id
        if field == "description":
            v = _get_description(entry, lang)
            if v is None:
                raise ResolveError(
                    f"symbol '{entry.id}' has no description.{lang}"
                )
            return v
        if field == "rtl_macro":
            v = entry.get("rtl_macro")
            if not isinstance(v, str):
                raise ResolveError(f"symbol '{entry.id}' has no rtl_macro")
            return v
        raise ResolveError(
            f"symbol '{entry.id}' does not support field '{field}'"
        )

    raise ResolveError(f"unknown kind '{entry.kind}' for id '{entry.id}'")


# ── Glossary block rendering ──────────────────────────────────────


def render_glossary_block(
    entries: dict[str, Entry], attrs: Attrs, lang: str
) -> str:
    """Render a ``::: {.glossary ...} ... :::`` block to a Markdown table."""
    filt = attrs.kv.get("filter")
    fmt = attrs.kv.get("format", "table")

    selected = [
        e for e in entries.values()
        if filt is None or e.kind == filt
    ]
    selected.sort(key=lambda e: e.id)

    if fmt == "dl":
        return _render_definition_list(selected, lang)
    return _render_table(selected, lang)


def _render_table(entries: list[Entry], lang: str) -> str:
    if not entries:
        return ""

    lines: list[str] = []
    lines.append("| ID | Kind | Name | Description |")
    lines.append("|----|------|------|-------------|")
    for e in entries:
        name = _get_name(e, lang) or ""
        if e.kind == "const":
            v = e.get("value")
            name = _format_value(v) if v is not None else ""
        elif e.kind == "symbol":
            name = e.get("rtl_macro") or ""
        desc = _get_description(e, lang) or ""
        lines.append(f"| {e.id} | {e.kind} | {name} | {desc} |")
    return "\n".join(lines)


def _render_definition_list(entries: list[Entry], lang: str) -> str:
    parts: list[str] = []
    for e in entries:
        name = _get_name(e, lang) or e.id
        desc = _get_description(e, lang) or ""
        parts.append(f"{name}\n:   {desc}")
    return "\n\n".join(parts)


# ── Main state machine ────────────────────────────────────────────


MissingHandler = Callable[[str, Attrs, str], str]
"""Called for an unresolved marker: (id, attrs, original_marker_text) -> replacement."""


def _default_missing(eid: str, attrs: Attrs, original: str) -> str:
    raise ResolveError(f"undefined id '{eid}' referenced by marker {original!r}")


def _warn_missing(stream):
    def handler(eid: str, attrs: Attrs, original: str) -> str:
        print(f"warning: undefined id '{eid}' in marker {original!r}", file=stream)
        return original
    return handler


def _keep_missing(eid: str, attrs: Attrs, original: str) -> str:
    return original


def resolve(
    text: str,
    entries: dict[str, Entry],
    lang: str,
    on_missing: str = "error",
) -> str:
    """Resolve all markers in ``text`` using the loaded registry.

    Args:
        text: Markdown input.
        entries: Loaded registry from :func:`loader.load`.
        lang: "en" or "ja" (used for term name / description selection).
        on_missing: "error" | "warn" | "keep".
    """
    import sys

    if on_missing == "error":
        missing_handler: MissingHandler = _default_missing
    elif on_missing == "warn":
        missing_handler = _warn_missing(sys.stderr)
    elif on_missing == "keep":
        missing_handler = _keep_missing
    else:
        raise ValueError(f"invalid on_missing value: {on_missing!r}")

    lines, trailing = split_text_preserving_trailing_newline(text)
    out: list[str] = []
    in_glossary_block = False
    pending_block_attrs: Attrs | None = None

    def substitute_spans(line: str) -> str:
        def repl(m: re.Match[str]) -> str:
            label = m.group(1)
            attrs = parse_attrs(m.group(2))
            cls = attrs.marker_class
            if cls is None:
                return m.group(0)
            eid = attrs.kv.get("id")
            if not eid:
                return m.group(0)
            entry = entries.get(eid)
            if entry is None:
                return missing_handler(eid, attrs, m.group(0))
            if entry.kind != cls:
                raise ResolveError(
                    f"marker class '.{cls}' does not match entry kind "
                    f"'{entry.kind}' for id '{eid}'"
                )
            return resolve_marker(entry, attrs, lang, label)
        return SPAN_RE.sub(repl, line)

    for md in scan_md_lines_from_list(lines):
        line = md.text

        if md.in_code_fence:
            out.append(line)
            continue

        if in_glossary_block:
            if FENCE_CLOSE_RE.match(line):
                assert pending_block_attrs is not None
                rendered = render_glossary_block(entries, pending_block_attrs, lang)
                if rendered:
                    out.extend(rendered.split("\n"))
                pending_block_attrs = None
                in_glossary_block = False
            continue

        m_gloss = GLOSSARY_OPEN_RE.match(line)
        if m_gloss:
            pending_block_attrs = parse_attrs(m_gloss.group(1))
            in_glossary_block = True
            continue

        out.append(substitute_spans(line))

    return join_lines_preserving_trailing_newline(out, trailing)


def find_missing(
    text: str, entries: dict[str, Entry]
) -> list[tuple[int, str, str]]:
    """Scan ``text`` for marker references not present in ``entries``.

    Returns a list of ``(line_number, id, original_marker_text)``.
    Line numbers are 1-based. Code fences are skipped.
    """
    missing: list[tuple[int, str, str]] = []

    for md in scan_md_lines_from_list(text.split("\n")):
        if md.in_code_fence:
            continue
        for m in SPAN_RE.finditer(md.text):
            attrs = parse_attrs(m.group(2))
            if attrs.marker_class is None:
                continue
            eid = attrs.kv.get("id")
            if eid and eid not in entries:
                missing.append((md.lineno, eid, m.group(0)))
    return missing
