"""Tests for the markdown parser."""

from mdsplit.parser import (
    RawSection,
    build_tree,
    extract_front_matter,
    parse_sections,
)


def test_extract_front_matter():
    lines = ["---", "title: Test", "---", "# Hello"]
    fm = extract_front_matter(lines)
    assert fm is not None
    assert fm.text == "---\ntitle: Test\n---"
    assert fm.end_line == 2


def test_extract_front_matter_absent():
    lines = ["# Hello", "world"]
    fm = extract_front_matter(lines)
    assert fm is None


def test_parse_simple():
    text = "# Title\n\nBody text\n\n## Sub\n\nSub body"
    fm, sections = parse_sections(text)
    assert fm is None
    assert len(sections) == 2
    assert sections[0].level == 1
    assert sections[0].title == "Title"
    assert "Body text" in sections[0].content
    assert sections[1].level == 2
    assert sections[1].title == "Sub"
    assert "Sub body" in sections[1].content


def test_parse_code_fence_ignores_headings():
    text = "# Real\n\n```\n# Not a heading\n```\n\n## Also Real\n\ntext"
    fm, sections = parse_sections(text)
    assert len(sections) == 2
    titles = [s.title for s in sections]
    assert "Real" in titles
    assert "Also Real" in titles
    assert "Not a heading" not in titles


def test_parse_pre_block_ignores_headings():
    text = "# Real\n\n<pre>\n# Not a heading\n</pre>\n\n## Also Real\n\ntext"
    fm, sections = parse_sections(text)
    assert len(sections) == 2
    assert sections[0].title == "Real"
    assert sections[1].title == "Also Real"


def test_parse_define_not_heading():
    text = "# Real\n\n#define FOO 1\n\n## Sub\n\ntext"
    fm, sections = parse_sections(text)
    assert len(sections) == 2
    assert "#define FOO 1" in sections[0].content


def test_parse_with_front_matter():
    text = "---\ntitle: Doc\n---\n# Heading\n\nBody"
    fm, sections = parse_sections(text)
    assert fm is not None
    assert fm.text == "---\ntitle: Doc\n---"
    assert len(sections) == 1
    assert sections[0].title == "Heading"


def test_parse_empty_section():
    text = "# H1\n\n## H2\n\nBody"
    fm, sections = parse_sections(text)
    assert len(sections) == 2
    assert sections[0].title == "H1"
    assert sections[0].content == ""
    assert sections[1].title == "H2"


def test_build_tree_simple():
    sections = [
        RawSection(level=1, title="H1", content="body1", line_number=1),
        RawSection(level=2, title="H2a", content="body2a", line_number=3),
        RawSection(level=2, title="H2b", content="body2b", line_number=5),
        RawSection(level=3, title="H3", content="body3", line_number=7),
    ]
    preamble, tree = build_tree(sections)
    assert preamble == ""
    assert len(tree) == 1  # one H1
    assert tree[0].title == "H1"
    assert len(tree[0].children) == 2  # H2a and H2b
    assert tree[0].children[0].title == "H2a"
    assert tree[0].children[1].title == "H2b"
    assert len(tree[0].children[1].children) == 1  # H3 under H2b
    assert tree[0].children[1].children[0].title == "H3"


def test_build_tree_with_preamble():
    sections = [
        RawSection(level=0, title="", content="preamble text", line_number=1),
        RawSection(level=1, title="H1", content="body", line_number=3),
    ]
    preamble, tree = build_tree(sections)
    assert preamble == "preamble text"
    assert len(tree) == 1


def test_build_tree_multiple_h1():
    sections = [
        RawSection(level=1, title="H1a", content="a", line_number=1),
        RawSection(level=1, title="H1b", content="b", line_number=3),
    ]
    preamble, tree = build_tree(sections)
    assert len(tree) == 2
    assert tree[0].title == "H1a"
    assert tree[1].title == "H1b"
