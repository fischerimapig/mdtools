
```
langfilter filter [--lang {en,ja,both}] [--keep-lang-fences] [-o OUTPUT] [INPUT]
```

| 引数 | 説明 | デフォルト |
|------|------|-----------|
| `INPUT` | 入力ファイルパス。`-` で stdin | stdin |
| `--lang` | 対象言語。`en`, `ja`, `both` | `both` |
| `--keep-lang-fences` | 対象言語ブロックの fenced div マーカー行も残す | false |
| `-o`, `--output` | 出力ファイルパス | stdout |
