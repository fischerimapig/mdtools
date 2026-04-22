# langfilter 実装計画

## 背景

IMAX2 コアアーキテクチャ文書化（Phase 0）の基盤ツールとして、
日英併記 Markdown から単一言語版を生成する langfilter を作成した。

要件定義: `docs/IMAX2/core/PHASE0-INFRASTRUCTURE.md` Section 1
受け入れ条件: 同ファイル末尾「Phase 0 の受け入れ条件」langfilter 項

## 設計判断

| 判断 | 決定 | 理由 |
|------|------|------|
| keep 時のマーカー | 保持 | Quarto で lang 属性によるスタイリングが将来可能 |
| 除去後の空行 | そのまま保持 | シンプルで予測可能。連続空行は Markdown として無害 |
| `both` モード | 入力をそのまま返す | 非破壊的なデフォルト |
| `:::` の閉じ判定 | 状態機械で追跡 | 自分が開いた lang ブロックのみ閉じる |
| 非 lang fenced div | パススルー | `::: {.note}` 等は触らない |
| コードフェンス内の `:::` | 無視 | コードフェンス状態を追跡 |
| Phase 0 非目標 | テーブル列単位の言語分離、図中ラベル翻訳 | PHASE0 文書で明記 |

## アーキテクチャ

```
langfilter/
├── __init__.py        # モジュール docstring
├── __main__.py        # エントリポイント → cli.main()
├── cli.py             # argparse: filter サブコマンド、I/O 処理
├── filter.py          # filter_lang() 純粋関数、状態機械
└── tests/
    ├── __init__.py
    ├── README.md      # テストプラン
    └── test_filter.py # 全41テスト
```

### モジュール責務

| モジュール | 責務 |
|-----------|------|
| `filter.py` | 純粋関数 `filter_lang(text, lang) -> str`。I/O なし。全ロジックはここ |
| `cli.py` | 引数解析、ファイル/stdin 読み込み、stdout/ファイル書き出し。filter_lang() を呼ぶだけ |

## アルゴリズム: 行単位の状態機械

### 状態

- `NORMAL` — lang ブロック外、コードフェンス外
- `IN_CODE_FENCE` — `` ` `` or `~` コードフェンス内
- `IN_LANG_BLOCK` — `::: {lang=XX}` ブロック内

### 正規表現

```python
LANG_OPEN_RE  = re.compile(r'^:::\s*\{\s*lang\s*=\s*"?(\w+)"?\s*\}')
LANG_CLOSE_RE = re.compile(r'^:::\s*$')
CODE_FENCE_RE = re.compile(r'^(`{3,}|~{3,})')
```

### 遷移ロジック

```
for each line:
  NORMAL:
    code fence? → IN_CODE_FENCE, emit
    lang open?  → IN_LANG_BLOCK
      match lang? → emit (keep with markers)
      else        → skip (remove)
    otherwise   → emit

  IN_CODE_FENCE:
    always emit
    closing fence? → NORMAL

  IN_LANG_BLOCK:
    lang close? → NORMAL
      match lang? → emit closing :::
      else        → skip
    otherwise:
      match lang? → emit content
      else        → skip
```

### エッジケース

| ケース | 処理 |
|--------|------|
| EOF 前の未閉じ lang ブロック | ブロック内として扱い続ける（クラッシュしない） |
| lang ブロック内のコードフェンス | コードフェンス追跡しない（`:::` と `` ` `` は混同しない） |
| 非 lang fenced div | LANG_OPEN_RE にマッチしないため NORMAL で素通り |
| NORMAL 状態の裸の `:::` | そのまま出力 |
| 末尾改行の有無 | 入力の末尾改行状態を保存・復元 |

## テスト戦略

t-wada 式 TDD に従い、全41テストを先に定義してから実装した。
テストプランの詳細は `tests/README.md` を参照。

### テストカテゴリ

| Phase | 件数 | 内容 |
|-------|------|------|
| 1. 退化ケース | 3 | 空入力、lang ブロックなし、both モード |
| 2. 単一ブロック | 4 | keep/remove の基本動作 |
| 3. 複数ブロック | 3 | en/ja ペアのフィルタリング |
| 4. 共有コンテンツ | 4 | テーブル、コード、画像、HTML コメントの保存 |
| 5. コードフェンス | 4 | コードフェンス内の `:::` 無視、lang ブロック内のコードフェンス |
| 6. 構文バリエーション | 4 | 空白、引用符、brace の位置 |
| 7. 非 lang div | 3 | `::: {.note}` 等のパススルー |
| 8. エッジケース | 9 | 空ブロック、未閉じ、連続、unknown lang、改行 |
| 9. CLI 統合 | 4 | ファイル I/O、stdin、デフォルト lang |
| 10. 全体統合 | 3 | 実文書相当の入力で en/ja/both |

## 検証

```bash
cd tools/mdtools
.venv/bin/pytest langfilter/tests/ -v
```

全41テスト PASSED (2026-03-29 確認)。
