# M2-redesign 先行試作：要求整理と実施計画

この計画は2026-11-04の依頼範囲を記録したもの。2026-11-05の追加指示で、試作ブランチへのcommit/pushのみ許可された。PR作成やIssue変更等は引き続き範囲外。

## 今回の受け入れ範囲

- 基点は origin/spec-integration = 17723261c3a9a47f69b763d4898c1db0d290c0fd（2026-11-04取得）。M2基準 b11368128d4e2a476f2204af40bdfdc947f1cc88 は祖先で、両treeの差分は空。PR #56のhead/mergeとも一致。
- 元workspaceはmaster=fabded041311a0070f98530ed314fcca17fc16c2、未追跡review-1.pdfを保持。milestone/m2-redesignとissue/52-document-parser-prototypeを作成し、.worktrees/m2-redesignに隔離。
- 実装はexperiments/document_parser、資料はdocs/design/m2-redesign。現行製品のAPI/CLI/SpecGraph/SpecIR・依存・契約原稿は変更しない。配布物混入も検査する。
- PDFのP1〜P4（位置、Block、Inline、Document）を内製し、P5はレビュー用projectionに限定する。PDFの外部engine採用案・M2中の切替案は、最新依頼に従い「内製先行試作・後続R5切替」に置き換える。
- .requirement/ID/lang/mdspecの意味はprojectionだけが扱う。JSON・式・参照解決・仕様診断はnot-run。試作成功をR1〜R6完了とはしない。
- 原文はSourceSnapshotで共有。元UTF-8 byteの半開範囲を索引経由で既存SourceSpanに接続。正規化せず、CRLF内をSourceSpanに丸めない。
- C:固定M2実測、I:#51と対照、A:構造・位置・境界・失敗。比較項目を事前固定し、全件ID/順序/本文slice/言語/所属と範囲を比較する。意味検査の互換は主張しない。
- 上限・失敗・未対応を正常0件と分離。opaqueのEOF終端と不正Divを区別。複数snapshotを連結しない。
- commit/push/PR/Issue編集・登録・Close/merge/tagは禁止。#31/#37既知制限、M3、LSP、Rust/FFI、全既存ツール移行は対象外。

## 調査で確認した基点

AGENTS.md（全体）以外の下位AGENTS.mdはなし。contract-v1と要件構文・予約構文のsection、core/source・pandoc・mdscan・diagnostics、spec/parser・_markdown、analysis、parser context/source tests、cancellation/model-contract実原稿、境界/CLI/E2E/CI、pyproject/uv.lockを確認。
GitHub #51/#52/#54/#55/#58/#59/#60/#61の本文と全コメント取得済み（全件コメント0）。取得時snapshotはissue-revisions/upstream.jsonへ保存する。
review-1.pdf全11ページを読んだ。同梱と記載されたdesign.md等は提供されていないため読んだ扱いにしない。
markdown-it-pyは6f586542653a56d2ee8549a0dccfaa6ba5ebe14aを参考にし、runtime/test依存にはしない。

変更前：関連pytest 180 passed (1.34s)、全pytest 1137 passed / 1 skipped (20.85s)。Python 3.13.18、uv lockに従う。skip理由は最終結果に記録。

## 分担・順序・引き渡し

|段階|担当|所有ファイル|入力→出力 / 終了条件|
|---|---|---|---|
|P0 契約固定|Main|model.py、plan.md|snapshot→byte索引・不変モデル・limits。以下の共通APIを固定|
|P1 Block|GPT-6.1 Sol|blocks.py、test_blocks.py|索引→汎用block、参照定義、coverage/notice。単一小原稿を縦通し後、literal/Div/不正を追加|
|P2 Inline|GPT-6.1 Terra|inline.py、links.py、test_inline.py|確定leafと収集済み参照表→leaf内inline。#51・escape・code span・HTML属性を独立期待値で検証|
|P3 コーパス|GPT-6.1 Sol|corpus/、tests/legacy_adapter.py、test_corpus.py|固定M2実測と独立新期待値。C/I/A、比較項目、検出目的をケースごとに保持|
|P4 統合|Main|parser.py、projection.py、__main__.py、位置/境界test|Block→Inline→Document→projectionを接続。失敗伝播、配布・逆依存確認|
|P5 検証・資料|Main＋部品担当の修正|README、design、results、benchmark、issue-revisions|全テスト・測定・トレースを実測。Issue本文は事実/提案を分けローカル改訂案|

P1/P2/P3はP0のデータ契約後に並行できる。P2が参照定義の字句helperを所有し、P1は同helperで収集する。Inlineはblockの境界を変更できない。担当外ファイルはMainが統合し、API変更は通知してから行う。

## 共通API（試作、公開APIではない）

- parse_document(source, *, profile=PROFILE, limits=Limits()) -> DocumentParse
- summarize_requirements(document) -> ReviewSummary
- SourceIndex: byte_range(cp_start, cp_end), cp_offset(byte), slice(ByteRange), span(ByteRange)。改行正規化なし。
- Node: kind/span/body/header/closing/children/attributes/info/marker/closure/valid/inlines。全範囲は元byte。closureはclosed/eof/none/limit。
- Attribute: kind/name/value/span/value_span（出現順、重複・不正を保持）。core.tokenize_attrsの汎用lexer再利用可、旧scannerは不可。
- Inline: kind/span/target/title/reference（全て範囲または参照label）。本文は複製しない。
- ReferenceDefinition: label/span/destination/title。全出現をtupleで保持、最初の定義を解決に使用。
- parse_blocks(index, limits) -> BlockResult(blocks, references, notices, coverage, status)。
- parse_inlines(index, owner, references, limits) -> InlineResult(inlines, notices, complete)。owner外のslice禁止。
- status: complete/partial/rejected/failed。coverageはrecognized/unsupported/unparsedの元範囲分割。completeは構文認識のみ。
- malformed headerは候補Nodeとrawを保持。非対応containerはunsupported領域を保持し正常として捨てない。

## 暫定判断と確認ゲート

1. 一般Divの3コロン以外、壊れたinfo、段落内未閉鎖コメントは差分候補として記録する。承認済み互換期待を自動更新しない。
2. 未対応装飾は原文text。複雑list/quote・HTML全種別・tableの意味構造は試作対象外。所属を判断できない領域はunsupportedとして区別する。
3. 実fixtureの正常projectionと#51三種の独立ID/byte範囲assertを通し、その後に新旧全比較を行う。
4. 0.1/1 MiB、多言語、長い行を同条件測定。構造parseとprojection、メモリ計測を分ける。高速化保証なし。
5. #52/#54/#55/#58/#59/#60/#61は実測後に差替え案を作る。updated_atを残し、反映時に最新本文との再照合を必須にする。
