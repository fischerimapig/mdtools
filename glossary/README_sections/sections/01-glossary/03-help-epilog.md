
```bash
# 最小例: 英語版を解決
mdtools glossary resolve manuscript.md --lang en -f defs.json -o out.md

# 一覧 (テキスト表、既定)
mdtools glossary list -f defs.json

# 未定義参照の検証 (CI 用)
mdtools glossary verify manuscript.md -f defs.json

# langfilter と組み合わせた言語別パイプライン
mdtools langfilter filter --lang en in.qmd | \
  mdtools glossary resolve --lang en -f defs.json > out.en.md
mdtools langfilter filter --lang ja in.qmd | \
  mdtools glossary resolve --lang ja -f defs.json > out.ja.md

# 複数の定義ファイルを合成 (JSON + YAML 混在可)
mdtools glossary resolve in.md --lang ja -f terms.json -f consts.yaml

# JSON 一覧
mdtools glossary list -f defs.json --kind term --format json
```

個別コマンドとして実行する場合は、上記の `mdtools glossary` を `glossary` に置き換えてください。
