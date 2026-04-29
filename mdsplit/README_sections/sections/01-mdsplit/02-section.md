
最初に `--help` を確認し、利用可能なサブコマンドとオプションを把握してください。

```bash
mdsplit --help
```

リポジトリルートから実行する場合:

```bash
# 分解: Markdown → セクションファイル + hierarchy.json
mdsplit decompose doc/emax6/combined.md -o output/

# 再構成: hierarchy.json + セクションファイル → Markdown
mdsplit compose output/hierarchy.json -o reconstructed.md

# 検証: 参照ファイルの存在チェック
mdsplit verify output/hierarchy.json
```

```mermaid
flowchart LR
    doc["canonical Markdown/QMD"]
    decompose["mdsplit decompose"]
    hierarchy["hierarchy.json"]
    sections["section files"]
    verify["mdsplit verify"]
    compose["mdsplit compose"]
    rebuilt["rebuilt Markdown/QMD"]

    doc --> decompose
    decompose --> hierarchy
    decompose --> sections
    hierarchy --> verify
    sections --> verify
    hierarchy --> compose
    sections --> compose
    compose --> rebuilt
```
