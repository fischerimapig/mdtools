
大きな Markdown/QMD 文書をセクション単位のファイルに分解し、`hierarchy.json` で階層を管理する。
JSON を編集してセクションの順序や見出しレベルを変更してから再構成できる。

```bash
# 分解: document.md → work/ 以下のセクションファイル群
mdtools mdsplit decompose document.md -o work/

# 再構成: セクションファイル群 → 単一ファイル
mdtools mdsplit compose work/hierarchy.json -o reconstructed.md

# 参照ファイルの存在チェック
mdtools mdsplit verify work/hierarchy.json

# フラット構造で分解（ネスト無し）
mdtools mdsplit decompose document.md -o work/ --flat
```

詳細は [mdsplit/README.md](mdsplit/README.md) を参照。
