
`mdtools.core` は、各ツールに重複していた I/O、Markdown スキャン、Pandoc/Quarto 属性処理を集約した内部共通パッケージです。公開 CLI は維持し、内部実装だけを共有しています。

```mermaid
flowchart TB
    cli["既存CLI"] --> build["mdtools.build"]
    cli --> docs["既存文書処理"]
    build --> docs
    docs --> core["mdtools.core: I/O・走査・属性・位置・診断"]
    workspace["mdtools.workspace"] --> tree["mdsplit.schema"]
    tree --> core
    workspace --> core
    diagnostics["mdtools.diagnostics: 診断組立て"] --> workspace
    diagnostics --> core
```

矢印はimport・API利用の方向です。workspaceは文書階層を知る原典選択の組立て層、`mdtools.diagnostics`はWorkspace固有エラーの診断組立て層としてcoreの外に置きます。core・文書処理からCLI・組立て層・将来のspec/backendへ逆依存しません。要件ID解決・要件や制約の意味・検査計画は将来のspec層の責務です。

実施記録は [docs/plans/core-refactor.md](docs/plans/core-refactor.md) にあります。用語としての []{.term id=mdtools-core} は `docs/glossary/defs.yaml` でも管理します。

仕様管理機能の開発は [仕様記述契約 v1](docs/spec/contract-v1.md) を基準に進めます。
要件ブロック、共有定義、生成IR、出典・診断と既存CLIの責務境界、およびM1〜M9の対応範囲を記載しています。
[キャンセル要件の例](docs/spec/examples/cancellation/README.md) も参照してください。
M1 / #23のWorkspace設定v1と`mdtools.workspace.load_workspace()`は、明示登録した原典・共有定義と生成物を区別して解析対象を決定します。
[実行可能な設定例](docs/spec/examples/cancellation/mdtools.toml) と契約の「Workspace設定 v1」を参照してください。新しい仕様解析・検査CLIは後続Milestoneで実装します。
M1 / #24は`mdtools.core.source`のsnapshot・1-based位置・半開範囲と、`snapshot_sources(workspace)`、`mdsplit.compose.compose_with_source_map()`を提供します。
位置対応はcompose単独までで、生成見出し等は合成位置、langfilter・glossary等の後段変換は未対応です。詳細は契約の「出典と診断の共通契約」を参照してください。

M1 / #25は`mdtools.core.diagnostics`の共通診断・明示的な検査状態・決定的なテキスト/JSON v1出力と、`mdtools.diagnostics.inspect_workspace()`の最小利用経路を提供します。
API・分類・位置なし診断・根拠・表示規則は契約の「M1 / #25 診断APIと検査状態」以降、機械可読形式は[診断JSON v1スキーマ](docs/spec/diagnostics-v1.schema.json)を参照してください。
#31の断片末尾CR＋次断片先頭LFによるmap構築失敗は未解消で、この経路の正確な原稿追跡は保証しません。通常のCRLF本文全般の問題ではありません。

M1 / #26ではCLI内のbuild本体を`mdtools.build.build_document()`へ、mdsplitの存在チェックを`mdsplit.verify.verify()`へ分離しました。例えば`build_document(input_text="本文", lang="ja")`はCLI・stdinを経由せず文字列を返し、`verify(hierarchy_path)`はsection数と欠落参照を返します。既存の独立した処理APIと互換入口は維持します。責務表、将来の解析サービス・backend・CLI・LSPホストの境界、例外と互換性の詳細は契約の「依存方向と既存CLIの互換性」を参照してください。

M2 / #35では`mdtools.spec.model` / `mdtools.spec.results`に要件・共有宣言・明示参照・ローカル/全体解析結果の不変データ契約を追加しました。M1の出典・診断を再利用し、部分結果と式未検査を保持します。契約の「M2 / #35 仕様モデルと解析結果」「M2 index/showの入出力・診断契約」と[小さなfixture](docs/spec/examples/model-contract/README.md)を参照してください。抽出器・厳格ローダー・Graph構築器・解析サービス・spec CLIは後続Issueで実装します。
