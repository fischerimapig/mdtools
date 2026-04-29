
| # | テスト名 | 入力 | lang | 期待出力 | 目的 |
|---|---------|------|------|---------|------|
| 4 | `test_keep_en_block_preserves_fences` | `::: {lang=en}\nHello\n:::\n` | `"en"` | 入力と同一 | keep時マーカー保持 |
| 5 | `test_remove_ja_block_when_lang_en` | `::: {lang=ja}\nこんにちは\n:::\n` | `"en"` | `""` | 不要ブロック除去 |
| 6 | `test_keep_ja_block_preserves_fences` | `::: {lang=ja}\nこんにちは\n:::\n` | `"ja"` | 入力と同一 | ja keep時マーカー保持 |
| 7 | `test_remove_en_block_when_lang_ja` | `::: {lang=en}\nHello\n:::\n` | `"ja"` | `""` | en除去 |
