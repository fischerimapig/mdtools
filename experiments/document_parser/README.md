# 内製Document parser先行試作

M2-redesign #52のレビュー用。原稿構造を内製し、要件候補の概要まで動かす。本番のparser/CLIへは接続していない。依存は標準ライブラリと既存core.source/core.pandocのみ。markdown-it-pyは参照資料であり、実行・テスト時には不要。

[要求と分担計画](../../docs/design/m2-redesign/plan.md)、[設計と対応表](../../docs/design/m2-redesign/design.md)、[短いトレース](../../docs/design/m2-redesign/traces.md)、[検証・性能結果](../../docs/design/m2-redesign/results.md)、[Issue改訂案](../../docs/design/m2-redesign/issue-revisions/README.md) を参照。

以下は試作worktreeのルートで成功を確認したコマンド。現在のworktreeは /home/coder/mdtools/.worktrees/m2-redesign。初回環境構築は既存uv.lockに従う uv run --locked pytest -q で実施済み。

~~~sh
cd /home/coder/mdtools/.worktrees/m2-redesign
.venv/bin/python -S -m experiments.document_parser experiments/document_parser/corpus/demo.md --trace
.venv/bin/python -m pytest -q experiments/document_parser/tests
.venv/bin/python -m experiments.document_parser.tests.report
.venv/bin/python -m experiments.document_parser.benchmark --repeats 3
~~~

1番目は元byte範囲・SourceSpan行列・raw slice・属性・Inlineを含むJSON dumpと、REQ-Aの概要を返す。通常の入力ファイルも同じ入口で渡せる。--traceを外すと構造dumpからrawを省く。CLI終了コードは complete=0、partial/rejected=2、failed/入力読込失敗=3。終了0は仕様の意味検査成功を表さない。

Python入口は parser.parse_document(source, *, profile=PROFILE, limits=Limits()) と projection.summarize_requirements(document)。profileは mdtools-document-prototype-v0。全候補の全ID属性、本文原文、言語、mdspecの所属と範囲を残す。候補は未検証であり、欠落/重複IDや不正JSONを受理した要件と呼ばない。JSON・要件規約・参照・式の検査表示はすべてnot-run。

対応は段落・見出し境界・fence・汎用Div・front matter・字下げ・pre/コメント、限定Inline、単一行参照定義。複雑list/quote/table/一般HTMLと複数行参照定義は未対応を示す。強調等の装飾は原文textとして保持し、rendererを提供しない。これはCommonMark完全準拠の宣言ではない。

limitsは既定4 MiB、200,000 nodes（BlockとInlineの合計）、Div深さ64、leaf最大2 Miコードポイント。Inlineの先読み予算も所有範囲長から制限する。上限到達はnoticeと未解析範囲を残す。原文snapshotと索引の確保はmax_bytes拒否より前に行うため、この上限はプロセスメモリの保証ではない。

tests/legacy_adapter.pyだけが旧parserを呼ぶ。固定コーパスの再観測用で、本番・新parserの出力やfallbackには使わない。現在の製品treeは固定M2と同じ。後続工程で製品parserを変更する際はR1で旧基準の再現環境を分離する。

wheelの既存package列挙に加え、sdistからexperimentsと本レビュー資料を除外している。pyprojectの変更はこの配布除外のみで、uv.lockとruntime依存は変更していない。
