from __future__ import annotations

import re
from pathlib import Path

from .model import DivBlock, Embed, FigureBlock, RefLink
from mdtools.core.io import write_json

FIGURE_RE = re.compile(r"<figure\b[^>]*>.*?</figure>", re.DOTALL)
DIV_RE = re.compile(r"<div\b[^>]*>.*?</div>", re.DOTALL)
A_RE = re.compile(r"<a\s+[^>]*href=\"#([^\"]+)\"[^>]*>.*?</a>", re.DOTALL)
ID_RE = re.compile(r'\bid\s*=\s*"([^"]+)"')
CLASS_RE = re.compile(r'\bclass\s*=\s*"([^"]+)"')
EMBED_RE = re.compile(r"<embed\s+[^>]*src=\"([^\"]+)\"[^>]*/?>", re.DOTALL)
STYLE_WIDTH_RE = re.compile(r"width\s*:\s*([0-9]+(?:\.[0-9]+)?)%")
FIGCAP_RE = re.compile(r"<figcaption\b[^>]*>(.*?)</figcaption>", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
REF_TYPE_RE = re.compile(r'data-reference-type\s*=\s*"([^"]+)"')


def _line_of_pos(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _extract_caption(fig_raw: str) -> str | None:
    m = FIGCAP_RE.search(fig_raw)
    if not m:
        return None
    cap = TAG_RE.sub("", m.group(1))
    return " ".join(cap.split())


def _parse_embeds(fig_raw: str) -> list[Embed]:
    embeds: list[Embed] = []
    for m in EMBED_RE.finditer(fig_raw):
        tag = m.group(0)
        src = m.group(1)
        wm = STYLE_WIDTH_RE.search(tag)
        width = float(wm.group(1)) if wm else None
        embeds.append(Embed(src=src, width_pct=width))
    return embeds


def _figure_kind(fig_raw: str, embeds: list[Embed]) -> str:
    has_code = "<pre><code>" in fig_raw
    if embeds and not has_code:
        return "image"
    if has_code and not embeds:
        return "code"
    if (not embeds) and (not has_code):
        return "caption_only"
    return "mixed"


def build_inventory(input_path: str | Path, output_path: str | Path | None = None) -> dict:
    p = Path(input_path)
    text = p.read_text(encoding="utf-8")

    figures: list[FigureBlock] = []
    divs: list[DivBlock] = []
    refs: list[RefLink] = []

    for m in FIGURE_RE.finditer(text):
        raw = m.group(0)
        idm = ID_RE.search(raw)
        embeds = _parse_embeds(raw)
        kind = _figure_kind(raw, embeds)
        figures.append(
            FigureBlock(
                start=_line_of_pos(text, m.start()),
                end=_line_of_pos(text, m.end()),
                raw=raw,
                id=idm.group(1) if idm else None,
                caption=_extract_caption(raw),
                embeds=embeds,
                kind=kind,  # type: ignore[arg-type]
            )
        )

    for m in DIV_RE.finditer(text):
        raw = m.group(0)
        idm = ID_RE.search(raw)
        cm = CLASS_RE.search(raw)
        div_class = cm.group(1) if cm else None
        kind = "other"
        if div_class == "screen":
            kind = "screen"
        elif div_class == "description":
            kind = "description"
        elif idm and idm.group(1) in {"physinterface", "logicinterface", "lmm-operation", "alu-operation"}:
            kind = "table_wrapper"
        divs.append(
            DivBlock(
                start=_line_of_pos(text, m.start()),
                end=_line_of_pos(text, m.end()),
                raw=raw,
                div_id=idm.group(1) if idm else None,
                div_class=div_class,
                kind=kind,  # type: ignore[arg-type]
            )
        )

    for m in A_RE.finditer(text):
        raw = m.group(0)
        rtm = REF_TYPE_RE.search(raw)
        refs.append(
            RefLink(
                start=_line_of_pos(text, m.start()),
                end=_line_of_pos(text, m.end()),
                raw=raw,
                target_id=m.group(1),
                ref_type=rtm.group(1) if rtm else None,
            )
        )

    needs_manual: list[dict] = []
    for f in figures:
        if f.kind in {"caption_only", "mixed"}:
            needs_manual.append(
                {
                    "type": f.kind,
                    "id": f.id,
                    "line": f.start,
                    "reason": "auto-conversion may be unsafe",
                }
            )

    counts = {
        "figure_total": len(figures),
        "figure_image": sum(1 for f in figures if f.kind == "image"),
        "figure_code": sum(1 for f in figures if f.kind == "code"),
        "figure_caption_only": sum(1 for f in figures if f.kind == "caption_only"),
        "figure_mixed": sum(1 for f in figures if f.kind == "mixed"),
        "div_total": len(divs),
        "div_screen": sum(1 for d in divs if d.kind == "screen"),
        "div_description": sum(1 for d in divs if d.kind == "description"),
        "div_table_wrapper": sum(1 for d in divs if d.kind == "table_wrapper"),
        "ref_links": len(refs),
    }

    inv = {
        "file": str(p),
        "counts": counts,
        "figures": [
            {
                "line_start": f.start,
                "line_end": f.end,
                "id": f.id,
                "kind": f.kind,
                "caption": f.caption,
                "embeds": [{"src": e.src, "width_pct": e.width_pct} for e in f.embeds],
            }
            for f in figures
        ],
        "divs": [
            {
                "line_start": d.start,
                "line_end": d.end,
                "id": d.div_id,
                "class": d.div_class,
                "kind": d.kind,
            }
            for d in divs
        ],
        "refs": [
            {
                "line_start": r.start,
                "line_end": r.end,
                "target_id": r.target_id,
                "ref_type": r.ref_type,
            }
            for r in refs
        ],
        "needs_manual": needs_manual,
    }

    if output_path:
        write_json(output_path, inv)

    return inv
