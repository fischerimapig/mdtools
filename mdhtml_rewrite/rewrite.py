from __future__ import annotations

import json
import re
from pathlib import Path

from .eps_png import resolve_display_image
from .inventory import build_inventory
from .refs import rewrite_ref_links

FIGURE_RE = re.compile(r"<figure\b[^>]*>.*?</figure>", re.DOTALL)
ID_RE = re.compile(r'\bid\s*=\s*"([^"]+)"')
EMBED_RE = re.compile(r"<embed\s+[^>]*src=\"([^\"]+)\"[^>]*/?>", re.DOTALL)
WIDTH_RE = re.compile(r"width\s*:\s*([0-9]+(?:\.[0-9]+)?)%")
FIGCAP_RE = re.compile(r"<figcaption\b[^>]*>(.*?)</figcaption>", re.DOTALL)
DIV_SCREEN_RE = re.compile(r'<div\s+class="screen">\s*(?:<pre><code>)?(.*?)(?:</code></pre>)?\s*</div>', re.DOTALL)
DIV_TABLE_RE = re.compile(r'<div\s+id="(physinterface|logicinterface|lmm-operation|alu-operation)">\s*(.*?)\s*</div>', re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
COMMENT_RE = re.compile(r"<!--\s*-->")


def _clean_caption(html_caption: str) -> str:
    cap = TAG_RE.sub("", html_caption)
    return " ".join(cap.split())


def _figure_to_md(raw: str, base_dir: Path, prefer_png: bool) -> tuple[str | None, dict | None]:
    idm = ID_RE.search(raw)
    fig_id = idm.group(1) if idm else None
    capm = FIGCAP_RE.search(raw)
    caption = _clean_caption(capm.group(1)) if capm else ""

    embeds = list(EMBED_RE.finditer(raw))
    has_code = "<pre><code>" in raw

    if has_code and not embeds:
        # code-as-figure, keep simple captioned code block
        code_m = re.search(r"<pre><code>(.*?)</code></pre>", raw, re.DOTALL)
        if not code_m:
            return None, {"type": "figure_code", "id": fig_id, "status": "skip_no_code"}
        code = code_m.group(1).strip("\n")
        label = f" {{#{fig_id}}}" if fig_id else ""
        out = f"```\n{code}\n```\n: {caption}{label}\n"
        return out, {"type": "figure_code", "id": fig_id, "status": "converted"}

    if not embeds:
        return None, {"type": "figure", "id": fig_id, "status": "skip_no_embed"}

    # image figure
    images: list[str] = []
    widths: list[str] = []
    statuses: list[str] = []
    for em in embeds:
        src = em.group(1)
        wm = WIDTH_RE.search(em.group(0))
        resolved, st = resolve_display_image(src, base_dir=base_dir, prefer_png=prefer_png)
        images.append(resolved)
        statuses.append(st)
        if wm:
            widths.append(wm.group(1).rstrip(".0") + "%")
        else:
            widths.append("")

    label = f"{{#{fig_id}}}" if fig_id else ""
    if len(images) == 1:
        attr = []
        if label:
            attr.append(label)
        if widths[0]:
            attr.append(f"width={widths[0]}")
        attr_str = f"{{{' '.join(attr)}}}" if attr else ""
        out = f"![{caption}]({images[0]}){attr_str}\n"
    else:
        # multi-image figure as small markdown list + final caption line
        lines = []
        for i, img in enumerate(images):
            w = f"{{width={widths[i]}}}" if widths[i] else ""
            lines.append(f"![]({img}){w}")
        out = "\n".join(lines) + "\n"
        if caption:
            out += f": {caption} {label}\n" if label else f": {caption}\n"

    return out, {
        "type": "figure_image",
        "id": fig_id,
        "status": "converted",
        "image_status": statuses,
        "images": images,
    }


def _rewrite_figures(text: str, base_dir: Path, prefer_png: bool) -> tuple[str, list[dict]]:
    report: list[dict] = []

    def repl(m: re.Match[str]) -> str:
        raw = m.group(0)
        out, rep = _figure_to_md(raw, base_dir, prefer_png)
        if rep:
            report.append(rep)
        return out if out is not None else raw

    return FIGURE_RE.sub(repl, text), report


def _rewrite_screen_divs(text: str) -> tuple[str, int]:
    count = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal count
        count += 1
        code = m.group(1).strip("\n")
        return f"```\n{code}\n```\n"

    return DIV_SCREEN_RE.sub(repl, text), count


def _rewrite_table_wrappers(text: str) -> tuple[str, int]:
    count = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal count
        count += 1
        div_id = m.group(1)
        inner = m.group(2).strip("\n")
        lines = inner.splitlines()
        if not lines:
            return inner
        title = lines[-1].strip()
        body = "\n".join(lines[:-1]).rstrip()
        if body:
            return f"{body}\n\n: {title} {{#{div_id}}}\n"
        return m.group(0)

    return DIV_TABLE_RE.sub(repl, text), count


def rewrite_file(
    input_path: str | Path,
    output_path: str | Path,
    inventory_path: str | Path | None = None,
    report_path: str | Path | None = None,
    prefer_png: bool = True,
) -> dict:
    p = Path(input_path)
    text = p.read_text(encoding="utf-8")

    if inventory_path and Path(inventory_path).exists():
        inventory = json.loads(Path(inventory_path).read_text(encoding="utf-8"))
    else:
        inventory = build_inventory(p)

    text, fig_report = _rewrite_figures(text, p.parent, prefer_png=prefer_png)
    text, screen_count = _rewrite_screen_divs(text)
    text, table_count = _rewrite_table_wrappers(text)
    text = rewrite_ref_links(text)
    text = COMMENT_RE.sub("", text)

    Path(output_path).write_text(text, encoding="utf-8")

    report = {
        "file": str(p),
        "output": str(output_path),
        "inventory_counts": inventory.get("counts", {}),
        "figures": fig_report,
        "screen_divs_converted": screen_count,
        "table_wrappers_converted": table_count,
    }

    if report_path:
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return report
