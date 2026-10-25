# キャンセル要件の契約例

[仕様記述契約v1](../../contract-v1.md) のレビュー用サンプル。M1では原稿と共有定義の形式を示す。仕様パーサー、Z3実行、検査結果ファイルはこの例に含まれず、以下の期待値はM2以降の実装が満たす条件である。

| ファイル | 役割 |
|----------|------|
| [cancel-allow.md](cancel-allow.md) | 日英本文を一つの要件IDと一つのモデルに結び付けた原典 |
| [cancel-deny.md](cancel-deny.md) | 別文書の相反する制約と明示的な要件参照 |
| [guidance.md](guidance.md) | 自然言語のみの有効な要件。形式化・論理検査は未実施 |
| [definitions.json](definitions.json) | 共有入力・出力と、型・範囲付きの定数。glossary用の定義ではない |

将来のWorkspaceでは上の3原稿を文書、definitions.jsonを仕様用共有定義として登録する。このREADMEは解析入力にしない。Workspaceの具体的な設定形式は#23で定める。

`paid`と`shipped`はBoolean入力、`cancel_allowed`はBoolean出力である。支払い済み・未発送の入力ではREQ-CANCEL-ALLOWが出力trueを要求し、REQ-CANCEL-DENYが出力falseを要求する。この入力で出力が存在しないことと、両原稿の要件ID・形式記述位置を報告するのがM3での期待値となる。

`paid=false`では両ルールが適用されず割当てが存在するため、全体SATだけでは衝突を検出できない。入力領域の全域成立性とルール適用可能性を別に調べる。未使用のcancel_window_daysは型付き定数の宣言例であり、14日を過ぎた場合の振る舞いを本文から推定して追加してはならない。

REQ-CANCEL-GUIDANCEは構造的に有効でも`natural-only`かつ論理検査`not-run`である。日本語本文だけを編集した場合も、対応確認記録があればstaleにする。M1では確認済みや検査成功の記録を作らない。

通常のコード例は要件として取り込まない。このJSONは予約されたmdspecではない。

```json
{"id": "EXAMPLE-ONLY", "kind": "constraint", "must": "false"}
```
