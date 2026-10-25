
#24のソースモデルは原稿URI/パス、snapshot、開始・終了位置を保持する。人向けの行・列は1-based、範囲は開始を含み終了を含まない。列はUnicode code pointで数え、バイト数やLSPのUTF-16単位と混同しない。日本語・絵文字・CRLFを含めて検証する。

出典は要件・形式記述・共有定義・式の各位置へ付ける。生成IR、compose/build出力、バックエンド入力の位置には元原稿への対応を保持する。生成された見出し・記号等に対応する実文字がない場合は合成位置として明示し、原稿に存在しない列を作らない。section原稿を入口にした診断の主位置は元sectionファイルとする。

#25の共通診断は安定した診断コード、重要度、メッセージ、主位置、関連位置、任意の要件IDと根拠を持つ。ユーザーが直せる構造/型エラーと、未対応・未実行・判定不能・ツール実行失敗を区別する。診断が0件でも、未実行の検査を成功としてはならない。

テキスト/JSONは同じ内容を表し、JSONにはスキーマ版を持たせる。パス、開始位置、診断コード、関連ID等による安定したソートを定める。出典のPython APIは以下の#24の契約、診断APIと出力・ソートは本節の#25の契約に定める。共通モデルはZ3/CUE/Quint/LeanやLSPのパッケージをimportしない。

M1 / #24は`mdtools.core.source`に以下の内部APIを追加する。共通診断・要件抽出・LSPの位置変換は追加しない。

| API | 契約 |
|-----|------|
| `SourcePosition(line, column)` | 正の整数による1-based位置。Boolean・浮動小数・0・負数を拒否する |
| `SourceRef(uri, snapshot, path=None)` | 絶対URIとsnapshot hashで出典を識別する。任意の補助パスは絶対PathでURIと一致させる。補助パスの有無は同一性に影響しない |
| `SourceSpan(source, start, end)` | 同じ出典の半開範囲。逆転を拒否し、空範囲を許可する。ファイル内に存在するかはsnapshotで検証する |
| `SourceSnapshot(uri, text, path=None)` / `from_path(path)` | 不変の原文と参照。ファイル読込はsymlink解決済み絶対パスとUTF-8を使い、改行やBOMを除去しない。不正UTF-8を拒否する |
| `snapshot.position(offset)` / `offset(position)` | Python文字列の0-based code point offsetと1-based位置の相互変換。範囲外とCRLFの途中を拒否する |
| `snapshot.span(start=0, end=None)` | offsetから範囲を作る。end省略時はEOF。引数なしなら全文範囲 |
| `snapshot.offsets(span)` / `slice(span)` | URI・snapshotと両端位置を検証し、offset対または原文を返す。別snapshotの位置を流用しない |
| `SourceMapping(generated, kind, original=None, reason=None)` | 生成範囲に対する対応。実原文のない対応にはoriginalを付けない |
| `SourceMap(artifact, inputs, mappings)` | 生成snapshot、依存する入力snapshot、全文を隙間・重複なく覆う対応のtuple。不変とし、対応の内容一致も構築時に検証する |
| `map.resolve(generated_span)` | 生成範囲を出典の境界で分割した`SourceMapping`のtupleを返す。複数ファイル・合成文字を一つの原稿範囲へ丸めない |
| `SourceMapBuilder` | 出力時に`add_source` / `add_synthetic` / `add_unmapped`で対応を記録し、`build(uri, path=None)`で生成物を固定する。文字列diffによる出典の推測はしない |

snapshotは**改行を含む原文をUTF-8にしたバイト列のSHA-256（小文字16進64桁）**とする。同じ本文の別sectionはhashが同じでもURIで区別する。ファイル移動は別出典、LF/CRLFの変更も別snapshotになる。原文を保持するため、読込後に実ファイルが編集されても古い範囲の参照先は変わらない。これは保存版番号・時刻・Workspace全体のhashではなく、最新状態の保証やキャッシュ再利用判定も行わない。

