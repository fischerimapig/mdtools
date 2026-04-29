
```bash
# 最小例
mdtools rewrite inventory input.md -o inventory.json

# よく使う例
mdtools rewrite inventory input.md -o inventory.json
mdtools rewrite rewrite input.md -o output.qmd --inventory inventory.json --report rewrite_report.json
mdtools rewrite convert figures --dry-run
mdtools rewrite convert figures --format svg --report convert_svg_report.json
mdtools rewrite convert figures --format png --dpi 300 --report convert_png_report.json

# 失敗しやすいケース回避例
# inventory を先に生成してから rewrite に渡し、判定の揺れを減らす
mdtools rewrite inventory input.md -o inventory.json && \
mdtools rewrite rewrite input.md -o output.qmd --inventory inventory.json
# convert は先に --dry-run で対象確認。SVG 優先か PNG+高DPI かを用途で切り替える
mdtools rewrite convert figures --dry-run && \
mdtools rewrite convert figures --format svg && \
mdtools rewrite convert figures --format png --dpi 300
```

個別コマンドとして実行する場合は、上記の `mdtools rewrite` を `mdhtml-rewrite` に置き換えてください。
