
IMAX2 コアアーキテクチャ文書化（Phase 0）の基盤ツールとして、日英併記 Markdown から単一言語版を生成する `langfilter` を作成した。その後の `mdtools.core` リファクタで、Markdown スキャンと Pandoc/Quarto 属性処理は共通モジュールへ移した。

要件定義: `docs/IMAX2/core/PHASE0-INFRASTRUCTURE.md` Section 1
受け入れ条件: 同ファイル末尾「Phase 0 の受け入れ条件」langfilter 項