改行はLF・CRLF・単独CRを認め、いずれも行間の区切りとする。行末位置の列は本文code point数+1であり、CRLFのCRとLFの間には位置を作らない。改行自体は前行の行末から次行の1列目までの範囲になる。最終改行があればEOFは次の空行の1列目、なければ最終行の行末位置。空原稿の唯一の位置は`(1, 1)`。タブも1 code pointで数え、結合文字・絵文字列を表示幅やgrapheme clusterでまとめない。front matter・preamble・コードフェンスの除去や位置の再採番はしない。

`mdtools.workspace.snapshot_sources(workspace)`は`analysis_files`の順に本文原稿のsnapshot tupleを返す。生成物、hierarchy JSON、共有定義はこの本文一覧に加えない。設定・hierarchy・参照の登録を読み直して比較し、変化があれば`workspace.changed-input`でWorkspaceの再読込を要求する。本文の編集自体は許可し、その読込時の新snapshotを取得する。不正UTF-8は`workspace.invalid-source`、I/O失敗は`workspace.read-error`になる。共有定義は登録パスに対して`SourceSnapshot.from_path()`を別途使えるが内容解析はしない。

複数ファイルの読込はファイルシステムのatomic snapshotでもロックでもない。各snapshotは実際に読み込んだ内容を固定する。登録後の再検証は行うが、並行編集やsymlink差し替えとの競合を完全に防ぐものではない。未保存文書版、Workspace全体の鮮度管理、非同期結果の適用判定は後続Milestoneの責務とする。

```python
from mdtools.core.source import SourcePosition, SourceSpan
from mdtools.workspace import load_workspace, snapshot_sources

workspace = load_workspace("docs/spec/examples/cancellation/mdtools.toml")
allow, deny, guidance = snapshot_sources(workspace)
point = SourcePosition(1, 1)
assert SourceSpan(allow.ref, point, point).source != SourceSpan(deny.ref, point, point).source
assert allow.slice(allow.span()) == allow.text
```

M1で位置対応を実装する生成段階は**mdsplit compose単独**とする。`mdsplit.compose.compose_with_source_map(hierarchy_path, *, artifact_uri, base_level=None)`はファイル出力せず、従来の`compose()`と同じ文字列を`map.artifact.text`に持つ`SourceMap`を返す。`artifact_uri`は呼出側が生成段階を識別する絶対URIとして指定する。`source_file`から出力先を推測しない。両APIは同じ出力順・区切り処理を使う。既存CLI、hierarchy形式、欠落sectionのskip動作は維持し、厳密な登録検証にはWorkspaceを使う。

| 対応のkind | composeと共通モデルでの意味 |
|-----------|----------------------------|
| `exact` | section/preambleからコピーした実文字。生成範囲と原稿範囲の文字列が一致する |
| `newline` | 既存composeのuniversal newline読込に合わせ、原稿のCRLF/CRをLFへ正規化した一改行。元の改行全体へ対応する |
| `synthetic` | 生成見出し（`heading`）、挿入改行（`separator`）、JSONから復号したfront matter（`hierarchy-front-matter`）。reasonを必須とし、架空の原稿位置を付けない |
| `unmapped` | 位置変換を未実装の出力。reasonを必須とする。空生成物の唯一の位置も`empty-artifact`として未対応を返す |

hierarchyのfront matterや見出しタイトルにはJSON内の元文字列があっても、Markdownと同じ実文字列・列にはならないため、この段階ではそのJSON範囲へ対応付けない。代わりにhierarchyのsnapshotを`map.inputs`へ依存として保持する。本文にコピーしなかった空・空白のみのpreambleや空sectionも、読み込んだものは入力snapshotに保持する。

`resolve()`の空範囲は境界の右側、EOFでは最後の対応を選ぶ。合成文字の開始・末尾を隣の原稿へ勝手に寄せない。非空範囲は対応ごとに切り出し、呼出側が診断の主位置や関連位置を選べるようにする。原稿EOFから生成物EOFまでを無条件に対応させない。

