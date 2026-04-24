"""TDD tests for mdtools.core.pandoc (t-wada style)."""

from __future__ import annotations

import pytest

from mdtools.core.pandoc import (
    BRACKETED_SPAN_RE,
    CODE_FENCE_RE,
    DIV_OPEN_RE,
    FENCE_CLOSE_RE,
    PandocAttrs,
    parse_attrs,
)


# ── Phase 1: Degenerate ───────────────────────────────────────────


def test_parse_empty_string():
    attrs = parse_attrs("")
    assert attrs.classes == []
    assert attrs.kv == {}


def test_parse_whitespace_only():
    attrs = parse_attrs("   ")
    assert attrs.classes == []
    assert attrs.kv == {}


# ── Phase 2: Classes ─────────────────────────────────────────────


def test_parse_single_class():
    attrs = parse_attrs(".foo")
    assert attrs.classes == ["foo"]


def test_parse_multiple_classes():
    attrs = parse_attrs(".foo .bar .baz")
    assert attrs.classes == ["foo", "bar", "baz"]


def test_parse_class_with_hyphen():
    attrs = parse_attrs(".callout-note")
    assert "callout-note" in attrs.classes


# ── Phase 3: Key-value ───────────────────────────────────────────


def test_parse_single_kv():
    attrs = parse_attrs("id=unit")
    assert attrs.kv == {"id": "unit"}


def test_parse_quoted_value():
    attrs = parse_attrs('id="unit"')
    assert attrs.kv["id"] == "unit"


def test_parse_quoted_value_with_spaces():
    attrs = parse_attrs('name="Processing Unit"')
    assert attrs.kv["name"] == "Processing Unit"


def test_parse_multiple_kv():
    attrs = parse_attrs("filter=term format=dl")
    assert attrs.kv == {"filter": "term", "format": "dl"}


# ── Phase 4: Mixed ───────────────────────────────────────────────


def test_parse_class_and_kv():
    attrs = parse_attrs(".term id=unit")
    assert "term" in attrs.classes
    assert attrs.kv["id"] == "unit"


def test_parse_class_and_quoted_kv():
    attrs = parse_attrs('.glossary filter="term"')
    assert "glossary" in attrs.classes
    assert attrs.kv["filter"] == "term"


# ── Phase 5: Helper methods ──────────────────────────────────────


def test_has_class_true():
    attrs = parse_attrs(".term .other")
    assert attrs.has_class("term") is True


def test_has_class_false():
    attrs = parse_attrs(".other")
    assert attrs.has_class("term") is False


def test_first_class_in_picks_earliest():
    attrs = parse_attrs(".other .term .const")
    result = attrs.first_class_in({"term", "const"})
    assert result == "term"


def test_first_class_in_none_when_no_match():
    attrs = parse_attrs(".other")
    result = attrs.first_class_in({"term", "const"})
    assert result is None


# ── Phase 6: Regex constants ─────────────────────────────────────


def test_code_fence_re_matches_backtick_3():
    assert CODE_FENCE_RE.match("```") is not None


def test_code_fence_re_matches_backtick_6():
    assert CODE_FENCE_RE.match("``````") is not None


def test_code_fence_re_matches_tilde_3():
    assert CODE_FENCE_RE.match("~~~") is not None


def test_code_fence_re_does_not_match_backtick_2():
    assert CODE_FENCE_RE.match("``") is None


def test_fence_close_re_matches_bare_colons():
    assert FENCE_CLOSE_RE.match(":::") is not None
    assert FENCE_CLOSE_RE.match(":::  ") is not None


def test_fence_close_re_does_not_match_with_attrs():
    assert FENCE_CLOSE_RE.match("::: {.foo}") is None


def test_div_open_re_captures_attrs():
    m = DIV_OPEN_RE.match("::: {.glossary filter=term}")
    assert m is not None
    assert ".glossary" in m.group(1)


def test_bracketed_span_re_captures_label_and_attrs():
    m = BRACKETED_SPAN_RE.search("[unit]{.term id=unit}")
    assert m is not None
    assert m.group(1) == "unit"
    assert ".term" in m.group(2)


def test_bracketed_span_re_matches_empty_label():
    m = BRACKETED_SPAN_RE.search("[]{.term id=foo}")
    assert m is not None
    assert m.group(1) == ""
