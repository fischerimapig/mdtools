
`mdtools.core.io` は text/JSON/YAML の共通 I/O を提供します。CLI の stdin/stdout 処理、JSON report の読み書き、glossary 定義ファイルの読み込みに使います。

主な API:

- `read_text_or_stdin(path)`
- `write_text_or_stdout(text, path)`
- `read_json(path)` / `write_json(path, obj)`
- `dumps_json(obj)`
- `read_structured_file(path)`
- `StructuredFileError`
