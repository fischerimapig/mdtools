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

## Issue #37 厳格ローダーの検証チェックリスト

分岐元はPR #44・#45を含むM2の`8d6e6ea`。変更前の全テストを再実行し、820 passed, 1 skippedを確認した。以下はローダーへ実原稿を渡す検証であり、#35の手構築モデルテストとは別に維持する。

| 再現入力・責務 | 期待結果・診断・状態 | 出典の確認 | テスト |
|---|---|---|---|
| cancellationのdefinitions.json | paid/shipped/cancel_allowedと範囲内の定数14、complete | 元ファイルsnapshotと全フィールド | test_loader.py: test_real_cancellation_and_model_contract_definitions |
| model-contractのdefinitions.json/yaml | 型・変数・定数・6明示参照が等価。別snapshotを維持、complete | 宣言名・型・値・glossaryの元トークン | 同上 |
| glossary.json / JSON-YAML等価表示データ | IDの空白、term/const/symbolと任意表示データを保持。式・型へ変換しない | ネストした表示フィールドもpointerで保持 | test_loader_glossary.py |
| duplicate-definitions.json、重複区分、types/variables/constants同名 | 全候補を保持。spec.invalid-definition / spec.duplicate-name、partial | 主位置と先行位置を保持 | test_loader.py: duplicate各テスト |
| glossary entry ID重複、entry内/表示データ内キー重複 | ID重複は両候補保持、spec.duplicate-glossary。フィールド重複は該当entry拒否、spec.invalid-glossary。partial | 両位置・拒否原文slice | test_loader_glossary.py / test_loader_yaml.py |
| 未知版、version欠落/誤型/重複、未知フィールド、区分誤型 | 未知版はv1を適用せずunsupported。他はfailed。partial、拒否原文保持 | version/問題のkey・値、既知container | test_loader.py |
| 不正名/予約語、type/role、int境界/bool、列挙、定数値 | spec.invalid-definition。最小/最大/単一点/大きな整数は受理。boolをintとしない | 不正値と上下限・列挙重複の両位置 | test_loader.py |
| missing-glossary.json、未収集の名前付き型 | ローカルcomplete。参照と名前付き型所属検査を#38へ留保 | 型/glossaryのReference.origin | test_loader.py |
| 不正宣言・entryの後の正常要素 | 不正一件だけ拒否し正常兄弟を保持。全体partial。構文破損は文書全体拒否 | 各拒否断片とsnapshot.sliceが一致 | test_loader.py / test_loader_glossary.py |
| unsupported.yaml、anchor/alias/merge/tag/複数文書/directive | spec.unsupported-syntax、structure=unsupported、declarations=not-run、partial。実行・展開しない | 問題の構文トークンと文書全体の拒否断片 | test_loader_yaml.py |
| 引用/block scalar、yes/no/日付/01/hex、true/false/null/有限数 | 引用・blockは文字列、plainは契約のJSON scalar規則。型を推測せず必要なら宣言不正 | デコード値と元トークンを分離 | test_loader_yaml.py / test_loader_sources.py |
| PyYAMLをimportできない環境 | JSON complete。YAMLはspec.missing-dependency、unsupported/unavailable、依存名保持 | 元snapshot保持、架空の解析位置なし | test_loader_yaml.py |
| ファイル未存在・UTF-8不正・ディレクトリ | DefinitionReadError.reportにspec.read-error/tool-error、structure=error、他6検査not-run | sources空、pathをEvidenceへ保持 | test_loader_sources.py |
| Unicode・絵文字・結合文字・LF/CRLF/単独CR・JSON/YAML escape | 値と原文が一致し、デコード後offsetを位置に流用しない | 元bytes/hash/URI/path、各fieldのslice | test_loader_sources.py |
| JSON Pointerにslash/tilde・表示配列 | RFC 6901のpointerと正確な元値 | /a~1b~0c/ja/0等 | test_loader_sources.py |
| Workspaceの明示登録と未登録/生成物 | definitionsだけを登録順に解析。未登録や生成物を走査しない | 各結果のsource.pathが登録pathと一致 | test_loader_sources.py |
| 共通レポートと副作用 | 正常/不正/unsupported/読込失敗を既存診断Schemaで検証。stdout/stderr出力なし | reportのsnapshot検証 | test_loader_sources.py |
| CLIと任意依存を禁止したpython -S | 新ローダーのJSON利用が成功、参照とM3は理由付きnot-run | 共通診断JSONへ元snapshotを保持 | mdtools/tests/test_boundaries.py |
| 既存glossary CLIと#36 | 後勝ち・警告・表示・終了コード、JSON重複で停止する既定動作を維持 | 既存の出典・回復テストを維持 | test_loader_glossary.py、既存全テスト |

ローダーテストは`test_loader.py`（構造・宣言・fixture・回復）、`test_loader_yaml.py`（YAML能力・依存不足）、`test_loader_glossary.py`（表示データ・重複・既存CLI）、`test_loader_sources.py`（出典・Workspace・読込失敗）へ分ける。`_loader_helpers.py`は原文builderと出典assertionだけを持ち、型モデルを手構築しない。

- [x] 追加107件が成功。固定seed 37による6,000件の不正JSONレコードでも未処理例外なし（補助確認であり、受け入れテストの代替ではない）。
- [x] 変更後の全テスト：927 passed, 1 skipped。CLI help 10経路、文書round-trip/見出し構造、README glossary参照検証が成功。
- コミット・push・M2向けPRと最新pushコミットのCI照合結果はPRへ記載する。このチェックリストのローカル検証とは区別する。

```bash
.venv/bin/python -m pytest mdtools/spec/tests/test_loader.py mdtools/spec/tests/test_loader_yaml.py mdtools/spec/tests/test_loader_glossary.py mdtools/spec/tests/test_loader_sources.py -q
.venv/bin/python -m pytest -q
.venv/bin/mdtools mdsplit verify docs/spec/contract-v1_sections/hierarchy.json
git diff --check
```

参照解決・ファイル間衝突・名前付き型の値所属は#38、サービス/IR/Schemaは#39、spec CLIは#40へ残す。M3・LLM・#31の変更、マージ・Issue Closeは行わない。
