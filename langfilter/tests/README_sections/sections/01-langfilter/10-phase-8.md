
| # | テスト名 | 概要 | 検証内容 |
|---|---------|------|---------|
| 26 | `test_empty_lang_block_kept` | `::: {lang=en}\n:::` (中身なし, keep) | fencesのみ出力 |
| 27 | `test_empty_lang_block_removed` | `::: {lang=en}\n:::` (中身なし, remove) | 何も出力しない |
| 28 | `test_consecutive_blocks_no_blank_line` | en/jaブロックが空行なしで連続 | 各ブロック独立にフィルタ |
| 29 | `test_multiline_content` | 5行以上の内容を持つブロック | 全行が保持/除去される |
| 30 | `test_unclosed_block_at_eof` | 閉じ `:::` がない | 内容をブロック内として扱い、クラッシュしない |
| 31 | `test_unknown_lang_removed` | `::: {lang=de}` | lang=en時に除去 |
| 32 | `test_unknown_lang_kept_in_both` | `::: {lang=de}` | lang=both時に保持 |
| 33 | `test_trailing_newline_preserved` | 末尾改行あり入力 | 末尾改行あり出力 |
| 34 | `test_no_trailing_newline_preserved` | 末尾改行なし入力 | 末尾改行なし出力 |
