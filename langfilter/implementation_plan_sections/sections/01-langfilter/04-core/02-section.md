
`langfilter` 自身は lang 専用の正規表現を持たない。`mdtools.core.pandoc.DIV_OPEN_RE` で fenced div の属性を取り出し、`parse_attrs()` の `kv["lang"]` を見る。
