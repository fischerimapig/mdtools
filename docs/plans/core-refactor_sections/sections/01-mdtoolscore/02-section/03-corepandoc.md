
`mdtools.core.pandoc` は Pandoc/Quarto 由来の構文を共有します。

- `CODE_FENCE_RE`
- `FENCE_CLOSE_RE`
- `DIV_OPEN_RE`
- `BRACKETED_SPAN_RE`
- `parse_attrs()`
- `PandocAttrs`

`parse_attrs()` は class と key-value を順序に依存せず抽出します。そのため `::: {.note lang=en}` や `::: {.note .glossary filter=term}` のような属性順序でも、`langfilter` と `glossary` は意図した属性を扱えます。