```python
from mdsplit.compose import compose_with_source_map

mapped = compose_with_source_map(
    "docs/spec/contract-v1_sections/hierarchy.json",
    artifact_uri="memory:contract-compose",
)
for part in mapped.resolve(mapped.artifact.span()):
    if part.original is not None:
        print(part.original.source.uri, part.original.start)
    else:
        print(part.kind, part.reason)
```

このAPIはWorkspaceのsnapshot取得とは別に入力を読み込む。位置の参照には**当該mapの`inputs`**を使用し、前後に読んだ別snapshotへ範囲を流用しない。単一原稿の恒等対応には`SourceMapBuilder.add_source(snapshot)`を使える。compose時の改行正規化を行う場合のみ`normalize_newlines=True`を指定する。

buildのcompose段階までの文字列は上記APIで対応できるが、**langfilter、glossary置換、HTML書換え、decomposeでの元canonicalへの逆対応、生成IR・バックエンド入力への対応の実装は今回の範囲外**。build CLIへsource map出力や後段変換への伝播は追加しない。後段出力をこのmapに渡すとURI/hashの不一致を拒否する。未対応の変換を表現する呼出側は`add_unmapped(text, reason)`を使い、元原稿へ正確に追跡できるようには扱わない。最初に述べた生成IR等への対応は後続段階で満たす目標であり、M1で実装済みという意味ではない。

### M1 / #25 診断APIと検査状態

`mdtools.core.diagnostics`は外部依存なしの共通モデルと表示のみを持つ。M2以降の内容解析、要件解決、検査計画・鮮度管理、外部ツール実行、終了コード決定は行わない。

| API | 契約 |
|-----|------|
| `Diagnostic(code, severity, category, message, primary=DiagnosticLocation(), related=(), requirement_id=None, evidence=())` | 不変の診断。主位置・関連位置・要件ID・根拠を保持する |
| `DiagnosticLocation(kind="none", span=None, reason=None)` | #24の`SourceSpan`を包む出典情報。別の座標系は作らない |
| `DiagnosticLocation.from_mapping(mapping)` | exact/newlineは`mapping.original`を主位置候補にし、synthetic/unmappedは生成範囲と理由を保持する。複数断片からの主位置の選択は呼出側の責務 |
| `RelatedLocation(message, location, requirement_id=None)` | 別原稿・別snapshotも参照できる関連位置。意味を説明するmessageを必須とする |
| `Evidence(kind, message, location=None)` | 根拠種別と自由記述の事実・前提・理由。任意の位置を付けられる。反例等もmessageで記述できるが、coreは式の意味や真偽を解釈しない |
| `CheckResult(check_id, status, reason=None)` | 特定の検査と範囲を識別するIDごとの明示的な結果。診断数やseverityから計算しない |
| `DiagnosticReport(diagnostics=(), checks=(), sources=())` | 不変tupleによるレポート。全ての位置のsnapshotを保持・検証する。同一URIの異なるsnapshotを許す。未参照の依存snapshotも保持できる |
| `report_to_dict(report)` / `render_json(report)` / `render_text(report)` | 新しいJSON互換dict、末尾LF付きJSON、末尾LF付きテキストを返す。I/Oや実ファイルの再読込はしない |

`code`・`check_id`・根拠の`kind`は`[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+`の識別子。生成側が名前空間ごとに管理し、同じcodeの意味を翻訳・message・severity・行番号に依存させない。意味を変える場合は新codeを割り当てる。既存Workspace診断の`workspace.*`コードは維持する。`example.*`は説明・テスト用で、仕様検査コードの予約ではない。message・理由・要件IDは空白だけの文字列を拒否する。UTF-8で表せない孤立surrogateも拒否する。

severityは表示上の`error / warning / info / hint`であり、検査の実行状態とは独立する。categoryは以下を区別する。

