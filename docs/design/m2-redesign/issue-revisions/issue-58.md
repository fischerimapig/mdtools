## R3：内製Blockと汎用Div

親#52、Milestone M2-redesign（10）。#54の対応表と#55の位置/失敗契約を承認・マージ後、最新 `milestone/m2-redesign` から `issue/58-document-blocks` を分岐し同MilestoneへPRする。

後段のtitle/comment状態で独立要件が消えないよう、Blockが先に原稿所有を確定する。試作 `blocks.py` のstack/優先順位/opaque範囲と `links.py` の参照定義helperを再利用候補とし、`mdtools/document/blocks.py` 等へ移す設計をレビューする。`.requirement`/lang/mdspecの意味、JSON、診断変換は#60に残し、既存spec/CLI/他ツールは切り替えない。

入力はSourceIndexとLimits、出力は `BlockResult(blocks,references,notices,coverage,status)`。小原稿 `::: {.x #A}\n本文\n:::\n` は閉じたDivにparagraphを持ち、header/body/closingは元byteの半開範囲となる。壊れた `::: {.requirement #REQ-A spec-version=1} trailing` も属性と候補を保持しvalid=False、閉鎖の有無は別に残す。未閉鎖Divはpartial、真のfence/comment/preのEOFはopaque終端として区別する。別snapshotから閉じ記号を借りない。

段落・見出し・空白・front matter・literal・Divを承認profileに限定する。参照定義は全出現を順番に保持しInlineへ渡す。試作は単一行定義までで、複数行destination/titleの代表候補は範囲付きunsupportedを返す。本番の対応範囲と全多行候補検出は#54で固定する。list/quote/HTML等で所属判断できない領域はunsupported/partialとして原文を隠さない。node/depth上限は残りをunparsed、engine例外は入口でfailedとし、通常0件へ変換しない。属性lexerの共有は可能だが旧scannerや全文コメントマスクへのfallbackは禁止。

必須ケースは `C-malformed-header`、`C-unclosed-div`、`C-literal-fence`、`C-literal-comment`、`I-51-reference-title`。`test_inline_quote_cannot_consume_independent_block_boundaries` と `test_limits_leave_remaining_source_unparsed` で境界と失敗を確認する。段落/Div末尾コメントの未承認差分は#54で決めてから本番期待へ採用する。

実行済みは `.venv/bin/python -m pytest experiments/document_parser/tests -q`（[results](../results.md)）。今後は移植後のBlock契約試験と公開parser接続前のC全比較を行う。成果物はBlock実装・優先順位/対応表・位置/coverage試験。#59へ確定leafと参照表を渡せることをレビューしPRマージ後にClose。完全Markdown適合、renderer、意味解析は対象外。
