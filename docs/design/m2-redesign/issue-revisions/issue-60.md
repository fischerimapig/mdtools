## R5：本番semantic extractorとサービス切替

親#52、Milestone M2-redesign（10）。#54/#55/#58/#59の承認契約と実装PRが全てマージ済みであることを着手条件とし、最新 `milestone/m2-redesign` から `issue/60-document-extractor` を分岐、同MilestoneへPRする。

利用者の公開 `parse_requirements(SourceSnapshot)`、LocalAnalysis/Graph/IR/CLIを維持し、内部をDocument解析一回→ `extract_requirements(DocumentParse)` へ切り替える。`mdtools/spec/parser.py` と解析サービスを変更対象とし、共有定義strict loader・resolver/IRの契約・他ツールは維持する。試作projectionの候補/本文/mdspec所属処理は参考にするが、意味未検査のReviewSummaryを本番結果の代用にしない。

extractorがrequirement ID/version/status/lang、mdspec info/所属/JSON、refs/uses、拒否原文と仕様診断を解釈する。既存JSON validatorを再利用し、式評価・参照解決の未実行状態を成功へ昇格しない。構造/属性/明示sliceだけを読み、全文regex、独自comment/fence判定、旧scanner fallbackを本番から除去する。公開位置はSourceSpanを保ちbyteとの変換を明示する。

小原稿 `::: {.requirement #REQ-A spec-version=1}\n本文\n:::\n` は一件のnatural-only要件。missing IDは候補観測と公開拒否を区別し、broken-modelは本文を保持してpresent/失敗を表す。unsupported coverage、partial、profile拒否、engine failureを公開診断/完全性へ写像し、空のcompleteへ置換しない。対応不能な公開差分はR1へ戻して承認する。

`C-fixture-normal` / `C-fixture-multilingual` / `C-fixture-invalid` / `C-fixture-broken-model` とcancellation三件を、R1で拡充した式・参照・出典・診断・IRまで比較する。I-51三種は公開APIでREQ-AのID/件数/spanを独立assertする。試作で実行済みは `.venv/bin/python -m pytest experiments/document_parser/tests -q`（[results](../results.md)）。今後は `.venv/bin/python -m pytest mdtools/spec -q` と新設サービス統合試験を実行する。前者の試作結果を本番互換の証明にしない。

成果物は互換facade・extractor・サービス接続・公開C/I/A・文書。旧scannerの本番非利用とM2契約をレビューし、PRマージ後にClose。#61へE2E/配布検証対象を渡す。Graph/IR全面刷新、M3、#31/#37、Rustは対象外。
