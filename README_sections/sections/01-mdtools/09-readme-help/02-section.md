
1. CLI の `epilog` を変更した場合、対応する README の「主要コマンド例（--help と同期）」節を同時に更新したか。
2. README 側で主要コマンド例を変更した場合、対応する CLI の `epilog` を同時に更新したか。
3. `--help` は短い実行例に留め、背景説明や長文の運用ノウハウは README に寄せたか。
4. 仕上げに次を実行し、差分が意図通りか確認したか。

```bash
mdsplit --help
langfilter --help
mdhtml-rewrite --help
glossary --help
git diff -- README.md mdsplit/README.md mdhtml_rewrite/README.md langfilter/README.md glossary/README.md \
  mdsplit/cli.py mdhtml_rewrite/cli.py langfilter/cli.py glossary/cli.py
```
