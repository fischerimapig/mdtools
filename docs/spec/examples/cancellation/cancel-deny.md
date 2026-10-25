# キャンセル禁止

::: {.requirement #REQ-CANCEL-DENY spec-version=1 status=draft refs="REQ-CANCEL-ALLOW"}
支払い済みなら、キャンセルを禁止する。

```mdspec
{
  "version": 1,
  "id": "MODEL-CANCEL-DENY",
  "kind": "constraint",
  "uses": ["paid", "cancel_allowed"],
  "when": "paid",
  "must": "cancel_allowed == false"
}
```
:::
