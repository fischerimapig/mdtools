# Document先行試作の設計と確認範囲

実装入口は [parse_document](../../../experiments/document_parser/parser.py)、レビュー用の意味付けは [summarize_requirements](../../../experiments/document_parser/projection.py)。現行仕様契約を置換せず、profileを mdtools-document-prototype-v0 / model_version=0 として隔離する。

review-1.pdf（11ページ、草案v0.1、2026-11-03）のP1〜P4を内製する。PDFの外部markdown-it-py採用案は今回採用せず、構造と意味を分離する責務を継承する。P5はLocalAnalysis生成ではなく候補概要、P6〜P8のresolver/IR/製品CLIは現行のまま。PDF記載の同梱design.md・fixtures等は今回の入力に存在せず未参照。

## 一方向の処理

~~~mermaid
flowchart LR
  S["SourceSnapshot 原文"] --> X["SourceIndex 元byte↔CP/行列"]
  X --> B["Block: Div・literal・段落・参照定義"]
  B --> I["Inline: 所有leafと参照lookup"]
  I --> D["DocumentParse 構造・closure・coverage・notice"]
  D --> P["ReviewSummary ID候補・本文・lang・mdspec範囲"]
  D --> V["dump / trace"]
  P --> V
  O["固定M2の保存観測値"] --> C["test専用比較"]
  P --> C
~~~

|段階|実ファイル/関数|入力・状態・出力|失敗と責務|
|---|---|---|---|
|入力|__main__.main / core.source.SourceSnapshot|ファイルを一度だけ読みexact UTF-8 snapshotを作る|I/O/UTF-8失敗は入力失敗。空原稿へ変換しない|
|索引|model.SourceIndex|元CP境界→UTF-8 byte配列と物理行範囲|改行正規化なし。元sourceを共有。byte内/CRLF内SourceSpan変換を拒否|
|Block|blocks.parse_blocks|行cursor、明示stack、node数、coverage、全参照定義出現|header不正情報を残す。literalは実閉じ/EOFまで所有。要件固有判定なし|
|参照|links.parse_reference_definition / build_reference_lookup|単一行定義からlabel/destination/title範囲。全出現を保持しlookupを一度構築|複数行候補はunsupported。後方定義も同じ表を利用|
|Inline|inline.parse_inlines|確定leafのowner、delimiter/bracket索引、共有lookup、局所予算|owner外へ状態を流さず、Blockを変更しない。上限はcomplete=False|
|検証/結果|parser.parse_document / model.validate_document|Block→Inline→不変tuple。profile/status/coverage/noticeとsnapshotを持つ|親子包含、兄弟順、header/body/closing、coverage分割、recognized領域の所有を検証|
|projection|projection.summarize_requirements / summary_dict|汎用Div属性と指定範囲のsliceのみ|.requirement/lang/mdspecをここで解釈。JSON・ID規約・式・参照検証はnot-run|
|レビュー|dump.document_dict / tests.report|元byteと行列の構造dump、限定候補比較|SpecIRではない。期待値を新parserから再生成しない|

Inlineへの入力はparagraph/headingのbodyだけ。参照リンクのtarget/titleは別のdefinition範囲を指せるが、usage spanとdelimiterの先読みはowner内に限定する。HTML引用も独立したblank/Div/headingを越えない。同一leaf内の複数行引用は扱う。BlockへInlineの引用追跡を重複実装しない。

## データの意味

- ByteRangeは元UTF-8の半開範囲。source識別はDocumentが共有するSourceSnapshot.ref（URI＋SHA-256）に束縛する。CPカーソル、byte、行列は別の単位。node単独の範囲を別Documentへ流用しない。
- SourceIndexは原文を複製しない。CP→byteは配列参照、byte→CPは二分探索、行列は既存SourceSnapshotを使う。元のCRLFは2 byteのまま。CR/LF間はbyte境界でもSourceSpanにできないため丸めない。
- Nodeはkind/span/body/header/closing/children/attributes/info/info_span/marker/closure/valid/inlinesを持つ。本文は範囲で保持する。validはheader/infoの構文情報で、closureや要件妥当性とは別。
- attributesは全出現tuple。重複をdictへ潰さず、invalid tokenも残す。汎用lexerは既存core.pandoc.tokenize_attrsを再利用する。valueと元value_span（引用符を含み得る）を区別する。
- Inlineのspanはdelimiterを含む。destination/titleは区切りを除く元範囲。escape/entityの意味上のdecodeやURL検証はしない。空destinationはゼロ幅。
- ReferenceDefinitionは定義の原文範囲、正規化label、destination/title範囲。ASCII space/tab/CR/LFを縮約後Unicode casefold、最初の定義を解決に使い全出現も保持する。CommonMark/Pandocとの全面一致は未確認。
- 一つのDocumentParseだけを維持し、別CoreDocumentの木や本文を複製しない。Inline付与時の一時的なnode差替えは原文/不変leafを共有する。projectionとtraceの文字列コピーはレビュー出力時のみ。

