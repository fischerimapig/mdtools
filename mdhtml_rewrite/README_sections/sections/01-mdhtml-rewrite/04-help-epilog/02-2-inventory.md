
```bash
mdtools rewrite inventory doc/emax6/combined.md \
  -o /tmp/combined.inventory.json
```

出力:
- `counts`: 要素タイプ別件数
- `figures` / `divs` / `refs`: 明細
- `needs_manual`: 自動変換を避けるべき候補
