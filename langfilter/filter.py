"""Core filtering logic for langfilter.

Provides a pure function ``filter_lang`` that processes Markdown text
containing Pandoc/Quarto fenced div language blocks and returns filtered text.
"""

from __future__ import annotations

import re
from enum import Enum, auto


# ── Regex patterns ─────────────────────────────────────────────────

# Opening lang fence:  ::: {lang=en}  or  :::{lang="ja"}  etc.
LANG_OPEN_RE = re.compile(r"^:::\s*\{\s*lang\s*=\s*\"?(\w+)\"?\s*\}")

# Closing fence for a lang block: exactly ::: with optional trailing whitespace
LANG_CLOSE_RE = re.compile(r"^:::\s*$")

# Code fence: 3+ backticks or tildes
CODE_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")


# ── State machine ─────────────────────────────────────────────────


class _State(Enum):
    NORMAL = auto()
    IN_CODE_FENCE = auto()
    IN_LANG_BLOCK = auto()


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

    lines = text.split("\n")
    # Preserve whether original text ended with newline
    ends_with_newline = text.endswith("\n")
    # split() on "foo\n" gives ["foo", ""], so drop trailing empty
    if ends_with_newline and lines and lines[-1] == "":
        lines = lines[:-1]

    out: list[str] = []
    state = _State.NORMAL
    code_fence_char: str | None = None
    code_fence_len: int = 0
    current_lang: str | None = None

    for line in lines:
        if state == _State.NORMAL:
            # Check code fence first (higher priority)
            m_code = CODE_FENCE_RE.match(line)
            if m_code:
                code_fence_char = m_code.group(1)[0]
                code_fence_len = len(m_code.group(1))
                state = _State.IN_CODE_FENCE
                out.append(line)
                continue

            # Check lang block opening
            m_lang = LANG_OPEN_RE.match(line)
            if m_lang:
                current_lang = m_lang.group(1)
                state = _State.IN_LANG_BLOCK
                if current_lang == lang:
                    out.append(line)
                # else: skip (remove)
                continue

            # Normal line — always emit
            out.append(line)

        elif state == _State.IN_CODE_FENCE:
            # Always emit inside code fence
            out.append(line)
            # Check if this line closes the code fence
            m_close = CODE_FENCE_RE.match(line)
            if m_close:
                close_char = m_close.group(1)[0]
                close_len = len(m_close.group(1))
                if close_char == code_fence_char and close_len >= code_fence_len:
                    state = _State.NORMAL
                    code_fence_char = None
                    code_fence_len = 0

        elif state == _State.IN_LANG_BLOCK:
            if LANG_CLOSE_RE.match(line):
                state = _State.NORMAL
                if current_lang == lang:
                    out.append(line)
                # else: skip closing fence
                current_lang = None
            else:
                if current_lang == lang:
                    out.append(line)
                # else: skip content

    result = "\n".join(out)
    if ends_with_newline and result:
        result += "\n"
    return result