## 状態の区別

|事象|status / closure / coverage|projectionでの意味|
|---|---|---|
|空文書・要件のない通常文|complete / recognized（空なら範囲0個）|候補0件、意味検査not-run|
|通常のfence/comment/preがEOF終端|complete / eof / recognized|内部の要件風文字列を抽出しない。仕様エラーへ昇格しない|
|不正generic header・未閉鎖Div|partial / closedまたはeof / recognized|候補・属性・本文を保持。要件診断の写像はR5|
|要件ID欠落・壊れたJSON|構造上成立すればcomplete|未検証候補。既存parserの拒否/partialとは責務が異なる|
|未知構造・複数行参照候補|partial / unsupported範囲＋notice|所属を推測して正常要件に昇格しない|
|node/depth/Inline上限|partial / limitまたは局所未完了 / unparsed|既知部分と元原稿・理由を残す|
|未知profile・byte上限|rejected / unparsed|0件成功ではない|
|engine例外・位置不変条件違反|failed / unparsed|理由とsnapshot、検証済みBlock部分を保持。不正な座標の木は返さない|

coverageは元byteの連続分割で、解釈した構文範囲を表す。意味検査やM2 completeとは独立。recognizedな範囲はnodeまたはcontainer header/closingに所有される。部分領域を正常として消さない。複数snapshotを連結した救済はない。

## 対応範囲と残る判断

|領域|試作の実装|限界・現行契約との差・後続判断|
|---|---|---|
|本文/見出し|段落、blank、ATX/Setext境界|見出しの表示ASTやレンダリングは提供しない|
|code fence|backtick/tilde、記号と長さ、同記号かつ十分長く末尾空白のみ閉じ|通常のbacktick info内backtickも候補として保持しpartial。旧版の通常prose判定との差をR1で決める|
|汎用Div|3コロン、ネスト、全属性、brace不足/末尾文字/重複/不正保持|4コロンはinvalid候補、4コロン閉じは親を閉じない。汎用DivをPandoc全仕様へ拡張するかはR1|
|front matter|先頭---と行頭---/...（後続space/tab可）の閉じた範囲|閉じ欠落は通常原文、先頭delimiter後の空白許容等はR1で詳細化|
|indented/pre/comment|tabstop4列、preの実閉じ、行頭HTMLコメントのEOF保護|paragraph内コメントが次blockを隠す旧挙動はI-pending。閉じHTML直後の同一行はliteralに含む|
|リンク/画像/コード/HTML属性|owner内title 3形式、escape、code span、一行/同leaf複数行HTML引用、参照リンク|装飾・entity decode・複雑nested link・HTML文法全種は対象外。未成立Inlineはraw textを保持|
|参照定義|単一行、後方定義、全重複、先勝ちlookup|複数行destination/titleの代表候補はunsupported。全多行文法の検出は未実装|
|list/quote/table/一般HTML|所属不明領域をopaque unsupportedに保持|list/quote/pipe tableは原則次blankまで。raw script/style/textareaは明確close/EOFまで。完全なcontainer内回復は後続R3|
|通常装飾|raw textとして保持|装飾を解釈しないことと構造不明のunsupportedを区別|
|要件概要|全候補ID/順序/本文slice/lang/mdspec範囲・direct所属|ID/JSON/仕様診断/式/refsの妥当性、拒否と受理は本番R5の仕事|

未承認差分をCの新正解へ書き換えていない。I-pending-paragraph-comment、I-pending-div-tail-commentは旧結果・新観測だけを記録する。HTML引用の独立Block境界、通常不正fence info、番号付き行の段落中断（2.等を試作では広くunsupportedにする）、front matter細部もR1の対応表で固定する。

## 試作で得た判断

1. 不正headerでも属性列が必要。原文headerだけ残す実装ではprojectionが要件候補を見失ったため修正した。
2. header validityとclosureは別項目。未閉鎖だけを理由にheader_validを書き換えるとCの互換比較が壊れた。
3. Block側のHTML引用先読みを除いた。Inlineを後付けするだけでなく、先行Blockがleafを確定する必要がある。
4. 参照表は1回構築する。各paragraphで全定義から再構築する方式を修正した。
5. 複数行参照の情報欠落をcompleteにしない。今回未対応であることを範囲付きで公開する。
6. byte上限は索引作成後のparser容量上限。メモリ上限としての早期判定、属性decoded文字ごとの位置map、厳密なprofile検証は後続R2/R3で検討する。
7. 試作の初期sdistにはコードが入ったため、配布除外を追加した。wheel/sdist実物から混入0を確認する。

責務境界の検証はできたが、製品置換の判断には公開LocalAnalysisの全意味・診断とGraph/IR/CLI比較が必要。工程ごとの引渡しは[Issue改訂案](issue-revisions/README.md)、根拠は[参考元](references.md)、実測は[結果](results.md)にまとめる。
