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

## Issue #38 SpecGraphの検証チェックリスト

分岐元は#36/#37のマージ済みM2先端`0ea9ff7`。着手時は`issue/38-spec-graph`の作業ツリーがクリーンで、fetch後もM2先端が一致していた。変更前の全テストは927 passed, 1 skipped。

| テスト | 責務・受け入れ条件 |
|--------|------------------|
| test_resolved_contract.py | 手構築値に対するbuiltin許可/拒否、非pendingの誤判定、partialやpendingを隠すreferences=passed、宣言検査未完了・列挙値不所属を隠すdeclarations=passed、読み取り専用registries、入力なしの成功拒否 |
| test_contract.py | #35の既存契約。pendingは未実行として許可。以前許していた誤ったundefined/wrong-kindはtest_resolved_contract.pyで拒否し、衝突時はdeclarationsもfailedに補正 |
| test_resolver.py | 全入力収集後の前方参照、名前空間優先、builtin特例、種別混在/全候補不適合のambiguous、別空間複数候補のwrong-kind、未定義、列挙値所属と未実行理由、再定義拒否の保持 |
| test_resolver_collisions.py | 4名前空間の未参照衝突、同一snapshotの要件/モデル重複、コードと両位置による既報告抑制、別の同コード衝突、ファイル内/ファイル間の併存、先行する全別snapshot候補、unmappedとcontainer |
| test_resolver_states.py | 入力0件/全unavailable、正常0ノード/拒否0ノード/混在、全状態の優先順位と全理由、ローカルreferencesの除外、不正参照優先、拒否断片から候補を推測しない、入力型/同一SourceRefの拒否 |
| test_resolver_sources.py | cancellation/model-contractの実parser/loader結合、回復・未知版・missing-glossary・重複定義、元bytes/hash・Unicode/改行/escape・診断位置・拒否slice、自己参照/循環/重複refs、移動/見出し/順序とID・SourceRef/ordinalの区別、I/Oと標準出力なし |
| mdtools/tests/test_boundaries.py | import方向・循環なし、CLIと任意依存を禁止したpython -Sでparser/loader/resolverから共通診断まで利用 |

追加のbuilderは`_resolver_helpers.py`で実原稿を作り、公開parser/loaderを呼ぶ。判定を代替実装しない。値モデルとresolverの実行テストを分け、既存#36/#37の回帰を維持する。

- [x] 不足を補う変更前の値モデル回帰テストで9件の失敗を再現。
- [x] builtinはtype/resolvedとuses/wrong-kindのみ。架空のノード・宣言位置なし。refs/glossaryには特例なし。
- [x] 全ノードと全明示参照を保持し、モデル所属や見出しから暗黙辺を作らない。M3は全て理由付きnot-run。
- [x] 診断の追加抑制と衝突状態を分離。全snapshot・ローカル診断・拒否断片をそのまま保持。
- [x] 宣言値不所属と型未解決による所属未実行を区別し、他の失敗が優先しても未実行理由を保持。
- [x] 関連135件（既存契約・新規契約/resolver・import境界）が成功。
- [x] 最終の全テスト：**1012 passed, 1 skipped**。skipは従来の外部combined.md未配置。既存927件に対し、旧契約の2ケースを厳格な拒否テストへ置き換え、87件を追加した。
- [x] import境界・python -S、#34の見出し順序/親子構造、4文書の分解・再合成バイト一致、CLI help 10経路、README glossary参照、git diff --checkが成功。

再現コマンド：

```bash
.venv/bin/python -m pytest mdtools/spec/tests/test_contract.py mdtools/spec/tests/test_resolv*.py mdtools/tests/test_boundaries.py -q
.venv/bin/python -m pytest -q
.venv/bin/mdtools mdsplit verify docs/spec/contract-v1_sections/hierarchy.json
.venv/bin/mdtools mdsplit compose docs/spec/contract-v1_sections/hierarchy.json -o /tmp/spec38-composed.md
diff -u docs/spec/contract-v1.md /tmp/spec38-composed.md
.venv/bin/mdtools glossary verify README.md -f docs/glossary/defs.yaml
git diff --check
```

契約とREADMEはsection原稿を編集してcanonicalを再生成した。全テスト、#34の見出し順序・親子構造、4文書の文字列round-trip、既存CLI help 10経路、glossary参照、diff checkを最終検証した。コミット・push・M2向けPR・最新push/PR head/CI対象SHAの一致とCI結果はPRに記載し、このローカル検証と区別する。

