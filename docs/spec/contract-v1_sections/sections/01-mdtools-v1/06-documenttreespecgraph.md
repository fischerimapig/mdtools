
DocumentTreeは見出し、sectionの順序・入れ子、ファイル参照を表す既存`mdsplit.schema.DocumentTree`である。SpecGraphは要件、モデル、型・変数・定数、明示的な参照の関係を表す。文書の親子を要件の継承・依存・制約の適用範囲へ暗黙に変換しない。

```mermaid
flowchart LR
    sources["登録された編集原典"] --> tree["DocumentTree: 表示順・階層"]
    sources --> graph["SpecGraph: 要件・定義・明示参照"]
    graph --> ir["SpecIR: 版付き生成snapshot"]
    ir --> checks["検査計画・バックエンド"]
    checks --> results["検査結果・診断"]
    sources --> build["compose / langfilter / glossary"]
    build --> distribution["配布文書"]
```

SpecIRはSpecGraphを機械可読に出力する生成snapshotとする。契約版・IRスキーマ版・入力の識別と内容hash、要件ID・本文・形式記述・定義・出典・参照を保持し、同じ入力と設定から決定的な順序で生成する。式が未解析ならその文字列と未検査状態を保持し、型検査済みASTのように表示しない。

原稿の移動は出典の変更として表現し、要件IDは保つ。文書順序の変更と仕様内容の変更は区別する。IRや配布文書だけを編集しても原典の更新にはならず、再生成時に派生物が変わる。
