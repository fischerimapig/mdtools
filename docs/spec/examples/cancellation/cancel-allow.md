# キャンセル許可

::: {.requirement #REQ-CANCEL-ALLOW spec-version=1 status=draft}
::: {lang=ja}
支払い済みで未発送なら、キャンセルを許可する。
:::

::: {lang=en}
Allow cancellation when payment is complete and the order has not shipped.
:::

```mdspec
{
  "version": 1,
  "id": "MODEL-CANCEL-ALLOW",
  "kind": "constraint",
  "uses": ["paid", "shipped", "cancel_allowed"],
  "when": "paid and not shipped",
  "must": "cancel_allowed == true"
}
```
:::
