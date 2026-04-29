
まず `mdtools rewrite --help` でサブコマンドと主要オプションを確認してください。個別コマンド `mdhtml-rewrite` も同じ機能を呼び出す互換入口です。

```bash
mdtools rewrite --help
mdhtml-rewrite --help
```

```mermaid
flowchart LR
    eps["EPS/PS/PDF assets"]
    convert["mdtools rewrite convert"]
    htmlmd["HTML-ish Markdown"]
    inventory["mdtools rewrite inventory"]
    invjson["inventory.json"]
    rewrite["mdtools rewrite rewrite"]
    qmd["Quarto-friendly QMD/MD"]

    eps --> convert
    htmlmd --> inventory --> invjson --> rewrite
    htmlmd --> rewrite --> qmd
```
