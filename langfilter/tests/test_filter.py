"""Tests for langfilter.filter — t-wada style, all tests defined up-front."""

from __future__ import annotations

import io
import sys
import textwrap

import pytest

from langfilter.filter import filter_lang


# ── Phase 1: Degenerate cases ──────────────────────────────────────


def test_empty_input_returns_empty():
    assert filter_lang("", "both") == ""


def test_no_lang_blocks_returns_unchanged():
    text = "# Hello\n\nSome text.\n"
    assert filter_lang(text, "en") == text


def test_both_mode_preserves_all():
    text = textwrap.dedent("""\
        ::: {lang=en}
        Hello
        :::

        ::: {lang=ja}
        こんにちは
        :::
    """)
    assert filter_lang(text, "both") == text


# ── Phase 2: Single block — core behaviour ─────────────────────────


def test_keep_en_block_preserves_fences():
    text = "::: {lang=en}\nHello\n:::\n"
    assert filter_lang(text, "en") == text


def test_remove_ja_block_when_lang_en():
    text = "::: {lang=ja}\nこんにちは\n:::\n"
    assert filter_lang(text, "en") == ""


def test_keep_ja_block_preserves_fences():
    text = "::: {lang=ja}\nこんにちは\n:::\n"
    assert filter_lang(text, "ja") == text


def test_remove_en_block_when_lang_ja():
    text = "::: {lang=en}\nHello\n:::\n"
    assert filter_lang(text, "ja") == ""


# ── Phase 3: Multiple blocks — en/ja pairs ─────────────────────────


EN_JA_PAIR = textwrap.dedent("""\
    ::: {lang=en}
    English text.
    :::

    ::: {lang=ja}
    日本語テキスト。
    :::
""")


def test_en_ja_pair_keep_en():
    result = filter_lang(EN_JA_PAIR, "en")
    assert "::: {lang=en}" in result
    assert "English text." in result
    assert "日本語テキスト。" not in result
    assert "::: {lang=ja}" not in result


def test_en_ja_pair_keep_ja():
    result = filter_lang(EN_JA_PAIR, "ja")
    assert "::: {lang=ja}" in result
    assert "日本語テキスト。" in result
    assert "English text." not in result
    assert "::: {lang=en}" not in result


def test_en_ja_pair_both():
    assert filter_lang(EN_JA_PAIR, "both") == EN_JA_PAIR


# ── Phase 4: Shared content preservation ───────────────────────────


def test_table_between_blocks_preserved():
    text = textwrap.dedent("""\
        ::: {lang=en}
        English paragraph.
        :::

        | Col1 | Col2 |
        |------|------|
        | a    | b    |

        ::: {lang=ja}
        日本語段落。
        :::
    """)
    result = filter_lang(text, "en")
    assert "| Col1 | Col2 |" in result
    assert "| a    | b    |" in result
    assert "English paragraph." in result
    assert "日本語段落。" not in result


def test_code_block_outside_lang_preserved():
    text = textwrap.dedent("""\
        ```python
        print("hello")
        ```
    """)
    assert filter_lang(text, "en") == text


def test_image_preserved():
    text = "![Figure 1](fig1.png)\n"
    assert filter_lang(text, "en") == text


def test_html_comment_preserved():
    text = "<!-- status: draft -->\n"
    assert filter_lang(text, "en") == text


# ── Phase 5: Code fence interaction ────────────────────────────────


def test_triple_colon_in_code_block_ignored():
    text = textwrap.dedent("""\
        ```
        ::: {lang=en}
        This is code, not a lang block.
        :::
        ```
    """)
    assert filter_lang(text, "ja") == text


def test_lang_block_containing_code_fence_kept():
    text = textwrap.dedent("""\
        ::: {lang=en}
        Here is some code:
        ```python
        print("hello")
        ```
        :::
    """)
    result = filter_lang(text, "en")
    assert result == text


def test_lang_block_containing_code_fence_removed():
    text = textwrap.dedent("""\
        ::: {lang=en}
        Here is some code:
        ```python
        print("hello")
        ```
        :::
    """)
    assert filter_lang(text, "ja") == ""


