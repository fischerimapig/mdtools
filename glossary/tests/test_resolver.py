"""Tests for glossary.resolver."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from glossary.loader import load
from glossary.resolver import (
    Attrs,
    ResolveError,
    find_missing,
    parse_attrs,
    resolve,
)


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def entries():
    return load([FIXTURES / "defs.json"])


# ── parse_attrs ─────────────────────────────────────────────────────


def test_parse_attrs_class_and_kv():
    a = parse_attrs(".term id=unit field=description")
    assert a.classes == ["term"]
    assert a.kv == {"id": "unit", "field": "description"}
    assert a.marker_class == "term"


def test_parse_attrs_quoted_value():
    a = parse_attrs('.term id="unit"')
    assert a.kv["id"] == "unit"


def test_parse_attrs_no_marker_class():
    a = parse_attrs(".callout-note foo=bar")
    assert a.marker_class is None


# ── resolve: spans ──────────────────────────────────────────────────


def test_resolve_term_default_field_uses_lang_name(entries):
    text = "The []{.term id=unit} is a compute element.\n"
    out = resolve(text, entries, lang="en")
    assert out == "The Processing Unit is a compute element.\n"


def test_resolve_term_ja(entries):
    text = "この []{.term id=unit} は計算要素。\n"
    out = resolve(text, entries, lang="ja")
    assert out == "この プロセッシングユニット は計算要素。\n"


def test_resolve_term_description(entries):
    text = "Unit: []{.term id=unit field=description}\n"
    out = resolve(text, entries, lang="en")
    assert "One compute element" in out


def test_resolve_term_abbr(entries):
    text = "([]{.term id=unit field=abbr})\n"
    out = resolve(text, entries, lang="en")
    assert out == "(PU)\n"


def test_resolve_const_value(entries):
    text = "Width = []{.const id=EMAX_WIDTH}.\n"
    out = resolve(text, entries, lang="en")
    assert out == "Width = 4.\n"


def test_resolve_symbol_default_returns_id(entries):
    text = "Depth = []{.symbol id=D}.\n"
    out = resolve(text, entries, lang="en")
    assert out == "Depth = D.\n"


def test_resolve_symbol_rtl_macro(entries):
    text = "Macro: []{.symbol id=D field=rtl_macro}.\n"
    out = resolve(text, entries, lang="en")
    assert out == "Macro: EMAX_DEPTH.\n"


def test_resolve_label_overrides(entries):
    text = "The [processing unit]{.term id=unit} array.\n"
    out = resolve(text, entries, lang="en")
    assert out == "The processing unit array.\n"


def test_resolve_multiple_markers_same_line(entries):
    text = "[]{.term id=unit} with []{.const id=EMAX_WIDTH} columns.\n"
    out = resolve(text, entries, lang="en")
    assert out == "Processing Unit with 4 columns.\n"


# ── resolve: error cases ────────────────────────────────────────────


def test_resolve_missing_id_raises_by_default(entries):
    with pytest.raises(ResolveError, match="undefined id 'nope'"):
        resolve("[]{.term id=nope}\n", entries, lang="en")


def test_resolve_missing_id_warn_keeps_marker(entries, capsys):
    text = "[]{.term id=nope}\n"
    out = resolve(text, entries, lang="en", on_missing="warn")
    assert out == text
    assert "undefined id 'nope'" in capsys.readouterr().err


def test_resolve_missing_id_keep_silent(entries, capsys):
    text = "[]{.term id=nope}\n"
    out = resolve(text, entries, lang="en", on_missing="keep")
    assert out == text
    assert capsys.readouterr().err == ""


def test_resolve_class_kind_mismatch(entries):
    with pytest.raises(ResolveError, match="does not match entry kind"):
        resolve("[]{.term id=EMAX_WIDTH}\n", entries, lang="en")


# ── resolve: code fence / lang div interactions ─────────────────────


def test_resolve_skips_code_fence(entries):
    text = textwrap.dedent("""\
        Normal []{.term id=unit}.
        ```
        In code: []{.term id=unit}
        ```
        After []{.term id=unit}.
    """)
    out = resolve(text, entries, lang="en")
    assert "Normal Processing Unit." in out
    assert "After Processing Unit." in out
    assert "In code: []{.term id=unit}" in out


def test_resolve_passes_lang_fence_through(entries):
    text = textwrap.dedent("""\
        ::: {lang=en}
        See []{.term id=unit}.
        :::
    """)
    out = resolve(text, entries, lang="en")
    assert "::: {lang=en}" in out
    assert ":::" in out
    assert "See Processing Unit." in out


def test_resolve_ignores_unrelated_span(entries):
    text = "A [click]{.link} here.\n"
    out = resolve(text, entries, lang="en")
    assert out == text


# ── resolve: glossary fenced div ────────────────────────────────────


def test_resolve_glossary_block_renders_table(entries):
    text = textwrap.dedent("""\
        Before.

        ::: {.glossary filter=term}
        :::

        After.
    """)
    out = resolve(text, entries, lang="en")
    assert "| ID | Kind | Name | Description |" in out
    assert "| unit | term | Processing Unit |" in out
    assert "Before." in out
    assert "After." in out


def test_resolve_glossary_block_definition_list(entries):
    text = "::: {.glossary filter=term format=dl}\n:::\n"
    out = resolve(text, entries, lang="ja")
    assert "プロセッシングユニット" in out
    assert ":   " in out


def test_resolve_glossary_block_no_filter_includes_all_kinds(entries):
    text = "::: {.glossary}\n:::\n"
    out = resolve(text, entries, lang="en")
    assert "unit" in out
    assert "EMAX_WIDTH" in out
    assert "D" in out


def test_resolve_glossary_class_not_first_renders_block(entries):
    text = "::: {.note .glossary filter=term}\n:::\n"
    out = resolve(text, entries, lang="en")
    assert "| ID | Kind | Name | Description |" in out
    assert "| unit | term | Processing Unit |" in out


def test_resolve_glossary_block_ignores_fence_close_inside_code(entries):
    text = textwrap.dedent("""\
        Before.

        ::: {.glossary filter=term}
        ```
        :::
        ```
        :::

        After.
    """)
    out = resolve(text, entries, lang="en")
    assert "Before." in out
    assert "| unit | term | Processing Unit |" in out
    assert "After." in out
    assert "```" not in out


# ── find_missing ────────────────────────────────────────────────────


def test_find_missing_collects_undefined(entries):
    text = "A []{.term id=unit} and []{.term id=nope1} and []{.const id=nope2}.\n"
    missing = find_missing(text, entries)
    ids = [m[1] for m in missing]
    assert ids == ["nope1", "nope2"]


def test_find_missing_skips_code_fence(entries):
    text = textwrap.dedent("""\
        ```
        []{.term id=not_defined}
        ```
    """)
    assert find_missing(text, entries) == []


def test_find_missing_reports_line_numbers(entries):
    text = "line1\nline2 []{.term id=bogus}\nline3\n"
    missing = find_missing(text, entries)
    assert missing == [(2, "bogus", "[]{.term id=bogus}")]
