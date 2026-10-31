
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

FieldSource.pathは正規化したモデル内の位置であり、原稿の座標や入力JSON全体の絶対pointerではない。RFC 6901の`~0`/`~1`を使う。要件属性は`/id`、`/spec-version`、`/status`、任意の`/refs`と`/refs/0`等。モデルは7必須フィールドのpointerと、`/uses/0`等の各参照を持つ。宣言は`/name`、`/kind`、`/values`、`/type`、`/role`、`/min`、`/max`、`/value`、`/glossary`のうち存在するものを持つ。`/name`は元のmapping keyに対応する正規化フィールドである。glossaryは`/id`、`/kind`と表示データ内のフィールドを対象とする。

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

M1が留保したglossary関連付けは、仕様の型・変数・定数宣言に任意の文字列`glossary`を1件指定する形とする。要件属性・モデルの7フィールドへ新しい項目を加えない。対象はterm/const/symbolのいずれでもよく、仕様宣言の種別・型・値と表示用途を同一視しない。

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
| `ResolvedAnalysis` | Workspace順のLocalAnalysis一覧、Graph、全体checks/completeness、全体段階で追加したdiagnostics。ローカル診断とsnapshotを欠落させずreportへ集約する |

両解析結果のreportプロパティは既存DiagnosticReportを返す。診断JSON版・ソート・表示を再実装しない。Graphは全入力の全出現を一度ずつ含み、全明示参照に解決結果を持たせる。曖昧な辺には同じ名前空間の全候補を残し、重複名のうち一つだけをresolvedにしない。built-inはtype参照だけに許し、原稿に架空の組み込み型宣言を作らない。

completenessはローカルならそのsnapshotの構造・ローカル宣言検査、全体ならM2の構造・宣言値・参照解決の完了範囲を示す。

| 値 | 意味 |
|----|------|
| complete | 当該範囲のM2検査が全てpassed。拒否断片・error診断なし。全体では全ローカル結果もcomplete、衝突なし、全辺resolved |
| partial | 原稿を保持し一部収集・解析できたが、不正・未対応・未実行・実行失敗等が残る。対応するM2チェックをfailed/unsupported/not-run/error/unknownで示す。ノード0件でも失敗を隠さない |
| unavailable | 当該結果としてノードを収集できなかった。構造等の検査状態と理由を残す。Workspace読込前の失敗ではResolvedAnalysisのinputs/Graphを空にできる |

constructorは成功を自動推定せず、producerが検査範囲と結果を明示する。診断0件でも未実行検査をpassedにしない。共通チェック状態と従来の説明上の構造状態は、not-run→not-checked、passed→valid、failed→invalid、unsupported→unsupportedと対応する。error/unknownは妥当性を確定できない実行状態として別に残す。

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

[契約fixture](examples/model-contract/README.md)は正常・natural-only・多言語・壊れた構造と回復・未知版・式未検査・glossary関連付けを示す。単体テストはこれらの原稿に対して手で構築したモデルと出典・状態の契約を検証するもので、抽出器・ローダー・Graph構築器の実装や通過を意味しない。
