## R1：公開互換契約と改善リファレンス

親#52、Milestone M2-redesign（10）。本番parserの実装は本Issueの対象外。#52配下の隔離先行試作を資料として読み、後続が何を維持・改善するか固定する。M2統合確認後、最新 `milestone/m2-redesign` から `issue/54-document-reference` を分岐し同MilestoneへPRする。

基準は `b11368128d4e2a476f2204af40bdfdc947f1cc88`。`experiments/document_parser/corpus/m2.json` のC19件はID/順序/本文raw/言語/mdspec所属/元byte spanのprojection比較まで実測済み。公開意味・診断・IR/CLI全体の合格ではない。R1では既存fixtureと単体/サービス/E2Eを追加選定し、モデル・式原文・refs/uses・重複/未定義・拒否・診断分類・完全性・snapshot・IR/CLIを固定JSON等へ保存する。比較項目をcaseごとに宣言し、実装の共通部分へ縮小しない。

`I-51-link-title`、`I-51-image-title`、`I-51-reference-title` は旧候補0、新期待REQ-Aと元byte範囲を持つ。例は `[説明](https://example.com "<!--")`、空行、REQ-A Div。構造はlink leafと独立Divである。`C-literal-comment` は本物のblockコメントが要件風文字列を隠す対照。`I-pending-paragraph-comment` / `I-pending-div-tail-comment` と独立Blockを跨ぐHTML引用状態は未承認差分として判断・理由・承認を残す。C期待を黙って更新しない。

契約には対応profile/モデル版/spec-version/IR版の責務、単一snapshot、UTF-8半開byteとSourceSpan CPのbridge、正常0件、不正候補、未対応coverage、partial/rejected/failedの変換方針を含める。モジュール案は `mdtools/document/` とsemantic extractor。Graph/IR/CLI・共有定義loaderを作り直さず、旧scannerの比較利用はtestに限定する。

実行済みは `.venv/bin/python -m pytest experiments/document_parser/tests -q`。今後は選定した公開parser/サービス/CLIテストを固定SHAと新経路で実行し、コマンド・期待・結果を追記する（最終試作結果は[results](../results.md)）。成果物は契約・フロー・C/I/A対応表・承認差分表。後続#55/#58/#59/#60/#61の入力条件をレビューし、文書/sectionを同期、PRマージ後にCloseする。試作の存在をR1完了としない。
