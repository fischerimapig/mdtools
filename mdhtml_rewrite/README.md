# mdhtml_rewrite

`mdhtml_rewrite` は、pandoc 変換後の Markdown に含まれる HTML 断片（`<figure>`, `<div>`, `<a ... data-reference-type="ref">` など）を調査し、Quarto / qmd で扱いやすい記法へ段階的に変換するためのツールです。

## できること

- `convert`
  - EPS ファイルを Web 表示向け形式（SVG / PNG）へ一括変換
  - ベクター EPS（Tgif 作成）→ SVG を優先し、`auto` では必要に応じて PNG へ退避
  - ラスター EPS（pnmtops 作成）→ PNG（Ghostscript）
  - EPS ヘッダの `%%Creator` から自動判別
- `inventory`
  - 文書内の主要要素（figure/div/ref）の件数・位置・属性を JSON で出力
  - 自動変換が危険な要素（例: 画像ソースを持たない figure）を `needs_manual` として抽出
- `rewrite`
  - HTML ベースの figure を Markdown 画像またはコードブロックへ変換
  - `div.screen` を fenced code block へ変換
  - 一部の表ラッパ `div` を Markdown 表 + キャプション形式へ変換
  - pandoc の HTML 参照リンクを `@id` 形式へ変換

## インストール

リポジトリ内からそのまま実行できます（Python 標準ライブラリのみ）。

EPS 変換機能（`convert`）を使う場合は以下の外部ツールが必要です:

| ツール | 用途 | インストール |
|-------|------|-------------|
| `gs` (Ghostscript) | ラスター EPS → PNG | `apt install ghostscript` |
| `dvisvgm` | ベクター EPS → SVG | `apt install dvisvgm` または `apt install texlive-full` |

```bash
python3 -m tools.mdhtml_rewrite --help
```

## 使い方

### 1) convert（EPS 変換）

```bash
# dry-run で変換対象を確認
python3 -m tools.mdhtml_rewrite convert doc/emax6/ --dry-run

# 一括変換（ベクター→SVG, ラスター→PNG を自動判別）
python3 -m tools.mdhtml_rewrite convert doc/emax6/ --report /tmp/convert-report.json

# 強制再変換
python3 -m tools.mdhtml_rewrite convert doc/emax6/ --force

# PNG のみで変換（SVG 不要の場合）
python3 -m tools.mdhtml_rewrite convert doc/emax6/ --format png --dpi 200
```

オプション:
- `--force`: 既存の変換済みファイルも再変換
- `--dry-run`: 変換せずに何が行われるか表示
- `--format auto|svg|png`: 変換先形式（デフォルト: auto）
- `--dpi N`: ラスター変換の解像度（デフォルト: 150）
- `--report FILE`: 変換レポート JSON 出力

### 2) inventory（要素調査）

```bash
python3 -m tools.mdhtml_rewrite inventory doc/emax6/combined.md \
  -o /tmp/combined.inventory.json
```

出力:
- `counts`: 要素タイプ別件数
- `figures` / `divs` / `refs`: 明細
- `needs_manual`: 自動変換を避けるべき候補

### 3) rewrite（変換）

```bash
python3 -m tools.mdhtml_rewrite rewrite doc/emax6/combined.md \
  -o /tmp/combined.rewritten.qmd \
  --inventory /tmp/combined.inventory.json \
  --report /tmp/combined.rewrite_report.json
```

出力:
- 変換後 `.qmd`（または `.md`）
- 変換レポート JSON

#### Web 形式優先を無効化したい場合

```bash
python3 -m tools.mdhtml_rewrite rewrite doc/emax6/combined.md \
  -o /tmp/combined.rewritten.qmd \
  --no-prefer-png
```

## 画像形式の扱い（重要）

### 1. 既に表示向きの形式は維持

以下の拡張子はそのまま使います:
- `.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp`

### 2. `.eps` / `.ps` / `.pdf` の扱い

- **同名の `.svg` が存在する場合** → `.svg` へ参照を切り替え（最優先）
- **同名の `.png` が存在する場合** → `.png` へ参照を切り替え
- いずれもなければ元のパス（例: `.eps`）を保持

### 3. EPS 変換について

`convert` サブコマンドで EPS ファイルを SVG/PNG へ実変換できます。
EPS ヘッダの `%%Creator` を読み取り、ベクター（Tgif 等）はまず SVG を試し、ラスター（pnmtops 等）は PNG へ変換します。
`--format auto` では、ベクター EPS の SVG 変換が失敗しても `gs` が使えれば PNG へフォールバックします。
一方で `--format svg` は厳密モードのため、SVG を生成できない場合は失敗します。

`dvisvgm` はバイナリが存在するだけでは不十分で、環境によっては TeX / DVIPS 系の補助ファイル
（`texmf.cnf`, `tex.pro`, `texps.pro` など）が不足すると EPS→SVG が失敗します。
その場合は `texlive-full` のようなより完全な TeX 環境を入れるか、`--format auto` で PNG フォールバックを利用してください。

## 現在の変換ルール（概要）

- `<figure>` + `<embed src="...">` + `<figcaption>`
  - Markdown 画像 `![caption](path){#id width=...}` へ
- `<figure>` 内 `pre/code`（画像なし）
  - キャプション付きコードブロックへ
- `<figure>` で画像もコードも無い場合
  - 変換せず維持（`needs_manual`）
- `<div class="screen"> ... </div>`
  - fenced code block へ
- `<div id="physinterface|logicinterface|lmm-operation|alu-operation">`
  - 表本文 + キャプション行 `{#id}` へ
- `<a ... data-reference-type="ref" ...>`
  - `@id` へ

## 注意点

- 正規表現ベースでの変換のため、複雑にネストされた HTML は意図通りに変換できない場合があります。
- 変換結果は必ず差分確認してください（特に図表番号・参照）。
- `needs_manual` を先に確認してから一括変換を適用する運用を推奨します。

## 推奨ワークフロー

1. `convert` で EPS を SVG/PNG へ変換
2. `inventory` を実行し、`needs_manual` を確認
3. `rewrite` を実行
4. 変換レポートと diff を確認
5. 問題箇所のみ手動修正
