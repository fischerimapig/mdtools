## R6：製品E2E・CI・配布・性能

親#52、Milestone M2-redesign（10）。#60の本番切替PRマージとR1〜R4の契約充足を確認し、最新 `milestone/m2-redesign` から `issue/61-document-acceptance` を分岐、同MilestoneへPRする。各部品の検証は先送りせず、本Issueでは利用者の原稿から製品出力まで受け入れる。

既存M2の要件/モデル/本文/言語/式原文/参照/出典/診断/完全性/IRと終了コードをR1固定基準で比較する。小原稿はlink title `<!--`、空行、REQ-A Div。別プロセスのサービス/CLIでREQ-Aと元spanを確認し、終了0だけで合格しない。`I-51-link-title` / `I-51-image-title` / `I-51-reference-title` と `C-fixture-normal` / `C-fixture-invalid` / cancellation三件をE2Eへ対応付ける。I-pending二件とHTML引用境界はR1承認表に従う。

正常0件、不正/拒否、未対応、上限partial、engine failureの出力を分け、意味未検査表示とsnapshotを保つ。Aは逆依存・全文再走査・旧fallback・再読込・必須外部parserがないこと。試作の `test_dependency_direction` / `test_python_without_site_packages` / `test_incomplete_zero_is_explicit` を本番境界へ拡張する。試作projectionをSpecIRへ昇格せず、実装の本番配置・公開APIは#60成果を検証する。

変更対象は既存CI/E2E・配布検査・測定・README/設計/section。実行済みは `.venv/bin/python -m pytest experiments/document_parser/tests -q`（[results](../results.md)）。今後は `.venv/bin/python -m pytest -q`、既存CLI smoke/文書verify/round-trip/見出し構造、wheel/sdistクリーン環境を実施し、実コマンドと対象SHAを記録する。試作がwheelへ混入しないことと、本番Documentの必要ファイルが含まれることを別々に確認する。

性能は0.1/1 MiB、多言語、長行、偏った区切り等を同一条件で測り、位置索引・Block/Inline・抽出・IR/JSONとpeak memoryを区別する。初回試作値は最終保証にせず、旧経路比較・再計測・退行の説明を残す。絶対速度や非決定的CI閾値は未承認。成果物はC/I/Aの製品結果、配布証跡、性能基線、既知制限と同期文書。所定PRマージ後に本IssueをCloseし、Main #52の全体統合へ渡す。全CommonMark、M3/Rust、#31/#37、リリース/tagは対象外。
