
推奨入口は `mdtools <tool>` の統合コマンドです。個別コマンドの `mdsplit` / `langfilter` / `mdhtml-rewrite` / `glossary` も互換用ショートカットとして同じ機能を呼び出せます。
まずは `mdtools <tool> --help` でオプション定義と最小実行例を確認し、詳細は各 README の該当節を参照してください。

```bash
mdtools mdsplit decompose document.md -o work/
# 上と同じ互換入口
mdsplit decompose document.md -o work/
```
