
```bash
mdhtml-rewrite rewrite doc/emax6/combined.md \
  -o /tmp/combined.rewritten.qmd \
  --inventory /tmp/combined.inventory.json \
  --report /tmp/combined.rewrite_report.json
```

出力:
- 変換後 `.qmd`（または `.md`）
- 変換レポート JSON
