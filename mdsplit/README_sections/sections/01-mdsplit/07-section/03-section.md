
```bash
mdtools mdsplit decompose document.md -o work/
mdtools mdsplit compose work/hierarchy.json -o roundtrip.md
diff document.md roundtrip.md  # 差分なしが期待値
```
