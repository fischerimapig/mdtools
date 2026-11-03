
`mdtools.diagnostics.inspect_workspace(config_path)`は既存のload_workspace→snapshot_sourcesを呼び、登録・本文読込の成否を`workspace.sources`チェックで返す。成功時はその範囲だけpassedで、仕様内容の検査は申告しない。WorkspaceErrorを共通診断に変換し、invalid-config/missing-file等はuser/failed、unsupported-versionはunsupported、changed-inputはunknown、read-errorはtool-error/errorとする。読めないファイルのsnapshotや行列を作らず、元のpathは`workspace.path`根拠として残す。既存Workspace APIの例外・既存CLIの出力・終了コードは変更しない。

```python
from mdtools.diagnostics import inspect_workspace
from mdtools.core.diagnostics import render_json, render_text

report = inspect_workspace("docs/spec/examples/cancellation/mdtools.toml")
print(render_text(report), end="")
print(render_json(report), end="")
```

実際に位置付き診断を作る呼出側は、snapshotとSourceSpanを渡す。以下は表示の例であり、衝突検出器を実行した結果ではない。

```python
from mdtools.core.diagnostics import (
    Diagnostic, DiagnosticLocation, DiagnosticReport, Evidence, RelatedLocation,
)
from mdtools.workspace import load_workspace, snapshot_sources

sources = snapshot_sources(load_workspace("docs/spec/examples/cancellation/mdtools.toml"))
allow, deny, guidance = sources
report = DiagnosticReport((Diagnostic(
    "example.conflict", "warning", "user", "両原稿を参照する表示例😀",
    DiagnosticLocation("original", allow.span(0, 0)),
    (RelatedLocation("関連原稿", DiagnosticLocation("original", deny.span(0, 0)), "REQ-CANCEL-DENY"),),
    "REQ-CANCEL-ALLOW", (Evidence("example.assumption", "表示例。意味検査は未実施"),),
),), sources=sources)
print(render_text(report), end="")
print(render_json(report), end="")
```
