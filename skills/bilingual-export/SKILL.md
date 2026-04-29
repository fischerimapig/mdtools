---
name: bilingual-export
description: "Use this skill when producing language-specific Markdown or QMD outputs from bilingual Pandoc fenced divs with langfilter, especially documents using ::: {lang=en} and ::: {lang=ja}, requests for English/Japanese exports, shared bilingual manuscripts, or pipelines that feed glossary resolution after language filtering."
---

# Bilingual Export

## Purpose

Use `mdtools langfilter` to export one language from a bilingual Markdown/QMD source while preserving shared content.

Prefer the unified entrypoint:

```bash
mdtools langfilter --help
```

Inside the mdtools repository, `uv run mdtools langfilter ...` is equivalent. The direct `langfilter` command is a compatibility shortcut.

## Supported Pattern

Language-specific content must be in Pandoc fenced divs:

```markdown
::: {lang=en}
English text.
:::

::: {.note lang=ja}
Japanese text.
:::
```

Shared content outside `lang=...` fenced divs remains in every output.

Code fences are protected. A `:::` sequence inside fenced code is not treated as a language block.

Opening fenced-div lines must be standalone. A line with trailing body text after `::: {lang=en}` is treated as a normal line, not as a language block opener.

## Standard Workflow

Generate each target language explicitly:

```bash
mdtools langfilter filter --lang en manuscript.qmd -o manuscript.en.qmd
mdtools langfilter filter --lang ja manuscript.qmd -o manuscript.ja.qmd
```

Use `both` to preserve the original content shape:

```bash
mdtools langfilter filter --lang both manuscript.qmd -o manuscript.both.qmd
```

For pipelines, stdin/stdout is supported:

```bash
mdtools mdsplit compose manuscript_sections/hierarchy.json | mdtools langfilter filter --lang en > manuscript.en.qmd
```

## With Glossary Markers

Run language filtering before glossary resolution so term names and descriptions resolve in the selected language:

```bash
mdtools langfilter filter --lang en manuscript.qmd | mdtools glossary resolve --lang en -f defs.yaml > manuscript.en.qmd
mdtools langfilter filter --lang ja manuscript.qmd | mdtools glossary resolve --lang ja -f defs.yaml > manuscript.ja.qmd
```

Do not expect `glossary` to interpret `lang=...` blocks. Treat `langfilter` as the language-selection stage.

## Validation

When changing bilingual source structure:

```bash
mdtools langfilter filter --lang en manuscript.qmd > /tmp/en.qmd
mdtools langfilter filter --lang ja manuscript.qmd > /tmp/ja.qmd
mdtools langfilter filter --lang both manuscript.qmd > /tmp/both.qmd
```

Review the outputs for missing shared content, unmatched fences, and accidental trailing text on opening div lines.

## References

When working in the mdtools repository, consult:

- `README.md` for the full document pipeline.
- `langfilter/README.md` for syntax variants and edge cases.
