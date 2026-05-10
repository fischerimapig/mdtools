
日英併記の Markdown ソースから、指定言語のブロックのみを残すフィルタツール。

Pandoc/Quarto 互換の fenced div 記法 (`::: {lang=XX}`) を認識し、
指定言語以外のブロックを除去する。対象言語の fenced div wrapper 行も既定で除去するため、配布用 Markdown に `lang=...` タグは残らない。属性順序には依存せず、テーブル・コードブロック・図版などの言語タグを持たないコンテンツはすべて保持される。

```mermaid
stateDiagram-v2
    [*] --> Normal
    Normal --> CodeFence: ``` or ~~~
    CodeFence --> Normal: matching fence
    Normal --> LangBlock: div attrs include lang
    LangBlock --> Normal: bare :::
    LangBlock --> LangBlock: code fence content
    Normal --> Normal: shared line
```
