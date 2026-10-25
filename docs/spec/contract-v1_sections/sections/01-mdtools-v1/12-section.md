
契約版、Workspace設定版、共有定義版、IRスキーマ版、診断JSON版、パッケージのリリース版は別に管理する。同じ数字であることを要求しない。v1の要件は`spec-version=1`、モデルと仕様用共有定義は`version: 1`を明示する。未知の版を推測して読み込まない。

意味や既存入力の解釈を変える変更には新しい契約版と移行手順を用意する。対応部分を増やす変更も、何を理解できるかを能力として明示し、古い実装が未知の必須構文を成功扱いしないようにする。IRや検査結果のキャッシュには各版を記録する。

開発順は`master → spec-integration → milestone/<milestone> → issue/<番号>-<slug>`。サブIssueは対応するMilestoneブランチから分岐し、同ブランチへPRする。別サブIssueの未マージブランチを分岐元にしない。#22の作業ブランチは`issue/22-spec-contract`、PR先は`milestone/m1-foundation`。

サブIssueは受け入れとPRの**マージを確認してから**Closeする。PRを未マージでCloseしただけでは完了にしない。非デフォルトブランチ向けPRの自動Closeに依存せず、対象Issueを明記してマージ後に明示的にCloseする。Milestoneの必須サブIssue完了後に`spec-integration`へ統合し、統合後にMain IssueとMilestoneをCloseする。

| リリース | 手順 |
|----------|------|
| Phase 1（M1〜M5）| 基本機能を統合し、M5完了後に`spec-integration → master`へPR。暫定版は`v0.2.0` |
| Phase 2（M6〜M9）| Phase 1後のmasterをspec-integrationへ同期。M6〜M9を順次統合し、M9完了後に2回目の`spec-integration → master`へPR。暫定版は`v0.3.0` |

各MilestoneのCloseはPhaseのリリースPRを前提としない。新しいMilestoneブランチは開始時点のspec-integrationから作る。版番号は受け入れ時に調整でき、pyprojectの変更やタグをM1で先行作成しない。タグはリリースPRが実際にマージされたコミットを指す。
