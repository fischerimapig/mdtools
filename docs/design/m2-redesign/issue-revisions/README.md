# M2-redesign Issue本文差替え案（未反映）

2026-11-04取得の [upstream.json](upstream.json) を基にしたローカル提案。GitHubの本文・状態・Milestone・親子関係は変更していない。各 `issue-*.md` は見出しを含め本文全体として差替え可能。#52の先行試作とR1〜R6を分離し、試作の成功を本番切替・意味検査・製品受け入れの完了へ読み替えない。

|対象|取得した updated_at (UTC)|主な改訂|
|---|---|---|
|[#52](issue-52.md)|2026-11-03T14:25:28Z|先行試作の位置付けと未完了工程|
|[#54](issue-54.md)|2026-11-03T14:20:35Z|projectionから公開意味・診断・IR/CLIへ基準を拡充|
|[#55](issue-55.md)|2026-11-03T14:21:01Z|元byte索引、所有・coverage・失敗の契約|
|[#58](issue-58.md)|2026-11-03T14:21:18Z|不正候補保持、opaque・未対応・Block先行|
|[#59](issue-59.md)|2026-11-03T14:21:40Z|所有leaf内Inline、参照表、#51三種|
|[#60](issue-60.md)|2026-11-03T14:24:17Z|本番semantic extractorとサービス切替|
|[#61](issue-61.md)|2026-11-03T14:24:40Z|製品E2E・配布・依存・性能受け入れ|

実測は [results.md](../results.md)、実施計画は [plan.md](../plan.md)、固定データは [m2.json](../../../../experiments/document_parser/corpus/m2.json) に結び付ける。results作成中の値を最終値として転載しない。基準は `b11368128d4e2a476f2204af40bdfdc947f1cc88`、試作開始HEAD `17723261c3a9a47f69b763d4898c1db0d290c0fd` は同一tree。各本文の「実行済み」は試作コマンド、「今後」は本番工程の未実施確認である。最終件数・性能はresultsを参照し、試作の比較範囲外を合格扱いしない。

確認できたのはC19件のcandidate projection全フィールド一致とI-51三種のREQ-A保持。公開意味・JSON・式・参照・診断の完全互換は未確認。`I-pending-paragraph-comment`、`I-pending-div-tail-comment` は未承認の差分候補。Inline HTMLの引用状態も独立Block境界を越えないことを試験したが、これを本番の新しい互換期待として自動採用しない。新たな先行試作Issueを設ける案も登録前の提案に留める。

反映時は各Issueの最新本文・全コメント・updated_at・状態・依存PRを再取得し、このsnapshot以降の変更を照合する。差分があれば本案を更新し、承認済み期待・公開契約を確認してから反映する。本案自体はcommit/push/Issue更新/Close/mergeを許可しない。正式なsub-issue親子関係の登録有無も本文参照とは別に確認する。
