"""Core filtering logic for langfilter.

Provides a pure function ``filter_lang`` that processes Markdown text
containing Pandoc/Quarto fenced div language blocks and returns filtered text.
"""

from __future__ import annotations

from mdtools.core.mdscan import (
    join_lines_preserving_trailing_newline,
    scan_md_lines_from_list,
    split_text_preserving_trailing_newline,
)
from mdtools.core.pandoc import DIV_OPEN_RE, FENCE_CLOSE_RE, parse_attrs


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

    lines, ends_with_newline = split_text_preserving_trailing_newline(text)

    out: list[str] = []
    current_lang: str | None = None

    for md in scan_md_lines_from_list(lines):
        line = md.text

        if current_lang is not None:
            if FENCE_CLOSE_RE.match(line) and not md.in_code_fence:
                if current_lang == lang:
                    out.append(line)
                current_lang = None
            elif current_lang == lang:
                out.append(line)
            continue

        if md.in_code_fence:
            out.append(line)
            continue

        m_div = DIV_OPEN_RE.match(line)
        if m_div:
            attrs = parse_attrs(m_div.group(1))
            lang_value = attrs.kv.get("lang")
            if lang_value is not None:
                current_lang = lang_value
                if current_lang == lang:
                    out.append(line)
                continue

        out.append(line)

    return join_lines_preserving_trailing_newline(out, ends_with_newline)
