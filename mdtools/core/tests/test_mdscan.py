"""TDD tests for mdtools.core.mdscan (t-wada style: degenerate → basic → edge)."""

from __future__ import annotations

import pytest

from mdtools.core.mdscan import (
    MdLine,
    join_lines_preserving_trailing_newline,
    scan_md_lines,
    scan_md_lines_from_list,
    split_text_preserving_trailing_newline,
)


# ── Phase 1: Degenerate ───────────────────────────────────────────


def test_scan_empty_yields_one_empty_line():
    lines = list(scan_md_lines(""))
    assert len(lines) == 1
    assert lines[0].lineno == 1
    assert lines[0].text == ""
    assert lines[0].in_code_fence is False


def test_scan_single_line_no_newline():
    lines = list(scan_md_lines("foo"))
    assert len(lines) == 1
    assert lines[0].text == "foo"


def test_scan_single_line_with_newline():
    lines = list(scan_md_lines("foo\n"))
    assert len(lines) == 2
    assert lines[0].text == "foo"
    assert lines[1].text == ""


# ── Phase 2: Normal (no fences) ─────────────────────────────────


def test_scan_plain_text_all_not_in_fence():
    lines = list(scan_md_lines("a\nb\nc"))
    assert all(not l.in_code_fence for l in lines)


def test_lineno_is_1_based_and_monotonic():
    lines = list(scan_md_lines("x\ny\nz"))
    assert [l.lineno for l in lines] == [1, 2, 3]


# ── Phase 3: Backtick fences ─────────────────────────────────────


def test_scan_backtick_fence_open_and_close_marked_in_fence():
    text = "```\ncode\n```"
    lines = list(scan_md_lines(text))
    assert lines[0].in_code_fence is True   # opening ```
    assert lines[1].in_code_fence is True   # content
    assert lines[2].in_code_fence is True   # closing ```


def test_scan_content_between_backtick_fences_in_fence():
    text = "before\n```\ninside\n```\nafter"
    lines = list(scan_md_lines(text))
    assert lines[0].in_code_fence is False  # before
    assert lines[1].in_code_fence is True   # ```
    assert lines[2].in_code_fence is True   # inside
    assert lines[3].in_code_fence is True   # closing ```
    assert lines[4].in_code_fence is False  # after


def test_scan_after_close_returns_to_normal():
    text = "```\ncode\n```\nnormal"
    lines = list(scan_md_lines(text))
    assert lines[3].in_code_fence is False


def test_longer_closing_fence_also_closes():
    # ``` opens, ```` closes (longer is OK)
    text = "```\ncode\n````"
    lines = list(scan_md_lines(text))
    assert lines[2].in_code_fence is True   # ```` still in fence (closing line)
    text2 = "```\ncode\n````\nafter"
    lines2 = list(scan_md_lines(text2))
    assert lines2[3].in_code_fence is False  # after closing


def test_shorter_fence_inside_does_not_close():
    # ```` opens, ``` inside does NOT close
    text = "````\ncode\n```\nstill inside\n````"
    lines = list(scan_md_lines(text))
    assert lines[2].in_code_fence is True   # ``` (shorter) is inside, stays in fence
    assert lines[3].in_code_fence is True   # still inside


def test_tilde_fence_independent_of_backtick():
    # ~~~ opens, ``` inside ~~~ block stays in fence
    text = "~~~\n```\nstill in tilde\n```\n~~~"
    lines = list(scan_md_lines(text))
    assert lines[1].in_code_fence is True   # ``` inside ~~~ is in fence
    assert lines[2].in_code_fence is True
    assert lines[3].in_code_fence is True


# ── Phase 4: Tilde fences ────────────────────────────────────────


def test_scan_tilde_fence():
    text = "~~~\ncode\n~~~\nnormal"
    lines = list(scan_md_lines(text))
    assert lines[0].in_code_fence is True
    assert lines[1].in_code_fence is True
    assert lines[2].in_code_fence is True
    assert lines[3].in_code_fence is False


# ── Phase 5: Round-trip helpers ──────────────────────────────────


def test_split_join_roundtrip_preserves_trailing_newline():
    text = "foo\nbar\n"
    lines, flag = split_text_preserving_trailing_newline(text)
    result = join_lines_preserving_trailing_newline(lines, flag)
    assert result == text


def test_split_join_roundtrip_no_trailing_newline():
    text = "foo\nbar"
    lines, flag = split_text_preserving_trailing_newline(text)
    result = join_lines_preserving_trailing_newline(lines, flag)
    assert result == text


def test_split_join_empty_string():
    text = ""
    lines, flag = split_text_preserving_trailing_newline(text)
    result = join_lines_preserving_trailing_newline(lines, flag)
    assert result == text


def test_split_yields_lines_without_trailing_empty_when_terminated():
    lines, flag = split_text_preserving_trailing_newline("foo\nbar\n")
    assert lines == ["foo", "bar"]
    assert flag is True


# ── Phase 6: Integration ─────────────────────────────────────────


def test_scan_mixed_fence_and_plain():
    text = "normal\n```\ncode\n```\nmore normal\n~~~\nother\n~~~\nend"
    lines = list(scan_md_lines(text))
    assert lines[0].in_code_fence is False   # normal
    assert lines[1].in_code_fence is True    # ```
    assert lines[2].in_code_fence is True    # code
    assert lines[3].in_code_fence is True    # closing ```
    assert lines[4].in_code_fence is False   # more normal
    assert lines[5].in_code_fence is True    # ~~~
    assert lines[6].in_code_fence is True    # other
    assert lines[7].in_code_fence is True    # closing ~~~
    assert lines[8].in_code_fence is False   # end


def test_unclosed_fence_keeps_in_fence_to_eof():
    text = "```\ncode\nno closing fence"
    lines = list(scan_md_lines(text))
    assert all(l.in_code_fence for l in lines)


def test_scan_md_lines_from_list_basic():
    lines = ["normal", "```", "code", "```", "after"]
    result = list(scan_md_lines_from_list(lines))
    assert result[0].in_code_fence is False
    assert result[1].in_code_fence is True
    assert result[2].in_code_fence is True
    assert result[3].in_code_fence is True
    assert result[4].in_code_fence is False
