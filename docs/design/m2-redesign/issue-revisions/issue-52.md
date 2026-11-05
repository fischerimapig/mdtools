## 目的と工程

M2の完成成果を基準に、利用者の要件ID・本文・出典・Graph/IR/CLIを保ちながら文書構造認識を独立させる。Milestone M2-redesign（10）、親Mainは本Issue。基準SHAは `b11368128d4e2a476f2204af40bdfdc947f1cc88`。M2統合 `17723261c3a9a47f69b763d4898c1db0d290c0fd` と同一treeを確認した。開始時に最新spec-integration・祖先・CIを確認する。

先行試作は本Issue配下の別工程で、`experiments/document_parser/` に隔離した内製Python実装である。R1〜R6完了や本番#51修正を意味しない。専用Issue追加は提案に留める。R1 #54 → R2 #55 → R3 #58 → R4 #59 → R5 #60 → R6 #61 の順で、先行PRマージ後の最新 `milestone/m2-redesign` から `issue/<番号>-<slug>` を分岐し同MilestoneへPRする。Mainの最終PR先はspec-integration。

## 境界と実測

`SourceSnapshot → SourceIndex → Block → Inline → DocumentParse → extractor → LocalAnalysis/Graph/IR/CLI`。Documentは汎用構造と元UTF-8半開byte範囲を保持し、意味はextractorが担う。単一snapshot、原稿順、全属性出現、親子包含、coverageを保ち、SourceSpanのCP/行列と混同しない。旧scannerの本番fallback、全文再走査、外部parser必須依存を作らない。

小原稿 `::: {.requirement #REQ-A spec-version=1}\n本文\n:::\n` はDivと本文leafを持つ。リンクtitleに `<!--` を前置してもREQ-Aを保持する。C19件のprojection互換と `I-51-link-title` / `I-51-image-title` / `I-51-reference-title` の改善は試作で実測済み。意味検査はnot-run。通常0件、malformed候補、opaque EOF、未対応、partial、rejected、failedを区別する。段落/Div末尾コメントのI-pending二件とHTML引用境界の公開挙動はR1で判断する。

## 受け入れ

実行済みは `.venv/bin/python -m pytest experiments/document_parser/tests -q`（最終結果は[results](../results.md)）。今後はR1で式・参照・診断・完全性・IR/CLIへC比較を拡充し、R5/R6で公開APIと製品E2Eを検証する。試作全passだけで本Issueを完了しない。

成果物は承認契約、差分表、製品実装、C/I/A、性能・配布記録、同期文書。全工程の所定PRマージ後に全体レビュー・統合・CIを確認しMainをCloseする。Graph/IR全面再設計、全ツール移行、完全Markdown、M3、Rust/FFI、#31/#37、リリース/tagは対象外。性能の採用可否は同条件の再計測と退行評価で判断する。