def test_lang_block_containing_triple_colon_in_code_fence_kept():
    text = textwrap.dedent("""\
        ::: {lang=en}
        ```text
        :::
        ```
        :::
    """)
    assert filter_lang(text, "en") == text


def test_lang_block_containing_triple_colon_in_code_fence_removed():
    text = textwrap.dedent("""\
        ::: {lang=en}
        ```text
        :::
        ```
        :::
    """)
    assert filter_lang(text, "ja") == ""


def test_tilde_code_fence_tracked():
    text = textwrap.dedent("""\
        ~~~
        ::: {lang=en}
        This is inside a tilde fence.
        :::
        ~~~
    """)
    assert filter_lang(text, "ja") == text


# ── Phase 6: Syntax variations ─────────────────────────────────────


def test_no_space_before_brace():
    text = ":::{lang=en}\nHello\n:::\n"
    assert filter_lang(text, "en") == text


def test_extra_spaces():
    text = ":::  { lang = en }\nHello\n:::\n"
    assert filter_lang(text, "en") == text


def test_quoted_attribute():
    text = '::: {lang="en"}\nHello\n:::\n'
    assert filter_lang(text, "en") == text


def test_trailing_text_after_brace_is_not_lang_block():
    text = "::: {lang=en} some text\nHello\n:::\n"
    assert filter_lang(text, "ja") == text


# ── Phase 7: Non-lang fenced divs ─────────────────────────────────


def test_non_lang_div_passed_through():
    text = textwrap.dedent("""\
        ::: {.callout-note}
        This is a callout.
        :::
    """)
    assert filter_lang(text, "en") == text


def test_lang_attribute_after_class_is_filtered():
    text = textwrap.dedent("""\
        ::: {.note lang=en}
        English note.
        :::
    """)
    assert filter_lang(text, "en") == text
    assert filter_lang(text, "ja") == ""


def test_non_lang_div_with_lang_blocks():
    text = textwrap.dedent("""\
        ::: {.callout-note}
        A callout.
        :::

        ::: {lang=en}
        English.
        :::

        ::: {lang=ja}
        日本語。
        :::
    """)
    result = filter_lang(text, "en")
    assert "::: {.callout-note}" in result
    assert "A callout." in result
    assert "English." in result
    assert "日本語。" not in result


def test_bare_triple_colon_normal():
    text = "some text\n:::\nmore text\n"
    assert filter_lang(text, "en") == text


# ── Phase 8: Edge cases ───────────────────────────────────────────


def test_empty_lang_block_kept():
    text = "::: {lang=en}\n:::\n"
    assert filter_lang(text, "en") == text


def test_empty_lang_block_removed():
    text = "::: {lang=en}\n:::\n"
    assert filter_lang(text, "ja") == ""


def test_consecutive_blocks_no_blank_line():
    text = textwrap.dedent("""\
        ::: {lang=en}
        English.
        :::
        ::: {lang=ja}
        日本語。
        :::
    """)
    result = filter_lang(text, "en")
    assert "English." in result
    assert "日本語。" not in result


def test_multiline_content():
    lines = "\n".join(f"Line {i}" for i in range(10))
    text = f"::: {{lang=en}}\n{lines}\n:::\n"
    result = filter_lang(text, "en")
    for i in range(10):
        assert f"Line {i}" in result


def test_unclosed_block_at_eof():
    text = "::: {lang=en}\nHello\n"
    result = filter_lang(text, "en")
    assert "Hello" in result
    # Should not crash


def test_unknown_lang_removed():
    text = "::: {lang=de}\nGerman text.\n:::\n"
    assert filter_lang(text, "en") == ""


def test_unknown_lang_kept_in_both():
    text = "::: {lang=de}\nGerman text.\n:::\n"
    assert filter_lang(text, "both") == text


def test_trailing_newline_preserved():
    text = "text\n"
    assert filter_lang(text, "en") == "text\n"


def test_no_trailing_newline_preserved():
    text = "text"
    assert filter_lang(text, "en") == "text"


# ── Phase 9: CLI integration ──────────────────────────────────────


from langfilter.cli import main as cli_main


