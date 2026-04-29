
```bash
# 最小例
mdtools mdsplit decompose manuscript.qmd

# よく使う例
mdtools mdsplit decompose manuscript.qmd -o manuscript_sections
mdtools mdsplit compose manuscript_sections/hierarchy.json -o rebuilt.qmd
mdtools mdsplit compose manuscript_sections/hierarchy.json > rebuilt.qmd
mdtools mdsplit verify manuscript_sections/hierarchy.json

# 失敗しやすいケース回避例
# 1) decompose -> 2) verify -> 3) compose の順で安全に確認
mdtools mdsplit decompose manuscript.qmd -o manuscript_sections && \
mdtools mdsplit verify manuscript_sections/hierarchy.json && \
mdtools mdsplit compose manuscript_sections/hierarchy.json -o rebuilt.qmd
# compose を標準出力で使うときはリダイレクトを忘れない
mdtools mdsplit compose manuscript_sections/hierarchy.json > rebuilt.qmd
```

個別コマンドとして実行する場合は、上記の `mdtools mdsplit` を `mdsplit` に置き換えてください。
