"""Core filtering logic for langfilter.

Provides a pure function ``filter_lang`` that processes Markdown text
containing Pandoc/Quarto fenced div language blocks and returns filtered text.
"""

from __future__ import annotations

import re

from mdtools.core.mdscan import (
    join_lines_preserving_trailing_newline,
    scan_md_lines_from_list,
    split_text_preserving_trailing_newline,
)


# Opening lang fence:  ::: {lang=en}  or  :::{lang="ja"}  etc.
LANG_OPEN_RE = re.compile(r"^:::\s*\{\s*lang\s*=\s*\"?(\w+)\"?\s*\}")

# Closing fence for a lang block: exactly ::: with optional trailing whitespace
LANG_CLOSE_RE = re.compile(r"^:::\s*$")


def filter_lang(text: str, lang: str) -> str:
    """Filter bilingual Markdown text for the specified language.

    Args:
        text: Input Markdown text.
        lang: ``"en"``, ``"ja"``, ``"both"``, or any language tag.
              ``"both"`` returns the input unchanged.

    Returns:
        Filtered Markdown text.
    """
    if not text:
        return ""

    if lang == "both":
        return text

    lines, trailing = split_text_preserving_trailing_newline(text)
    out: list[str] = []
    current_lang: str | None = None

    for md in scan_md_lines_from_list(lines):
        line = md.text

        # Inside a lang block: code fences are just content; use lang logic only
        if current_lang is not None:
            if LANG_CLOSE_RE.match(line):
                if current_lang == lang:
                    out.append(line)
                current_lang = None
            elif current_lang == lang:
                out.append(line)
            continue

        # Outside a lang block: pass code fence content through unchanged
        if md.in_code_fence:
            out.append(line)
            continue

        m_lang = LANG_OPEN_RE.match(line)
        if m_lang:
            current_lang = m_lang.group(1)
            if current_lang == lang:
                out.append(line)
            continue

        out.append(line)

    return join_lines_preserving_trailing_newline(out, trailing)
