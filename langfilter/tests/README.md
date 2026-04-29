# langfilter テストプラン

t-wada式 TDD に従い、テストを先に全て定義してから実装する。
テストは単純なケースから複雑なケースへ段階的に進む。

## 実行方法

```bash
cd tools/mdtools
python -m pytest langfilter/tests/ -v
```

---

## テスト対象

- `filter_lang(text: str, lang: str) -> str` — 純粋関数、I/O なし
- CLI (`main(argv)`) — ファイル/stdin 経由の統合テスト

---

## Phase 1: 退化ケース（関数シグネチャの確立）

| # | テスト名 | 入力 | lang | 期待出力 | 目的 |
|---|---------|------|------|---------|------|
| 1 | `test_empty_input_returns_empty` | `""` | `"both"` | `""` | 関数が存在し空文字を返す |
| 2 | `test_no_lang_blocks_returns_unchanged` | `"# Hello\n\nSome text.\n"` | `"en"` | 入力と同一 | langブロックなしはパススルー |
| 3 | `test_both_mode_preserves_all` | en/jaブロック含む入力 | `"both"` | 入力と同一 | bothは恒等変換 |

## Phase 2: 単一ブロック — コア動作

| # | テスト名 | 入力 | lang | 期待出力 | 目的 |
|---|---------|------|------|---------|------|
| 4 | `test_keep_en_block_preserves_fences` | `::: {lang=en}\nHello\n:::\n` | `"en"` | 入力と同一 | keep時マーカー保持 |
| 5 | `test_remove_ja_block_when_lang_en` | `::: {lang=ja}\nこんにちは\n:::\n` | `"en"` | `""` | 不要ブロック除去 |
| 6 | `test_keep_ja_block_preserves_fences` | `::: {lang=ja}\nこんにちは\n:::\n` | `"ja"` | 入力と同一 | ja keep時マーカー保持 |
| 7 | `test_remove_en_block_when_lang_ja` | `::: {lang=en}\nHello\n:::\n` | `"ja"` | `""` | en除去 |

## Phase 3: 複数ブロック — en/jaペア

| # | テスト名 | 概要 | lang | 検証内容 |
|---|---------|------|------|---------|
| 8 | `test_en_ja_pair_keep_en` | en+jaペア | `"en"` | enブロック(fences込み)残存、jaブロック除去 |
| 9 | `test_en_ja_pair_keep_ja` | en+jaペア | `"ja"` | jaブロック残存、enブロック除去 |
| 10 | `test_en_ja_pair_both` | en+jaペア | `"both"` | 入力と同一 |

## Phase 4: 共有コンテンツの保存

| # | テスト名 | 概要 | 検証内容 |
|---|---------|------|---------|
| 11 | `test_table_between_blocks_preserved` | en/jaブロック間にテーブル | テーブルが全言語版で残る |
| 12 | `test_code_block_outside_lang_preserved` | langブロック外のコードブロック | コードブロックが残る |
| 13 | `test_image_preserved` | `![Figure](fig.png)` | 画像リンクが残る |
| 14 | `test_html_comment_preserved` | `<!-- status: draft -->` | HTMLコメントが残る |

## Phase 5: コードフェンスとの相互作用

| # | テスト名 | 概要 | 検証内容 |
|---|---------|------|---------|
| 15 | `test_triple_colon_in_code_block_ignored` | コードブロック内の `::: {lang=en}` | langブロックとして解釈されない |
| 16 | `test_lang_block_containing_code_fence_kept` | langブロック内にコードフェンス (keep) | 内容（コードフェンス含む）がfences付きで残る |
| 17 | `test_lang_block_containing_code_fence_removed` | langブロック内にコードフェンス (remove) | ブロック全体が除去される |
| 17a | `test_lang_block_containing_triple_colon_in_code_fence_kept` | langブロック内コードの `:::` | コード内の `:::` ではlangブロックを閉じない |
| 17b | `test_lang_block_containing_triple_colon_in_code_fence_removed` | langブロック内コードの `:::` | 外側の閉じ `:::` までをブロックとして除去 |
| 18 | `test_tilde_code_fence_tracked` | `~~~` コードフェンス内の `:::` | 無視される |

## Phase 6: 構文バリエーション

| # | テスト名 | 入力パターン | 検証内容 |
|---|---------|-------------|---------|
| 19 | `test_no_space_before_brace` | `:::{lang=en}` | 認識される |
| 20 | `test_extra_spaces` | `:::  { lang = en }` | 認識される |
| 21 | `test_quoted_attribute` | `::: {lang="en"}` | 認識される |
| 22 | `test_trailing_text_after_brace_is_not_lang_block` | `::: {lang=en} some text` | Pandoc fenced div としては不正なため通常行として保持 |

## Phase 7: 非lang fenced div

| # | テスト名 | 概要 | 検証内容 |
|---|---------|------|---------|
| 23 | `test_non_lang_div_passed_through` | `::: {.callout-note}\n...\n:::` | そのまま出力 |
| 23a | `test_lang_attribute_after_class_is_filtered` | `::: {.note lang=en}\n...\n:::` | 属性順序に依存せず `lang` を検出してフィルタ |
| 24 | `test_non_lang_div_with_lang_blocks` | 非lang div + langブロック混在 | 非lang div保持、langブロックはフィルタ |
| 25 | `test_bare_triple_colon_normal` | `:::` のみの行 (NORMAL状態) | そのまま出力 |

## Phase 8: エッジケース

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

## Phase 9: CLI統合テスト

| # | テスト名 | 概要 | 検証内容 |
|---|---------|------|---------|
| 35 | `test_cli_filter_from_file` | ファイル入力 | 正しくフィルタされstdoutに出力 |
| 36 | `test_cli_filter_to_output_file` | `-o` で出力先指定 | ファイルに書き込まれる |
| 37 | `test_cli_default_lang_is_both` | `--lang` 省略 | bothモード |
| 38 | `test_cli_stdin` | stdin入力 (monkeypatch) | 正しくフィルタ |

## Phase 10: 全体統合テスト

| # | テスト名 | 概要 |
|---|---------|------|
| 39 | `test_full_document_en` | 実文書相当の入力を lang=en でフィルタ。en内容+共有コンテンツが残り、ja内容が消える |
| 40 | `test_full_document_ja` | 同上を lang=ja で |
| 41 | `test_full_document_both` | 同上を lang=both で。入力と完全一致 |

---

## 実装順序

t-wada式の RED → GREEN → REFACTOR サイクルに従い、上記Phase順にテストを書いて通す:

1. Phase 1 (#1-#3): `filter_lang` のシグネチャとパススルーを確立
2. Phase 2 (#4-#7): 単一ブロックのkeep/removeで状態機械の骨格を実装
3. Phase 3 (#8-#10): 複数ブロック処理の確認
4. Phase 4 (#11-#14): 共有コンテンツが壊れないことを保証
5. Phase 5 (#15-#18): コードフェンス追跡を追加
6. Phase 6 (#19-#22): 正規表現の柔軟性を確認
7. Phase 7 (#23-#25): 非lang divとの共存
8. Phase 8 (#26-#34): エッジケース網羅
9. Phase 9 (#35-#38): CLI層
10. Phase 10 (#39-#41): 実文書相当の統合テスト
