# mdtools

Markdown 文書の編集を補助するコマンドラインツール集。

| ツール | 概要 |
|--------|------|
| **mdsplit** | Markdown/QMD 文書を見出し単位のセクションファイルに分解・再構成する |
| **langfilter** | 日英併記 Markdown から指定言語のブロックだけを抽出する |
| **mdhtml-rewrite** | pandoc 変換後の HTML 断片を Quarto (.qmd) 互換の記法へ変換する |

## 必要環境

- Python 3.13+
- 外部ライブラリ不要（標準ライブラリのみ）
- `mdhtml-rewrite convert` には Ghostscript (`gs`) と dvisvgm が別途必要

## インストール

### グローバルインストール（推奨）

```bash
uv tool install .
```

`mdtools` / `mdsplit` / `langfilter` / `mdhtml-rewrite` の 4 コマンドがシェルから直接使えるようになります。
コードを変更した場合は `uv tool install . --reinstall` で再インストールしてください。

### 開発用（エディタブルインストール）

```bash
uv pip install -e .
# インストール後は uv run <command> で呼び出す
uv run mdsplit --help
```

## 使い方

各ツールは個別コマンドとして、または `mdtools <tool>` の統合コマンドとして呼び出せます。
まずは各コマンドの `--help` を確認し、オプション定義と最小実行例を把握してから README の詳細へ進んでください。

```bash
mdsplit decompose document.md -o work/
# 上と同じ
mdtools mdsplit decompose document.md -o work/
```

### mdsplit

大きな Markdown/QMD 文書をセクション単位のファイルに分解し、`hierarchy.json` で階層を管理する。
JSON を編集してセクションの順序や見出しレベルを変更してから再構成できる。

```bash
# 分解: document.md → work/ 以下のセクションファイル群
mdsplit decompose document.md -o work/

# 再構成: セクションファイル群 → 単一ファイル
mdsplit compose work/hierarchy.json -o reconstructed.md

# 参照ファイルの存在チェック
mdsplit verify work/hierarchy.json

# フラット構造で分解（ネスト無し）
mdsplit decompose document.md -o work/ --flat
```

詳細は [mdsplit/README.md](mdsplit/README.md) を参照。

### langfilter

`::: {lang=en}` / `::: {lang=ja}` の fenced div ブロックを認識し、指定言語以外を除去する。
言語タグを持たないテーブル・コードブロック・図版はすべて保持される。

```bash
# 英語版を生成（ja ブロックを除去）
langfilter filter --lang en input.md -o output-en.md

# 日本語版を生成（en ブロックを除去）
langfilter filter --lang ja input.md -o output-ja.md

# stdin/stdout パイプライン
mdsplit compose work/hierarchy.json | langfilter filter --lang en > core-en.md
```

詳細は [langfilter/README.md](langfilter/README.md) を参照。

### mdhtml-rewrite

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

## 典型的なワークフロー

```bash
# EPS 画像を Web 向け形式へ変換
mdhtml-rewrite convert doc/

# HTML 断片を Quarto 記法へ変換
mdhtml-rewrite inventory doc/combined.md -o inv.json
mdhtml-rewrite rewrite doc/combined.md -o doc/combined.qmd --inventory inv.json

# 必要に応じてセクション分割して編集
mdsplit decompose doc/combined.qmd -o work/
# ... セクションファイルを編集 ...
mdsplit compose work/hierarchy.json -o doc/combined-edited.qmd

# 言語別バージョンを出力
langfilter filter --lang en doc/combined-edited.qmd -o doc/en.qmd
langfilter filter --lang ja doc/combined-edited.qmd -o doc/ja.qmd
```

## テスト

```bash
uv run python -m pytest -q
```

## ライセンス

MIT

## ドキュメント運用ルール（README / --help 同期）

### 基本方針

- `--help` は「実行時に必要な操作情報（オプション定義・短い例）」を示す。
- README は「背景、設計意図、詳細ユースケース」を示す。
- まず `--help` を見てから README を読む導線を維持する。

### 変更時チェックリスト（簡易運用）

1. CLI の `epilog` を変更した場合、対応する README の「主要コマンド例（--help と同期）」節を同時に更新したか。
2. README 側で主要コマンド例を変更した場合、対応する CLI の `epilog` を同時に更新したか。
3. `--help` は短い実行例に留め、背景説明や長文の運用ノウハウは README に寄せたか。
4. 仕上げに次を実行し、差分が意図通りか確認したか。

```bash
mdsplit --help
langfilter --help
mdhtml-rewrite --help
git diff -- README.md mdsplit/README.md mdhtml_rewrite/README.md langfilter/README.md \
  mdsplit/cli.py mdhtml_rewrite/cli.py langfilter/cli.py
```
