
M2 / [#35](https://github.com/fischerimapig/mdtools/issues/35)は`mdtools.spec.model`と`mdtools.spec.results`に、抽出器・共有定義ローダー・名前解決器が共有する不変の内部データ契約を追加する。原稿のパース、定義の読み込み、Graphの構築、サービス・IR生成・CLIの本体は追加しない。各constructorは渡された表現の不変条件を検証し、不正な組合せに`ValueError`を返す。原稿の不正をconstructorの例外だけで報告せず、後続のproducerが共通診断と部分結果へ変換する。

**モデルと出現の識別**

| 型 | 内容とproducerの責務 |
|----|-----------------------|
| `NodeKey(namespace, name, source, ordinal)` | 原稿内の出現。nameは人が記述したID/宣言名、sourceはM1のSourceRef。ordinalは同一snapshot内の全ノード種別を横断した0-based原稿順で一意にする。重複名も別出現として保持する |
| `FieldSource(path, location, container=None)` | 正規化モデル内のJSON Pointer、M1のDiagnosticLocation、任意の既知の原稿包含範囲。別の座標型は作らない |
| `Body(language, text, span)` | 言語（未指定はNone）、原稿のMarkdown断片とその正確な範囲。wrapper、mdspecを除いた本文断片を原稿順に保持し、複数断片を架空の連続範囲へ結合しない |
| `Expression(text, origin)` | JSONデコード後の式文字列と、元のフィールドの出典。式ASTではない |
| `FormalModel` | key/span/fields、uses、when/must、version=1、kind=constraint、4件のM3未検査結果 |
| `Requirement` | key/span/fields、bodies、structure、formalization、任意のmodel、refs、version=1、status=draft/active/deprecated |
| `Declaration` | type/variable/constantの区別、名前・出典、型参照、role、整数上下限、列挙値、定数リテラル、任意のglossary関連付け |
| `GlossaryEntry` | 独立したkey/span/fields、既存のterm/const/symbol、表示用データ。仕様型を付加しない |
| `JsonObject(items)` | glossary表示データの不変JSON object。文字列キーと値のpairのtupleを使い、配列はtuple、入れ子objectはJsonObjectで区別する。可変dict/list、重複キー、非有限数を受け付けない |
| `Reference(kind, name, origin)` | refs/uses/type/glossaryの明示参照。未解決の段階で対象を推定しない |
| `RejectedFragment(kind, span, text, diagnostic_codes)` | 正常な型へ変換できなかった予約構文の原文、範囲、対応する診断コード。ID等を捏造して正常ノードにしない |

ordinalは同一snapshot内の出現を区別する補助キーであり、仕様の永続IDではない。移動・並べ替えでURI/hash/ordinalが変わっても要件IDとモデルIDは原稿から保持する。Graphを名前だけのdictへ変換して重複を消さない。DocumentTreeの親子・章番号から依存・継承・制約を生成しない。

本文は未言語指定の断片と各lang divの断片を混在して保持できる。同じ言語の離れた断片も原稿順に残す。形式記述は言語共通で一つだけとし、言語別本文へ複製しない。本文全体として空白だけの要件は不正とする。本文textとRejectedFragment.textはsnapshotのsliceと一致しなければならない。

**出典の粒度**

FieldSource.pathは正規化したモデル内の位置であり、原稿の座標や入力JSON全体の絶対pointerではない。RFC 6901の`~0`/`~1`を使う。要件属性は`/id`、`/spec-version`、`/status`、任意の`/refs`と`/refs/0`等。モデルは6必須フィールドのpointerと、`/uses/0`等の各参照を持つ。宣言は`/name`、`/kind`、`/values`、`/type`、`/role`、`/min`、`/max`、`/value`、`/glossary`のうち存在するものを持つ。`/name`は元のmapping keyに対応する正規化フィールドである。glossaryは`/id`、`/kind`と表示データ内のフィールドを対象とする。

producerは属性値、宣言名、JSON/YAMLのフィールドと各明示参照に、特定できる最小の原稿トークン範囲を付ける。オブジェクト・配列しか特定できない場合、その範囲をフィールドそのものの精密位置と偽らずcontainerへ保持し、locationは理由付き・spanなしのunmappedにする。containerは実原稿だけを指す。既知のcontainerは診断のRelatedLocationとして利用できる。

省略したstatusのdraftには原稿トークンがないため、理由付きunmappedと要件のcontainerを付ける。JSONの`"\u0070aid"`、改行escape、YAMLの引用符・block scalar等ではデコード後の文字offsetと原稿列を対応付けない。tokenを正確に特定できれば引用符やescapeを含む原稿範囲をoriginalとして保持し、内部文字へ分割する対応が不明なら分割しない。合成・unmappedのspanはM1契約どおり生成物のみを指し、近傍の原稿を代用しない。

LocalAnalysisは全モデルのspan、field/container、参照、拒否断片と診断を同じSourceSnapshotで検証する。範囲外・別snapshot・raw本文不一致を拒否する。Unicode code point、半開範囲、LF/CRLF/単独CRはM1の規則を使う。#31の断片連結修正は含めず、元の各snapshotを直接解析する。

**名前空間と参照**

| 名前空間 | 名前と衝突規則 | 参照先 |
|----------|----------------|--------|
| requirement | 大文字小文字を区別する既存ID形式。Workspace全体で一意 | refs |
| model | 同じID形式。要件IDとは別に一意 | 要件内のmodel所属。v1にモデル名での参照構文は追加しない |
| declaration | types/variables/constantsを横断して一意。型名は既存ID形式、変数/定数名は既存の識別子・予約語規則。bool/intは組み込み型として予約 | usesはvariable/constant、typeはtypeまたは組み込み型 |
| glossary | 既存entriesの空でない文字列IDを大小文字・空白を含めそのまま保持。Workspaceの仕様解析経路では一意 | glossary |

名前空間が異なれば同じ綴りを許す。同じ空間の重複は後勝ちにも先勝ちにもせず、全候補と両宣言位置を診断する。別空間の同名を参照先へ代用しない。未定義・種別不一致・曖昧な参照を区別する。

usesは従来どおり一意な名前の配列とする。refsにはv1で新たな重複禁止を設けず、同じIDが繰り返されても各出現のoriginを保持する。

M1が留保したglossary関連付けは、仕様の型・変数・定数宣言に任意の文字列`glossary`を1件指定する形とする。要件属性・モデルの6フィールドへ新しい項目を加えない。対象はterm/const/symbolのいずれでもよく、仕様宣言の種別・型・値と表示用途を同一視しない。

```json
{"type": "bool", "role": "input", "glossary": "paid label"}
```

上例はvariablesの一宣言の値である。仕様用ローダーはglossaryを明示参照として残し、全体解決時に未定義なら`spec.undefined-glossary`、重複対象なら`spec.ambiguous-reference`を参照位置付きで返す。複数の仕様宣言から同じglossary IDへの関連付けは許す。glossary CLI、entriesスキーマ、表示文字列から仕様定数への変換は変更しない。

この追加はM1契約がM2へ留保した能力の具体化であり、契約・要件・モデル・共有定義の版は1を維持する。既存v1入力の意味・必須項目は変えず、移行作業は不要。能力として`declaration-glossary-link`を明記し、対応しない古い実装は新フィールドを未知フィールドとして拒否する。既知でない拡張を無視して成功させない。既存入力の意味を変える将来変更には新契約版と移行手順を必要とする。

**宣言値とYAMLの対応範囲**

型宣言はkind=enumと空でない一意な文字列valuesを持つ。variableにはtypeとinput/outputのrole、constantにはtypeとリテラルvalueが必須。intには整数min/maxとmin <= maxを要求し、boolをintとして受け付けない。bool定数はbool、int定数は範囲内のint、名前付き列挙型の定数は文字列を保持する。別ファイルの型や列挙値への所属はローカル収集で断定せず、#38の全体解決後に宣言値検査を完成する。これをM3の式型検査とは区別する。

JSON/YAMLの未知フィールド・重複mapping key・重複glossary entry IDを黙って上書きしない。名前を持つ個々の宣言の列挙値等の位置もFieldSourceで保持できる。仕様解析用の読み込みに、既存glossary.loader.load()で上書きされたdictを使わない。

初期の厳格YAML能力は単一文書のmapping/sequence/scalarと通常の引用・block scalarとする。仕様の型付きリテラルはJSONと同じbool、10進整数、文字列で表す。Booleanはtrue/false、整数はJSONの10進表記を使い、yes/no、日付、自動的な型変換で型を推測しない。文字列として使う値が曖昧な場合は引用する。anchor、alias、merge key、明示tag、複数文書は`spec.unsupported-syntax`と理由付きunsupportedで拒否する。任意tagを実行せず、safeな読込とノード単位の重複・位置検証を行う。これはv1のYAML対応能力の明示であり、既存表示用glossaryのYAML挙動を狭めない。実装は#37で行い、JSONだけの利用にはPyYAMLを要求しない。

**結果と状態**

| 型 | 契約 |
|----|------|
| `AnalysisChecks` | structure/declarations/referencesのCheckResultと、expression-syntax/expression-types/expression-uses/logicの4件のCheckResult。check_idは全てspec.* |
| `LocalAnalysis` | 1個の元snapshot、収集したrequirements/declarations/glossary、rejected、diagnostics、checks、completeness。referencesは必ずnot-run。構造・その場で確定する宣言値の検査を終えてもWorkspace参照の成否は未確定 |
| `ReferenceResolution` | ownerのNodeKey、元のReference、pending/resolved/undefined/ambiguous/wrong-kind、候補のNodeKey一覧、または組み込み型bool/int |
| `SpecGraph` | 渡された全出現nodesと明示参照edges。グラフ構築器ではなく値。自己参照・循環を許す |
| `ResolvedAnalysis` | 入力順のLocalAnalysis一覧、Graph、全体checks/completeness、全体段階で追加したdiagnostics。ローカル診断とsnapshotを欠落させずreportへ集約する。registriesはGraph.nodesから導出する読み取り専用property |

両解析結果のreportプロパティは既存DiagnosticReportを返す。診断JSON版・ソート・表示を再実装しない。Graphは全入力の全出現を一度ずつ含み、全明示参照に解決結果を持たせる。曖昧な辺には同じ名前空間の全候補を残し、重複名のうち一つだけをresolvedにしない。

ReferenceResolution.builtinは参照名がbool/intと一致し、candidatesが空で、type/resolvedまたはuses/wrong-kindのときだけ許す。後者は変数・定数を要求するusesへ組み込み型を指定した誤りを表す。架空のNodeKey・宣言位置を作らない。refs/glossaryには組み込み型の特例を適用しない。

ResolvedAnalysis.registriesの型は`Mapping[Namespace, Mapping[str, tuple[NodeKey, ...]]]`で、requirement/model/declaration/glossaryの4空間を常に持つ。名前・候補はGraph.nodesの出現順、外側・内側mappingは読み取り専用、候補はtupleとする。constructor引数や保存フィールドを増やさず、組み込み型を登録しない。

completenessはローカルならそのsnapshotの構造・ローカル宣言検査、全体ならM2の構造・宣言値・参照解決の完了範囲を示す。

| 値 | 意味 |
|----|------|
| complete | 当該範囲のM2検査が全てpassed。拒否断片・error診断なし。全体では全ローカル結果もcomplete、衝突なし、全辺resolved |
| partial | 原稿を保持し一部収集・解析できたが、不正・未対応・未実行・実行失敗等が残る。対応するM2チェックをfailed/unsupported/not-run/error/unknownで示す。ノード0件でも失敗を隠さない |
| unavailable | 当該結果としてノードを収集できなかった。構造等の検査状態と理由を残す。Workspace読込前の失敗ではResolvedAnalysisのinputs/Graphを空にできる |

constructorは成功を自動推定せず、producerが検査範囲と結果を明示する。診断0件でも未実行検査をpassedにしない。共通チェック状態と従来の説明上の構造状態は、not-run→not-checked、passed→valid、failed→invalid、unsupported→unsupportedと対応する。error/unknownは妥当性を確定できない実行状態として別に残す。

ResolvedAnalysisのconstructorは非pending辺の候補欠落、誤った状態、種別不一致の隠蔽を拒否する。references=passedには空でない全入力のcomplete、全辺resolved、全名前空間の衝突なしを要求する。declarations=passedはローカル宣言検査の未完了、宣言/glossary衝突、名前付き定数の未解決型・列挙値不所属を許さない。pendingは未実行の値表現として維持するが、resolverは返さない。constructorは診断・検査成功を自動生成しない。

Requirement.formalizationはnatural-onlyまたはpresentで、構造状態とは独立する。壊れたモデルがある場合もpresentを保持し、model=None、structure=failed/unsupported等、RejectedFragmentと診断を残す。natural-onlyへの格下げは禁止する。ID等すら安全に保持できない要件全体はRejectedFragmentへ残す。

全ての式の構文・式型・識別子とusesの照合・論理検査はM2では理由付きnot-runで固定する。形式記述がなくても論理成功を表示しない。構造のcompleteはM3の検査成功、本文と形式の意味的一致、人の確認、M4の鮮度の保証ではない。M4用の確認・鮮度状態を自動生成しない。

**診断コードと後続実装**

| コード | 意味と分類 |
|--------|------------|
| spec.invalid-requirement / spec.invalid-model | 属性・本文・予約構文またはモデルJSONの構造不正。user / failed |
| spec.invalid-definition / spec.invalid-glossary | 宣言・表示定義の不正、文書内重複キー等。user / failed |
| spec.unsupported-version / spec.unsupported-syntax | 未知版・未対応予約構文やYAML能力。unsupported / unsupported |
| spec.duplicate-id / spec.duplicate-name / spec.duplicate-glossary | 要件/モデルID、仕様宣言名、glossary IDの衝突。user / failed。両位置を付ける |
| spec.undefined-reference / spec.undefined-glossary | 明示参照またはglossary関連付けの未定義。user / failed |
| spec.ambiguous-reference / spec.wrong-reference-kind | 曖昧な対象または型/変数等の種別不一致。user / failed |
| spec.read-error / spec.execution-error | I/Oや内部処理の失敗。tool-error / error |
| spec.missing-dependency | 入力に必要な任意依存不足。unsupported / unsupported。依存名と理由を付ける |
| spec.unknown-id | CLI showの対象要件IDが存在しない。user。参照解決失敗とは区別する |

コードは安定識別子、messageは人向け説明とする。主位置は該当する元原稿の属性・参照・宣言等、重複や型参照の宣言先はRelatedLocationにする。正確な位置が不明ならunmappedと理由・既知containerを使う。Workspaceの既存workspace.*コードは改名しない。

この契約はspec→core/標準ライブラリだけに依存する。core・既存文書処理・Workspaceからspecへ逆依存せず、specモデルからCLI、LSP、backend、既存glossaryの可変Entryへ依存しない。#36は抽出器、#37は定義ローダー、#38は名前解決とGraph、#39は設定・hierarchyを含む入力manifest/版付きIR/サービス/Schema、#40はCLIを担当する。時刻・乱数・一時パスを結果の意味へ混ぜず、入力のWorkspace順と各snapshot内の原稿順を保持する。IRの完全なJSON表現と決定的ソートは#39で実装する。

[契約fixture](examples/model-contract/README.md)は正常・natural-only・多言語・壊れた構造と回復・未知版・式未検査・glossary関連付けを示す。#35の単体テストは手で構築したモデルの契約検証として維持する。#36では同じMarkdown原稿とキャンセル例を実際の抽出器へ入力し、出典・状態・回復を別のテストで検証する。定義ローダー・Graph構築器の動作確認は後続Issueで行う。

**M2 / #36 抽出APIと出典**

`mdtools.spec.parser.parse_requirements(source: SourceSnapshot) -> LocalAnalysis`は一つの元Markdown/QMD snapshotを受け取る。読込・標準入出力・終了コードを扱わず、Workspace選択済みの各原稿を呼出側が個別に渡す。原稿の不正は共通診断とpartialへ変換する。引数がSourceSnapshotでなければTypeErrorとする。

```python
from mdtools.workspace import load_workspace, snapshot_sources
from mdtools.spec.parser import parse_requirements

workspace = load_workspace("docs/spec/examples/cancellation/mdtools.toml")
local_results = tuple(parse_requirements(source) for source in snapshot_sources(workspace))
assert all(result.completeness == "complete" for result in local_results)
assert all(result.checks.references.status == "not-run" for result in local_results)
```

attributesは`core.pandoc.tokenize_attrs()`の全出現トークンから検査する。属性順序、裸の値、単一・二重引用符を扱い、引用内のbackslash escapeはデコード値と元範囲を分ける。既存`parse_attrs()`の後勝ちや既存Markdown走査の挙動は変更しない。仕様固有の属性名・値・重複禁止はspec側で判定する。

要件spanは開始divから終了行まで、モデルspanとモデル拒否断片はcode fence全体とする。閉じ忘れではsnapshot末尾までを指す。属性FieldSourceは値トークン（引用符があれば含む）、JSONフィールドは値トークン、refs/usesは各要素を指す。JSONのkeyは重複・未知フィールド診断に使用し、重複キーとusesの重複には先行トークンの関連位置を付ける。JSON escape後の文字offsetを原稿列へ流用しない。

Bodyはwrapperとmdspecを除いた連続する原文断片で、同じ言語でも離れた範囲は結合しない。空白だけの断片は省略できるが、保持する断片の前後空白・改行は加工しない。本文全体が空なら要件全体を拒否する。status省略時のdraftは理由付きunmappedと要件containerを持ち、存在しないトークン位置を作らない。

このMarkdown入力範囲に共有宣言がないことを明示してdeclarationsをpassedとする。これは別の共有定義ファイルの検査成功を意味しない。referencesとM3の4検査は常に理由付きnot-run。重複した要件ID・モデルIDは原稿順の別NodeKeyとして残す。全体の衝突診断は#38で行い、ローカル抽出時に参照先や一意性を断定しない。

**M2 / #37 厳格ローダーAPI・回復・状態**

`mdtools.spec.loader.load_definitions(source: SourceSnapshot, *, kind="spec" | "glossary", format="json" | "yaml" | "yml") -> LocalAnalysis`は、Workspaceへ明示登録した一つの共有定義snapshotを解析する。kindとformatは呼出側が登録情報から渡し、内容・URIから推測しない。I/O・標準入出力・終了コード・Workspaceのimport・参照解決を含まない。SourceSnapshot以外はTypeError、不正なkind/formatはValueErrorとし、原稿の不正は診断と拒否断片へ返す。

汎用の原文トークン走査は`core._structured`と`core.io.parse_structured_text()`へ置く。mappingは全key/value出現を原稿順に保持し、strict経路のToken.valueはmapping種別を示す空dictで、内容はmembersから読む。#36の`spec._json`は互換importとして維持し、parse_jsonの既定経路は従来どおり重複キーで停止する。既存coreファイル読込・glossary.loader.load()のsafe_load/後勝ちをstrict入力には使わない。

YAMLはBaseLoaderのイベント・ノードだけを利用し、暗黙resolverやオブジェクトconstructorを使わない。引用・block scalarは文字列、plain scalarのtrue/false/nullとJSON表記の10進整数・有限小数だけをJSONの値に変換し、値省略はnullとする。それ以外のplain scalar（yes/no、日付、01、+1、0x10、~等）は文字列のまま保持する。仕様のbool/int定数に文字列を指定しても補正しない。glossary表示データはJSON相当のnull・bool・int・有限float・文字列・配列・objectを保持する。mapping keyは文字列を要求するため、trueや数値等の文字列キーは引用する。anchor/alias/明示tag/複数文書・YAML directivesはイベント段階で、未引用のmerge keyはノード段階で文書全体をunsupportedとする。引用された"<<"は通常の文字列キーとして扱う。

strict glossaryのトップレベルはentriesだけとし、entryのid/kind以外は任意の表示データとして保持する。既存CLIが許す表示用の追加フィールドを仕様の未知フィールドとして拒否せず、表示値を仕様リテラルへ変換しない。CLI側の入力許容・上書き・警告・表示・終了コードは変更しない。

| 状況 | 結果・回復境界 |
|------|----------------|
| 正常な単一文書 | 原稿順の全宣言/entryと明示参照を収集。ローカルstructure/declarationsはpassed、complete |
| 不正JSON/YAML、版の欠落・型不正・重複 | 文書全体を拒否。structure=failed、declarations=not-run、partial。構文を推測して後半へ復帰しない |
| 未知の整数version | v1フィールド契約を適用せず文書全体を拒否。structure=unsupported、declarations=not-run、partial。重複キーの構文検査は版に依存しない |
| 必須の区分mapping欠落・型不正、未知トップレベル項目 | 診断と拒否断片を保持。解釈可能な他の区分は収集しpartial |
| 宣言/entryの未知・欠落・重複フィールド、不正な名前/値 | 該当する完全な宣言/entryを拒否し、次の完全な要素へ回復。entry内の表示データの重複キーもentry全体を拒否 |
| 宣言名を表すmapping key、区分mapping、entriesの重複 | 全出現を走査し、正常に表せる候補はすべて保持。宣言名/entry IDの衝突も両位置付きで診断しpartial |
| 未対応YAML、走査の深さ・整数変換容量超過 | 推測せず理由付きunsupported・partial。保持できない原文を拒否断片へ残す |
| YAML依存不足 | spec.missing-dependencyとPyYAMLの根拠、元snapshotと拒否断片を保持。structure=unsupported、declarations=not-run、unavailable |

フィールド構造違反・文書内キー重複はstructure、名前・role・型名・値領域・宣言名/entry ID重複はdeclarationsへ記録する。構造的に拒否された宣言の値は推測しない。構造不正の兄弟を拒否した結果、収集済み候補のdeclarationsだけがpassedでも、結果全体はpartialを維持する。各check内で不正と未対応が混在する場合はfailedを優先し、両方の診断を残す。未知フィールド・拒否範囲内を含む全mappingの重複キーも検査する。

宣言spanは名前トークンから宣言値の末尾まで、entry spanはentry object全体とする。/nameは元mapping key、各フィールドと/values/N、表示データ内の各pointerは元の値トークンを指す。JSON escapeやYAML引用・block scalarのデコード値と原文範囲を分離し、元トークン内部をデコード後offsetで分割しない。正確な座標が得られなければspanなしunmappedと理由・既知containerを使う。拒否断片のtextはsnapshot.slice(span)と一致する。

ファイル取得は外側の`mdtools.diagnostics.read_definition_source(path)`で行える。WorkspaceのDefinitionInput.pathだけを渡し、得たsnapshotを上のAPIへ渡す。OSError/UTF-8デコード失敗は`DefinitionReadError(ValueError)`となり、reportにspec.read-error / tool-errorとstructure=error、宣言・参照・M3のnot-runを持つ既存DiagnosticReportを保持する。読めなかったpathはEvidenceへ残し、sourcesは空で架空のsnapshotや行列を作らない。これは単一ファイルの読込境界であり、Workspaceの原典選択・全体サービス・IRは実装しない。

型名・glossary関連付けはReferenceのまま全出現を残す。名前付き型の定数は文字列の形式までをローカル検査し、別ファイルを含む型解決と列挙値所属は#38で完成する。referencesとM3の4検査は理由付きnot-runで固定する。キャンセルとmodel-contractの定義原稿を実際にローダーへ入力し、#35の手構築モデルテストとは別に[チェックリスト](../../mdtools/spec/tests/README.md#issue-37-厳格ローダーの検証チェックリスト)で再現・期待結果・診断・状態・出典を管理する。

**M2 / #38 参照解決API・Graph・全体状態**

`mdtools.spec.resolver.resolve_analyses(inputs: Iterable[LocalAnalysis]) -> ResolvedAnalysis`は全入力をtupleへ保持してから、全ノードと宣言種別を収集し、各明示参照を判定する。不正な要素はTypeError、同一SourceRefの二重入力はValueErrorとする。ファイル再読込、Workspace選択、標準入出力、CLI処理を含めない。

```python
from mdtools.spec.resolver import resolve_analyses

# 各snapshotをparse_requirements/load_definitionsで収集した結果を渡す。
resolved = resolve_analyses(local_results)
assert all(edge.status != "pending" for edge in resolved.graph.edges)
assert all(check.status == "not-run" for check in resolved.checks.expressions)
```

| 判定順 | 収集済み候補に対する条件 | 結果 |
|--------|------------------------|------|
| 1 | type/usesの参照名がbool/int | builtinによるtype/resolvedまたはuses/wrong-kind |
| 2 | 対象名前空間に同名が2件以上 | ambiguous。宣言種別で絞らず全候補を保持 |
| 3 | 対象名前空間に1件 | 許可種別ならresolved、他はwrong-kind |
| 4 | 対象空間になく、別空間に同名が存在 | wrong-kind。別空間の全同名候補をGraph順に保持 |
| 5 | 全空間に存在しない | undefined |

usesの許可種別はvariable/constant、typeはtypeとする。別空間の候補が複数でも対象空間に候補がなければwrong-kindであり、ambiguousとしない。拒否断片から候補を推定せず、個別の辺は収集できたノード集合に対する結果とする。入力登録漏れの検出は#39の責務である。全ノード・全明示参照を保持し、モデル所属・文書階層から追加辺を作らない。自己参照・循環の再帰展開や論理判定を行わない。

名前付き列挙型定数はtype辺が一意にresolvedの場合だけ所属を検査する。不所属はspec.invalid-definitionとし、主位置は値、関連位置は型宣言と列挙値集合とする。型未解決なら所属を実行せず、型参照診断のspec.enum-membership Evidenceへ対象値・値位置・未実行理由を残す。declarationsの集約理由にも未実行を残し、他の失敗を優先しても消さない。

各チェックの同じ範囲内で`error → failed → unsupported → unknown → not-run → passed`の優先順位を使い、全理由を保持する。

| チェック | 集約範囲 |
|----------|----------|
| structure | 各ローカルstructure |
| declarations | 各ローカルdeclarations、宣言/glossary衝突、列挙値所属とその未実行 |
| references | ローカルreferences=not-runを除外して独自算出。参照不正または全名前空間の衝突でfailed。その他は不完全な入力があればunknown、全入力complete・全辺resolved・衝突なしでpassed |
| M3の4検査 | 常に理由付きnot-run |

入力0件または全入力unavailableならreferencesは理由付きnot-run、全体completenessはunavailableとする。それ以外で全入力complete、M2の3検査passed、拒否・error診断・衝突・未解決なしならcomplete、その他はpartialとする。正常原稿のノード0件はcompleteにできる。読めた入力を全て拒否した場合はノード0件でもpartialで、正常な空入力とunavailable入力の混在もpartialである。

ローカル診断・snapshot・拒否断片を変更せずinputs/reportへ全件保持する。同一snapshot内の衝突の追加診断は、対応する衝突コードと両定義の正確な位置がローカル診断で既報告と確認できる場合だけ抑制する。コードがあるだけでは抑制せず、診断抑制後もレジストリの衝突とfailed状態を維持する。別snapshotとの衝突は必ず追加し、後続の各出現を主位置、先行する別snapshotの全同名候補を関連位置にする。正確な位置がない場合は理由付きunmappedと既知containerを使い、重複と証明できない診断を抑制しない。

契約値の不変条件、解決規則、状態集約、衝突診断、実fixture・出典の責務別テストと確認手順は[検証チェックリスト](../../mdtools/spec/tests/README.md#issue-38-specgraphの検証チェックリスト)を参照する。#37の既知のP3制限、#39のサービス/IR/Schema、#40のCLI、M3、LLM、#31は変更しない。
