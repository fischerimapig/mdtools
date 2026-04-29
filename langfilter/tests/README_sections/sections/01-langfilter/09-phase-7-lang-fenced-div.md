
| # | テスト名 | 概要 | 検証内容 |
|---|---------|------|---------|
| 23 | `test_non_lang_div_passed_through` | `::: {.callout-note}\n...\n:::` | そのまま出力 |
| 23a | `test_lang_attribute_after_class_is_filtered` | `::: {.note lang=en}\n...\n:::` | 属性順序に依存せず `lang` を検出してフィルタ |
| 24 | `test_non_lang_div_with_lang_blocks` | 非lang div + langブロック混在 | 非lang div保持、langブロックはフィルタ |
| 25 | `test_bare_triple_colon_normal` | `:::` のみの行 (NORMAL状態) | そのまま出力 |
