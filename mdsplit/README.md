# mdsplit

Markdown/QMD 文書を見出し(Heading)単位でセクションファイルに分解し、階層構造を JSON で管理、セクションファイル群から元の文書を再構成するツール。

## 必要環境

- Python 3.13 以上
- 外部ライブラリ不要（標準ライブラリのみ）
- テスト実行には `pytest` が必要

## クイックスタート

最初に `--help` を確認し、利用可能なサブコマンドとオプションを把握してください。

```bash
mdsplit --help
```

リポジトリルートから実行する場合:

```bash
# 分解: Markdown → セクションファイル + hierarchy.json
mdsplit decompose doc/emax6/combined.md -o output/

# 再構成: hierarchy.json + セクションファイル → Markdown
mdsplit compose output/hierarchy.json -o reconstructed.md

# 検証: 参照ファイルの存在チェック
mdsplit verify output/hierarchy.json
```

```mermaid
flowchart LR
    doc["canonical Markdown/QMD"]
    decompose["mdsplit decompose"]
    hierarchy["hierarchy.json"]
    sections["section files"]
    verify["mdsplit verify"]
    compose["mdsplit compose"]
    rebuilt["rebuilt Markdown/QMD"]

    doc --> decompose
    decompose --> hierarchy
    decompose --> sections
    hierarchy --> verify
    sections --> verify
    hierarchy --> compose
    sections --> compose
    compose --> rebuilt
```

## 主要コマンド例（`--help` の epilog と同期）

```bash
# 最小例
mdsplit decompose manuscript.qmd

# よく使う例
mdsplit decompose manuscript.qmd -o manuscript_sections
mdsplit compose manuscript_sections/hierarchy.json -o rebuilt.qmd
mdsplit compose manuscript_sections/hierarchy.json > rebuilt.qmd
mdsplit verify manuscript_sections/hierarchy.json

# 失敗しやすいケース回避例
# 1) decompose -> 2) verify -> 3) compose の順で安全に確認
mdsplit decompose manuscript.qmd -o manuscript_sections && \
mdsplit verify manuscript_sections/hierarchy.json && \
mdsplit compose manuscript_sections/hierarchy.json -o rebuilt.qmd
# compose を標準出力で使うときはリダイレクトを忘れない
mdsplit compose manuscript_sections/hierarchy.json > rebuilt.qmd
```

## コマンドリファレンス

### decompose

Markdown/QMD ファイルをセクションファイルに分解し、`hierarchy.json` を生成する。

```
mdsplit decompose <input> [-o <dir>] [--flat]
```

| オプション | 説明 |
|---|---|
| `<input>` | 入力ファイル（`.md` または `.qmd`） |
| `-o`, `--output-dir` | 出力ディレクトリ（デフォルト: `<入力ファイル名>_sections/`） |
| `--flat` | フラットなディレクトリ構造を使用（デフォルトはネスト型） |

### compose

`hierarchy.json` とセクションファイルから単一の Markdown ファイルを再構成する。

```
mdsplit compose <hierarchy.json> [-o <output>] [--base-level N]
```

| オプション | 説明 |
|---|---|
| `<hierarchy.json>` | 階層定義ファイルへのパス |
| `-o`, `--output` | 出力ファイルパス（省略時は標準出力） |
| `--base-level` | 見出しの基準レベルを上書き（例: `2` で `##` 始まりに） |

### verify

`hierarchy.json` が参照する全セクションファイルの存在を確認する。

```
mdsplit verify <hierarchy.json>
```

## 出力ディレクトリ構造

### ネスト型（デフォルト）

見出し階層に合わせてディレクトリをネストする:

```
output/
    hierarchy.json
    sections/
        01-imax-hardware.md
        01-imax-hardware/
            01-background.md
            02-history-of-cgra.md
            03-policy-of-imax.md
        02-imax-software.md
        02-imax-software/
            01-section.md
            ...
```

### フラット型（`--flat`）

全セクションファイルを同一ディレクトリに配置する:

```
output/
    hierarchy.json
    sections/
        01-imax-hardware.md
        01-01-background.md
        01-02-history-of-cgra.md
        02-imax-software.md
        ...
```

## JSON スキーマ（hierarchy.json）

```json
{
  "source_file": "combined.md",
  "base_level": 1,
  "metadata": {},
  "sections": [
    {
      "title": "IMAX Hardware",
      "file": "sections/01-imax-hardware.md",
      "order": 0,
      "children": [
        {
          "title": "Background",
          "file": "sections/01-imax-hardware/01-background.md",
          "order": 0,
          "children": []
        }
      ]
    }
  ]
}
```

