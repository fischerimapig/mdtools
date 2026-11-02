
Workspaceへ明示登録した原典から要件・モデル・宣言・glossary・明示参照と出典を取得します。

```bash
mdtools spec index --project docs/spec/examples/model-contract/mdtools.toml --format json
mdtools spec show REQ-NORMAL --project docs/spec/examples/model-contract/mdtools.toml --format text
mdtools spec show REQ-MULTILINGUAL --project docs/spec/examples/model-contract/mdtools.toml --format json
```

`--project PATH`は必須、`--format`はtext/json（既定text）です。showの対象は大小文字を区別する要件ID一つです。
設定や生成IRを暗黙に探索せず、langfilter・glossary置換前の原典を解析します。

処理順は「設定・原典選択 → snapshot取得 → parser/loader → resolver・SpecGraph → SpecIR → 表示」です。
indexはIR全体を返します。showはそのIRから対象要件の全出現、各言語本文、所属モデル、uses先の宣言と型依存・glossary関連付け、明示参照、対象要件内の拒否断片を選択します。
refs先のID・解決状態・全候補を保持し、他要件の本文は展開しません。
両コマンドは独立し、それぞれWorkspace全体を一度解析します。indexのJSONをshowへ入力する方式ではなく、原典が変わればsnapshotも変わります。

JSON stdoutは末尾LF付きの単一objectです。`schema_version=1`、`command`、解析の`status`、`exit_code`、`result`、全体の`report`を持ちます。
showは成功・失敗とも`query.requirement_id`に指定IDを保持します。これは原典中の出現識別子NodeKeyとは別の問い合わせ条件です。
showのresultは`requirements/models/declarations/glossary/references/rejected`の配列で、重複IDも全出現を保持します。
IR生成不能・対象不存在ではresultはnullです。解析済み集合に対象がなければ`spec.unknown-id`を追加しますが、解析status自体は変更しません。
通常経路のstderrは空で、診断はreportへ集約します。textは全フィールドを階層パスと引用した値で表示し、全体診断には共通rendererを使用します。
パスは`.`で区切り、objectキーが`[A-Za-z_][A-Za-z0-9_]*`に一致する場合はそのまま、それ以外はJSON文字列として引用・escapeして`[...]`で囲みます。空文字・改行・引用符・backslashもこの規則で扱い、配列添字の`[0]`とキーの`["[0]"]`を区別します。

```text
result.glossary.[0].data.["a.b"] = "flat"
result.glossary.[0].data.a.b = "nested"
result.glossary.[0].data.["line\nbreak"] = "value"
```

終了コードは0=M2解析・表示成功、1=設定/原稿/宣言/参照不正・未対応、2=引数不備、3=解析completeで対象不存在、4=I/O/文字コード/内部実行失敗、5=必要な任意依存不足です。
優先順位は`2 → 4 → 5 → 1 → 3 → 0`で、showの対象が存在しても全体のpartial/unavailableや失敗を隠しません。
引数不備はstdoutを空にしてstderrへusageと理由、helpはstdoutへ表示して0で終了します。

M2成功は構造・宣言値・明示参照の範囲です。natural-only、形式記述の構造不正・未対応、M3の式構文/式型/uses照合/論理の理由付きnot-runを区別します。
論理的な無矛盾性や本文と形式の意味的一致は保証しません。YAML入力だけが任意依存PyYAMLを必要とします。
詳細は[CLI契約](docs/spec/contract-v1.md#m2-indexshowの入出力診断契約)を参照してください。