def test_cli_filter_from_file(tmp_path):
    f = tmp_path / "input.md"
    f.write_text("::: {lang=en}\nHello\n:::\n::: {lang=ja}\nこんにちは\n:::\n", encoding="utf-8")
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        rc = cli_main(["filter", "--lang", "en", str(f)])
    finally:
        sys.stdout = old_stdout
    assert rc == 0
    out = captured.getvalue()
    assert "Hello" in out
    assert "こんにちは" not in out


def test_cli_filter_to_output_file(tmp_path):
    f_in = tmp_path / "input.md"
    f_out = tmp_path / "output.md"
    f_in.write_text("::: {lang=en}\nHello\n:::\n", encoding="utf-8")
    rc = cli_main(["filter", "--lang", "en", str(f_in), "-o", str(f_out)])
    assert rc == 0
    assert "Hello" in f_out.read_text(encoding="utf-8")


def test_cli_default_lang_is_both(tmp_path):
    f = tmp_path / "input.md"
    text = "::: {lang=en}\nHello\n:::\n::: {lang=ja}\nこんにちは\n:::\n"
    f.write_text(text, encoding="utf-8")
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        rc = cli_main(["filter", str(f)])
    finally:
        sys.stdout = old_stdout
    assert rc == 0
    assert captured.getvalue() == text


def test_cli_stdin(monkeypatch):
    text = "::: {lang=en}\nHello\n:::\n::: {lang=ja}\nこんにちは\n:::\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        rc = cli_main(["filter", "--lang", "ja"])
    finally:
        sys.stdout = old_stdout
    assert rc == 0
    out = captured.getvalue()
    assert "こんにちは" in out
    assert "Hello" not in out


# ── Phase 10: Full document integration ────────────────────────────


FULL_DOCUMENT = textwrap.dedent("""\
    ---
    title: Test Document
    ---

    # Core Architecture Overview

    ::: {lang=en}
    The EMAX6 core consists of a D x 4 array of processing units.
    Each unit contains a 5-stage pipeline.
    :::

    ::: {lang=ja}
    EMAX6コアは D x 4 のプロセッシングユニットアレイで構成される。
    各ユニットは5段パイプラインを含む。
    :::

    | Field | Bits | EN: Description | JA: 説明 |
    |-------|------|-----------------|----------|
    | v     | [0]  | Valid bit       | 有効ビット |

    ```verilog
    module unit #(parameter UNIT_NO = 0) (
        input clk,
        input rst
    );
    endmodule
    ```

    ![Pipeline Diagram](pipeline.png)

    <!-- RTL ref: module=unit lines=1-10 -->

    ::: {lang=en}
    The pipeline processes data in five stages.
    :::

    ::: {lang=ja}
    パイプラインは5つのステージでデータを処理する。
    :::
""")


def test_full_document_en():
    result = filter_lang(FULL_DOCUMENT, "en")
    # English content present with fences
    assert "::: {lang=en}" in result
    assert "The EMAX6 core consists of" in result
    assert "The pipeline processes data" in result
    # Japanese content absent
    assert "EMAX6コアは" not in result
    assert "パイプラインは5つの" not in result
    assert "::: {lang=ja}" not in result
    # Shared content present
    assert "# Core Architecture Overview" in result
    assert "| Field | Bits |" in result
    assert "module unit" in result
    assert "![Pipeline Diagram]" in result
    assert "<!-- RTL ref:" in result
    # Front matter present
    assert "title: Test Document" in result


def test_full_document_ja():
    result = filter_lang(FULL_DOCUMENT, "ja")
    # Japanese content present with fences
    assert "::: {lang=ja}" in result
    assert "EMAX6コアは" in result
    assert "パイプラインは5つの" in result
    # English content absent
    assert "The EMAX6 core consists of" not in result
    assert "The pipeline processes data" not in result
    assert "::: {lang=en}" not in result
    # Shared content present
    assert "# Core Architecture Overview" in result
    assert "| Field | Bits |" in result
    assert "module unit" in result


def test_full_document_both():
    assert filter_lang(FULL_DOCUMENT, "both") == FULL_DOCUMENT
