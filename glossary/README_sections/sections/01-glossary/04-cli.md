
```
glossary resolve [INPUT] --lang {en|ja} -f PATH [-f PATH ...] [-o OUT] [--on-missing {error|warn|keep}]
glossary list -f PATH [-f PATH ...] [--kind {term|const|symbol}] [--format {text|json}] [-o OUT]
glossary verify [INPUT] -f PATH [-f PATH ...]
```

| オプション | 説明 | デフォルト |
|------------|------|-----------|
| `INPUT` | 入力 Markdown/QMD。`-` または省略で stdin | stdin |
| `--lang` | 解決する言語 (`resolve` のみ必須) | — |
| `-f`, `--defs` | 定義ファイル (JSON/YAML)。複数回指定で合成 | — |
| `-o`, `--output` | 出力ファイル | stdout |
| `--on-missing` | 未定義 ID への対応 (`error`/`warn`/`keep`) | `error` |
| `--kind` | `list` の種別絞り込み | (全種別) |
| `--format` | `list` の出力 (`text`/`json`) | `text` |
