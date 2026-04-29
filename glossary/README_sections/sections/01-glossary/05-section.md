
```yaml
# defs.yaml (同等の JSON でも可)
entries:
  - id: unit                # 必須: 一意の識別子
    kind: term              # 必須: term | const | symbol
    names:                  # term: 言語別名称
      en: "Processing Unit"
      ja: "プロセッシングユニット"
    abbr: "PU"              # term: 略称 (field=abbr)
    aliases:                # 参考情報 (検索等の用途, 現状は置換には非使用)
      en: [PU]
      ja: [ユニット]
    description:
      en: "One compute element in the D x 4 array."
      ja: "D x 4 アレイを構成する計算要素。"
    source: "sections/01-overview/01-array-topology.md"

  - id: EMAX_WIDTH
    kind: const
    value: 4                # const: 値 (数値・文字列・式の文字列表現)
    description:
      en: "Number of columns per row."
      ja: "1 行あたりの列数。"
    source: "legacy/core/common.vh:43"

  - id: D
    kind: symbol
    rtl_macro: EMAX_DEPTH   # symbol: 外部参照 (field=rtl_macro で展開)
    description:
      en: "Number of logical rows in the unit array."
      ja: "ユニットアレイの論理行数。"
```

- `-f` は複数回指定可。後勝ちでマージし、id 衝突時は警告を stderr に出す。
- `source` と `aliases` は任意。
- YAML 入力は `pyyaml` が必要 (optional dep)。JSON のみ使う場合は追加依存不要。
