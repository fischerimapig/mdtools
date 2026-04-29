
| # | テスト名 | 概要 | 検証内容 |
|---|---------|------|---------|
| 15 | `test_triple_colon_in_code_block_ignored` | コードブロック内の `::: {lang=en}` | langブロックとして解釈されない |
| 16 | `test_lang_block_containing_code_fence_kept` | langブロック内にコードフェンス (keep) | 内容（コードフェンス含む）がfences付きで残る |
| 17 | `test_lang_block_containing_code_fence_removed` | langブロック内にコードフェンス (remove) | ブロック全体が除去される |
| 17a | `test_lang_block_containing_triple_colon_in_code_fence_kept` | langブロック内コードの `:::` | コード内の `:::` ではlangブロックを閉じない |
| 17b | `test_lang_block_containing_triple_colon_in_code_fence_removed` | langブロック内コードの `:::` | 外側の閉じ `:::` までをブロックとして除去 |
| 18 | `test_tilde_code_fence_tracked` | `~~~` コードフェンス内の `:::` | 無視される |
