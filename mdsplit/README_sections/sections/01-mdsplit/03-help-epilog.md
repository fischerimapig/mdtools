
```bash
# 最小例
mdsplit decompose manuscript.qmd

# よく使う例
mdsplit decompose manuscript.qmd -o manuscript_sections
mdsplit compose manuscript_sections/hierarchy.json -o rebuilt.qmd
mdsplit compose manuscript_sections/hierarchy.json > rebuilt.qmd
mdsplit verify manuscript_sections/hierarchy.json

# 失敗しやすいケース回避例
# 1) decompose -> 2) verify -> 3) compose の順で安全に確認
mdsplit decompose manuscript.qmd -o manuscript_sections && \
mdsplit verify manuscript_sections/hierarchy.json && \
mdsplit compose manuscript_sections/hierarchy.json -o rebuilt.qmd
# compose を標準出力で使うときはリダイレクトを忘れない
mdsplit compose manuscript_sections/hierarchy.json > rebuilt.qmd
```
