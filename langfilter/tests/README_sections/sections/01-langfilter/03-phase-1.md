
| # | テスト名 | 入力 | lang | 期待出力 | 目的 |
|---|---------|------|------|---------|------|
| 1 | `test_empty_input_returns_empty` | `""` | `"both"` | `""` | 関数が存在し空文字を返す |
| 2 | `test_no_lang_blocks_returns_unchanged` | `"# Hello\n\nSome text.\n"` | `"en"` | 入力と同一 | langブロックなしはパススルー |
| 3 | `test_both_mode_preserves_all` | en/jaブロック含む入力 | `"both"` | 入力と同一 | bothは恒等変換 |
