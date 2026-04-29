
Markdown/QMD ファイルをセクションファイルに分解し、`hierarchy.json` を生成する。

```
mdsplit decompose <input> [-o <dir>] [--flat]
```

| オプション | 説明 |
|---|---|
| `<input>` | 入力ファイル（`.md` または `.qmd`） |
| `-o`, `--output-dir` | 出力ディレクトリ（デフォルト: `<入力ファイル名>_sections/`） |
| `--flat` | フラットなディレクトリ構造を使用（デフォルトはネスト型） |
