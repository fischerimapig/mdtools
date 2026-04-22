"""Tests for composition."""

import tempfile
from pathlib import Path

from mdsplit.compose import compose
from mdsplit.schema import DocumentTree, SectionNode


def test_compose_simple():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create section files
        sections_dir = tmpdir / "sections"
        sections_dir.mkdir()
        (sections_dir / "01-title.md").write_text("\nBody text", encoding="utf-8")
        (sections_dir / "01-title").mkdir()
        (sections_dir / "01-title" / "01-sub.md").write_text(
            "\nSub body", encoding="utf-8"
        )

        # Create hierarchy
        doc = DocumentTree(
            source_file="test.md",
            base_level=1,
            sections=[
                SectionNode(
                    title="Title",
                    file="sections/01-title.md",
                    order=0,
                    children=[
                        SectionNode(
                            title="Sub",
                            file="sections/01-title/01-sub.md",
                            order=0,
                        ),
                    ],
                ),
            ],
        )
        doc.save(tmpdir / "hierarchy.json")

        result = compose(tmpdir / "hierarchy.json")

        assert "# Title" in result
        assert "## Sub" in result
        assert "Body text" in result
        assert "Sub body" in result


def test_compose_order():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        sections_dir = tmpdir / "sections"
        sections_dir.mkdir()
        (sections_dir / "a.md").write_text("\nFirst", encoding="utf-8")
        (sections_dir / "b.md").write_text("\nSecond", encoding="utf-8")

        doc = DocumentTree(
            source_file="test.md",
            base_level=1,
            sections=[
                SectionNode(title="B", file="sections/b.md", order=1),
                SectionNode(title="A", file="sections/a.md", order=0),
            ],
        )
        doc.save(tmpdir / "hierarchy.json")

        result = compose(tmpdir / "hierarchy.json")

        # A (order=0) should come before B (order=1)
        pos_a = result.index("# A")
        pos_b = result.index("# B")
        assert pos_a < pos_b


def test_compose_base_level_override():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        sections_dir = tmpdir / "sections"
        sections_dir.mkdir()
        (sections_dir / "01-title.md").write_text("\nBody", encoding="utf-8")

        doc = DocumentTree(
            source_file="test.md",
            base_level=1,
            sections=[
                SectionNode(title="Title", file="sections/01-title.md", order=0),
            ],
        )
        doc.save(tmpdir / "hierarchy.json")

        result = compose(tmpdir / "hierarchy.json", base_level=2)
        assert result.startswith("## Title")
