# Issue #36 抽出器の検証チェックリスト

基準HEADは`28c91a3`。この記録は再レビュー後のローカル差分の検証結果であり、過去HEADのCI成功とは区別する。

## 再現と境界条件

- [x] 再レビューの原稿を独立再現。修正前は要件0件・診断0件・complete。
- [x] Pandoc 3.12の`markdown` / `commonmark`からJSON ASTを取得し、下表のCodeトークンを確認。Pandocは調査用であり、抽出器・自動テストの必須依存に追加しない。
- [x] 公開APIへ同じ原稿を入力し、修正後は`REQ-REAL`を1件・診断0件・completeで返すことを確認。
- [x] 出典のsnapshot・本文slice、参照解決とM3のnot-run状態も既存の共通assertionで確認。

| コードスパンの継続候補 | Pandoc markdown | Pandoc commonmark | 今回の抽出器の先読み |
|---|---|---|---|
| `2. not a real comment` | 継続し1個のCode | 継続し1個のCode | 継続。後続要件を保持 |
| `2) continuation` | 継続 | 継続 | 継続。括弧区切りも同じ規則 |
| `1. new item` | 継続 | 段落中断、Codeなし | 従来の中断境界を維持 |
| `1. `だけの行 | 継続 | 継続 | 継続。空項目では中断しない |

単なる「数字＋区切り」の一致を段落中断にしない。先読みでは、非空の1始まりの項目を境界とするCommonMark型の判定を使う。これはPandoc既定markdown readerの全文構文との同値性を保証するものではない。`1.`をPandoc既定の継続へ統一する変更は今回行っていない。

再レビュー例の実動作はリポジトリルートで再確認できる。

```bash
.venv/bin/python - <<'PY'
from mdtools.core.source import SourceSnapshot
from mdtools.spec.parser import parse_requirements

raw = ("The comment marker is `<!--\n"
       "2. not a real comment`.\n\n"
       "::: {.requirement #REQ-REAL spec-version=1}\n本文\n:::\n")
result = parse_requirements(SourceSnapshot("memory:review-numbered", raw))
print([r.key.name for r in result.requirements])
print([d.code for d in result.diagnostics], result.completeness)
PY
```

期待出力は`['REQ-REAL']`、次の行が`[] complete`。

## テストの役割と過去3コミットの整理

| 配置 | 責務・件数 | 由来 |
|---|---|---|
| [test_parser.py](test_parser.py) | 実fixture、属性、6フィールドのJSON構造・不正・未対応・回復。90件 | 主に初期実装`b13634e` |
| [test_parser_contexts.py](test_parser_contexts.py) | フェンス、コメント、pre、front matter、div所属、回復境界。79件 | 初期実装＋`89e39a2`＋`28c91a3`＋今回4件 |
| [test_parser_sources.py](test_parser_sources.py) | Unicode・改行・escape・本文断片・snapshot・Workspace原典選択。8件 | 初期実装から移動 |
| [_parser_helpers.py](_parser_helpers.py) | 原稿builderと共通の出典assertion。モデルを手構築するヘルパーではない | 既存ヘルパーを共通化 |
| [core属性テスト](../../core/tests/test_pandoc.py) | strict lexerの10件は元の場所で維持 | 初期実装`b13634e` |
| [import境界・依存なし実行](../../tests/test_boundaries.py) | 実抽出APIを`python -S`・禁止importの環境で呼ぶ既存テストを維持 | 初期実装で拡張 |
| [test_contract.py](test_contract.py) | #35の値モデル契約47件。抽出器テストとは別に維持 | 先行Issue #35 |

- [x] 初期142件＋前回コメント修正19件＋front matter修正12件＝抽出器173件を整理前後の収集IDで照合し、全件を保持。
- [x] 同じ動作を行数・組合せだけで増やさず、今回の追加は下記4ケースに限定。

| 追加ケース | 修正前 | 修正後 | 検証の目的 |
|---|---|---|---|
| 再レビューの`2.`原稿そのもの | 失敗 | 成功 | 要件欠落を直接検出 |
| `2)`の継続 | 失敗 | 成功 | 数字と括弧区切りの同じ境界規則 |
| 非空`1.`の中断 | 成功 | 成功 | 従来の境界を維持する対照 |
| 空の`1.`の継続 | 失敗 | 成功 | 開始番号だけで中断しない対照 |

テスト名は`test_review_numbered_continuation_keeps_code_span_and_real_requirement`と`test_ordered_marker_boundary_distinguishes_continuation_from_interruption`。いずれも内部正規表現への一致ではなく、実際の抽出要件集合・診断・完全性・出典を検査する。

## 既存の受け入れ条件の確認

- [x] キャンセル要件2件・guidanceとmodel-contractの全Markdown fixtureを実抽出。本文・多言語・natural-only・present・式未検査を保持。
- [x] 必須属性、未知・重複属性、6必須JSONフィールド、型、重複キー・uses、重複を許すrefs、未知版、空本文を確認。
- [x] 外側コード、コメント、pre、字下げコード、引用属性値、front matterからの誤抽出を防ぎ、リテラルのコメント記号で正常要件を隠さない。
- [x] 本物のコメント、空行、要件ブロック境界で先読みを制限。未閉鎖コードや予約構文から推測で回復しない。
- [x] `89e39a2`の複数行コードスパン・HTML属性・タブ混在字下げと、`28c91a3`のscalar内区切りを含む回帰を維持。
- [x] LF/CRLF/単独CR、Unicode・絵文字・結合文字・JSON escape、元ファイル・snapshot・spanを確認。
- [x] sectionごとの解析、生成canonical・未参照原稿の除外、重複IDの保持、参照解決とM3検査のnot-runを維持。
- [x] 全テスト：**820 passed, 1 skipped**。skipは従来の外部combined.md未配置。変更前816件から今回4件追加。
- [x] import境界・CLI/任意依存なし実行、文書round-trip、#34の基準レベル・見出し順序・親子構造を全テストで確認。
- [x] 契約書のsection原稿からcanonicalを再生成し、CLI verifyで20 section、`git diff --check`を確認。

```bash
.venv/bin/python -m pytest mdtools/spec/tests/test_parser.py mdtools/spec/tests/test_parser_contexts.py mdtools/spec/tests/test_parser_sources.py -q
.venv/bin/python -m pytest -q
.venv/bin/mdtools mdsplit verify docs/spec/contract-v1_sections/hierarchy.json
git diff --check
```

## 今回の確認範囲

抽出器の段落先読み境界とテスト整理のローカル検証まで。全Markdown方言との同値性、後続Issueの機能、コミット・push・最新差分のCI確認は、このチェックリストの成功項目に含めない。
