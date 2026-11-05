## R4：所有範囲内のInline

親#52、Milestone M2-redesign（10）。#54/#55/#58の契約とBlock実装が承認・マージ済みであることを確認し、最新 `milestone/m2-redesign` から `issue/59-document-inlines` を分岐、同MilestoneへPRする。

利用者がtitleに `<!--` を書いても後続REQ-Aを失わない文脈分離を完成させる。試作 `inline.py` / `links.py` / `parser.py` のbounded helper・参照lookup・freeze接続を再利用候補にする。配置案は `mdtools/document/inline.py` 等。Blockを再認識せず、specの意味/JSON/式/共有定義/CLIには触れない。

`parse_inlines(index,owner,references,limits)` は確定leafの元byte範囲内だけを読み、InlineResultのspan/target/title/referenceとnotice/completeを返す。小入力 `[説明](https://example.com "<!--")` はlinkであり、空行後のDivはBlockが既に所有する別node。link/image/参照定義のtitle、code span、escape、HTML引用属性、inline commentを承認profile内で認識する。参照定義はBlockが収集し、Unicode casefoldとASCII空白縮約で照合、最初の定義を使い全出現は残す。この正規化規則はR1で承認する。

lookahead・delimiter・引用状態はowner外へ出さず、HTML引用でも独立Blockを吸収しない。未成立inlineは原文textとして保持し、未対応containerの所属はBlock結果に従う。node/文字数/work上限は未完了とnoticeを返し、入口がunparsed/partialへ接続する。内部失敗はfailed、正常0件と区別する。EOF literal/commentの扱いと `I-pending-paragraph-comment` / `I-pending-div-tail-comment` はR1判断を継承する。

必須は `I-51-link-title` / `I-51-image-title` / `I-51-reference-title` の独立REQ-A/byte範囲、`C-literal-code-span` / `C-literal-html-attribute` / `C-literal-comment` の対照、`test_lookahead_stays_within_owner`、`test_reference_definition_and_first_resolution`、`test_nested_brackets_stop_before_unbounded_label_copies`。実行済みは `.venv/bin/python -m pytest experiments/document_parser/tests -q`（[results](../results.md)）。今後は本番配置の同試験とR5公開APIで三種の改善を検証する。

成果物はInline/helper/接続実装、範囲・上限試験、対応表。Block→Inline→Documentの失敗伝播と標準ライブラリ実行を確認しPRマージ後にClose。renderer、全CommonMark、外部parser、意味検査、Rustは対象外。
