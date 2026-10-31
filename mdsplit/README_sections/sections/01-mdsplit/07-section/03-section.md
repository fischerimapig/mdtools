
```bash
mdtools mdsplit decompose document.md -o work/
mdtools mdsplit compose work/hierarchy.json -o roundtrip.md
diff document.md roundtrip.md  # 差分なしが期待値
```

本文の完全一致だけでは、見出しが前のセクション本文へ取り込まれる不具合を検出できない。構造も保存したい場合は、再分解した hierarchy の見出し件数・タイトル・順序・親子関係・基準レベルを、正しい既存 hierarchy と比較する。自動生成されるファイル名は構造比較の対象にしない。`verify` は参照先の存在チェックであり、この構造比較を代替しない。

このリポジトリのCIでは、README、mdsplit README、仕様記述契約、coreリファクタ実施記録について、`test_document_structure.py` が文字列一致と見出し構造の両方を検証する。
