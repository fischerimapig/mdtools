
```bash
uv run pytest mdsplit/tests/ -v
```

テストには以下が含まれる:

- **test_parser.py** — 見出し検出、コードブロック内スキップ、front matter 抽出、ツリー構築
- **test_decompose.py** — ファイル生成、JSON構造、フラット/ネスト対応
- **test_compose.py** — 再構成、並び順、base_level 上書き
- **test_roundtrip.py** — 分解→再構成の完全一致テスト（`doc/emax6/combined.md` 含む）
