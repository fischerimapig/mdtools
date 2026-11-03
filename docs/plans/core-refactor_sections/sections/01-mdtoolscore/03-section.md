
リファクタ中に master 実装との差分がいくつか見つかりました。最終的には、Markdown/Pandoc 的に自然な挙動は新仕様として採用し、共通化で caller 固有の優先順位を壊した箇所だけ修正しました。

| 領域 | 現在の仕様 |
|------|------------|
| langfilter | `lang` 属性は属性順序に依存しない |
| langfilter | `::: {lang=en} trailing` は Pandoc fenced div として扱わない |
| langfilter | code fence 内の `:::` では lang block を閉じない |
| glossary | `.glossary` class は属性順序に依存しない |
| glossary | glossary block 内 code fence の `:::` では block を閉じない |
| mdsplit | `<pre>` 内では Markdown code fence marker を追跡しない |
| mdscan | opener より短い closing fence では code fence を閉じない |
