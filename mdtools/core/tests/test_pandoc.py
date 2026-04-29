"""TDD tests for mdtools.core.pandoc (t-wada style: degenerate -> basic -> edge)."""

from __future__ import annotations

from mdtools.core.pandoc import (
    BRACKETED_SPAN_RE,
    CODE_FENCE_RE,
    DIV_OPEN_RE,
    FENCE_CLOSE_RE,
    PandocAttrs,
    parse_attrs,
)


# ---------------------------------------------------------------------------
# Phase 1: Degenerate
# ---------------------------------------------------------------------------

def test_parse_empty_string():
    a = parse_attrs("")
    assert a.classes == []
    assert a.kv == {}


def test_parse_whitespace_only():
    a = parse_attrs("   ")
    assert a.classes == []
    assert a.kv == {}


# ---------------------------------------------------------------------------
# Phase 2: Classes
# ---------------------------------------------------------------------------

def test_parse_single_class():
    a = parse_attrs(".foo")
    assert a.classes == ["foo"]
    assert a.kv == {}


def test_parse_multiple_classes():
    a = parse_attrs(".foo .bar .baz")
    assert a.classes == ["foo", "bar", "baz"]


def test_parse_class_with_hyphen():
    a = parse_attrs(".callout-note")
    assert a.classes == ["callout-note"]


# ---------------------------------------------------------------------------
# Phase 3: Key-value
# ---------------------------------------------------------------------------

def test_parse_single_kv():
    a = parse_attrs("id=unit")
    assert a.kv == {"id": "unit"}
    assert a.classes == []


def test_parse_quoted_value():
    a = parse_attrs('id="unit"')
    assert a.kv == {"id": "unit"}


def test_parse_quoted_value_with_spaces():
    a = parse_attrs('name="Processing Unit"')
    assert a.kv == {"name": "Processing Unit"}


def test_parse_multiple_kv():
    a = parse_attrs("id=foo lang=en")
    assert a.kv == {"id": "foo", "lang": "en"}


def test_parse_attrs_is_order_independent_for_classes_and_kv():
    a = parse_attrs(".note lang=en .callout")
    assert a.classes == ["note", "callout"]
    assert a.kv == {"lang": "en"}


# ---------------------------------------------------------------------------
# Phase 4: Mixed
# ---------------------------------------------------------------------------

def test_parse_class_and_kv():
    a = parse_attrs(".term id=unit")
    assert a.classes == ["term"]
    assert a.kv == {"id": "unit"}


def test_parse_class_and_quoted_kv():
    a = parse_attrs('.term id="unit-1"')
    assert a.classes == ["term"]
    assert a.kv == {"id": "unit-1"}


# ---------------------------------------------------------------------------
# Phase 5: Helper methods
# ---------------------------------------------------------------------------

def test_has_class_true():
    a = PandocAttrs(classes=["foo", "bar"], kv={})
    assert a.has_class("foo") is True


def test_has_class_false():
    a = PandocAttrs(classes=["foo"], kv={})
    assert a.has_class("bar") is False


def test_first_class_in_picks_earliest():
    a = PandocAttrs(classes=["x", "term", "const"], kv={})
    assert a.first_class_in({"const", "term"}) == "term"


def test_first_class_in_none_when_no_match():
    a = PandocAttrs(classes=["x", "y"], kv={})
    assert a.first_class_in({"term", "const"}) is None


# ---------------------------------------------------------------------------
# Phase 6: Regex constants
# ---------------------------------------------------------------------------

def test_code_fence_re_matches_backtick_3():
    assert CODE_FENCE_RE.match("```")


def test_code_fence_re_matches_backtick_6():
    assert CODE_FENCE_RE.match("``````")


def test_code_fence_re_matches_tilde_3():
    assert CODE_FENCE_RE.match("~~~")


def test_code_fence_re_does_not_match_backtick_2():
    assert CODE_FENCE_RE.match("``") is None


def test_fence_close_re_matches_bare_colons():
    assert FENCE_CLOSE_RE.match(":::")
    assert FENCE_CLOSE_RE.match(":::   ")


def test_fence_close_re_does_not_match_with_attrs():
    assert FENCE_CLOSE_RE.match("::: {.foo}") is None


def test_div_open_re_captures_attrs():
    m = DIV_OPEN_RE.match("::: {.glossary filter=term}")
    assert m is not None
    assert m.group(1).strip() == ".glossary filter=term"


def test_div_open_re_rejects_trailing_text_after_attrs():
    assert DIV_OPEN_RE.match("::: {lang=en} some text") is None


def test_bracketed_span_re_captures_label_and_attrs():
    m = BRACKETED_SPAN_RE.search("text [unit]{.term id=u} more")
    assert m is not None
    assert m.group(1) == "unit"
    assert m.group(2) == ".term id=u"


def test_bracketed_span_re_matches_empty_label():
    m = BRACKETED_SPAN_RE.search("[]{.const id=x}")
    assert m is not None
    assert m.group(1) == ""
    assert m.group(2) == ".const id=x"
