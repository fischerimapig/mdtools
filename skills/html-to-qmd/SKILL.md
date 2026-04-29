---
name: html-to-qmd
description: "Use this skill when converting pandoc-derived or HTML-heavy Markdown into Quarto-friendly Markdown or QMD with mdhtml-rewrite, including EPS image conversion, inventory reports, figure rewrites, screen div rewrites, table wrapper rewrites, reference-link cleanup, or requests that mention mdtools rewrite."
---

# HTML to QMD

## Purpose

Use `mdtools rewrite` to inspect and rewrite HTML-ish Markdown into Quarto-friendly Markdown/QMD.

Prefer the unified entrypoint:

```bash
mdtools rewrite --help
```

Inside the mdtools repository, `uv run mdtools rewrite ...` is equivalent. The direct `mdhtml-rewrite` command is a compatibility shortcut.

## Standard Workflow

1. Convert EPS assets when the document references EPS/PS/PDF figures.
2. Build an inventory before rewriting.
3. Review `needs_manual` and counts in the inventory.
4. Rewrite with the inventory and a report.
5. Inspect the report and diff the output.

```bash
mdtools rewrite convert figures --dry-run
mdtools rewrite convert figures --report convert-report.json
mdtools rewrite inventory input.md -o inventory.json
mdtools rewrite rewrite input.md -o output.qmd --inventory inventory.json --report rewrite-report.json
```

Skip `convert` when the document already references display-friendly images such as PNG, JPG, SVG, GIF, or WebP.

## EPS Conversion

Use `--dry-run` first. `convert` only scans `.eps` files directly under the target directory.

```bash
mdtools rewrite convert figures --dry-run
mdtools rewrite convert figures --format svg --report convert-svg-report.json
mdtools rewrite convert figures --format png --dpi 300 --report convert-png-report.json
```

External tools matter:

- Ghostscript (`gs`) is required for PNG conversion and fallback.
- `dvisvgm` is used for vector EPS to SVG.
- Auto mode prefers SVG for vector EPS when `dvisvgm` is available, otherwise PNG.
- Existing newer targets are skipped unless `--force` is used.

Do not install missing external tools without user approval.

## Inventory First

Run inventory before rewrite whenever possible:

```bash
mdtools rewrite inventory input.md -o inventory.json
```

Use it to identify:

- Figures that are images, code figures, caption-only figures, or mixed figures.
- Screen divs and known table wrapper divs.
- Reference links with `data-reference-type`.
- `needs_manual` items where automatic conversion may be unsafe.

## Rewrite Behavior

`rewrite` converts the currently supported patterns:

- Image figures to Markdown image syntax, using sibling SVG/PNG when available.
- Code figures to fenced code blocks with captions.
- `<div class="screen">` blocks to fenced code blocks.
- Known table wrapper divs to captioned Markdown blocks.
- Pandoc-style HTML reference links to Markdown/Quarto references.
- Empty HTML comments are removed.

Prefer PNG/SVG sibling files for EPS/PS/PDF references. Use `--no-prefer-png` only when preserving original references is intentional.

## Review

After rewrite:

```bash
git diff -- input.md output.qmd
```

Check captions, figure labels, table captions, code blocks, and unresolved `needs_manual` entries. Treat inventory/report JSON as review aids, not as proof that the document needs no manual pass.

## References

When working in the mdtools repository, consult:

- `README.md` for the overall conversion pipeline.
- `mdhtml_rewrite/README.md` for supported rewrites and image-format rules.