| category | 意味 |
|----------|------|
| `user` | ユーザーが原稿・設定を修正できる問題 |
| `unsupported` | 実装が対応しない版・構文・能力 |
| `unknown` | 判定不能・タイムアウト・入力変化等により結果を確定できない |
| `not-run` | 検査を実施していない。未導入等の理由をmessage/根拠に残す |
| `tool-error` | 読込・ツール実行・内部処理の失敗。仕様違反の判定とは分ける |

`CheckResult.status`は既存契約の`not-run / passed / failed / unknown / unsupported / error`を使う。not-run・unknown・unsupported・errorにはreasonを必須とし、passed・failedにも任意で付けられる。同じレポート内のcheck_id重複は拒否する。生成側が検査範囲・計画をIDと根拠で明確にし、実行済みの範囲に限ってpassedを設定する。coreは全体の成功を集約しない。checksが空なら検査状態の申告なしであり、診断0件でも成功にはならない。categoryは個々の診断の性質、statusは検査の結果であり、診断からstatusを暗黙変換しない。原稿の失敗はfailed、実行失敗はerrorとして生成側が対応を決定する。

位置のkindは`original / synthetic / unmapped / none`。originalは実原稿のspan必須・reasonなし。syntheticとunmappedはreason必須で、spanを持つ場合も生成物だけを指す。map構築前の失敗等で生成範囲も不明ならspanを省略する。noneは位置がない診断で、spanとreasonを持たない。全てのspanのURI/hashと範囲はreport.sourcesのsnapshotで検証し、欠落・不一致・存在しない行列を拒否する。関連位置・根拠の位置も同じ規則。補助パスの有無は#24の出典同一性を変えない。

#31は未解消であり、**断片末尾CR＋次断片先頭LFによって新しくCRLFができる境界**ではSourceMapBuilder.build()やcompose_with_source_map()が`ValueError: offset inside CRLF`で失敗し、map自体を取得できない。単一断片内のCRLF、通常のCRLF section本文全般の制約ではない。#25はこの修正を取り込まない。該当経路で呼出側が失敗を診断にする場合はtool-error / CheckResult.errorと理由を記録し、位置なし、またはspanなしのunmappedとする。近傍の原稿へ丸めたり、生成範囲から元原稿を推測したりしない。この経路を正確な原稿追跡が可能な経路として扱わない。

### 診断JSON v1とテキスト表示

JSONスキーマ版は整数`schema_version: 1`。[機械可読スキーマ](diagnostics-v1.schema.json)も参照する。レポートの必須フィールドは`schema_version / sources / checks / diagnostics`。空一覧も`[]`で残す。未知の版の読込やJSONデシリアライザーは今回実装しない。

| オブジェクト | 必須フィールド | 任意フィールド（値なしなら省略） |
|--------------|----------------|--------------------------------|
| source | `uri`, `snapshot` | `path` |
| check | `check_id`, `status` | `reason` |
| diagnostic | `code`, `severity`, `category`, `message`, `primary`, `related`, `evidence` | `requirement_id` |
| location | `kind` | `span`, `reason`（kindの規則に従う） |
| span | `source`, `start`, `end` | なし |
| start/end | `line`, `column` | なし |
| related | `message`, `location` | `requirement_id` |
| evidence | `kind`, `message` | `location` |

nullは出力しない。related/evidenceは空でも残す。span.sourceはsourceオブジェクトを直接含み、配列indexを使わない。sourcesにはURI・完全なSHA-256 snapshot・任意の絶対pathを出す。原文全体はメモリのreport.sourcesに保持し、**両形式とも原文textは出力しない**。出力したhashは読込内容の識別であり、実ファイルの現在の内容や結果の鮮度を保証しない。sourcesは依存一覧でもあり、未参照の入力も落とさない。

URIは#24の入力値をそのまま表示し、file URIのpercent encodingも勝手に復号・正規化しない。補助pathがあれば絶対パスを別フィールドで表示し、なければ省略する。相対化、cwd、OSのlocale、現在のファイル状態、時刻はソート・表示に使わない。JSONはオブジェクトキーを昇順、2空白indent、末尾LF、`ensure_ascii=False`で生成する。日本語・絵文字・結合文字を保持し、引用符・backslash・C0制御文字はJSONエスケープする。

