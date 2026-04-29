
pandoc が出力した HTML ベースの Markdown（`<figure>`, `<div>`, 参照リンクなど）を
Quarto の記法へ段階的に変換する。3 つのサブコマンドを順に使うのが基本ワークフロー。

```bash
# 1. EPS ファイルを SVG/PNG へ一括変換
mdhtml-rewrite convert doc/ --dry-run          # 対象確認
mdhtml-rewrite convert doc/ --report report.json

# 2. 文書内の HTML 要素を調査
mdhtml-rewrite inventory document.md -o inv.json

# 3. HTML 断片を Quarto 記法へ変換
mdhtml-rewrite rewrite document.md -o document.qmd \
  --inventory inv.json --report rewrite-report.json
```

EPS 変換の詳細（`dvisvgm` の注意点など）は [mdhtml_rewrite/README.md](mdhtml_rewrite/README.md) を参照。
