---
name: sectioned-docs
description: "Use this skill when authoring, editing, restructuring, or validating long Markdown or QMD documents with mdsplit section trees, especially files with a sibling *_sections/hierarchy.json, documents that should be edited section-by-section, or requests that mention mdsplit, round-trip verification, canonical Markdown, or section-managed documentation."
---

# Sectioned Docs

## Purpose

Use `mdtools mdsplit` to edit long Markdown/QMD documents as a section tree without losing the canonical single-file document.

Prefer the unified entrypoint:

```bash
mdtools mdsplit --help
```

Inside the mdtools repository, `uv run mdtools mdsplit ...` is equivalent. The direct `mdsplit` command is a compatibility shortcut.

## Decision Rule

Use the section workflow when any of these are true:

- The target `.md` or `.qmd` has a sibling `*_sections/hierarchy.json`.
- The document is large enough that editing one file is inefficient.
- The task changes document structure, section order, or heading hierarchy.
- The user asks for `mdsplit`, section-level editing, canonical Markdown, or round-trip checks.

Do not manually edit both the canonical document and its section files as independent sources. Pick one side, regenerate the other, then verify.

## Existing Section-Managed Document

1. Locate the hierarchy file, usually `<stem>_sections/hierarchy.json`.
2. Use `hierarchy.json` to identify the section file that owns the requested content.
3. Edit the section file only.
4. Compose the canonical file.
5. Verify references and round-trip equivalence.

```bash
mdtools mdsplit compose path/to/doc_sections/hierarchy.json -o path/to/doc.md
mdtools mdsplit verify path/to/doc_sections/hierarchy.json
mdtools mdsplit compose path/to/doc_sections/hierarchy.json | diff - path/to/doc.md
```

The final `diff` must be empty.

## New Section-Managed Document

Start skeleton-first. Write the canonical `.md` or `.qmd` with the intended H1/H2/H3 structure before drafting long bodies.

```markdown
# Title

## Chapter

### Section
```

Then decompose, edit section files, compose, and verify.

```bash
mdtools mdsplit decompose path/to/doc.md -o path/to/doc_sections
mdtools mdsplit compose path/to/doc_sections/hierarchy.json -o path/to/doc.md
mdtools mdsplit verify path/to/doc_sections/hierarchy.json
mdtools mdsplit compose path/to/doc_sections/hierarchy.json | diff - path/to/doc.md
```

If the document has no headings, `decompose` cannot produce useful sections. Add H2/H3 structure first.

## Structural Changes

For small moves, edit `hierarchy.json` and the affected section files, then compose and verify.

For large restructures, prefer editing the canonical document first, then regenerate the section tree:

```bash
mdtools mdsplit decompose path/to/doc.md -o path/to/doc_sections
mdtools mdsplit verify path/to/doc_sections/hierarchy.json
```

Be careful when replacing an existing section tree. Do not delete user edits unless you have confirmed that the canonical file already contains them.

## Practical Checks

- `verify` checks that referenced section files exist.
- Round-trip `compose ... | diff - canonical.md` checks textual equivalence.
- `compose --base-level N` can intentionally change heading depth.
- Code fences and `<pre>...</pre>` blocks are not treated as headings.
- Front matter and preamble content are preserved through metadata and preamble files.

## References

When working in the mdtools repository, consult:

- `README.md` for the overall document workflow.
- `mdsplit/README.md` for hierarchy JSON, file layout, and examples.
