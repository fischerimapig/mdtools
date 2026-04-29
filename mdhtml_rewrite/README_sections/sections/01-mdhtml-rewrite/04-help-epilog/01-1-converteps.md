
```bash
# dry-run で変換対象を確認
mdtools rewrite convert doc/emax6/ --dry-run

# 一括変換（ベクター→SVG, ラスター→PNG を自動判別）
mdtools rewrite convert doc/emax6/ --report /tmp/convert-report.json

# 強制再変換
mdtools rewrite convert doc/emax6/ --force

# PNG のみで変換（SVG 不要の場合）
mdtools rewrite convert doc/emax6/ --format png --dpi 200
```

オプション:
- `--force`: 既存の変換済みファイルも再変換
- `--dry-run`: 変換せずに何が行われるか表示
- `--format auto|svg|png`: 変換先形式（デフォルト: auto）
- `--dpi N`: ラスター変換の解像度（デフォルト: 150）
- `--report FILE`: 変換レポート JSON 出力
