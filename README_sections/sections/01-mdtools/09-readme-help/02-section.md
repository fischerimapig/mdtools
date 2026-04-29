
1. README 側の「使い方」または「主要コマンド例」を変更し、CLI の `epilog` が同じ意図を短く参照しているか。
2. CLI の `epilog` を変更した場合、対応する README 節が原典として読める状態になっているか。
3. `--help` は短い実行例と README 参照先に留め、背景説明や長文の運用ノウハウは README に寄せたか。
4. 仕上げに次を実行し、差分が意図通りか確認したか。

```bash
mdtools --help
mdtools mdsplit --help
mdtools langfilter --help
mdtools rewrite --help
mdtools glossary --help
git diff -- README.md mdsplit/README.md mdhtml_rewrite/README.md langfilter/README.md glossary/README.md \
  mdtools/main.py mdsplit/cli.py mdhtml_rewrite/cli.py langfilter/cli.py glossary/cli.py
```
