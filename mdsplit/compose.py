"""Reassemble a Markdown/QMD file from section files and hierarchy JSON."""

from __future__ import annotations

from pathlib import Path

from .schema import DocumentTree, SectionNode


def _compose_section(
    node: SectionNode,
    depth: int,
    base_level: int,
    base_dir: Path,
) -> str:
    """Recursively compose a section and its children into markdown text."""
    parts: list[str] = []
    heading_level = depth + base_level
    heading = "#" * heading_level + " " + node.title

    parts.append(heading)

    # Read section content (always include, even if empty, to preserve spacing)
    file_path = base_dir / node.file
    if file_path.exists():
        content = file_path.read_text(encoding="utf-8")
        parts.append(content)

    # Process children sorted by order
    sorted_children = sorted(node.children, key=lambda c: c.order)
    for child in sorted_children:
        child_text = _compose_section(child, depth + 1, base_level, base_dir)
        parts.append(child_text)

    return "\n".join(parts)


def compose(
    hierarchy_path: str | Path,
    output_path: str | Path | None = None,
    base_level: int | None = None,
) -> str:
    """Reassemble a markdown document from hierarchy JSON and section files.

    Args:
        hierarchy_path: Path to hierarchy.json.
        output_path: Path for the output file. If None, returns the text.
        base_level: Override the base heading level from JSON.

    Returns:
        The composed markdown text.
    """
    hierarchy_path = Path(hierarchy_path)
    base_dir = hierarchy_path.parent

    doc_tree = DocumentTree.load(hierarchy_path)
    if base_level is not None:
        doc_tree.base_level = base_level

    parts: list[str] = []

    # Emit front matter if present
    front_matter = doc_tree.metadata.get("front_matter")
    if front_matter:
        parts.append(front_matter)

    # Emit preamble if present
    preamble_file = doc_tree.metadata.get("preamble_file")
    if preamble_file:
        preamble_path = base_dir / preamble_file
        if preamble_path.exists():
            preamble_text = preamble_path.read_text(encoding="utf-8")
            if preamble_text.strip():
                parts.append(preamble_text)

    # Compose sections sorted by order
    sorted_sections = sorted(doc_tree.sections, key=lambda s: s.order)
    for section in sorted_sections:
        section_text = _compose_section(
            section, depth=0, base_level=doc_tree.base_level, base_dir=base_dir
        )
        parts.append(section_text)

    result = "\n".join(parts)

    if output_path:
        Path(output_path).write_text(result, encoding="utf-8")

    return result
