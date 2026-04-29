
`::: {.callout-note}` のような lang 属性を持たない fenced div はそのまま保持される。`::: {lang=en} trailing text` のように属性ブロックの後へ文字列が続く行は Pandoc fenced div として扱わず、通常行として保持する。
