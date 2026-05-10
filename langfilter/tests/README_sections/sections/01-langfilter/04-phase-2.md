
| # | テスト名 | 入力 | lang | 期待出力 | 目的 |
|---|---------|------|------|---------|------|
| 4 | `test_keep_en_block_strips_fences_by_default` | `::: {lang=en}\nHello\n:::\n` | `"en"` | `Hello\n` | 既定では対象言語のwrapperを除去 |
| 4a | `test_keep_en_block_can_preserve_fences` | 同上 | `"en"` | 入力と同一 | `keep_fences=True` でマーカー保持 |
| 5 | `test_remove_ja_block_when_lang_en` | `::: {lang=ja}\nこんにちは\n:::\n` | `"en"` | `""` | 不要ブロック除去 |
| 6 | `test_keep_ja_block_strips_fences_by_default` | `::: {lang=ja}\nこんにちは\n:::\n` | `"ja"` | `こんにちは\n` | ja keep時も既定ではwrapper除去 |
| 7 | `test_remove_en_block_when_lang_ja` | `::: {lang=en}\nHello\n:::\n` | `"ja"` | `""` | en除去 |
