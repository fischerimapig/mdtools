"""CLI entry point for langfilter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .filter import filter_lang


def main(argv: list[str] | None = None) -> int:
    """Run the langfilter CLI.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(
        prog="langfilter",
        description="言語ブロック付き Markdown/QMD から必要な言語だけを抽出します。",
        epilog=(
            "最小例:\n"
            "  langfilter filter manuscript.qmd --lang ja -o manuscript.ja.qmd\n"
            "\n"
            "よく使う例:\n"
            "  cat manuscript.md | langfilter filter --lang en > manuscript.en.md\n"
            "  langfilter filter --lang en manuscript.qmd -o manuscript.en.qmd\n"
            "  langfilter filter --lang ja manuscript.qmd -o manuscript.ja.qmd\n"
            "  langfilter filter --lang both manuscript.qmd -o manuscript.both.qmd\n"
            "\n"
            "失敗しやすいケース回避例:\n"
            "  # パイプ入力時に input 引数は省略可能（- 扱い）\n"
            "  cat bilingual.md | langfilter filter --lang ja > ja.md\n"
            "  # --lang を切り替えて出力差分を比較\n"
            "  langfilter filter manuscript.qmd --lang en > /tmp/en.md && \\\n"
            "  langfilter filter manuscript.qmd --lang ja > /tmp/ja.md && \\\n"
            "  langfilter filter manuscript.qmd --lang both > /tmp/both.md"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_filter = sub.add_parser(
        "filter",
        help="言語ブロックを抽出・除外する",
        description="fenced div の言語ブロックを判定し、指定した言語の本文のみを出力します。",
    )
    p_filter.add_argument(
        "input",
        nargs="?",
        default="-",
        help="入力 Markdown/QMD ファイル。省略または - 指定時は標準入力を読み取る。",
    )
    p_filter.add_argument(
        "--lang",
        choices=["en", "ja", "both"],
        default="both",
        help="出力に残す言語（en/ja/both）。既定値 both は原文を維持。",
    )
    p_filter.add_argument(
        "-o",
        "--output",
        default=None,
        help="出力ファイルパス。未指定時は標準出力へ書き出し。",
    )

    args = parser.parse_args(argv)

    if args.command == "filter":
        # Read input
        if args.input == "-":
            text = sys.stdin.read()
        else:
            text = Path(args.input).read_text(encoding="utf-8")

        # Filter
        result = filter_lang(text, args.lang)

        # Write output
        if args.output:
            Path(args.output).write_text(result, encoding="utf-8")
        else:
            sys.stdout.write(result)

        return 0

    return 1
