
要件はPandoc fenced divの`.requirement`で宣言する。IDと構文版は必須、`status`の省略値は`draft`とする。

````markdown
::: {.requirement #REQ-CANCEL-ALLOW spec-version=1 status=draft}
支払い済みで未発送なら、キャンセルを許可する。

```mdspec
{
  "version": 1,
  "id": "MODEL-CANCEL-ALLOW",
  "kind": "constraint",
  "uses": ["paid", "shipped", "cancel_allowed"],
  "when": "paid and not shipped",
  "must": "cancel_allowed == true"
}
```
:::
````

- 要件属性は`#ID`、`.requirement`、`spec-version`、`status`、任意の`refs`を認識する。`refs="REQ-A REQ-B"`は空白区切りの要件参照であり、制約の暗黙継承を意味しない。属性順序・引用符の有無で意味を変えない。
- IDは大文字小文字を区別する`[A-Za-z][A-Za-z0-9_.-]*`とする。要件IDはWorkspace全体で一意。ファイル名・見出し・章番号から生成し直さず、移動・並べ替えでも保持する。
- 本文は空にしない。本文だけの要件も有効であり、`mdspec`は任意。形式記述の省略は検査成功を意味しない。
- v1では要件に直接属する`mdspec`を最大1個とする。モデルIDはWorkspaceのモデル名前空間で一意とし、要件IDと区別する。複数のモデルを要する構文は将来の拡張として診断する。
- `mdspec`の内容はUTF-8のJSON objectとする。上の7フィールドを必須とし、`version`は整数`1`、`kind`は`constraint`、`uses`は一意な共有定義名の配列、`when`と`must`は空でない式文字列とする。未知の必須構文やフィールドを黙って捨てない。

この例で使う式の最小語彙はBooleanリテラル`true`/`false`、宣言した識別子、`not`、`and`、`==`である。演算子の結合は`not`、`==`、`and`の順とし、`when`と`must`はいずれもBooleanを要求する。`when`成立時に`must`を満たす条件付き制約として解釈する。自然言語から式を補完しない。

M2では式文字列と出典を保持する構造検査までを行い、型・式の対応可否や成立性は未検査と表示する。M3でBoolean・列挙型・有界整数、比較・論理結合の文法と型規則を追加文書化する。未対応の式をPythonの`eval`等へ渡さない。

多言語本文は一つの要件内に`::: {lang=en}` / `::: {lang=ja}`を子divとして置き、形式記述をその外側に1回だけ書く。[cancel-allow.md](examples/cancellation/cancel-allow.md) を参照。同じIDの要件を言語ごとに複製して登録しない。
