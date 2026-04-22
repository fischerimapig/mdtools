"""Roundtrip tests: decompose -> compose should reproduce the original."""

import tempfile
from pathlib import Path

from mdsplit.compose import compose
from mdsplit.decompose import decompose


def test_roundtrip_simple():
    md = "# Title\n\nBody text\n\n## Sub\n\nSub body"
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "test.md"
        input_path.write_text(md, encoding="utf-8")
        output_dir = Path(tmpdir) / "output"

        decompose(input_path, output_dir)
        result = compose(output_dir / "hierarchy.json")

        assert result == md


def test_roundtrip_nested():
    md = (
        "# H1\n\n"
        "H1 body\n\n"
        "## H2a\n\n"
        "H2a body\n\n"
        "### H3\n\n"
        "H3 body\n\n"
        "## H2b\n\n"
        "H2b body"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "test.md"
        input_path.write_text(md, encoding="utf-8")
        output_dir = Path(tmpdir) / "output"

        decompose(input_path, output_dir)
        result = compose(output_dir / "hierarchy.json")

        assert result == md


def test_roundtrip_empty_sections():
    md = "# H1\n\n## H2\n\nBody"
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "test.md"
        input_path.write_text(md, encoding="utf-8")
        output_dir = Path(tmpdir) / "output"

        decompose(input_path, output_dir)
        result = compose(output_dir / "hierarchy.json")

        assert result == md


def test_roundtrip_code_blocks():
    md = "# Title\n\n```python\n# this is a comment\nprint('hello')\n```\n\n## Sub\n\ntext"
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "test.md"
        input_path.write_text(md, encoding="utf-8")
        output_dir = Path(tmpdir) / "output"

        decompose(input_path, output_dir)
        result = compose(output_dir / "hierarchy.json")

        assert result == md


def test_roundtrip_with_front_matter():
    md = "---\ntitle: Test\n---\n# Heading\n\nBody"
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "test.md"
        input_path.write_text(md, encoding="utf-8")
        output_dir = Path(tmpdir) / "output"

        decompose(input_path, output_dir)
        result = compose(output_dir / "hierarchy.json")

        assert result == md


def test_roundtrip_combined_md():
    """Roundtrip test with the real combined.md sample file."""
    sample = Path(__file__).resolve().parents[3] / "doc" / "emax6" / "combined.md"
    if not sample.exists():
        import pytest
        pytest.skip("Sample file not found")

    original = sample.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "output"

        decompose(sample, output_dir)
        result = compose(output_dir / "hierarchy.json")

        assert result == original, (
            f"Roundtrip mismatch: original has {len(original)} chars, "
            f"result has {len(result)} chars"
        )


def test_double_roundtrip():
    """decompose -> compose -> decompose -> compose should be stable."""
    md = "# H1\n\nBody\n\n## H2\n\nSub body\n\n### H3\n\nDeep body"
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "test.md"
        input_path.write_text(md, encoding="utf-8")

        # First roundtrip
        out1 = Path(tmpdir) / "out1"
        decompose(input_path, out1)
        result1 = compose(out1 / "hierarchy.json")

        # Write result and do second roundtrip
        input2 = Path(tmpdir) / "test2.md"
        input2.write_text(result1, encoding="utf-8")
        out2 = Path(tmpdir) / "out2"
        decompose(input2, out2)
        result2 = compose(out2 / "hierarchy.json")

        assert result1 == result2
