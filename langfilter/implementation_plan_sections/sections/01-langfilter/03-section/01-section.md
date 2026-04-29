
| モジュール | 責務 |
|-----------|------|
| `filter.py` | 純粋関数 `filter_lang(text, lang) -> str`。I/O なし。core.mdscan と core.pandoc を使う |
| `cli.py` | 引数解析、core.io 経由の入力/出力、filter_lang() 呼び出し |
