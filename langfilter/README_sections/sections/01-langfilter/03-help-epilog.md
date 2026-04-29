
```bash
# 最小例
langfilter filter manuscript.qmd --lang ja -o manuscript.ja.qmd

# よく使う例
cat manuscript.md | langfilter filter --lang en > manuscript.en.md
langfilter filter --lang en manuscript.qmd -o manuscript.en.qmd
langfilter filter --lang ja manuscript.qmd -o manuscript.ja.qmd
langfilter filter --lang both manuscript.qmd -o manuscript.both.qmd

# 失敗しやすいケース回避例
# パイプ入力時に input 引数は省略可能（- 扱い）
cat bilingual.md | langfilter filter --lang ja > ja.md
# --lang を切り替えて出力差分を比較
langfilter filter manuscript.qmd --lang en > /tmp/en.md && \
langfilter filter manuscript.qmd --lang ja > /tmp/ja.md && \
langfilter filter manuscript.qmd --lang both > /tmp/both.md
```
