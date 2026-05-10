
section 管理された原稿や単一 Markdown/QMD から、配布用の統合ファイルを作る公式ビルド入口。
入力が `hierarchy.json` の場合だけ `mdsplit compose` を先に実行し、`--lang en/ja` が指定された場合だけ `langfilter`、`-f/--defs` が指定された場合だけ `glossary resolve` を実行する。
各ステージ後の結果は中間ファイルに保存し、次ステージはそのファイルを入力として読む。

```bash
# section 原稿から英語版を生成
mdtools build manuscript_sections/hierarchy.json --lang en -f defs.yaml -o manuscript.en.qmd

# 日本語版。中間ファイルも確認したい場合
mdtools build manuscript_sections/hierarchy.json --lang ja -f defs.yaml -o manuscript.ja.qmd \
  --work-dir .build/manuscript-ja

# すでに単一ファイルへ統合済みなら compose は省略される
mdtools build manuscript.qmd --lang en -o manuscript.en.qmd
```

実行順は `compose → langfilter → glossary` が基本です。
`mdsplit compose` は小さな原稿ファイル群を単一の文書構造へ戻す段階なので先頭に置く。
`glossary` は `lang=...` fenced div を解釈しないため、言語別出力では `langfilter` を先に通してから用語を解決する。
`langfilter` は選択言語の wrapper 行を既定で除去するため、配布物に `::: {lang=...}` は残らない。
