# M2受け入れハーネス

[#13](https://github.com/fischerimapig/mdtools/issues/13)の機能受け入れを、[#41](https://github.com/fischerimapig/mdtools/issues/41)のシナリオと対応付ける。部品の単体・結合テストに加え、実原稿→Workspace→抽出→共有定義→参照解決→IR→CLIを別プロセスで検証する。テストは生成物から期待値を作らず、重要な本文・式・宣言・候補・位置・順序を独立して指定する。

## 実行と出力

リポジトリルートで実行する。

```bash
.venv/bin/mdtools spec index --project docs/spec/examples/m2-acceptance/mdtools.toml --format json
.venv/bin/mdtools spec show REQ-SECTION --project docs/spec/examples/m2-acceptance/mdtools.toml --format text
.venv/bin/mdtools spec index --project docs/spec/examples/cancellation/mdtools.toml --format json
.venv/bin/python -m pytest mdtools/tests/test_spec_acceptance.py -q
```

新しい[例](examples/m2-acceptance/README.md)は通常文書・section原稿・共有JSON定義・glossaryを組み合わせる。rootはexamplesディレクトリで、既存model-contractの定義を共有する。通常文書の説明例は要件0件、section原稿とnormal.mdからはREQ-SECTION、REQ-DETAIL、REQ-NORMALの順に3要件を収集する。REQ-SECTIONはja/enの2本文と1モデル、REQ-DETAILはnatural-only。自己参照と循環参照も明示されている。生成manual.mdや未登録原稿を本文として再収集しない。

JSONのstdoutは末尾LF付き単一object。indexのresultはSpecIR、showのresultは指定要件の全出現と関連情報、queryは問い合わせID、reportはWorkspace全体の診断JSON v1である。通常の正常・不正原稿・未知IDのstderrは空。引数不備はstdout空・stderrにusage。textも同じ内容と全体診断、未実行の検査を表示する。詳細は[契約](contract-v1.md#m2-indexshowの入出力診断契約)、[IR Schema](spec-ir-v1.schema.json)、[診断Schema](diagnostics-v1.schema.json)を参照する。showの選択で全体の失敗を隠さない。

| 終了コード | 意味 |
|---|---|
| 0 | M2解析と表示成功 |
| 1 | 設定・原稿・宣言・参照の不正、未知版・未対応構文 |
| 2 | 引数不備 |
| 3 | 全体completeだがshowの要件IDが不存在 |
| 4 | I/O・UTF-8・内部処理の実行失敗 |
| 5 | 実際の入力に必要な任意依存の不足 |

優先順位は **2→4→5→1→3→0**。partial/unavailableの元の終了1/4/5を、showの対象有無で0/3へ置き換えない。

## 受け入れ条件とテスト

以下のE2E名は[受け入れテスト](../../mdtools/tests/test_spec_acceptance.py)の関数名から`test_`を省略したもの。他のテスト名・配置もリポジトリルート基準。

| #41 | #13の機能・受け入れ | 主な自動検証 |
|---|---|---|
| 1 複数文書・section・共有定義 | 原典選択、Graph/IR、共通APIとCLI | E2E `originals_service_cli_content_and_determinism`：取得9ファイルの役割・順序・hash、3要件の完全なkey、詳細とAPIの一致。二重登録拒否はtest_workspace.py、test_analysis.py |
| 2 日英本文と単一形式記述 | 要件抽出・多言語保持 | 同E2E：ja/en本文とMODEL-SECTION所属。最大1モデルの拒否はtest_parser_contexts.py |
| 3 natural-only・通常0件 | 未検査の区別 | 同E2Eと`zero_requirements_and_rejected_syntax[None]`：説明例のみのWorkspaceもcomplete・終了0 |
| 4 重複・未定義参照 | ID/参照・厳格定義読込 | E2E `collisions_undefined_and_show_global_failure`：全候補・宣言・未定義4種・両位置・全体診断。全名前空間の衝突・元トークン精度はtest_resolver_collisions.py、test_resolver_sources.py、test_loader*.py |
| 5 不正・未知版・未対応構文 | 壊れた予約構文を捨てない | E2E `zero_requirements_and_rejected_syntax`の異常5ケース：partial・終了1・診断と保持内容。細かな回復境界はtest_parser*.py |
| 6 fence・コメント・front matter・pre | 誤抽出防止と#34 | 同E2Eの正常0件。test_parser_contexts.py、mdsplit/tests/test_parser.py、test_document_structure.py：独立した見出し件数・順序・親子構造と文字列round-trip |
| 7 移動・見出し・並べ替え | IDと参照同一性 | E2E `move_heading_and_registration_order`：移動だけのhash不変、本文変更のhash/位置更新、設定/hierarchy snapshot、要件順・参照維持 |
| 8 自己参照・循環 | Graphと文書階層の分離 | 正常E2E：全明示辺と候補を照合。timeout付き実CLIが終了し、showはrefs先本文を展開しない |
| 9 決定性と公開Schema | 決定的IR・診断と出典 | 正常／異常E2Eの出力再実行一致とSchema適合。内容比較は別assertion。test_ir.pyはSchemaの不正値拒否とシリアライズを確認 |
| 10 許可・禁止の保持 | M2/M3の責務分離 | E2E `cancellation_handoff`：両must・when・uses・元位置・宣言値・理由付きnot-run |
| 11 YAMLあり／なし | 任意依存とCLI非依存 | E2E `real_yaml_presence_and_absence`：実PyYAMLと`python -E -S`でJSON成功／YAML不足・終了5。test_boundaries.pyはCLI/validator/solver/LSPのimportを禁止して同じ原稿を共通サービスへ渡す |

[既存CLIテスト](../../mdtools/tests/test_spec_cli.py)は引数・help・未知対象・名前空間・部分結果・実行失敗・依存不足・複数問題の終了コード優先順位を担当する。E2Eで同じ組合せを重複展開しない。[テスト履歴](../../mdtools/spec/tests/README.md)と各部品テストはそれぞれの契約を引き続き保護する。

## CIと再現方法

既存[CI](../../.github/workflows/ci.yml)のM2向けPR上で、全pytest（単体・結合・E2E・Schema・import境界・見出し構造）、既存／新CLI smoke、5文書のround-trip、README glossary参照を実行する。PyYAMLはlocked dev環境で利用し、なし経路は同じテストから`python -E -S`を起動してsite-packagesとPYTHON環境変数の影響を除く。別環境の手動uninstallは不要。

```bash
.venv/bin/python -m pytest -q -rs
.venv/bin/mdtools mdsplit verify docs/spec/examples/m2-acceptance/manual_sections/hierarchy.json
.venv/bin/mdtools glossary verify README.md -f docs/glossary/defs.yaml
git diff --check
```

Schema validatorはdev依存だけである。JSON-onlyのruntime依存は増やさない。検証記録には対象SHA・差分・成功／失敗／skipを添え、他のSHAのCI成功を転用しない。既存の外部combined.md未配置skipは受け入れテストのskipとは区別する。

## 保証の限界とM3への引継ぎ

M2 complete／終了0は構造・宣言値・明示参照の範囲だけを保証する。式構文・式型・式中識別子とusesの照合・論理はそれぞれ理由付きnot-run。キャンセル例のtrue/false両要求も保持するが、無矛盾性や本文との意味的一致を保証しない。M3は式原文、元の引用・escapeを含む出典、uses、型・役割・範囲・列挙・定数値と参照候補を受け取る。式ASTや検査済み状態をM2で捏造しない。

原典、生成canonical/IR、DocumentTree、SpecGraph、意味上のID、URI/hash/ordinalによる出現は別の情報である。snapshotは呼出しごとのper-file取得で、atomic snapshotや現在の鮮度は保証しない。

#31の「断片末尾CR＋次断片先頭LF」によるSourceMap構築失敗は未解消で、通常のCRLF原稿全般の問題ではない。#37の深いglossary出典検証のRecursionErrorとPyYAMLによる未知directive破棄も既知制限として残る。サービスのexecution-error報告はローダーの制限解消を意味しない。

M3の式検査/Z3、M4のcontext/差分/鮮度、M5のbuildゲート、LLM、パッケージ版・リリースタグはこの受け入れの対象外。#41のマージ・Closeと、M2全体のspec-integrationへの統合は別の工程である。
