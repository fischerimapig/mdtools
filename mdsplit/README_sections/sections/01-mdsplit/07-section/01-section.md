
```bash
# 1. 分解
mdtools mdsplit decompose document.md -o work/

# 2. hierarchy.json を編集してセクションの order を変更
#    例: "Background" の order を 0 → 2 に変更

# 3. 再構成
mdtools mdsplit compose work/hierarchy.json -o reordered.md
```
