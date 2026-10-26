
M1 / #23は`mdtools.workspace.load_workspace(config_path)`を内部APIとして提供する。設定はUTF-8のTOMLとし、整数の`version = 1`を必須とする。契約版や共有定義版とは独立した版であり、未知の版、未知のフィールド、必須値の欠落、値の型の不一致、TOMLの重複キーを拒否する。暗黙の設定探索やディレクトリ走査は行わない。既存CLIの設定や終了コードは変更せず、新しい検査CLIもこの段階では追加しない。

```toml
version = 1
root = "."
generated = ["build/manual.en.qmd"]

[[documents]]
kind = "markdown"
path = "guidance.md"

[[documents]]
kind = "hierarchy"
path = "manual_sections/hierarchy.json"
canonical = "manual.qmd"

[[definitions]]
kind = "spec"
path = "shared/definitions.json"

[[definitions]]
kind = "glossary"
path = "shared/glossary.yaml"
```

| 設定 | 契約v1 |
|------|--------|
| `version` | 必須。Booleanや文字列ではなく整数`1` |
| `root` | 省略時は`"."`。設定ファイルの所在ディレクトリを基準に解決する、存在するディレクトリ |
| `documents` | 必須かつ1件以上の配列。登録順が文書順。各要素は`kind`と`path`を必須とする |
| `kind = "markdown"` | 単一の`.md`/`.qmd`原稿。複数登録すれば複数文書になる。`canonical`は指定不可 |
| `kind = "hierarchy"` | 既存DocumentTree形式のJSON。`canonical`を必須とし、その文書から生成するMarkdown/QMDの出力先を明示する |
| `definitions` | 省略時は空配列。各要素は`kind = "spec"`または`"glossary"`と`path`を必須とする。JSON/YAML/YMLを登録順に保持する |
| `generated` | 省略時は空配列。canonical以外の言語別配布物・生成IR等をパスの配列で明示する。canonicalをここへ再登録しない |

`root`以外のWorkspace設定内のパスは、すべて解決済みの`root`を基準にする。hierarchy内の`metadata.preamble_file`と各sectionの`file`だけは、そのhierarchyファイルのsymlink解決後の所在ディレクトリを基準にする。設定ファイル自体もsymlink解決後の所在ディレクトリからrootを解決する。絶対パスも受け付けるが、入力・生成物ともに解決後に`root`の内側でなければならない。`..`はこの範囲内で許可する。設定ファイルの所在ディレクトリはrootの外側でもよい。

パスはsymlinkと`.`/`..`を解決した絶対パスで保持する。環境変数、`~`、globを展開しない。設定ファイルの引数が相対パスの場合に限り、呼出時のCWDを基準に設定ファイル自体を探す。設定内のパスの意味は、以後のCWD変更で変わらない。サンプルは[キャンセル要件のmdtools.toml](examples/cancellation/mdtools.toml)を参照。

生成物の識別は`canonical`と`generated`への明示登録を根拠にする。hierarchyの`source_file`は従来の文書メタデータとして保持するが、パス解決・入力選択・出力先推定には使用しない。同名ファイルを探すこともしない。実際に別の場所へcompose/buildした配布物も、入力との衝突を検査するには`generated`に登録する。未登録ファイルの役割を内容やファイル名から推測することはしない。

hierarchyは既存の`DocumentTree`へ読み込む。`source_file`（文字列）、`base_level`（整数）、`metadata`（object）、`sections`（配列）は既存と同じ省略値を使う。sectionには`title`（文字列）、`file`（空でない文字列）、`order`（整数）が必須であり、`children`は省略時空配列とする。未知のhierarchy/sectionフィールド、JSONの重複キー、不正な構造はエラーとする。任意のmetadataは保持し、`front_matter`があれば文字列、`preamble_file`があれば空でない文字列を要求する。この検証はWorkspace入口で行い、既存mdsplitの読み込み方は変更しない。

