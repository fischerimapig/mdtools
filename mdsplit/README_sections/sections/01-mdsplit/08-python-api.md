
```python
from pathlib import Path

# mdtoolsのインストール済み環境、またはリポジトリ直下で実行
from mdsplit.decompose import decompose
from mdsplit.compose import compose
from mdsplit.schema import DocumentTree, SectionNode

# 分解
doc_tree = decompose("document.md", "output/")

# JSON の読み込み・操作
tree = DocumentTree.load("output/hierarchy.json")
for section in tree.sections:
    print(f"{section.title} ({len(section.children)} children)")

# 再構成
text = compose("output/hierarchy.json")

# base_level を変えて再構成（## 始まりに）
text = compose("output/hierarchy.json", base_level=2)
```

M1 / #26で、CLIと同じ参照ファイル存在チェックを直接利用できるようにしました。

```python
from mdsplit.verify import verify

result = verify("output/hierarchy.json")
print(result.section_count, result.missing_files)
```

API自身は表示・終了せず、欠落一覧は格納順の深さ優先、重複を保持し、preambleを末尾に含めます。判定は従来の`Path.exists()`のままで、Workspaceの厳格な原典登録検証とは分けます。読込・形式エラーは呼出側へ伝播します。
