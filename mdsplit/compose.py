"""Reassemble a Markdown/QMD file from section files and hierarchy JSON."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

from mdtools.core.source import SourceMap, SourceMapBuilder, SourceSnapshot

from .schema import DocumentTree, SectionNode

# Text, source file (if copied), synthetic reason (otherwise).
_Part = tuple[str, Path | None, str | None]


def _section_parts(
    node: SectionNode, depth: int, base_level: int, base_dir: Path,
    read: Callable[[Path], str],
) -> Iterator[_Part]:
    yield "#" * (depth + base_level) + " " + node.title, None, "heading"
    file_path = base_dir / node.file
    if file_path.exists():
        yield "\n", None, "separator"
        yield read(file_path), file_path, None
    for child in sorted(node.children, key=lambda c: c.order):
        yield "\n", None, "separator"
        yield from _section_parts(child, depth + 1, base_level, base_dir, read)


def _document_parts(
    tree: DocumentTree, base_dir: Path, base_level: int | None,
    read: Callable[[Path], str],
) -> Iterator[_Part]:
    emitted = False
    front_matter = tree.metadata.get("front_matter")
    if front_matter:
        # The JSON value is decoded metadata, not literal Markdown in a file.
        yield front_matter, None, "hierarchy-front-matter"
        emitted = True
    preamble_file = tree.metadata.get("preamble_file")
    if preamble_file:
        path = base_dir / preamble_file
        if path.exists():
            text = read(path)
            if text.strip():
                if emitted:
                    yield "\n", None, "separator"
                yield text, path, None
                emitted = True
    level = tree.base_level if base_level is None else base_level
    for section in sorted(tree.sections, key=lambda s: s.order):
        if emitted:
            yield "\n", None, "separator"
        yield from _section_parts(section, 0, level, base_dir, read)
        emitted = True


def compose(
    hierarchy_path: str | Path,
    output_path: str | Path | None = None,
    base_level: int | None = None,
) -> str:
    """Reassemble Markdown; preserve the existing text API and CLI behavior."""
    hierarchy_path = Path(hierarchy_path)
    tree = DocumentTree.load(hierarchy_path)
    result = "".join(text for text, _, _ in _document_parts(
        tree, hierarchy_path.parent, base_level,
        lambda path: path.read_text(encoding="utf-8"),
    ))
    if output_path:
        Path(output_path).write_text(result, encoding="utf-8")
    return result


def compose_with_source_map(
    hierarchy_path: str | Path,
    *,
    artifact_uri: str,
    base_level: int | None = None,
) -> SourceMap:
    """Map this compose stage only; do not write or map later build stages.

    Copied preamble/section text maps to the exact bytes read, including CRLF
    normalization. Headings, separators and decoded hierarchy metadata are
    synthetic. Missing files retain compose's historical skip behavior.
    """
    hierarchy_path = Path(hierarchy_path)
    hierarchy = SourceSnapshot.from_path(hierarchy_path)
    tree = DocumentTree.from_json(hierarchy.text)
    sources: dict[Path, SourceSnapshot] = {}

    def read(path: Path) -> str:
        if path not in sources:
            sources[path] = SourceSnapshot.from_path(path)
        return sources[path].text.replace("\r\n", "\n").replace("\r", "\n")

    builder = SourceMapBuilder()
    for text, path, reason in _document_parts(tree, hierarchy_path.parent, base_level, read):
        if path is None:
            builder.add_synthetic(text, reason)
        else:
            builder.add_source(sources[path], normalize_newlines=True)
    # Record metadata and even omitted whitespace-only preambles as dependencies.
    result = builder.build(artifact_uri)
    inputs = dict.fromkeys((hierarchy, *sources.values(), *result.inputs))
    return SourceMap(result.artifact, tuple(inputs), result.mappings)
