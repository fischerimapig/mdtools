
初回coreリファクタ時の検証結果は次の通りです。

```bash
uv run pytest -q
```

結果:

```text
190 passed, 1 skipped
```

追加された core テストは以下を守ります。

- `core.io`: stdin/stdout、UTF-8、JSON/YAML、エラー処理
- `core.mdscan`: code fence の開閉、短い closing fence、trailing newline 保持
- `core.pandoc`: 属性順序、class/key-value、fenced div と bracketed span
