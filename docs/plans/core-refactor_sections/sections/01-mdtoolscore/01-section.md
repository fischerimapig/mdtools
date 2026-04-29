
`mdsplit`、`langfilter`、`mdhtml-rewrite`、`glossary` はそれぞれ独立した CLI として始まりました。glossary 追加後、以下の重複が目立つようになりました。

- stdin/stdout と UTF-8 ファイル I/O
- JSON/YAML 読み書きと `ensure_ascii=False, indent=2` の JSON 出力
- Markdown code fence の状態追跡
- Pandoc/Quarto 属性の正規表現とパース処理

これらを []{.term id=mdtools-core} に集約し、公開 CLI は維持したまま内部実装だけを整理しました。
