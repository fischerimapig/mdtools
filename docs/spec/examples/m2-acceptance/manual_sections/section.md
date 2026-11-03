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
