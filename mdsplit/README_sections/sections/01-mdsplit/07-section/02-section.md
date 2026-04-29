
```bash
# 1. 分解
mdtools mdsplit decompose document.md -o work/

# 2. hierarchy.json を編集:
#    "### Deep Section" を children から取り出してトップレベルの sections に移動
#    → 再構成時に ### から # に昇格

# 3. 再構成
mdtools mdsplit compose work/hierarchy.json -o restructured.md
```