診断のソートキーは順に、spanなしの真偽（ありを先）、主spanのURI、開始行、開始列、code、requirement_id（省略は空文字）、最後に**診断全体のcanonical JSON**。spanなしはURI空文字・行列0を内部ソートキーにするだけで、位置として出力しない。severity順による優先表示は行わない。終端位置、snapshot、category、message、関連位置、根拠等の差は最後のキーで区別する。完全一致の重複診断は削除せず同じ行を繰り返すため、同順位でも出力は変わらない。

canonical JSONはオブジェクトキー昇順、`ensure_ascii=False`、空白なし（separatorsは`,`と`:`）。relatedとevidenceは各要素のcanonical JSONで先に整列し、sourcesもsourceオブジェクトのcanonical JSON順、checksはcheck_id順にする。これらの一覧は意味上の順序を持たない。文字列比較はPythonのUnicode code point順で、自然順やlocale順ではない。入力tupleの挿入順を変えても同じ出力になる。

テキストは`diagnostics schema_version=1`、source行、check行、`diagnostic_count=N`、診断とそのrequirement_id・primary・related・evidence行の順。両形式は同じ正規化dictから全フィールドを表示する。範囲は`range=[開始行:列,終了行:列)`とし、全て1-based・code point単位。出典URI・snapshot・任意のpathも各位置に表示し、primary kind=noneを明示する。source/check/related/evidenceの0件は行を出さず、checkの成功行や全体成功文言を補わない。

テキスト中の自由文字列は全てJSON文字列として引用する。改行・タブ・引用符・backslashに加えてC1制御文字、Unicode行区切りU+2028/U+2029、bidi制御文字を`\uXXXX`表記にして、メッセージやファイル名が別レコードや表示方向に影響しないようにする。JSONとして復号した値は元の文字列と一致する。テキスト形式の読込APIは提供しない。

### 最小利用経路

`mdtools.diagnostics.inspect_workspace(config_path)`は既存のload_workspace→snapshot_sourcesを呼び、登録・本文読込の成否を`workspace.sources`チェックで返す。成功時はその範囲だけpassedで、仕様内容の検査は申告しない。WorkspaceErrorを共通診断に変換し、invalid-config/missing-file等はuser/failed、unsupported-versionはunsupported、changed-inputはunknown、read-errorはtool-error/errorとする。読めないファイルのsnapshotや行列を作らず、元のpathは`workspace.path`根拠として残す。既存Workspace APIの例外・既存CLIの出力・終了コードは変更しない。

```python
from mdtools.diagnostics import inspect_workspace
from mdtools.core.diagnostics import render_json, render_text

report = inspect_workspace("docs/spec/examples/cancellation/mdtools.toml")
print(render_text(report), end="")
print(render_json(report), end="")
```

実際に位置付き診断を作る呼出側は、snapshotとSourceSpanを渡す。以下は表示の例であり、衝突検出器を実行した結果ではない。

```python
from mdtools.core.diagnostics import (
    Diagnostic, DiagnosticLocation, DiagnosticReport, Evidence, RelatedLocation,
)
from mdtools.workspace import load_workspace, snapshot_sources

sources = snapshot_sources(load_workspace("docs/spec/examples/cancellation/mdtools.toml"))
allow, deny, guidance = sources
report = DiagnosticReport((Diagnostic(
    "example.conflict", "warning", "user", "両原稿を参照する表示例😀",
    DiagnosticLocation("original", allow.span(0, 0)),
    (RelatedLocation("関連原稿", DiagnosticLocation("original", deny.span(0, 0)), "REQ-CANCEL-DENY"),),
    "REQ-CANCEL-ALLOW", (Evidence("example.assumption", "表示例。意味検査は未実施"),),
),), sources=sources)
print(render_text(report), end="")
print(render_json(report), end="")
```
