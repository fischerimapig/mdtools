
```bash
# EPS 画像を Web 向け形式へ変換
mdtools rewrite convert doc/

# HTML 断片を Quarto 記法へ変換
mdtools rewrite inventory doc/combined.md -o inv.json
mdtools rewrite rewrite doc/combined.md -o doc/combined.qmd --inventory inv.json

# 必要に応じてセクション分割して編集
mdtools mdsplit decompose doc/combined.qmd -o work/
# ... セクションファイルを編集 ...

# 配布用の言語別バージョンを公式ビルド手順で出力
mdtools build work/hierarchy.json --lang en -f doc/defs.json -o doc/en.qmd
mdtools build work/hierarchy.json --lang ja -f doc/defs.json -o doc/ja.qmd --work-dir .build/ja
```