本文の解析対象は、Workspaceの文書登録順に、単一原稿ならそのファイル、hierarchyならpreambleを先頭に置き、各兄弟の`order`で安定ソートした深さ優先のsection順に並べる。`order`が同じ場合はJSON配列内の順序を保つため、既存composeの順序と一致する。空のpreambleやsectionも参照されていれば対象に含める。未参照ファイル、hierarchy JSON、front matter、canonical、配布物は本文対象に加えない。front matterを含むメタデータは`DocumentInput.tree`のDocumentTreeに保持する。

未存在入力、通常ファイルでない入力、用途に合わない拡張子、解決ルート外の参照を拒否する。登録したhierarchy・preamble・section・単一原稿・共有定義・生成物を横断し、正規化パス、存在するファイルのデバイス番号とinodeで重複を検出する。symlinkやhard linkによる別名登録も対象とする。同一sectionの複数回参照や、共有定義のspec/glossary二重登録も後勝ち・黙った重複除去にしない。すべての生成物を入力より先に予約するため、canonicalと原稿の衝突は文書の登録順やcanonicalの存在有無に左右されない。生成物自体は未生成でもよく、読み込み時にディレクトリやファイルを作成しない。

APIの戻り値`Workspace`は`version`、`config_path`、`root`、`documents`、`definitions`、`generated`、`analysis_files`を持つ。各一覧はtuple、各パスは解決済みの`pathlib.Path`である。`documents`の要素`DocumentInput`は`kind`、`path`、hierarchyの場合の`canonical`と`tree`を持つ。`definitions`の要素`DefinitionInput`は`kind`と`path`を持つ。`generated`は文書登録順のcanonicalに設定の`generated`を続けた一覧、`analysis_files`は上記の順序の本文原稿パス一覧とする。共有定義は本文と混ぜず、`definitions`から別途取得する。定義の内容解析・名前衝突検査はM2の責務であり、YAML登録だけでPyYAMLを要求しない。langfilterやglossary置換も実行しない。

```python
from mdtools.workspace import WorkspaceError, load_workspace

workspace = load_workspace("docs/spec/examples/cancellation/mdtools.toml")
for path in workspace.analysis_files:
    print(path.relative_to(workspace.root).as_posix())
# cancel-allow.md / cancel-deny.md / guidance.md の順に各行を出力する。
```

異常時は`WorkspaceError(ValueError)`を送出し、部分的な一覧を返さない。`code`、`path`と説明文字列を持つWorkspace専用のエラーであり、#24の出典範囲や#25の共通診断・JSON出力は実装しない。同じ設定・ファイル状態に対して、設定検証、生成物予約、文書とその参照、共有定義の順で最初の異常を返す。

| エラーコード | 意味 |
|--------------|------|
| `workspace.invalid-config` | TOML、必須フィールド、未知フィールドや値の型が不正 |
| `workspace.unsupported-version` | 対応しない設定版（整数1以外） |
| `workspace.invalid-path` | 不正なパス文字列や解決不能なパス |
| `workspace.outside-root` | symlink解決後のパスがroot外 |
| `workspace.missing-file` / `workspace.not-file` / `workspace.not-directory` | 必要な入力・rootが存在しない、または期待するファイル種別でない |
| `workspace.invalid-extension` | 入力の用途またはcanonicalの拡張子が不正 |
| `workspace.invalid-hierarchy` | hierarchyのJSON・重複キー・構造が不正 |
| `workspace.duplicate-input` | 同じ実体の複数登録（生成物同士を含む） |
| `workspace.generated-input` | 生成物を原典またはhierarchyとしても登録している |
| `workspace.read-error` | 設定・hierarchyの読み込み、ファイル情報取得等のI/Oエラー |

このAPIはファイル登録と選択時点の検証であり、入力snapshotや内容hashを固定するものではない。後の読み込みまでのファイル変更・symlink差し替えは別途出典/snapshot基盤で扱う。診断0件を仕様内容の妥当性や検査成功とは表示しない。
