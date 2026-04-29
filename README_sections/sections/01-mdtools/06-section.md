
主要 Markdown 文書は `mdsplit` で section 管理します。canonical `.md` と対応する `*_sections/` は同じ変更として扱い、最後に round-trip を確認します。

```bash
mdtools mdsplit decompose README.md -o README_sections
mdtools mdsplit verify README_sections/hierarchy.json
mdtools mdsplit compose README_sections/hierarchy.json | diff - README.md
```

用語定義は `docs/glossary/defs.yaml` に置き、マーカーを含む文書は `mdtools glossary verify` で検証します。
