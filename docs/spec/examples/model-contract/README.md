# M2モデル契約fixture

Issue #35のデータ契約の小さな原典例です。#36の抽出器はMarkdown原稿を実際のテスト入力として使います。#37の厳格ローダーは共有定義原稿も実際のテスト入力として使います。#38は両APIの収集結果を結合し、Graphと全体診断を検証します。spec CLIは#40の範囲です。

| ファイル | 期待する扱い |
|----------|--------------|
| normal.md | 構造は正常、active、形式記述あり。paidの解決は全定義収集後 |
| natural-only.md | draftが省略値。本文のみ、形式化なし、論理未実行 |
| multilingual.md | 一つの要件IDにja/en本文、Unicode/絵文字の原稿範囲を保持 |
| unchecked.md | 構造は正常。式文法不正・usesとの不一致もM2では判定しない。escapeを含む原稿範囲とデコード後の式を区別 |
| invalid.md | ID欠落を拒否断片と診断に残し、REQ-RECOVERを収集してもpartial |
| broken-model.md | 必須when/must欠落。形式化present・構造failed、natural-onlyにしない |
| unsupported.md | spec-version=2を推測して読まず、unsupported・partial |
| definitions.json / definitions.yaml | 同じ型・変数・定数。出典は別snapshot。どちらか一方だけをWorkspaceへ登録 |
| glossary.json | 既存entries形式。空白を含むID、term/symbolへの明示関連付け |
| missing-glossary.json | 関連付け先なし。全体解決でspec.undefined-glossary、references=failed、partial |
| duplicate-definitions.json | 同じ文書の重複キー。辞書上書きで隠さずspec.invalid-definition、partial |
| unsupported.yaml | anchor/aliasは未対応。spec.unsupported-syntax、unsupported、partial |
| cli-show-unknown.json | 将来のJSON envelope例。解析completeでも対象不存在は終了3。M1診断JSON v1を埋め込む |
| cli-index-missing-yaml.json | 将来のJSON envelope例。任意依存不足はunavailable・終了5、未実行検査を成功にしない |

`mdtools.toml`は正常な構造の原稿4件、JSON共有定義、glossaryだけを登録します。`unchecked.md`の式は意図的に未検査です。構造と明示参照の正常性は論理的な成功を意味しません。不正例はこのWorkspaceに含めず、各後続Issueの異常系入力として利用します。従来のキャンセル要件例は変更しません。

`expectations.json`はMarkdown原稿のローカル結果の期待値であり、生成SpecIRの形式ではありません。`mdtools/spec/tests/examples.py`はテスト作者が指定したトークン・本文位置から型を手で構築します。これはパーサーの代替実装ではなく、#36/#37が同じ型を生成する際の参照例です。単体テストは原稿slice、snapshot、状態、不変条件、手で与えたGraphの入出力を検証します。

`mdtools/spec/tests/test_parser.py`は`parse_requirements(SourceSnapshot.from_path(...))`を通して全Markdown fixtureを解析します。`expectations.json`の状態・言語・診断コードを照合し、追加の出典・異常・回復テストを実行します。同じコードの複数診断が出る場合もあります。例えばbroken-model.mdは欠落するwhen/mustそれぞれの診断を持ちます。

追加テストは文脈・回復の`test_parser_contexts.py`と出典・Workspaceの`test_parser_sources.py`へ整理しています。初期実装・レビュー修正を含む検証項目と再現結果は[チェックリスト](../../../../mdtools/spec/tests/README.md)を参照してください。

契約は[仕様記述契約v1](../../contract-v1.md)の「M2 / #35 仕様モデルと解析結果」「M2 index/showの入出力・診断契約」を参照してください。厳格JSON/YAML・glossary読み込みテストは#37、衝突診断・参照解決・列挙型定数の所属検査は#38で追加済みです。IR Schema/シリアライズは#39、コマンドの実行と出力検証は#40で追加します。

#37の実入力テストは`mdtools/spec/tests/test_loader*.py`です。definitions.json/yamlの同じ宣言・明示参照、glossary.jsonの表示データ、duplicate-definitions.jsonの全候補と両位置、unsupported.yamlの拒否を確認します。missing-glossary.jsonはローカルではcomplete・references=not-runで、未定義診断は#38に残します。YAML依存不足は既存の元snapshotを保持したunavailable、ファイル取得失敗はsnapshotを捏造せずDefinitionReadError.reportへ返します。

#38の実fixture結合は`test_resolver_sources.py`で検証します。正常Workspaceは全明示参照resolved・complete、missing-glossary.jsonはspec.undefined-glossary・partial、duplicate-definitions.jsonは既報告診断を保持してreferences/declarations=failedです。invalid.md・broken-model.md・unsupported.mdは元の拒否断片・診断を保持してpartialのままです。式が壊れているunchecked.mdでも、M2の構造・参照とM3の式未検査を分けて保持します。
