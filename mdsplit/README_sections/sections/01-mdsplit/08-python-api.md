
```python
from pathlib import Path

# tools/ を PYTHONPATH に含める必要あり
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
