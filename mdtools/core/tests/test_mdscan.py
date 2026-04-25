"""TDD tests for mdtools.core.mdscan (t-wada style: degenerate -> basic -> edge)."""

from __future__ import annotations

from mdtools.core.mdscan import (
    MdLine,
    join_lines_preserving_trailing_newline,
    scan_md_lines,
    scan_md_lines_from_list,
    split_text_preserving_trailing_newline,
)


# ---------------------------------------------------------------------------
# Phase 1: Degenerate
# ---------------------------------------------------------------------------

def test_scan_empty_yields_one_empty_line():
    out = list(scan_md_lines(""))
    assert out == [MdLine(1, "", False)]


def test_scan_single_line_no_newline():
    out = list(scan_md_lines("foo"))
    assert out == [MdLine(1, "foo", False)]


def test_scan_single_line_with_newline():
    out = list(scan_md_lines("foo\n"))
    assert out == [MdLine(1, "foo", False), MdLine(2, "", False)]


# ---------------------------------------------------------------------------
# Phase 2: Normal (no fences)
# ---------------------------------------------------------------------------

def test_scan_plain_text_all_not_in_fence():
    text = "abc\ndef\nghi"
    out = list(scan_md_lines(text))
    assert all(not md.in_code_fence for md in out)
    assert [md.text for md in out] == ["abc", "def", "ghi"]


def test_lineno_is_1_based_and_monotonic():
    text = "a\nb\nc\nd"
    out = list(scan_md_lines(text))
    assert [md.lineno for md in out] == [1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Phase 3: Backtick fences
# ---------------------------------------------------------------------------

def test_scan_backtick_fence_open_and_close_marked_in_fence():
    text = "```\ncode\n```"
    out = list(scan_md_lines(text))
    assert [md.in_code_fence for md in out] == [True, True, True]


def test_scan_content_between_backtick_fences_in_fence():
    text = "before\n```\ncode line\n```\nafter"
    out = list(scan_md_lines(text))
    flags = [md.in_code_fence for md in out]
    assert flags == [False, True, True, True, False]


def test_scan_after_close_returns_to_normal():
    text = "```\ncode\n```\nplain"
    out = list(scan_md_lines(text))
    assert out[-1].in_code_fence is False
    assert out[-1].text == "plain"


def test_longer_closing_fence_also_closes():
    text = "```\ncode\n````\nafter"
    out = list(scan_md_lines(text))
    assert out[2].in_code_fence is True  # closing fence
    assert out[3].in_code_fence is False  # after


def test_shorter_fence_inside_does_not_close():
    text = "````\ncode\n```\nstill code\n````\nafter"
    out = list(scan_md_lines(text))
    assert [md.in_code_fence for md in out] == [True, True, True, True, True, False]


def test_tilde_fence_independent_of_backtick():
    text = "~~~\n```\ninside\n```\n~~~\nafter"
    out = list(scan_md_lines(text))
    # ~~~ opens, ``` inside is plain code content, ~~~ closes
    assert [md.in_code_fence for md in out] == [True, True, True, True, True, False]


# ---------------------------------------------------------------------------
# Phase 4: Tilde fences
# ---------------------------------------------------------------------------

def test_scan_tilde_fence():
    text = "~~~\ncode\n~~~"
    out = list(scan_md_lines(text))
    assert [md.in_code_fence for md in out] == [True, True, True]


# ---------------------------------------------------------------------------
# Phase 5: Round-trip helpers
# ---------------------------------------------------------------------------

def test_split_join_roundtrip_preserves_trailing_newline():
    text = "a\nb\nc\n"
    lines, trailing = split_text_preserving_trailing_newline(text)
    assert lines == ["a", "b", "c"]
    assert trailing is True
    assert join_lines_preserving_trailing_newline(lines, trailing) == text


def test_split_join_roundtrip_no_trailing_newline():
    text = "a\nb\nc"
    lines, trailing = split_text_preserving_trailing_newline(text)
    assert lines == ["a", "b", "c"]
    assert trailing is False
    assert join_lines_preserving_trailing_newline(lines, trailing) == text


def test_split_join_empty_string():
    text = ""
    lines, trailing = split_text_preserving_trailing_newline(text)
    assert lines == [""]
    assert trailing is False
    assert join_lines_preserving_trailing_newline(lines, trailing) == text


def test_split_yields_lines_without_trailing_empty_when_terminated():
    lines, trailing = split_text_preserving_trailing_newline("foo\n")
    assert lines == ["foo"]
    assert trailing is True


# ---------------------------------------------------------------------------
# Phase 6: Integration
# ---------------------------------------------------------------------------

def test_scan_mixed_fence_and_plain():
    text = (
        "intro\n"
        "```\n"
        "code1\n"
        "```\n"
        "middle\n"
        "~~~\n"
        "code2\n"
        "~~~\n"
        "end"
    )
    out = list(scan_md_lines(text))
    flags = [md.in_code_fence for md in out]
    assert flags == [False, True, True, True, False, True, True, True, False]


def test_unclosed_fence_keeps_in_fence_to_eof():
    text = "```\ncode\nmore code"
    out = list(scan_md_lines(text))
    assert [md.in_code_fence for md in out] == [True, True, True]


def test_scan_md_lines_from_list_matches_scan():
    text = "a\n```\nb\n```\nc"
    lines, _ = split_text_preserving_trailing_newline(text)
    a = list(scan_md_lines_from_list(lines))
    b = list(scan_md_lines("\n".join(lines)))
    assert a == b
