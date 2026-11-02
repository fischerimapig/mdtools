# 受け入れ例
説明中の `<pre>` はHTMLブロックを開始しない。

## 状態表示
::: {.requirement #REQ-SECTION spec-version=1 refs="REQ-DETAIL"}
::: {lang=ja}
状態を表示する。📚
:::
::: {lang=en}
Show the state.
:::
```mdspec
{"version":1,"id":"MODEL-SECTION","kind":"constraint","uses":["paid","initial"],"when":"paid","must":"initial == \"new\""}
```
:::

## 案内
::: {.requirement #REQ-DETAIL spec-version=1 refs="REQ-DETAIL REQ-SECTION"}
利用者へ案内する。
:::
