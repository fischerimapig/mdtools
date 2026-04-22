# langfilter

日英併記の Markdown ソースから、指定言語のブロックのみを残すフィルタツール。

Pandoc/Quarto 互換の fenced div 記法 (`::: {lang=XX}`) を認識し、
指定言語以外のブロックを除去する。テーブル・コードブロック・図版などの
言語タグを持たないコンテンツはすべて保持される。

## 記法

```markdown
::: {lang=en}
The core consists of a D x 4 array of processing units.
:::

::: {lang=ja}
コアは D x 4 のプロセッシングユニットアレイで構成される。
:::

| Field | Bits | EN: Description | JA: 説明 |
|-------|------|-----------------|----------|
| v     | [0]  | Valid bit       | 有効ビット |
```

## 使い方

まず `--help` でオプションと最小例を確認してください。

```bash
langfilter --help
```

## 主要コマンド例（`--help` の epilog と同期）

```bash
# 最小例
langfilter filter manuscript.qmd --lang ja -o manuscript.ja.qmd

# よく使う例
cat manuscript.md | langfilter filter --lang en > manuscript.en.md
langfilter filter --lang en manuscript.qmd -o manuscript.en.qmd
langfilter filter --lang ja manuscript.qmd -o manuscript.ja.qmd
langfilter filter --lang both manuscript.qmd -o manuscript.both.qmd

# 失敗しやすいケース回避例
# パイプ入力時に input 引数は省略可能（- 扱い）
cat bilingual.md | langfilter filter --lang ja > ja.md
# --lang を切り替えて出力差分を比較
langfilter filter manuscript.qmd --lang en > /tmp/en.md && \
langfilter filter manuscript.qmd --lang ja > /tmp/ja.md && \
langfilter filter manuscript.qmd --lang both > /tmp/both.md
```

```bash
# 英語版を生成（jaブロック除去、enブロック+マーカー保持）
python -m langfilter filter --lang en input.md -o output-en.md

# 日本語版を生成
python -m langfilter filter --lang ja input.md -o output-ja.md

# 日英併記版（デフォルト: 入力をそのまま出力）
python -m langfilter filter input.md

# stdin/stdout パイプライン（mdsplit と組み合わせ）
python -m mdsplit compose hierarchy.json \
  | python -m langfilter filter --lang en > core-en.md
```

## CLI リファレンス

```
python -m langfilter filter [--lang {en,ja,both}] [-o OUTPUT] [INPUT]
```

| 引数 | 説明 | デフォルト |
|------|------|-----------|
| `INPUT` | 入力ファイルパス。`-` で stdin | stdin |
| `--lang` | 対象言語。`en`, `ja`, `both` | `both` |
| `-o`, `--output` | 出力ファイルパス | stdout |

## 動作仕様

### keep（対象言語ブロック）

`::: {lang=XX}` と閉じ `:::` のマーカー行を **保持** し、内容もそのまま出力する。

### remove（対象外言語ブロック）

`::: {lang=XX}` から閉じ `:::` まで（マーカー行含む）をすべて除去する。
除去後に空行が連続する場合もそのまま保持する（正規化しない）。

### both モード

入力をそのまま返す（恒等変換）。

### 共有コンテンツ

`::: {lang=...}` の外にあるコンテンツは常に保持される:
- テーブル（日英併記ヘッダーを含む）
- コードブロック
- 画像・図版
- HTML コメント
- 見出し・front matter

### コードフェンスとの相互作用

コードブロック（`` ``` `` / `~~~`）内の `:::` はフィルタ対象外。
langブロック内のコードフェンスは内容の一部として正しく処理される。

### 非lang fenced div

`::: {.callout-note}` のような lang 属性を持たない fenced div はそのまま保持される。

## 構文バリエーション

以下の記法はすべて認識される:

- `::: {lang=en}`
- `:::{lang=en}`（空白なし）
- `:::  { lang = en }`（余分な空白）
- `::: {lang="en"}`（引用符付き）

## テスト

```bash
cd tools/mdtools
.venv/bin/pytest langfilter/tests/ -v
```

## 要件

- Python 3.9+
- 外部依存なし（標準ライブラリのみ）
- テスト実行には pytest が必要
