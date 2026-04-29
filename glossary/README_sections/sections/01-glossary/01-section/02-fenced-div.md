
```markdown
::: {.glossary filter=term}
:::
```

`filter=term|const|symbol` で種別絞り込み、`format=table|dl` で Markdown 表 / 定義リストを切り替え (既定 table)。
`.glossary` は属性順序に依存しないため、`::: {.note .glossary filter=term}` のような複数クラス付き div も glossary block として扱う。
