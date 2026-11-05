# 先行試作の実行結果

追記（2026-11-05）：ユーザー指示により、試作ブランチへのcommit/pushが許可された。以下のHEAD・未コミット・未pushの記載とverification.jsonは2026-11-04の検証時点の記録として保持する。PRは作成しない。

2026-11-04、ローカル未コミット差分で検証した。開始/現在HEADは17723261c3a9a47f69b763d4898c1db0d290c0fd、ブランチはissue/52-document-parser-prototype、worktreeは/home/coder/mdtools/.worktrees/m2-redesign。基準b11368128d4e2a476f2204af40bdfdc947f1cc88と同一tree、origin/spec-integrationも1772326であることを取得時に確認した。PR #56のhead/mergeと一致。

[verification.json](verification.json)に環境・内容SHA-256・基準tree・本番差分なし・配布確認を記録。[test-results.txt](test-results.txt)は全テストの実出力。変更は新規experiments/document_parser、docs/design/m2-redesign、およびpyproject.tomlのsdist除外3行。uv.lock、本番Pythonコード、既存契約/section、CIは変更していない。

## テストと再実行

|検証|実行コマンド|結果|
|---|---|---|
|変更前の関連|uv run --locked pytest -q mdtools/spec/tests/test_parser.py mdtools/spec/tests/test_parser_contexts.py mdtools/spec/tests/test_parser_sources.py mdtools/tests/test_boundaries.py|180 passed、1.34s|
|変更前の全体|uv run --locked pytest -q|1137 passed / 1 skipped、20.85s|
|最終試作|.venv/bin/python -m pytest -q experiments/document_parser/tests|132 passed、1.36s|
|変更後の全体|.venv/bin/python -m pytest -q -rs|1269 passed / 1 skipped、19.54s|
|旧診断保存の詳細化後|.venv/bin/python -m pytest -q experiments/document_parser/tests/test_corpus.py|49 passed、0.22s|
|デモ|.venv/bin/python -S -m experiments.document_parser experiments/document_parser/corpus/demo.md --trace|終了0、REQ-A [38,90)、本文・構造・元位置を確認|
|比較レポート|.venv/bin/python -m experiments.document_parser.tests.report|終了0、C19＋I-51の3件がmatched、未承認2件は別表示|
|配布物|uv build --out-dir /tmp/mdtools-m2-prototype-dist-final|wheel/sdistとも成功。試作・レビュー資料のentry 0|
|クリーンなwheel smoke|python -I -Sでwheelをsys.pathへ追加しspec show REQ-NORMALを実行|site-packages/CWDに依存せず、REQ-NORMALとcompleteを確認|
|差分空白|git diff --check と新規テキストの末尾空白検査|成功|

全体テスト後、旧結果の診断をcodeだけからmessage/category/severity/原稿範囲/related/拒否原文付きへ詳細化し、固定M2の製品ファイル未変更を照合して再観測した。新parserの期待値や実装は変えていない。このtest専用adapterとデータの変更に対応する49件を再実行した。テスト数は文法対応数ではなく、未対応・上限・失敗の正しい表示を検証する試験も含む。

skipは既存mdsplit/tests/test_roundtrip.py:89の「Sample file not found」1件。新規skip/恒常的xfailはない。リモートGitHub Actionsは実行していない。本番CLI/E2E/schema/依存境界/見出し構造は既存全pytestに含む。既存canonicalを編集していないため別途CI文書再生成一式は実行していない。

初回uvはキャッシュがsandbox外にあるため権限エラーとなり、許可後にlockどおりPythonと依存を取得した。最初のsdistには試作19entryが入ったが、除外設定後はsdist 339entry、wheel 226entry、混入0。ローカルのbuildであり公開はしていない。

## C / I / Aの実測と範囲

[固定入力・期待値](../../../experiments/document_parser/corpus/m2.json)と[旧結果/新結果/trace](comparison-results.json)に全24ケースを記録。本文raw、URIに対応するsnapshot hash、byte範囲、ID、出現順、旧診断と拒否原文を保持している。正規化はテストのURIをmemoryに固定することと、旧SourceSpanを元byteへ可逆変換することだけ。診断や位置を削除して一致させていない。