#37のP3制限2件、#39のサービス/IR/Schema、#40のCLI、M3、LLM、#31は変更しない。マージ・Issue Closeは行わない。

## Issue #39 SpecIR・共通解析サービスの検証チェックリスト

基準はPR #47マージ後のM2先端`4d9535a685997713f98966f9e229d67a459cc99b`。着手時の作業ツリーはクリーン。現在の#38作業ツリーとM2先端のtreeが同一であることを確認し、変更前の全テストを再実行して1012 passed, 1 skippedを確認した。

| 検証 | 保証する範囲 |
|------|--------------|
| mdtools/tests/test_analysis.py | cancellation/model-contractを実サービスへ入力。本文・言語・モデル・式未検査・共有定義・glossary・元snapshotを保持。回復/拒否/未知版、未定義/wrong-kind/衝突/曖昧参照をpartialとして保持 |
| 同上・I/O責務 | 設定不正/未知版/UTF-8不正、読込失敗/producer失敗、YAML依存不足と正常入力の混在。resolverだけcompleteでも全体partial。読めない入力のsnapshot/LocalAnalysisなし。resolver失敗時も実入力を保持 |
| 同上・snapshot/順序責務 | 設定・hierarchyの読込直後の変更でも選択に使ったhashと一致。全取得ファイルのbytes/hash、Unicode/絵文字/結合文字/LF/CRLF/CR/JSON escapeの原稿sliceを照合。順序・移動・見出し変更でIDを再生成しない。未登録原稿を除外 |
| mdtools/spec/tests/test_ir.py | サービス生成の正常/partial/unavailable JSONをDraft 2020-12で検証。未知版/不正状態/負ordinal/hash終端LF/M3成功偽装/atomic表記等を拒否。診断v1 Schemaも参照検証。全登録入力の欠落をcompleteとする値を拒否 |
| 同上・純粋変換責務 | I/O禁止下の変換、出力dictの独立性、同一snapshotでの決定性、固定例の再生成一致。例のfile:///example URIはメモリで明示構築した説明用snapshotであり、実ファイル取得成功を主張しない |
| mdtools/tests/test_boundaries.py | analysisだけにworkspace/core/spec依存を許可。逆依存・循環なし。CLI/YAML/dev validator/backendを禁止したpython -Sでサービス→IR JSON、stdout/stderrなし |
| 既存全pytest | #35～#38と既存CLI、M1診断Schema、#34のbase_level・見出し順序・親子構造を回帰確認 |

- [x] 全テスト：**1050 passed, 1 skipped**。追加38件。skipは従来の外部combined.md未配置。
- [x] README、mdsplit README、契約、core-refactorの4文書で既存section composeと分解・再合成のバイト一致を確認。
- [x] 契約/root READMEはsection原稿からcanonicalを再生成。#34の構造検査と契約の20 sectionを維持。
- [x] CIと同じCLI help 10経路、README glossary list/verify、git diff --checkが成功。

再現：`.venv/bin/python -m pytest -q`。個別責務は上表のテストを指定する。Schema validatorはdev依存だけで、JSON実行経路の必須依存は増やしていない。通常の原稿・式・参照を再パースする別経路は追加していない。設定/hierarchyの読込callbackは選択とmanifestの整合を保つための追加で、既存load_workspaceとsnapshot_sourcesの既定挙動は維持する。

#37の深いglossary出典検証RecursionErrorとPyYAMLによる未知directive破棄は未修正。前者がサービスへ漏れればexecution-errorとして扱うが、ローダー自体の制限解消ではない。#31、#40 CLI、M3、M4以降、LLM/solver、IR書戻しは対象外。コミット・push・PR head・CI対象SHAとCI結果はPRに記載し、このローカル検証と区別する。マージ・Issue Closeはユーザーが行う。

### PR #48 レビュー対応：設定の自己登録

