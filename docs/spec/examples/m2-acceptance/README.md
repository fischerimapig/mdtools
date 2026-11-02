# M2の複数文書・section利用例

[受け入れ条件・コマンド・テスト対応表](../../m2-acceptance.md)を参照する。

mdtools.tomlはexamples.md、manual_sectionsの原典、既存model-contract/normal.mdを登録し、model-contractの仕様定義とglossaryを一度ずつ共有する。rootは親のexamplesディレクトリ。manual.mdは生成物であり解析の第二の入力ではない。

```bash
mdtools spec index --project docs/spec/examples/m2-acceptance/mdtools.toml --format json
mdtools spec show REQ-SECTION --project docs/spec/examples/m2-acceptance/mdtools.toml
```

3要件・2モデルを取得し、M2の構造・宣言・参照検査は成功する。REQ-SECTIONの日英本文は言語抽出前の状態で保持する。REQ-DETAILの自己参照・相互参照から論理矛盾は推定しない。examples.mdの説明用構文は要件0件。式・論理は理由付きnot-runである。

編集はmanual_sectionsの原稿とhierarchyで行い、canonicalを再生成する。

```bash
mdtools mdsplit compose docs/spec/examples/m2-acceptance/manual_sections/hierarchy.json -o docs/spec/examples/m2-acceptance/manual.md
mdtools mdsplit verify docs/spec/examples/m2-acceptance/manual_sections/hierarchy.json
```
