
表示用の用語・定数・記号は既存glossaryの`entries`スキーマを維持する。仕様用宣言は別のJSON/YAML文書とし、整数の`version: 1`と、`types`、`variables`、`constants`の4フィールドを必須とする。各宣言は名前から宣言内容へのmappingで、空の場合も`{}`を指定する。未知のフィールドや版は診断する。JSONでは追加依存を要求しない。YAMLは既存と同じ任意依存を利用する。

```json
{
  "version": 1,
  "types": {},
  "variables": {
    "paid": {"type": "bool", "role": "input"},
    "shipped": {"type": "bool", "role": "input"},
    "cancel_allowed": {"type": "bool", "role": "output"}
  },
  "constants": {
    "cancel_window_days": {"type": "int", "min": 0, "max": 30, "value": 14}
  }
}
```

型名は要件IDと同じ文字集合を使い、組み込み型名`bool`と`int`の再定義を禁止する。式から参照する変数・定数名は`[A-Za-z_][A-Za-z0-9_]*`とし、`true`、`false`、`not`、`and`、`or`を予約する。名前は大文字小文字を区別し、`types`・`variables`・`constants`を横断する重複名はエラーとする。

初期の型は`bool`、上下限を明示する`int`、`types`に`{"kind":"enum","values":["new","paid"]}`の形で宣言する列挙型とする。変数の`role`は`input`または`output`。整数には`min`/`max`を必須とし、`min <= max`を要求する。定数の`value`は宣言型と範囲を満たす値でなければならない。空の列挙・重複要素・未定義の型は診断する。列挙値や整数を使う式の文法と検査はM3の範囲である。

`uses`はモデルが使用する変数・定数名を明示する。式中の識別子は`uses`に含まれ、全参照が解決できなければならない。型依存は宣言から追跡する。要件の`refs`は要件名前空間に解決し、型・モデル・glossary IDへ偶然一致しても代用しない。循環参照があっても走査は停止し、要件参照の循環だけから論理矛盾を推定しない。

複数の仕様定義ファイルでの重複名、同一JSON/YAML文書内の重複キーはエラーとし、後勝ちで制約を消さない。仕様から利用するglossary IDも読み込み時に衝突を診断し、既存glossary CLIの「警告して後勝ち」と区別する。

glossaryの表示文字列を式・型・数値へ暗黙変換しない。仕様用の定数には明示型が必要であり、既存glossary定義に型を追加する移行は要求しない。M2 / #35で留保した関連付けを具体化し、型・変数・定数宣言に任意の文字列glossaryを1件指定できる。「M2 / #35 仕様モデルと解析結果」の名前空間・能力・出典規則に従う。
