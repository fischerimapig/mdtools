::: {.requirement #REQ-NORMAL spec-version=1 status=active}
支払い済みなら処理を許可する。

```mdspec
{
  "version": 1,
  "id": "MODEL-NORMAL",
  "kind": "constraint",
  "uses": ["paid"],
  "when": "paid",
  "must": "paid == true"
}
```
:::
