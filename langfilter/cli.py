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
        description="Filter bilingual Markdown by language blocks.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_filter = sub.add_parser(
        "filter",
        help="Filter fenced div language blocks.",
    )
    p_filter.add_argument(
        "input",
        nargs="?",
        default="-",
        help="Input file (default: stdin).",
    )
    p_filter.add_argument(
        "--lang",
        choices=["en", "ja", "both"],
        default="both",
        help="Target language (default: both).",
    )
    p_filter.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output file (default: stdout).",
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
