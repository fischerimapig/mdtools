"""Tests for the markdown parser."""

import pytest

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


def test_parse_pre_block_ignores_code_fence_markers():
    text = "# Real\n\n<pre>\n```\n</pre>\n\n## After Pre\n\ntext"
    fm, sections = parse_sections(text)
    assert [s.title for s in sections] == ["Real", "After Pre"]


@pytest.mark.parametrize("literal", [
    "`<pre>` を説明する。",
    "``<pre> with `backticks` ``",
    "説明中の <pre> タグ",
    r"\<pre>",
    "&lt;pre&gt;",
    "| HTML | description |\n| --- | --- |\n| <pre> | literal |",
    "| HTML | description |\n| --- | --- |\n| `<pre>` | literal |",
    "    <pre>",
    "\t<pre>",
    "<prefix>",
    "<pre-formatted>",
    "<pre/>",
    "<pre\u00a0class=example>",
    "<!-- <pre> -->",
    "```html\n<pre>\n# Code\n```",
    "~~~~html\n<pre>\n# Code\n~~~\n~~~~",
])
def test_parse_literal_pre_preserves_following_headings(literal):
    text = f"# A\n\n{literal}\n\n## B\n本文\n"
    _, sections = parse_sections(text)
    assert [(s.level, s.title) for s in sections] == [(1, "A"), (2, "B")]
    assert literal in sections[0].content


def test_parse_heading_mentioning_pre():
    _, sections = parse_sections("# A <pre>\n\ntext\n\n## B\ntext")
    assert [s.title for s in sections] == ["A <pre>", "B"]


@pytest.mark.parametrize("opening", [
    "<pre>",
    '<pre class="example">',
    "<PRE>",
    " <pre>",
    "  <pre>",
    "   <pRe data-lang='md'>",
    "<pre\tclass=example>",
    "<pre\nclass=example>",
    "<pre>text",
    "<pre>\r",  # Raw CRLF input remains supported.
    "<pre\r\nclass=example>",
])
def test_parse_html_pre_block_preserves_content(opening):
    body = f"\n{opening}\n# Hidden\n\n## Also hidden\n```\n  </PRE>\n"
    text = f"# A\n{body}\n## B\n本文\n"
    _, sections = parse_sections(text)
    assert [(s.level, s.title) for s in sections] == [(1, "A"), (2, "B")]
    assert sections[0].content == body
    assert sections[1].line_number == text.split("\n").index("## B") + 1


@pytest.mark.parametrize("body", [
    "<pre>one line</pre>",
    "<pre>\n# Still raw HTML </pre>",
    "<pre>\n# Hidden\n</pre><pre>",  # The closing line ends the raw block.
])
def test_parse_pre_closing_line_is_always_content(body):
    _, sections = parse_sections(f"# A\n\n{body}\n\n## B\ntext")
    assert [s.title for s in sections] == ["A", "B"]
    assert body in sections[0].content


def test_parse_unclosed_pre_block_ignores_headings_until_eof():
    _, sections = parse_sections("# A\n\n<pre>\n\n## Hidden\ntext")
    assert [s.title for s in sections] == ["A"]
    assert "## Hidden" in sections[0].content


def test_parse_fence_after_pre_block_is_tracked_normally():
    text = "# A\n\n<pre>\n```\n</pre>\n\n~~~\n<pre>\n# Hidden\n~~~\n\n## B\ntext"
    _, sections = parse_sections(text)
    assert [s.title for s in sections] == ["A", "B"]


def test_parse_shorter_code_fence_does_not_close():
    text = "# Real\n\n````\n# Not a heading\n```\n\n## Still code\n````\n\n## After\n\ntext"
    fm, sections = parse_sections(text)
    assert [s.title for s in sections] == ["Real", "After"]


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
