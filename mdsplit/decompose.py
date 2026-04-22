"""Decompose a Markdown/QMD file into section files and a hierarchy JSON."""

from __future__ import annotations

from pathlib import Path

from .parser import TreeNode, build_tree, parse_sections
from .schema import DocumentTree, SectionNode
from .slugify import make_filename


def _write_section_files(
    nodes: list[TreeNode],
    base_dir: Path,
    flat: bool,
    flat_prefix: str = "",
) -> list[SectionNode]:
    """Recursively write section files and build SectionNode list.

    Returns a list of SectionNode objects with file paths populated.
    """
    result: list[SectionNode] = []

    for i, node in enumerate(nodes):
        filename = make_filename(i, node.title)
        stem = Path(filename).stem

        if flat:
            # Flat: prefix encodes hierarchy, e.g., "01-02-background.md"
            if flat_prefix:
                file_path = base_dir / f"{flat_prefix}-{filename}"
            else:
                file_path = base_dir / filename
            child_prefix = flat_prefix + f"-{i + 1:02d}" if flat_prefix else f"{i + 1:02d}"
        else:
            # Nested: sections/01-imax-hardware.md + sections/01-imax-hardware/
            file_path = base_dir / filename

        # Write the section content
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(node.content, encoding="utf-8")

        # Process children
        children: list[SectionNode] = []
        if node.children:
            if flat:
                children = _write_section_files(
                    node.children, base_dir, flat=True, flat_prefix=child_prefix
                )
            else:
                child_dir = base_dir / stem
                children = _write_section_files(
                    node.children, child_dir, flat=False
                )

        section_node = SectionNode(
            title=node.title,
            file=str(file_path),
            order=i,
            children=children,
        )
        result.append(section_node)

    return result


def _make_relative(sections: list[SectionNode], base: Path) -> None:
    """Convert absolute file paths to relative paths in-place."""
    for s in sections:
        try:
            s.file = str(Path(s.file).relative_to(base))
        except ValueError:
            pass  # already relative or different base
        _make_relative(s.children, base)


def decompose(
    input_path: str | Path,
    output_dir: str | Path | None = None,
    flat: bool = False,
) -> DocumentTree:
    """Decompose a Markdown/QMD file into sections.

    Args:
        input_path: Path to the input .md or .qmd file.
        output_dir: Directory for output files. Defaults to <stem>_sections/.
        flat: If True, use flat directory structure instead of nested.

    Returns:
        The DocumentTree representing the hierarchy.
    """
    input_path = Path(input_path)
    if output_dir is None:
        output_dir = input_path.parent / f"{input_path.stem}_sections"
    output_dir = Path(output_dir)

    text = input_path.read_text(encoding="utf-8")
    front_matter, raw_sections = parse_sections(text)
    preamble, tree_nodes = build_tree(raw_sections)

    # Determine base heading level from the tree
    base_level = min((n.level for n in tree_nodes), default=1)

    # Create sections directory
    sections_dir = output_dir / "sections"
    sections_dir.mkdir(parents=True, exist_ok=True)

    # Write preamble if present
    metadata: dict = {}
    if front_matter:
        metadata["front_matter"] = front_matter.text
    if preamble.strip():
        preamble_path = sections_dir / "00-preamble.md"
        preamble_path.write_text(preamble, encoding="utf-8")
        metadata["preamble_file"] = "sections/00-preamble.md"

    # Write section files
    section_nodes = _write_section_files(tree_nodes, sections_dir, flat=flat)

    # Convert to relative paths
    _make_relative(section_nodes, output_dir)

    # Build document tree
    doc_tree = DocumentTree(
        source_file=input_path.name,
        base_level=base_level,
        metadata=metadata,
        sections=section_nodes,
    )

    # Save hierarchy JSON
    doc_tree.save(output_dir / "hierarchy.json")

    return doc_tree
