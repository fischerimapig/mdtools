
用語・定数・記号を 1 本の定義ファイル (JSON / YAML) に登録し、本文中の
Pandoc bracketed span マーカー (`[]{.term id=unit}` 等) を言語別に解決する。
`langfilter` の後段で走らせる運用が基本。

```bash
# 英語版: 言語抽出 → 用語解決
langfilter filter --lang en manuscript.qmd | \
  glossary resolve --lang en -f defs.json > manuscript.en.md

# 日本語版
langfilter filter --lang ja manuscript.qmd | \
  glossary resolve --lang ja -f defs.json > manuscript.ja.md

# 登録済みエントリの一覧 (デフォルト: テキスト表)
glossary list -f defs.json --kind term
glossary list -f defs.json --format json

# 本文マーカーの定義漏れを検出 (CI 用, exit code で通知)
glossary verify manuscript.qmd -f defs.json
```

詳細とスキーマ定義は [glossary/README.md](glossary/README.md) を参照。
