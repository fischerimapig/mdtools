"""CLI entry point for glossary."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import lister
from .loader import GlossaryError, load
from .resolver import ResolveError, find_missing, resolve


def _read_input(arg: str) -> str:
    if arg == "-":
        return sys.stdin.read()
    return Path(arg).read_text(encoding="utf-8")


def _write_output(text: str, dest: str | None) -> None:
    if dest:
        Path(dest).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glossary",
        description="Markdown 中の用語・定数マーカーを定義ファイルから解決/一覧化します。",
        epilog=(
            "最小例:\n"
            "  glossary resolve manuscript.md --lang en -f defs.json -o out.md\n"
            "  glossary list -f defs.json\n"
            "\n"
            "対応マーカー (Pandoc bracketed span / fenced div):\n"
            "  []{.term id=unit}                   -> names.<lang>\n"
            "  []{.term id=unit field=description} -> description.<lang>\n"
            "  []{.const id=EMAX_WIDTH}            -> value\n"
            "  []{.symbol id=D}                    -> id (or field=rtl_macro)\n"
            "  ::: {.glossary filter=term}\n"
            "  :::                                  -> 用語表を差し込み\n"
            "\n"
            "よく使う例:\n"
            "  # langfilter -> glossary パイプライン (言語別出力)\n"
            "  langfilter filter --lang en in.qmd | \\\n"
            "    glossary resolve --lang en -f defs.json > out.en.md\n"
            "\n"
            "  # 複数定義ファイルの合成\n"
            "  glossary resolve in.md --lang ja -f terms.json -f consts.yaml\n"
            "\n"
            "  # 一覧 (JSON)\n"
            "  glossary list -f defs.json --kind term --format json\n"
            "\n"
            "  # CI 用: 未定義 ID の検出 (exit code で通知)\n"
            "  glossary verify in.md -f defs.json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_defs(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "-f",
            "--defs",
            action="append",
            required=True,
            metavar="PATH",
            help="定義ファイル (JSON / YAML)。複数回指定で合成可能。",
        )

    p_resolve = sub.add_parser(
        "resolve",
        help="マーカーを定義ファイルで解決して置換出力",
        description="Markdown 内の用語・定数マーカーを定義ファイルで置換します。",
    )
    p_resolve.add_argument(
        "input",
        nargs="?",
        default="-",
        help="入力 Markdown/QMD ファイル。省略または - で stdin。",
    )
    p_resolve.add_argument(
        "--lang",
        choices=["en", "ja"],
        required=True,
        help="用語名や定義文の解決言語。",
    )
    add_defs(p_resolve)
    p_resolve.add_argument(
        "-o",
        "--output",
        default=None,
        help="出力ファイル。未指定時は stdout。",
    )
    p_resolve.add_argument(
        "--on-missing",
        choices=["error", "warn", "keep"],
        default="error",
        help="未定義 ID に遭遇したときの挙動 (既定: error)。",
    )

    p_list = sub.add_parser(
        "list",
        help="登録済みエントリの一覧を出力",
        description="定義ファイルに登録されている用語・定数・記号の一覧を出力します。",
    )
    add_defs(p_list)
    p_list.add_argument(
        "--kind",
        choices=["term", "const", "symbol"],
        default=None,
        help="種別で絞り込み。",
    )
    p_list.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="出力フォーマット (既定: text)。",
    )
    p_list.add_argument(
        "-o",
        "--output",
        default=None,
        help="出力ファイル。未指定時は stdout。",
    )

    p_verify = sub.add_parser(
        "verify",
        help="本文中のマーカーが全て定義済みかチェック",
        description="マーカーの ID が定義ファイルに存在するか検査し、欠落があれば exit 1。",
    )
    p_verify.add_argument(
        "input",
        nargs="?",
        default="-",
        help="入力 Markdown/QMD ファイル。省略または - で stdin。",
    )
    add_defs(p_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        entries = load(args.defs)
    except GlossaryError as exc:
        print(f"glossary: {exc}", file=sys.stderr)
        return 2

    if args.command == "resolve":
        text = _read_input(args.input)
        try:
            out = resolve(text, entries, args.lang, on_missing=args.on_missing)
        except ResolveError as exc:
            print(f"glossary: resolve failed: {exc}", file=sys.stderr)
            return 1
        _write_output(out, args.output)
        return 0

    if args.command == "list":
        selected = lister.filter_entries(entries, args.kind)
        if args.format == "json":
            out = lister.format_json(selected)
        else:
            out = lister.format_text(selected)
        _write_output(out, args.output)
        return 0

    if args.command == "verify":
        text = _read_input(args.input)
        missing = find_missing(text, entries)
        if missing:
            for lineno, eid, marker in missing:
                src = args.input if args.input != "-" else "<stdin>"
                print(f"{src}:{lineno}: undefined id '{eid}' in {marker}", file=sys.stderr)
            print(
                f"glossary: {len(missing)} undefined reference(s)",
                file=sys.stderr,
            )
            return 1
        return 0

    return 1
