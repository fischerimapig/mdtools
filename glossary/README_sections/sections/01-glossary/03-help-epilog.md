
```bash
# 最小例: 英語版を解決
glossary resolve manuscript.md --lang en -f defs.json -o out.md

# 一覧 (テキスト表、既定)
glossary list -f defs.json

# 未定義参照の検証 (CI 用)
glossary verify manuscript.md -f defs.json

# langfilter と組み合わせた言語別パイプライン
langfilter filter --lang en in.qmd | \
  glossary resolve --lang en -f defs.json > out.en.md
langfilter filter --lang ja in.qmd | \
  glossary resolve --lang ja -f defs.json > out.ja.md

# 複数の定義ファイルを合成 (JSON + YAML 混在可)
glossary resolve in.md --lang ja -f terms.json -f consts.yaml

# JSON 一覧
glossary list -f defs.json --kind term --format json
```
