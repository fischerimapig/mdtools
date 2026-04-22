"""Tests for decomposition."""

import json
import tempfile
from pathlib import Path

from mdsplit.decompose import decompose


def test_decompose_simple():
    md = "# Title\n\nBody\n\n## Sub\n\nSub body"
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "test.md"
        input_path.write_text(md, encoding="utf-8")
        output_dir = Path(tmpdir) / "output"

        doc_tree = decompose(input_path, output_dir)

        # Check hierarchy.json exists
        assert (output_dir / "hierarchy.json").exists()

        # Check sections
        assert len(doc_tree.sections) == 1
        assert doc_tree.sections[0].title == "Title"
        assert len(doc_tree.sections[0].children) == 1
        assert doc_tree.sections[0].children[0].title == "Sub"

        # Check section files exist
        for section in doc_tree.sections:
            assert (output_dir / section.file).exists()
            for child in section.children:
                assert (output_dir / child.file).exists()


def test_decompose_flat():
    md = "# H1\n\nBody1\n\n## H2\n\nBody2"
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "test.md"
        input_path.write_text(md, encoding="utf-8")
        output_dir = Path(tmpdir) / "output"

        doc_tree = decompose(input_path, output_dir, flat=True)

        # In flat mode, all files should be in sections/ directly
        for section in doc_tree.sections:
            file_path = output_dir / section.file
            assert file_path.parent.name == "sections"
            for child in section.children:
                child_path = output_dir / child.file
                assert child_path.parent.name == "sections"


def test_decompose_preserves_content():
    md = "# Title\n\nLine 1\nLine 2\n\n## Sub\n\nSub content"
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "test.md"
        input_path.write_text(md, encoding="utf-8")
        output_dir = Path(tmpdir) / "output"

        doc_tree = decompose(input_path, output_dir)

        content = (output_dir / doc_tree.sections[0].file).read_text(encoding="utf-8")
        assert "Line 1" in content
        assert "Line 2" in content


def test_decompose_json_roundtrip():
    md = "# Title\n\nBody\n\n## Sub\n\nSub body"
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "test.md"
        input_path.write_text(md, encoding="utf-8")
        output_dir = Path(tmpdir) / "output"

        doc_tree = decompose(input_path, output_dir)

        # Load JSON and verify structure
        with open(output_dir / "hierarchy.json") as f:
            data = json.load(f)

        assert data["source_file"] == "test.md"
        assert data["base_level"] == 1
        assert len(data["sections"]) == 1
        assert data["sections"][0]["title"] == "Title"
