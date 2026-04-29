
| # | テスト名 | 入力パターン | 検証内容 |
|---|---------|-------------|---------|
| 19 | `test_no_space_before_brace` | `:::{lang=en}` | 認識される |
| 20 | `test_extra_spaces` | `:::  { lang = en }` | 認識される |
| 21 | `test_quoted_attribute` | `::: {lang="en"}` | 認識される |
| 22 | `test_trailing_text_after_brace_is_not_lang_block` | `::: {lang=en} some text` | Pandoc fenced div としては不正なため通常行として保持 |