|群|ケース|観測|
|---|---|---|
|C 実原稿8|C-fixture-cancel-allow / cancel-deny / guidance / normal / multilingual / natural-only / invalid / broken-model|候補の全ID・順序・本文slice・言語・mdspec所属と範囲が一致|
|C 小原稿11|C-normal / body-only / malformed-header / unclosed-div / literal-fence / literal-comment / literal-code-span / literal-html-attribute / unicode-lf / unicode-crlf / unicode-cr|固定した全projection項目が一致。malformed/unclosedは構造partial|
|I 改善3|I-51-link-title / image-title / reference-title|旧候補0、新REQ-A各1。Div byte範囲は[38,90) / [49,101) / [35,87)|
|I 未承認2|I-pending-paragraph-comment / div-tail-comment|旧候補0、新REQ-A各1。期待未確定、unapproved-observation。成功の22ケースに含めない|
|A|source_contract / architecture / blocks / inline / review_entry|元UTF-8/CP/改行/EOF、親子・coverage、全属性、limits/失敗、sliceのみprojection、-Sと逆依存を検証|

C-fixture-invalid等は「未検証候補」の比較で、旧公開parserの受理・拒否の意味まで一致させたとは言わない。旧の公開IDs/診断/completenessは別欄で保存した。新projectionのJSON、要件検証、式、参照はすべてnot-run。Graph/IR/CLIの新parser接続と全意味互換は未実装・未確認で、R5/R6に残る。

Aの未対応範囲を試験したことは、その文法を実装済みにする意味ではない。複数行参照候補、list/quote/table、一般HTMLは範囲と理由を伴うunsupported/partial。強調等は装飾を解釈せず原文textを保持。true block comment/通常fence/preのEOFはliteralな終端として保持する。

## 性能基線

[benchmark-results.json](benchmark-results.json)に各試行と条件を保存した。実行は .venv/bin/python -m experiments.document_parser.benchmark --repeats 3。Python 3.13.18 / Linux 6.18.35 x86_64 / glibc2.43 / uv 0.13.6。pytest 9.0.3、jsonschema 4.26.0、PyYAML 6.0.3などはuv.lockに一致。

各条件3回の中央値。parseは索引・Block・Inline・不変条件検査を含み、dump/traceを除く。snapshot作成とprojectionは別計時。位置bridgeは別に最大1000範囲を変換して記録しており、parse中の全位置検証時間を切り出した値ではない。メモリは計時とは別runのtracemallocピークで、原文SourceSnapshot確保分・プロセスRSSは含まない。

|入力|UTF-8 bytes|parse ms|projection ms|parse peak MiB|
|---|---:|---:|---:|---:|
|要件反復 約0.1 MiB|102396|425.09|10.29|9.65|
|要件反復 約1 MiB|1048524|5947.22|133.31|96.23|
|日本語/emoji/結合文字 約0.1 MiB|102375|392.94|8.98|8.74|
|日本語/emoji/結合文字 約1 MiB|1048575|4951.04|104.91|85.96|
|単一長行 約0.1 MiB|102400|50.68|0.01|0.93|
|単一長行 1 MiB|1048576|522.15|0.01|9.31|

全6条件の構造statusはcomplete。要件反復は同一IDを繰り返しており、意味上の有効性を測定する入力ではない。1 MiBで要件15,196候補となる細かい構造は約6秒・96 MiBを要する。小規模試作として得た課題であり、大規模本番採用の性能を承認する根拠にはしない。R2/R6で索引・node表現・位置検証の費用を分けて測る提案とする（今回その内訳は未測定）。旧版と仕事量の違う速度比較、Rustの予測、保証値、時間閾値のCI化は行っていない。

## レビューで修正した点と未決事項

SolがBlockとコーパス/A試験、TerraがInlineと独立した統合確認、Mainが共通モデル・統合・projection・CLI・測定・資料を担当した。二段階PRレビューとしては実施していない。

不正header属性の欠落、header validity/closure混同、BlockでのInline引用先読み、paragraphごとの参照表再構築、code span内の閉じ角括弧誤認、未対応参照定義のcomplete表示を修正した。欠落nodeがrecognized coverageだけで隠れない検証、異常なengine結果でもdump可能なfailed結果も追加した。

未決は未承認I2件、HTML引用のBlock境界、通常不正fence info、Divの3/4コロン、番号付き行の段落中断、front matter細部、参照名正規化・全多行検出、decoded属性の文字ごとの位置対応、早期メモリ制限。現行の契約原稿は変更していない。[設計対応表](design.md)と[Issue改訂案](issue-revisions/README.md)へ引き継いだ。

R1〜R6はいずれも未完了。#53/#57/#62は作業対象にしていない。#31/#37既知制限、M3、LSP、Rust/FFI、既存ツール全面移行は未着手。

元masterとreview-1.pdfを保持した。commit・push・PR・GitHub Issue本文/状態/親子関係変更・merge・tagはすべて未実施。今回の停止点はこのローカル差分のレビュー待ち。
