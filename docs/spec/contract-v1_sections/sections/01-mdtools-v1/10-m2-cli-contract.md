
M2 / #35は#39の共通解析サービスと#40のCLIが共有する外部契約を定める。本節のコマンドは将来の入口であり、#35時点では実行できない。既存CLIの引数・表示・終了コード・helpは変更しない。

```bash
mdtools spec index --project mdtools.toml --format json
mdtools spec show REQ-NORMAL --project mdtools.toml --format text
```

`--project PATH`は必須で、既存Workspace設定を明示指定する。暗黙の探索、stdin原稿、生成IRを第二の原典とする入力は設けない。`--format`はtext/json、既定値はtext。showの位置引数は要件IDを1個だけ受け付け、モデル・宣言・glossaryの同名で代用しない。ID形式の不備は引数エラー、形式上正しいが不存在のIDはunknown-idとする。設定内のパス解決・原典選択はWorkspace v1の規則を使う。

index/showは同じWorkspace全体の解析サービスを一度利用する。indexは要件・モデル・宣言・glossary・明示参照とIR、showは指定要件の各言語本文・形式記述・明示参照・出典・状態を取得する。showはusesが直接指す宣言とその型依存・glossary関連付けを含める。refsの先はIDと解決結果を示し、他要件本文を循環して展開しない。表示選択で全体の診断・部分結果・失敗を隠さず、名前衝突時は候補を残す。

**JSONと診断の出力先**

JSONモードではstdoutは末尾LF付きの単一JSON objectだけにする。最上位フィールドは次のとおりとする。

| フィールド | 内容 |
|------------|------|
| schema_version | 整数1。CLI envelopeの版。契約版・IRスキーマ版・診断JSON版とは別に管理 |
| command | indexまたはshow |
| status | 解析のcomplete/partial/unavailable。プロセス全体の成功フラグではない |
| exit_code | 本節の終了コードと同じ整数 |
| result | indexでは#39のSpecIR、showでは対象requirementと関連models/declarations/glossary/references。生成不能・未知対象はnull |
| report | M1のreport_to_dict()と同じ診断JSON v1 object。入力snapshot、全体checks、診断を含む |

indexのIRは契約版・IRスキーマ版・manifest・requirements/models/declarations/glossary/references・出典・状態を持つ。manifestは本文と共有定義だけでなく、選択・順序に影響する設定とhierarchyも記録する。正確なIR Schemaと各フィールドのJSON表現は#39で追加し、#35ではIRシリアライザーを作らない。showの内容は同じIRからの選択結果とし、別パーサーを作らない。

診断はreportに集約し、JSONモードのstderrへ重複表示しない。stderrは予期せぬ実行時ログ用であり、通常の正常/原稿不正/未知ID経路では空とする。既存glossaryローダー等の警告やデバッグprintをstdoutへ流入させない。引数解析に失敗して実行を開始できない場合だけstdoutを空にしてstderrへusageと理由を出す。helpはstdout、終了0とする。

textモードは同じ要件・出典・参照・検査状態と全体診断をstdoutへ表示する。診断の座標・quote・内容はM1のテキストrendererに従う。壊れた入力の部分結果にもpartialと理由を示す。式未検査・論理未実行を省略せず、「無矛盾」「verified」等の全体保証へ置き換えない。

入力順に依存する文書/本文一覧と、IDによる意味上の同一性を分ける。繰り返し出力は同じsnapshot・設定・実装版から決定的とし、診断の順序はM1、IRの順序は#39の契約に従う。環境の現在時刻やランダム値を追加しない。

**終了コードとエラー優先順位**

| コード | 意味 |
|--------|------|
| 0 | 対象範囲のM2解析と要求された表示が成功。M3の式/論理検査は未実行でもよい |
| 1 | Workspace設定、原稿構造、宣言値、参照の不正、未知版・未対応構文等。部分結果を出しても0にしない |
| 2 | CLI引数不備。stdoutは空、stderrにusageと理由 |
| 3 | 全体解析がcompleteであるがshowの要件IDが存在しない。spec.unknown-id、result=null。解析のstatus自体はcompleteを保持する |
| 4 | I/O、文字コード読込、内部処理等の実行失敗。tool-error/errorと理由 |
| 5 | 実際の入力に必要な任意依存（例: YAML用PyYAML）がない。spec.missing-dependencyと依存名・理由 |

複数問題があれば`2 → 4 → 5 → 1 → 3 → 0`の順で最初に該当する分類を選ぶ。引数不備は解析前に確定し、その後は実行失敗・依存不足を原稿の不正と区別する。WorkspaceErrorのread-errorは4、他の設定・登録不正は1とする。ソース内容の不正な構造と、入力をUTF-8で読み取れない失敗は区別する。警告だけでは非0にしないが、未対応・未実行がM2必須検査に残る結果は0にしない。

Workspace全体がpartial/unavailableの場合、showの対象が見つからなくても3へ置き換えず、元の1/4/5を返す。対象が見つかっても全体の失敗を成功へ変更しない。unknown-idは解析済み要件集合に対する問い合わせの診断であり、解析のcompleteを取り消すものではない。reportには解析診断にこの問い合わせ診断を追加する。

0は宣言したM2検査範囲の成功に限り、式の文法・型・usesとの完全一致・論理整合性・本文との意味的一致を保証しない。パース前に失敗した場合も、実施していない各チェックへ理由付きnot-runを残す。どの失敗でも架空の原稿位置を生成しない。
