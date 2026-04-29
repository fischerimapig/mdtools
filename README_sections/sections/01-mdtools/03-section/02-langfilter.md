
`::: {lang=en}` / `::: {lang=ja}` の fenced div ブロックを認識し、指定言語以外を除去する。
言語タグを持たないテーブル・コードブロック・図版はすべて保持される。

```bash
# 英語版を生成（ja ブロックを除去）
langfilter filter --lang en input.md -o output-en.md

# 日本語版を生成（en ブロックを除去）
langfilter filter --lang ja input.md -o output-ja.md

# stdin/stdout パイプライン
mdsplit compose work/hierarchy.json | langfilter filter --lang en > core-en.md
```

詳細は [langfilter/README.md](langfilter/README.md) を参照。
