"""Output formatting for ``glossary list``."""

from __future__ import annotations

from typing import Iterable

from mdtools.core.io import dumps_json

from .loader import Entry


def filter_entries(
    entries: dict[str, Entry], kind: str | None
) -> list[Entry]:
    items = list(entries.values())
    if kind is not None:
        items = [e for e in items if e.kind == kind]
    items.sort(key=lambda e: (e.kind, e.id))
    return items


def format_text(entries: Iterable[Entry]) -> str:
    entries = list(entries)
    if not entries:
        return ""

    rows: list[tuple[str, str, str, str]] = []
    for e in entries:
        names = e.get("names") or {}
        name_en = names.get("en", "") if isinstance(names, dict) else ""
        name_ja = names.get("ja", "") if isinstance(names, dict) else ""

        if e.kind == "const":
            display = str(e.get("value", ""))
        elif e.kind == "symbol":
            display = e.get("rtl_macro") or ""
        else:
            display = name_en or name_ja or ""

        rows.append((e.id, e.kind, display, name_ja))

    widths = [
        max(len(r[0]) for r in rows + [("id", "", "", "")]),
        max(len(r[1]) for r in rows + [("", "kind", "", "")]),
        max(len(r[2]) for r in rows + [("", "", "name/value", "")]),
    ]

    header = f"{'id':<{widths[0]}}  {'kind':<{widths[1]}}  {'name/value':<{widths[2]}}  ja"
    sep = "-" * len(header)
    lines = [header, sep]
    for r in rows:
        lines.append(
            f"{r[0]:<{widths[0]}}  {r[1]:<{widths[1]}}  {r[2]:<{widths[2]}}  {r[3]}"
        )
    return "\n".join(lines) + "\n"


def format_json(entries: Iterable[Entry]) -> str:
    out = []
    for e in entries:
        obj = {"id": e.id, "kind": e.kind, **e.data}
        out.append(obj)
    return dumps_json(out) + "\n"
