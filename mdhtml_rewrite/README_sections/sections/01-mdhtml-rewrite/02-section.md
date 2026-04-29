
リポジトリ内からそのまま実行できます（Python 標準ライブラリのみ）。

EPS 変換機能（`convert`）を使う場合は以下の外部ツールが必要です:

| ツール | 用途 | インストール |
|-------|------|-------------|
| `gs` (Ghostscript) | ラスター EPS → PNG | `apt install ghostscript` |
| `dvisvgm` | ベクター EPS → SVG | `apt install dvisvgm` または `apt install texlive-full` |

```bash
mdhtml-rewrite --help
```