基準HEADは`c820365611bfee2b951f293a9c7c12a0bea8542e`。[第一段階レビュー](https://github.com/fischerimapig/mdtools/pull/48#pullrequestreview-5731990301)のP3を修正した。設定名を`.md`にして自身を本文登録すると、修正前は同一パスとsymlinkで`ValueError('duplicate source snapshot')`、hard linkでは誤ってcompleteとなることを、追加したサービス結合テストの失敗で再現した。

- [x] 設定とrootの検証後に設定の実体を既存Registryへ予約。生成物、文書とその参照、共有定義をその後に登録する。正規化パスとdevice/inodeによる既存の判定を使い、snapshotの黙った重複除去は追加しない。
- [x] `test_workspace.py`に18ケース追加。自己登録・`.`/`..`・symlink・hard link、hierarchy/preamble/section/spec/glossaryへの二重登録は`workspace.duplicate-input`。canonical/generatedとの衝突は`workspace.generated-input`。root内外の`.md`名の設定から別本文を登録する正常例も成功する。
- [x] `test_analysis.py`に6ケース追加。本文登録と生成物登録の同一パス・symlink・hard linkを実サービスへ渡し、unavailable、workspace/resolved/irなし、inputs空、`workspace.sources=failed`、M2の3検査が理由付きnot-runとなる。設定snapshotとmanifest entryは取得済みの1件だけを保持し、設定本文・hashも一致する。
- [x] Workspace契約のsection原稿に設定自身も重複検査対象であること、予約順、診断コード、設定名の拡張子を制限しないことを追記し、canonicalを再生成した。

### PR #48 レビュー対応：IR JSONの内容保持

serializerの誤変換が確認されたものではなく、既存テストの回帰検出不足への対応。`test_ir.py`に次の3本を追加し、すべて実サービスから`render_ir_json()`を通したJSONを検証する。期待する意味上の値・順序・ordinal・位置は明示し、出典のURI/path/hashだけを元ファイルから組み立てる。serializerや解析モデルから期待値を生成しない。

| 追加テスト | 内容の保証範囲 |
|------------|----------------|
| `test_service_json_preserves_bodies_model_links_and_expression_tokens` | model-contractの4要件、本文・言語、natural-only、2モデルへの完全なNodeKeyによる結合と順序。when/mustの値、`paid and (`とescapeを復号した`paid == true`、引用符とescapeを含む元トークンの範囲 |
| `test_service_json_preserves_builtins_and_nested_glossary_values` | bool/intのbuiltinと空候補、宣言値false/0、glossaryの入れ子・null・false・0・空文字・配列・空配列・空object。falseと0は値に加え、scalarと配列要素の型も照合 |
| `test_service_json_preserves_all_ambiguous_occurrences_and_candidate_order` | 2原稿にある同名要件3出現と別の参照元をpartialとして保持。同一snapshot内のordinal差と別snapshotのURI/hash/pathを含む完全なNodeKey、本文、曖昧参照3候補の登録順を照合。名前のdict化による重複除去なし |

隔離した作業ツリーのコピーで、無変更の追加3テストが成功することを確認した後、以下を1件ずつ適用した。各変更で対象の追加テストを実行し、JSON内容の不一致による`AssertionError`を確認した。構文・収集エラーを検出成功として数えていない。

| 個別に適用した誤変換 | 検出した不一致 |
|--------------------|----------------|
| candidatesを先頭1件に切り詰める | 期待する3件に対して2件欠落 |
| glossaryを常に空配列にする | 表示entryと入れ子データが欠落 |
| Expression.textを`"true"`に固定する | `paid`等の式原文が変化 |
| modelsのwhen/mustを交換する | whenにmustの`paid == true`が入る |
| builtinのbool/intを交換する | bool参照のbuiltinがintになる |
| requirement.modelを要件自身のkeyにする | modelのnamespace/name/ordinalと不一致 |

- [x] 対象6種類をすべて内容比較で検出。構文・収集エラーによる無効試行は0件。この確認は上記の誤変換に限定し、レビューの未検出25件すべてやコード全体のmutation coverageを保証しない。
- [x] 関連3ファイルは149 passed。全pytestは**1077 passed, 1 skipped**（既存1050件に27件追加、skipは従来の外部combined.md未配置）。
- [x] 4文書の既存section composeとdecompose→composeのバイト一致、#34のbase_level・見出し順序・親子構造、契約の20 sectionを確認。CLI help 10経路、README glossary参照、`git diff --check`も成功。

再現コマンド：

```bash
.venv/bin/python -m pytest mdtools/tests/test_workspace.py mdtools/tests/test_analysis.py mdtools/spec/tests/test_ir.py -q
.venv/bin/python -m pytest -q
```

公開API・正常入力のIR表現・各版は変更しない。#37の既知制限、#31、#40以降は今回の対象外。コミット・push・PR head・CI対象SHAの一致とCI完了はPRへ記録し、上記のローカル検証とは区別する。マージ・Issue Closeは行わない。
