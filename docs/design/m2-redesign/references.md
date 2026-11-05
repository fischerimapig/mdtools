# 参照資料と取り入れた原理

確認日2026-11-04。markdown-it-pythonは[markdown-it-py](https://github.com/executablebooks/markdown-it-py)を指す。実際に読んだrevisionは **6f586542653a56d2ee8549a0dccfaa6ba5ebe14a**。PDFに記載された4.2.0の実験結果を今回の実測として転記していない。

[Design principles](https://markdown-it-py.readthedocs.io/en/latest/architecture.html) のcore/block/inlineの状態分離と処理順を参考にした。Token互換ではなく、先行Blockの結果を後段が使う責務を採った。

|参照ファイル（上記SHA）|読んで採った原理|今回採らなかったもの|
|---|---|---|
|markdown_it/parser_core.py|Block後にInlineを適用|normalize、linkify、smartquotes等の変換|
|markdown_it/parser_block.py、rules_block/paragraph.py|優先順位とparagraph終端、段階別state|Ruler/動的plugin、list/quote全実装|
|rules_block/fence.py|記号・開始長・閉じ長・末尾空白、literalの所有|本文deindent/レンダリング、無診断の自動補完|
|rules_block/html_block.py|HTML/commentの開始分類と終端|HTML全種別の意味・renderer|
|rules_block/reference.py|Block段階で定義を集め、後段に表を渡す|多行定義全文法、URL正規化|
|markdown_it/parser_inline.py、rules_inline/backticks.py|leaf上限、区切り索引、同じ長さのcode span|Token公開API、emphasis等の第二規則列|
|rules_inline/link.py、image.py、html_inline.py|destination/title/引用属性をそれぞれ局所認識|リンク文字列レンダリング、URL安全性ポリシー、全HTML適合|
|helpers/parse_link_title.py、parse_link_destination.py|titleの3区切りとescape、destinationの括弧所有|decode済み文字列から位置を再発見する処理|

固定revisionの[ソース一覧](https://github.com/executablebooks/markdown-it-py/tree/6f586542653a56d2ee8549a0dccfaa6ba5ebe14a/markdown_it)と[LICENSE](https://github.com/executablebooks/markdown-it-py/blob/6f586542653a56d2ee8549a0dccfaa6ba5ebe14a/LICENSE)を確認。MIT、Copyright (c) 2020 ExecutableBookProject。第三者実装ファイルのvendoringやToken/Rulerの転載はしていない。独自モデルと限定した認識器を作り、参照した解析原理・範囲をここに表示する。今後コードを転載・翻案する場合は同MIT表示を保持する。

[CommonMark 0.31.2 §3.1](https://spec.commonmark.org/0.31.2/#precedence) と [解析戦略](https://spec.commonmark.org/0.31.2/#a-parsing-strategy) のBlock優先・参照定義収集後のInlineという区別を検討材料にした。原稿契約としてCommonMark全体を採用したわけではない。ケース原稿は既存mdtools fixtureと独自再現で、CommonMarkの全例をコーパスへ転載していない。

review-1.pdfの全11ページを確認した。構造/意味の分離、元位置、失敗状態、#51回帰の役割を継承し、外部engine導入と本番切替の時期は最新依頼へ読み替えた。PDFのSHA-256は実行環境記録に保存する。元PDFはmaster側のユーザー未追跡ファイルのまま保持した。

mdtools内で再利用した実装は既存core.source（snapshot/行列）とcore.pandoc.tokenize_attrs（汎用属性lexer）。spec/_markdown.pyはtest専用旧adapterでのみ読み、新parserの結果生成・fallbackに使用していない。
