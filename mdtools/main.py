"""Unified entry point for mdtools."""

from __future__ import annotations

import sys

_TOOLS: dict[str, tuple[str, str]] = {
    "mdsplit":    ("mdsplit.cli",        "Decompose and reassemble Markdown documents"),
    "langfilter": ("langfilter.cli",     "Filter bilingual Markdown by language"),
    "rewrite":    ("mdhtml_rewrite.cli", "Rewrite HTML-ish Markdown to QMD-friendly format (mdhtml-rewrite)"),
    "glossary":   ("glossary.cli",       "Resolve term/constant markers and list registered entries"),
}


def _print_help(file=None) -> None:
    if file is None:
        file = sys.stdout
    tool_list = ",".join(_TOOLS)
    print(f"usage: mdtools [-h] [--version] {{{tool_list}}} ...", file=file)
    print("", file=file)
    print("Markdown ドキュメント処理向けのツール群です。", file=file)
    print("通常は mdtools <tool> から使います。個別コマンドも互換入口として利用できます。", file=file)
    print("", file=file)
    print("tools:", file=file)
    for name, (_, desc) in _TOOLS.items():
        print(f"  {name:<12} {desc}", file=file)
    print("", file=file)
    print("tool details:", file=file)
    print("  mdsplit", file=file)
    print("    概要: Markdown を章・セクション単位で分割/再結合します。", file=file)
    print("    代表的な利用シーン: 長文ドキュメントをレビュー単位で小さく分けたいとき。", file=file)
    print("    次のヘルプ: mdtools mdsplit --help", file=file)
    print("", file=file)
    print("  langfilter", file=file)
    print("    概要: バイリンガル Markdown から必要言語の行だけを抽出します。", file=file)
    print("    代表的な利用シーン: 日英併記の原稿から配布用に片言語版を作るとき。", file=file)
    print("    次のヘルプ: mdtools langfilter --help", file=file)
    print("", file=file)
    print("  rewrite", file=file)
    print("    概要: mdhtml-rewrite を mdtools から呼び出し、HTML 風 Markdown を QMD 向け形式へ変換します。", file=file)
    print("    代表的な利用シーン: 既存 Markdown を Quarto 用に整形したいとき。", file=file)
    print("    次のヘルプ: mdtools rewrite --help", file=file)
    print("", file=file)
    print("  glossary", file=file)
    print("    概要: 用語・定数マーカーを定義ファイルから解決し、一覧表も出力します。", file=file)
    print("    代表的な利用シーン: langfilter で言語別出力を作ったあとに", file=file)
    print("      []{.term id=...} 等のマーカーを差し込みたいとき。", file=file)
    print("    次のヘルプ: mdtools glossary --help", file=file)
    print("", file=file)
    print("基本形:", file=file)
    print("  mdtools <tool> <subcommand> --help", file=file)
    print("  例: mdtools mdsplit decompose --help", file=file)
    print("", file=file)
    print("互換入口:", file=file)
    print("  mdsplit / langfilter / mdhtml-rewrite / glossary", file=file)
    print("", file=file)
    print("詳細:", file=file)
    print("  README.md「使い方」「ドキュメント運用ルール（README / --help 同期）」", file=file)
    print("", file=file)
    print("options:", file=file)
    print("  --version    バージョンを表示して終了", file=file)
    print("  -h, --help   このヘルプを表示して終了", file=file)


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help"):
        _print_help()
        sys.exit(0)

    if argv[0] in ("-V", "--version"):
        print("mdtools 0.1.0")
        sys.exit(0)

    tool = argv[0]
    if tool not in _TOOLS:
        print(f"mdtools: unknown tool '{tool}'", file=sys.stderr)
        print(f"hint: available tools: {', '.join(_TOOLS)}", file=sys.stderr)
        print("hint: try `mdtools --help` or `mdtools <tool> --help`", file=sys.stderr)
        _print_help(file=sys.stderr)
        sys.exit(1)

    import importlib
    mod = importlib.import_module(_TOOLS[tool][0])
    sys.exit(mod.main(argv[1:], prog=f"mdtools {tool}"))
