# glossary

用語 (term) と定数 (constant) の参照を定義ファイルで一元管理するツール。
Markdown 本文に埋め込んだマーカーを検出し、定義ファイルから解決して置換する。
登録済みエントリの一覧出力・未定義参照の検証も行える。

Pandoc/Quarto の bracketed span / fenced div 記法に準拠しているため、
`langfilter` などの他ツールと同じパイプラインで自然に組み合わせられる。

## 記法

### インラインマーカー (bracketed span)

| 用途 | 記法 | 置換結果 (lang=en の例) |
|------|------|------------------------|
| 用語 (名称) | `[]{.term id=unit}` | `Processing Unit` |
| 用語 (定義文) | `[]{.term id=unit field=description}` | `One compute element in...` |
| 用語 (略称) | `[]{.term id=lmm field=abbr}` | `LMM` |
| 定数 (値) | `[]{.const id=EMAX_WIDTH}` | `4` |
| 記号 | `[]{.symbol id=D}` | `D` |
| 記号 (RTL マクロ) | `[]{.symbol id=D field=rtl_macro}` | `EMAX_DEPTH` |

`[]` 内にテキストを書くと Pandoc 互換でそのテキストが保持される (ラベル上書き)。

### 一覧ブロック (fenced div)

```markdown
::: {.glossary filter=term}
:::
```

`filter=term|const|symbol` で種別絞り込み、`format=table|dl` で Markdown 表 / 定義リストを切り替え (既定 table)。

## 使い方

まず `--help` でオプションと最小例を確認。

```bash
glossary --help
```

## 主要コマンド例（`--help` の epilog と同期）

```bash
# 最小例: 英語版を解決
glossary resolve manuscript.md --lang en -f defs.json -o out.md

# 一覧 (テキスト表、既定)
glossary list -f defs.json

# 未定義参照の検証 (CI 用)
glossary verify manuscript.md -f defs.json

# langfilter と組み合わせた言語別パイプライン
langfilter filter --lang en in.qmd | \
  glossary resolve --lang en -f defs.json > out.en.md
langfilter filter --lang ja in.qmd | \
  glossary resolve --lang ja -f defs.json > out.ja.md

# 複数の定義ファイルを合成 (JSON + YAML 混在可)
glossary resolve in.md --lang ja -f terms.json -f consts.yaml

# JSON 一覧
glossary list -f defs.json --kind term --format json
```

## CLI リファレンス

```
glossary resolve [INPUT] --lang {en|ja} -f PATH [-f PATH ...] [-o OUT] [--on-missing {error|warn|keep}]
glossary list -f PATH [-f PATH ...] [--kind {term|const|symbol}] [--format {text|json}] [-o OUT]
glossary verify [INPUT] -f PATH [-f PATH ...]
```

| オプション | 説明 | デフォルト |
|------------|------|-----------|
| `INPUT` | 入力 Markdown/QMD。`-` または省略で stdin | stdin |
| `--lang` | 解決する言語 (`resolve` のみ必須) | — |
| `-f`, `--defs` | 定義ファイル (JSON/YAML)。複数回指定で合成 | — |
| `-o`, `--output` | 出力ファイル | stdout |
| `--on-missing` | 未定義 ID への対応 (`error`/`warn`/`keep`) | `error` |
| `--kind` | `list` の種別絞り込み | (全種別) |
| `--format` | `list` の出力 (`text`/`json`) | `text` |

## スキーマ

```yaml
# defs.yaml (同等の JSON でも可)
entries:
  - id: unit                # 必須: 一意の識別子
    kind: term              # 必須: term | const | symbol
    names:                  # term: 言語別名称
      en: "Processing Unit"
      ja: "プロセッシングユニット"
    abbr: "PU"              # term: 略称 (field=abbr)
    aliases:                # 参考情報 (検索等の用途, 現状は置換には非使用)
      en: [PU]
      ja: [ユニット]
    description:
      en: "One compute element in the D x 4 array."
      ja: "D x 4 アレイを構成する計算要素。"
    source: "sections/01-overview/01-array-topology.md"

  - id: EMAX_WIDTH
    kind: const
    value: 4                # const: 値 (数値・文字列・式の文字列表現)
    description:
      en: "Number of columns per row."
      ja: "1 行あたりの列数。"
    source: "legacy/core/common.vh:43"

  - id: D
    kind: symbol
    rtl_macro: EMAX_DEPTH   # symbol: 外部参照 (field=rtl_macro で展開)
    description:
      en: "Number of logical rows in the unit array."
      ja: "ユニットアレイの論理行数。"
```

- `-f` は複数回指定可。後勝ちでマージし、id 衝突時は警告を stderr に出す。
- `source` と `aliases` は任意。
- YAML 入力は `pyyaml` が必要 (optional dep)。JSON のみ使う場合は追加依存不要。

## 動作仕様

### コードフェンスとの相互作用

` ``` ` / `~~~` で囲まれた行内のマーカーは置換対象外 (原文のまま保持)。

### langfilter との関係

`::: {lang=en}` / `::: {lang=ja}` は glossary からは不可視 (スルー)。
`langfilter` → `glossary` の後段方式を推奨する。

### 未定義 ID の扱い

`resolve` は既定で exit 1 + エラー出力。`--on-missing warn` なら警告のみ、
`--on-missing keep` で静かにマーカーを残す。`verify` は未定義を全件列挙して exit 1。

### クラスと kind のミスマッチ

`[]{.term id=EMAX_WIDTH}` のようにクラスとエントリの `kind` が食い違う場合は
`resolve` が `ResolveError` で失敗する。参照側のタイプミスを早期に検出するため。

## テスト

```bash
uv run python -m pytest glossary/tests/ -v
```

## 要件

- Python 3.13+
- JSON のみ使う場合は外部依存なし
- YAML 定義ファイルを使う場合は `pyyaml` (optional dep: `pip install 'mdtools[yaml]'`)
