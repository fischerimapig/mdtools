
```bash
# EPS 画像を Web 向け形式へ変換
mdtools rewrite convert doc/

# HTML 断片を Quarto 記法へ変換
mdtools rewrite inventory doc/combined.md -o inv.json
mdtools rewrite rewrite doc/combined.md -o doc/combined.qmd --inventory inv.json

# 必要に応じてセクション分割して編集
mdtools mdsplit decompose doc/combined.qmd -o work/
# ... セクションファイルを編集 ...
mdtools mdsplit compose work/hierarchy.json -o doc/combined-edited.qmd

# 言語別バージョンを出力 (必要なら glossary で用語・定数マーカーを解決)
mdtools langfilter filter --lang en doc/combined-edited.qmd | \
  mdtools glossary resolve --lang en -f doc/defs.json > doc/en.qmd
mdtools langfilter filter --lang ja doc/combined-edited.qmd | \
  mdtools glossary resolve --lang ja -f doc/defs.json > doc/ja.qmd
```
