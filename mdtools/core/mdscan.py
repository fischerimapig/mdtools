"""Markdown line scanner with code-fence state tracking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from .pandoc import CODE_FENCE_RE as _CODE_FENCE_RE


@dataclass(frozen=True)
class MdLine:
    """One Markdown line with its code-fence classification.

    Attributes:
        lineno: 1-based line number in the original text.
        text: The line content, without trailing newline.
        in_code_fence: True for fence-opening lines, for content inside a fenced
            code block, and for the fence-closing line. False for normal
            Markdown lines that should undergo further parsing.
    """

    lineno: int
    text: str
    in_code_fence: bool


class CodeFenceTracker:
    """Stateful code-fence classifier for callers with extra block rules."""

    def __init__(self) -> None:
        self._fence_char: str | None = None
        self._fence_len = 0

    def classify(self, line: str) -> bool:
        """Return whether ``line`` is part of a Markdown code fence.

        A fence closes only on a line that starts with the same fence character
        and is at least as long as the opening fence.
        """
        m = _CODE_FENCE_RE.match(line)
        if self._fence_char is None:
            if m:
                self._fence_char = m.group(1)[0]
                self._fence_len = len(m.group(1))
                return True
            return False

        in_code_fence = True
        if (
            m
            and m.group(1)[0] == self._fence_char
            and len(m.group(1)) >= self._fence_len
        ):
            self._fence_char = None
            self._fence_len = 0
        return in_code_fence


def _scan_lines(lines: list[str]) -> Iterator[MdLine]:
    tracker = CodeFenceTracker()
    for idx, line in enumerate(lines, start=1):
        yield MdLine(idx, line, in_code_fence=tracker.classify(line))


def scan_md_lines(text: str) -> Iterator[MdLine]:
    """Yield :class:`MdLine` for each line of ``text``.

    Recognizes ``` and ~~~ fences of length 3 or more. A fence closes only on
    a line that starts with the same character and is at least as long as the
    opener.
    """
    return _scan_lines(text.split("\n"))


def scan_md_lines_from_list(lines: list[str]) -> Iterator[MdLine]:
    """Same as :func:`scan_md_lines` but takes already-split lines."""
    return _scan_lines(lines)


def split_text_preserving_trailing_newline(text: str) -> tuple[list[str], bool]:
    """Split text by '\\n' while remembering whether a trailing newline existed.

    Python's ``str.split('\\n')`` turns ``'foo\\n'`` into ``['foo', '']``.
    This helper returns ``(['foo'], True)`` instead, so callers can faithfully
    round-trip via :func:`join_lines_preserving_trailing_newline`.
    """
    ends_with_newline = text.endswith("\n")
    lines = text.split("\n")
    if ends_with_newline and lines and lines[-1] == "":
        lines = lines[:-1]
    return lines, ends_with_newline


def join_lines_preserving_trailing_newline(
    lines: list[str], ends_with_newline: bool
) -> str:
    """Inverse of :func:`split_text_preserving_trailing_newline`."""
    result = "\n".join(lines)
    if ends_with_newline and result:
        result += "\n"
    return result
