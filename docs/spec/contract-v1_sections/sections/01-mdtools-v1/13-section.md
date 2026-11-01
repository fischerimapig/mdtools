
[キャンセル要件の原稿と共有定義](examples/cancellation/README.md) は、この契約をレビューするための編集可能な最小例である。M1時点では実行済みの検査結果を含まない。

| 例・変更 | 後続実装で確認すること |
|----------|------------------------|
| cancel-allow.md + cancel-deny.md | 条件`paid=true, shipped=false`での出力衝突を両要件・両原稿位置に戻す（M3） |
| guidance.md | 自然言語のみを抽出でき、形式化済み・検査成功とは表示しない（M2〜M3） |
| 四重fence内の要件例、通常のJSONコード例 | 要件や形式記述として抽出しない（M2） |
| 要件ID重複・未定義refs/uses・不正JSON・未知の版 | 元原稿の構造診断となり、後勝ちや無視で成功しない（M2） |
| 要件・mdspecの閉じ忘れ、section跨ぎ、ネスト | 元ファイルで診断し、composeによる結合で補わない（M2） |
| 未対応式・backend未導入・タイムアウト | unsupported / not-run / unknownと理由を表示する（M3以降） |
| 本文・形式記述・依存定義の個別変更 | 対応確認と過去の検査結果をstaleとして扱う（M4） |
| 原稿移動・見出し変更・並べ替え | 要件IDを保ち、出典や文書構造の変更と内容差分を区別する（M2〜M4） |

M1 / #22の検証は文書のリンク・例のJSON・既存CLIでの文書round-tripと回帰テストに限定する。表の将来の検査が実装済みであるかのように受け入れ記録へ付け替えない。

M2 / #36では`mdtools/spec/tests/test_parser.py`でキャンセル例3原稿とmodel-contractのMarkdown fixtureを実際に抽出する。本文・多言語・6フィールド・refs/usesの元位置、誤抽出防止、不正属性/JSON、未知版、複数モデル、閉じ忘れ、section境界、回復後のpartialを確認する。Unicode・絵文字・結合文字・LF/CRLF/単独CR・JSON escapeを含む元ファイルのbytes/hashとspanを検証する。Workspace結合テストでは生成canonical・未参照原稿を入力に加えず、言語・glossary置換前のsection本文を保つ。

import境界とCLI・任意依存を禁止した`python -S`のテストにも抽出APIを含める。既存全テストと、文字列round-tripに加えた#34の基準レベル・見出しタイトル・順序・親子構造比較を維持する。式構文・型・usesとの照合・論理の検証はM3へ残し、キャンセル例の論理矛盾を今回検出済みとは扱わない。

抽出テストは構造・fixture（`test_parser.py`）、Markdown文脈・回復（`test_parser_contexts.py`）、出典・Workspace（`test_parser_sources.py`）へ役割別に整理する。[チェックリスト](../../mdtools/spec/tests/README.md)は初期実装とレビュー修正の対応、再現例、修正前後の結果、実行コマンドをまとめる。
