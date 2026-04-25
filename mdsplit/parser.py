"""Markdown parsing engine: extract headings and build section tree."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from mdtools.core.mdscan import scan_md_lines_from_list

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
PRE_OPEN_RE = re.compile(r"<pre[\s>]", re.IGNORECASE)
PRE_CLOSE_RE = re.compile(r"</pre>", re.IGNORECASE)


@dataclass
class RawSection:
    """A parsed section before tree construction."""

    level: int
    title: str
    content: str  # body text without the heading line
    line_number: int  # 1-based line number of the heading


@dataclass
class FrontMatter:
    """YAML front matter extracted from the document."""

    text: str  # raw YAML content including delimiters
    end_line: int  # 0-based index of the closing '---' line


def extract_front_matter(lines: list[str]) -> FrontMatter | None:
    """Extract YAML front matter if present at the start of the document."""
    if not lines or lines[0].rstrip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            text = "\n".join(lines[: i + 1])
            return FrontMatter(text=text, end_line=i)
    return None


def parse_sections(text: str) -> tuple[FrontMatter | None, list[RawSection]]:
    """Parse markdown text into a flat list of sections.

    Returns the front matter (if any) and a flat list of RawSection objects
    in document order. Content before the first heading is captured as a
    section with level=0 and title="".
    """
    lines = text.split("\n")
    front_matter = extract_front_matter(lines)
    start_idx = (front_matter.end_line + 1) if front_matter else 0

    sections: list[RawSection] = []
    current_content_lines: list[str] = []
    current_level = 0
    current_title = ""
    current_line_number = start_idx + 1  # 1-based

    in_pre_block = False

    for md in scan_md_lines_from_list(lines[start_idx:]):
        line = md.text
        abs_line_number = start_idx + md.lineno  # 1-based in original `lines`

        if md.in_code_fence:
            current_content_lines.append(line)
            continue

        if PRE_OPEN_RE.search(line):
            in_pre_block = True
        if PRE_CLOSE_RE.search(line):
            in_pre_block = False

        if not in_pre_block:
            heading_match = HEADING_RE.match(line)
            if heading_match:
                # Save previous section
                content = "\n".join(current_content_lines)
                if current_title:
                    sections.append(RawSection(
                        level=current_level,
                        title=current_title,
                        content=content,
                        line_number=current_line_number,
                    ))
                elif content.strip():
                    sections.append(RawSection(
                        level=current_level,
                        title=current_title,
                        content=content,
                        line_number=current_line_number,
                    ))

                current_level = len(heading_match.group(1))
                current_title = heading_match.group(2).strip()
                current_content_lines = []
                current_line_number = abs_line_number
                continue

        current_content_lines.append(line)

    # Save the last section
    content = "\n".join(current_content_lines)
    if current_title or content.strip():
        sections.append(RawSection(
            level=current_level,
            title=current_title,
            content=content,
            line_number=current_line_number,
        ))

    return front_matter, sections


@dataclass
class TreeNode:
    """A node in the section tree."""

    level: int
    title: str
    content: str
    line_number: int
    children: list[TreeNode] = field(default_factory=list)


def build_tree(sections: list[RawSection]) -> tuple[str, list[TreeNode]]:
    """Build a tree from a flat list of sections.

    Returns a tuple of (preamble_content, root_nodes).
    Preamble is any content before the first heading (level=0 sections).
    """
    preamble = ""
    heading_sections: list[RawSection] = []

    for s in sections:
        if s.level == 0:
            preamble = s.content
        else:
            heading_sections.append(s)

    if not heading_sections:
        return preamble, []

    # Stack-based tree construction
    root_nodes: list[TreeNode] = []
    stack: list[TreeNode] = []  # stack of ancestor nodes

    for s in heading_sections:
        node = TreeNode(
            level=s.level,
            title=s.title,
            content=s.content,
            line_number=s.line_number,
        )

        # Pop stack until we find a parent (lower level)
        while stack and stack[-1].level >= s.level:
            stack.pop()

        if stack:
            stack[-1].children.append(node)
        else:
            root_nodes.append(node)

        stack.append(node)

    return preamble, root_nodes
