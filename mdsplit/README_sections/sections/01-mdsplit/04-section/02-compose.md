
`hierarchy.json` とセクションファイルから単一の Markdown ファイルを再構成する。

```
mdsplit compose <hierarchy.json> [-o <output>] [--base-level N]
```

| オプション | 説明 |
|---|---|
| `<hierarchy.json>` | 階層定義ファイルへのパス |
| `-o`, `--output` | 出力ファイルパス（省略時は標準出力） |
| `--base-level` | 見出しの基準レベルを上書き（例: `2` で `##` 始まりに） |
