
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
