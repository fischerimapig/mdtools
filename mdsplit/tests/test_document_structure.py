"""Repository documents must preserve structure as well as round-trip text."""

from pathlib import Path

import pytest

from mdsplit.compose import compose
from mdsplit.decompose import decompose
from mdsplit.schema import DocumentTree, SectionNode
from mdsplit.verify import verify


REPO_ROOT = Path(__file__).resolve().parents[2]


def heading_structure(nodes: list[SectionNode]) -> list[tuple]:
    """Ignore filenames; retain titles, sibling order, and parent/child shape."""
    return [
        (node.title, heading_structure(node.children))
        for node in sorted(nodes, key=lambda node: node.order)
    ]


@pytest.mark.parametrize("document", [
    "README.md",
    "mdsplit/README.md",
    "docs/spec/contract-v1.md",
    "docs/plans/core-refactor.md",
])
def test_repository_document_preserves_structure_and_text(document, tmp_path):
    source = REPO_ROOT / document
    hierarchy = source.with_name(f"{source.stem}_sections") / "hierarchy.json"
    expected = DocumentTree.load(hierarchy)
    original = source.read_text(encoding="utf-8")
    assert not verify(hierarchy).missing_files
    assert compose(hierarchy) == original

    output = tmp_path / "roundtrip"
    decompose(source, output)
    actual = DocumentTree.load(output / "hierarchy.json")
    assert not verify(output / "hierarchy.json").missing_files
    assert compose(output / "hierarchy.json") == original
    # Text can round-trip even when headings have been swallowed into a body.
    assert actual.base_level == expected.base_level
    assert heading_structure(actual.sections) == heading_structure(expected.sections)
    if document == "docs/spec/contract-v1.md":
        # #34 restored 18 headings; #35 adds two explicit M2 contract sections.
        assert verify(output / "hierarchy.json").section_count == 20
