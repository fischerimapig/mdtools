# 原稿 → 構造 → 要件概要の短いトレース

元UTF-8 byteの半開範囲。全原稿・旧観測・新期待・全node/属性/Inline/SourceSpan/rawは[comparison-results.json](comparison-results.json)に保存した。通常のdump入口は[README](../../../experiments/document_parser/README.md)。JSONのcase_idで検索できる。本文はレンダリングしない。

## 正常な小原稿：C-normal

~~~markdown
::: {.requirement #REQ-A spec-version=1}
本文
:::
~~~

BlockはDiv [0,52)、header [0,41)、body [41,48)、closing [48,52)。子paragraph [41,48)をInlineに渡すとtextになる。projectionはclass属性を選びID=REQ-A、bodyの原文「本文\n」を返す。構造status=complete、JSON/参照/式/要件検証はnot-run。旧公開parserの要件IDと限定projectionも一致する。

## #51：I-51-link-title

~~~markdown
[説明](https://example.com "<!--")

::: {.requirement #REQ-A spec-version=1}
本文
:::
~~~

Blockはparagraph [0,37)、blank [37,38)、Div [38,90)。Inlineがlink [0,36)と改行textを作り、titleは「<!--」のまま。既に別BlockのDivを消す経路はない。projectionのREQ-A [38,90)、本文 [79,86)は入力から独立に固定した期待値と一致する。旧公開parser/旧scannerの候補は0件だった。

|case ID|旧候補ID|新候補ID|新Div原文範囲|
|---|---|---|---|
|I-51-link-title|[]|REQ-A|[38,90)|
|I-51-image-title|[]|REQ-A|[49,101)|
|I-51-reference-title|[]|REQ-A|[35,87)|

参照定義の例はBlockがtitleを含む定義範囲を収集する。Inlineより前に表が完成し、後方定義にも別の全文再走査を行わない。

## 本物のコメント：C-literal-comment

先頭「<!--\n」、C-normal原稿、「-->\n」の61 byte。Blockはhtml_comment [0,61)だけで子Divを作らない。Inline対象ではなく、旧・新候補IDは共に[]。未閉鎖の真のblock commentもEOFまでliteralとして保持する。普通の例示コメントを仕様エラーへ昇格しない。

## 不正headerと未閉鎖：C-malformed-header / C-unclosed-div

C-malformed-headerは開始行の閉じbraceの後に「 trailing」を付けた61 byte。Div [0,61)、header [0,50)、body [50,57)、closing [57,61)。属性列は残り、header_valid=false、closure=closed、構造partial。projectionは未検証REQ-A候補と本文を残す。旧公開parserは拒否しているため、比較対象は旧scannerの汎用候補であり、受理の互換とは主張しない。

C-unclosed-divは正常原稿の最後の「:::\n」を除いた48 byte。Div [0,48)、header_valid=true、closure=eof、body [41,48)。notice=block.unclosed-div、構造partial。次snapshotの閉じ記号を借りない。通常code/commentのeof completeとは異なる。

## 未対応・上限・未承認差分

comparison-results.jsonのfailure_tracesには、node上限と複数行参照定義のunsupported原文・notice・coverageを保存した。双方partialで、正常0件とは区別する。

I-pending-paragraph-commentは旧候補[]に対し新REQ-A [11,63)、I-pending-div-tail-commentは旧候補[]に対し新REQ-A [26,78)。前者complete、後者header不正のpartial。新観測を承認済み期待とはしない。この2件の成功テストは作らず、結果表でunapproved-observationと表示する。HTML引用が独立Blockを跨がない判断も本番導入前にR1で確認する。
