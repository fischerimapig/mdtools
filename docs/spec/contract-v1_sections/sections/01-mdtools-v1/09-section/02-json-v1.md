
JSONスキーマ版は整数`schema_version: 1`。[機械可読スキーマ](diagnostics-v1.schema.json)も参照する。公開Schemaもmessage・要件ID・理由の空白のみの値を拒否する。空白集合はPythonの`str.strip()`と同じく`U+0009–000D / U+001C–0020 / U+0085 / U+00A0 / U+1680 / U+2000–200A / U+2028–2029 / U+202F / U+205F / U+3000`を明示し、validatorごとに意味が異なる`\s`に依存しない。識別子とsnapshotの終端には`(?![\s\S])`を使い、末尾LFの直前も許す`$`による受理を避ける。開発依存のDraft 2020-12 validatorでSchema自体、生成JSON、不正文字列のモデルとの拒否一致をCIのpytestで検証する。レポートの必須フィールドは`schema_version / sources / checks / diagnostics`。空一覧も`[]`で残す。未知の版の読込やJSONデシリアライザーは今回実装しない。

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
