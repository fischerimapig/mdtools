
PR #30は`76f224d`、PR #32は`c9cbac3`でMilestoneへマージ済み。#32のSchema/Python文字列制約の指摘は`1610831`で修正・再レビュー済みで、dev用Draft 2020-12 validatorと122件の回帰を維持した。クリーンな作業ツリーから`origin/milestone/m1-foundation`の`c9cbac3`を取得し、`issue/26-core-boundaries`を作成した。別sub-issueブランチからは分岐していない。着手時の全テストは`512 passed, 1 skipped`。skipは外部combined.md未配置。

実際のimport調査と変更判断:

| 調査した経路 | 調査結果と対応 |
|--------------|----------------|
| core | ioは標準ライブラリと任意YAMLの遅延読込、mdscan→pandoc、diagnostics→source。CLI・spec・文書処理への逆依存なし。既存モデルを維持 |
| workspace | core.sourceとmdsplit.schemaを利用。文書階層を知る原典登録の組立てなのでcoreへ移動しない |
| mdtools.diagnostics | workspace→snapshotの結果とWorkspaceErrorをcore診断へ組み立てる。workspace/coreからの逆importなし。配置を維持 |
| 文書処理 | compose/decompose、filter_lang、glossaryのload/resolve/find_missing/list、HTML inventory/rewrite/convertは既にCLIなしで利用可能。既存配置と副作用を維持 |
| build | build_cli内でcompose/filter_lang/load/resolveを順に実行していた。処理順・中間ファイル・再読込をmdtools.buildへ分離し、CLIは引数、stdin、最終出力、表示、終了コードを担当 |
| mdsplit verify | CLI内だけに再帰存在チェックがあった。mdsplit.verifyへ結果を返す本体を分離し、CLIは従来の一覧表示と0/1終了を維持。Workspaceの厳格検証へ置換しない |
| 公開入口 | pyprojectの5コマンド、統合mainの遅延dispatch、互換__main__、help例・README参照は変更不要。API/設計の説明をREADME・契約の原稿側に追加 |

許されるimportは契約の責務表を正とする。`mdtools.build`は既存文書処理の組立て、`mdtools.workspace`は設定と原典選択、`mdtools.diagnostics`は登録失敗の共通診断化であり、coreへまとめない。coreと文書処理はCLI・組立て・spec・backendへ依存しない。将来の解析サービスがworkspaceのsnapshotとspec処理を組み立て、CLI/LSPホストから共通利用し、外側で任意adapterを渡す。要件ID解決・意味・検査計画はspec内に閉じる。空パッケージや将来用抽象化、大規模移動は追加しない。

#31は調査時もopen。SourceMapBuilderの断片末尾CR＋次断片先頭LFで新しくできるCRLF境界がmap構築に失敗する。通常のCRLF本文全般は対象外。今回も最小例の失敗を確認し、修正を取り込まない。buildはcomposeと中間再読込を維持し、map経路へ切り替えない。該当経路の正確な原稿追跡は保証せず、架空の位置を作らない。後段langfilter/glossaryの位置伝播、atomic snapshot、M2以降の仕様内容検査も未実装のまま。

検証では、処理本体の直接呼出、正常・エラー時のCLI入出力/終了コード、中間ファイルと改行、依存方向と循環の不在、`python -S`でCLI/任意/dev依存を禁止したAPI呼出を追加した。共通位置・診断・公開Schemaの既存回帰、mdscan、mdsplit round-trip、build、既存公開コマンドも全テストで確認した。文書はsection原稿を編集しcanonicalを再生成、hierarchy verify・compose一致・decompose→composeを検証した。

最終ローカル検証は`.venv/bin/python -m pytest -q`で**549 passed, 1 skipped**（基準から37件追加）。新しいCLIや必須依存は追加していない。分岐元c9cbac3との64ケースの比較で、終了コード・stdout・stderr・生成ファイルのbytesが一致した。変更したREADME / mdsplit README / 契約 / 本記録の4文書はhierarchy verify、canonicalとのcompose一致、decompose→compose round-tripを通過。契約の6つのPython例も記載順で実行し、README glossary参照と`git diff --check`を確認した。CIは公開5コマンド・統合helpと4文書のround-tripを確認するよう拡張した。PR先はmilestone/m1-foundation、関連Issueは#26。PRはマージせず、Issueはマージ確認前にCloseしない。
