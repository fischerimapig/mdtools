---
name: glossary-markers
description: "Use this skill when validating, listing, or resolving glossary markers in Markdown or QMD with mdtools glossary, including term, const, symbol, and .glossary block markers, definition files in JSON or YAML, missing-id checks, language-specific term resolution, or pipelines after langfilter."
---

# Glossary Markers

## Purpose

Use `mdtools glossary` to replace Markdown/QMD markers with definitions from JSON/YAML files and to validate marker coverage.

Prefer the unified entrypoint:

```bash
mdtools glossary --help
```

Inside the mdtools repository, `uv run mdtools glossary ...` is equivalent. The direct `glossary` command is a compatibility shortcut.

## Marker Forms

Inline markers use Pandoc bracketed spans:

```markdown
[]{.term id=unit}
[]{.term id=unit field=description}
[]{.const id=EMAX_WIDTH}
[]{.symbol id=D}
```

Glossary-list blocks use fenced divs:

```markdown
::: {.glossary filter=term}
:::
```

Code fences are protected. Marker-looking text inside code fences is not resolved.

## Definition Files

Definitions are JSON or YAML files with an `entries` list. Entries have:

- `id`
- `kind`, one of `term`, `const`, or `symbol`
- kind-specific fields such as `names`, `description`, `abbr`, `value`, or `rtl_macro`

Multiple `-f` files may be supplied. Later files override earlier entries with the same `id`, with a warning.

## Standard Workflow

List definitions first:

```bash
mdtools glossary list -f defs.yaml
mdtools glossary list -f defs.yaml --kind term --format json
```

Verify all document markers before resolving:

```bash
mdtools glossary verify manuscript.qmd -f defs.yaml
```

Resolve for the target language:

```bash
mdtools glossary resolve manuscript.qmd --lang en -f defs.yaml -o manuscript.resolved.qmd
mdtools glossary resolve manuscript.qmd --lang ja -f defs.yaml -o manuscript.resolved.ja.qmd
```

The default missing-id behavior is strict: unresolved IDs make `resolve` fail. Use `--on-missing warn` or `--on-missing keep` only when preserving incomplete drafts is intentional.

## With Bilingual Documents

Run `langfilter` before `glossary`:

```bash
mdtools langfilter filter --lang en manuscript.qmd | mdtools glossary resolve --lang en -f defs.yaml > manuscript.en.qmd
mdtools langfilter filter --lang ja manuscript.qmd | mdtools glossary resolve --lang ja -f defs.yaml > manuscript.ja.qmd
```

`glossary` passes `lang=...` fenced divs through. It does not choose language blocks by itself.

## Review

Use `verify` in CI or pre-commit checks because it reports all missing references and exits nonzero.

After `resolve`, inspect:

- Wrong marker class, such as `.term` pointing to a `const` entry.
- Unsupported `field` values.
- Missing `names.<lang>` or `description.<lang>` values.
- Empty rendered glossary blocks caused by filters that match no entries.

## References

When working in the mdtools repository, consult:

- `README.md` for the full document pipeline.
- `glossary/README.md` for schema details and command examples.
- `docs/glossary/README.md` for the repository's own glossary definitions.
