
| # | テスト名 | 概要 | 検証内容 |
|---|---------|------|---------|
| 35 | `test_cli_filter_from_file` | ファイル入力 | 正しくフィルタされstdoutに出力 |
| 36 | `test_cli_filter_to_output_file` | `-o` で出力先指定 | ファイルに書き込まれる |
| 37 | `test_cli_filter_can_keep_lang_fences` | `--keep-lang-fences` | 検査用にwrapperを保持 |
| 38 | `test_cli_default_lang_is_both` | `--lang` 省略 | bothモード |
| 39 | `test_cli_stdin` | stdin入力 (monkeypatch) | 正しくフィルタ |