### トップレベルフィールド

| フィールド | 型 | 説明 |
|---|---|---|
| `source_file` | string | 分解元ファイル名（参考情報） |
| `base_level` | int | ツリー最上位の見出しレベル（通常 `1` = `#`） |
| `metadata` | object | YAML front matter や将来の Quarto 設定用 |
| `sections` | array | トップレベルセクションのリスト |

### SectionNode フィールド

| フィールド | 型 | 説明 |
|---|---|---|
| `title` | string | 見出しテキスト（`#` プレフィックスなし） |
| `file` | string | セクションファイルへの相対パス |
| `order` | int | 兄弟間の並び順（0始まり） |
| `children` | array | 子セクションのリスト |

### 見出しレベルの導出

見出しレベル（`#` の数）は JSON に保存しない。再構成時にツリー深さから自動計算する:

```
見出しレベル = base_level + ツリー内の深さ
```

これにより、JSON 上でノードを移動するだけで見出しレベルが自動的に変わる。例えば `###`（深さ2）のセクションをルート直下（深さ0）に移動すれば、再構成時に `#` になる。

## ワークフロー例

### セクションの並び替え

```bash
# 1. 分解
mdsplit decompose document.md -o work/

# 2. hierarchy.json を編集してセクションの order を変更
#    例: "Background" の order を 0 → 2 に変更

# 3. 再構成
mdsplit compose work/hierarchy.json -o reordered.md
```

### セクションの階層変更

```bash
# 1. 分解
mdsplit decompose document.md -o work/

# 2. hierarchy.json を編集:
#    "### Deep Section" を children から取り出してトップレベルの sections に移動
#    → 再構成時に ### から # に昇格

# 3. 再構成
mdsplit compose work/hierarchy.json -o restructured.md
```

### ラウンドトリップ検証

```bash
mdsplit decompose document.md -o work/
mdsplit compose work/hierarchy.json -o roundtrip.md
diff document.md roundtrip.md  # 差分なしが期待値
```

## Python API としての利用

```python
from pathlib import Path

# tools/ を PYTHONPATH に含める必要あり
from mdsplit.decompose import decompose
from mdsplit.compose import compose
from mdsplit.schema import DocumentTree, SectionNode

# 分解
doc_tree = decompose("document.md", "output/")

# JSON の読み込み・操作
tree = DocumentTree.load("output/hierarchy.json")
for section in tree.sections:
    print(f"{section.title} ({len(section.children)} children)")

# 再構成
text = compose("output/hierarchy.json")

# base_level を変えて再構成（## 始まりに）
text = compose("output/hierarchy.json", base_level=2)
```

## テスト

```bash
uv run pytest mdsplit/tests/ -v
```

テストには以下が含まれる:

- **test_parser.py** — 見出し検出、コードブロック内スキップ、front matter 抽出、ツリー構築
- **test_decompose.py** — ファイル生成、JSON構造、フラット/ネスト対応
- **test_compose.py** — 再構成、並び順、base_level 上書き
- **test_roundtrip.py** — 分解→再構成の完全一致テスト（`doc/emax6/combined.md` 含む）

## 設計上の注意点

### パーサーの見出し判定

見出しとして認識するパターン: `^(#{1,6})\s+(.+)$`

以下の状況では見出し判定をスキップする:

- **フェンスドコードブロック内** (` ``` ` で囲まれた領域)
- **HTML `<pre>` ブロック内**

`#define` のような行は `#` の直後にスペースがないため、正規表現にマッチせず自動的に除外される。

### ファイル命名

- 形式: `NN-slug.md`（`NN` = 0埋め連番、`slug` = タイトルの ASCII スラグ化）
- 日本語タイトルは ASCII 部分のみ抽出し、全て非 ASCII の場合は `section` にフォールバック
- スラグの最大長: 40文字

### セクションファイルの内容

各セクションファイルには見出し行を含めない。見出しのテキストは JSON の `title` フィールドに保持される。ファイルには見出し行と次の見出しの間のコンテンツ（本文）のみが格納される。

## 今後の拡張予定

- 資料内部の相互参照（`<a href="#...">` 等）の整合性チェック・自動修正パーサー
- Quarto YAML メタデータのセクション別管理
- git hook 連携による更新日時・コミットハッシュの metadata 自動挿入
