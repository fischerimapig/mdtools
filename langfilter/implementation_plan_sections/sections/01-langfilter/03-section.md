
```
langfilter/
├── __init__.py        # モジュール docstring
├── __main__.py        # エントリポイント → cli.main()
├── cli.py             # argparse: filter サブコマンド、core.io 経由の I/O
├── filter.py          # filter_lang() 純粋関数
└── tests/
    ├── __init__.py
    ├── README.md      # テストプラン
    └── test_filter.py # 挙動仕様テスト

mdtools/core/
├── io.py              # stdin/stdout と UTF-8 text I/O
├── mdscan.py          # code fence 状態追跡
└── pandoc.py          # DIV_OPEN_RE / FENCE_CLOSE_RE / parse_attrs
```
