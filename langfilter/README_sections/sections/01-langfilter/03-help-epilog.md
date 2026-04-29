
```bash
# 最小例
mdtools langfilter filter manuscript.qmd --lang ja -o manuscript.ja.qmd

# よく使う例
cat manuscript.md | mdtools langfilter filter --lang en > manuscript.en.md
mdtools langfilter filter --lang en manuscript.qmd -o manuscript.en.qmd
mdtools langfilter filter --lang ja manuscript.qmd -o manuscript.ja.qmd
mdtools langfilter filter --lang both manuscript.qmd -o manuscript.both.qmd

# 失敗しやすいケース回避例
# パイプ入力時に input 引数は省略可能（- 扱い）
cat bilingual.md | mdtools langfilter filter --lang ja > ja.md
# --lang を切り替えて出力差分を比較
mdtools langfilter filter manuscript.qmd --lang en > /tmp/en.md && \
mdtools langfilter filter manuscript.qmd --lang ja > /tmp/ja.md && \
mdtools langfilter filter manuscript.qmd --lang both > /tmp/both.md
```

個別コマンドとして実行する場合は、上記の `mdtools langfilter` を `langfilter` に置き換えてください。
