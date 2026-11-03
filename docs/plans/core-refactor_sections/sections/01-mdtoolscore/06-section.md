
- help epilogやargparse設定の共通化（必要ならCLI側に置き、coreへ処理からの逆依存を作らない）
- `mdtools.core.tree`: `mdsplit` の tree traversal helper の切り出し
- `mdtools.core.html`: `mdhtml-rewrite` の HTML 正規表現と model helper の整理

これらは今回の core refactor の範囲外です。公開 CLI と既存ファイル形式の互換性を優先して、必要になった段階で小さく切り出します。
