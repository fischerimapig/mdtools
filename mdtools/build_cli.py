"""CLI adapter for the staged document build API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from glossary.loader import GlossaryError
from glossary.resolver import ResolveError
from mdtools.build import BuildOptionsError, build_document, validate_build_options
from mdtools.core.io import read_text_or_stdin, write_text_or_stdout


def _stage_suffix(input_arg: str, output_arg: str | None) -> str:
    if output_arg:
        suffix = Path(output_arg).suffix
        if suffix:
            return suffix
    if input_arg != "-":
        suffix = Path(input_arg).suffix
        if suffix and suffix != ".json":
            return suffix
    return ".md"


def _build_parser(prog: str = "mdtools build") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="section 原稿から配布用 Markdown/QMD を段階ビルドします。",
        epilog=(
            "最小例:\n"
            f"  {prog} manuscript_sections/hierarchy.json --lang ja -f defs.yaml -o manuscript.ja.qmd\n"
            "\n"
            "実行順:\n"
            "  1. INPUT が hierarchy.json の場合だけ mdsplit compose\n"
            "  2. --lang en/ja が指定された場合だけ langfilter\n"
            "  3. -f/--defs が指定された場合だけ glossary resolve\n"
            "\n"
            "中間ファイル:\n"
            "  各ステージ後の結果を作業ディレクトリに保存し、次ステージはそのファイルを入力にします。\n"
            "  --work-dir 未指定時は一時ディレクトリを使い、完了後に削除します。\n"
            "\n"
            "よく使う例:\n"
            f"  {prog} doc_sections/hierarchy.json --lang en -f doc/defs.yaml -o doc/en.qmd\n"
            f"  {prog} doc_sections/hierarchy.json --lang ja -f doc/defs.yaml -o doc/ja.qmd --work-dir .build/ja\n"
            f"  {prog} combined.qmd --lang en -o combined.en.qmd\n"
            "\n"
            "README 原典:\n"
            "  README.md「典型的なワークフロー」\n"
            "  README.md「ドキュメント運用ルール（README / --help 同期）」"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input",
        help="入力 hierarchy.json または Markdown/QMD ファイル。- で stdin。",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="最終出力ファイル。未指定時は stdout。",
    )
    parser.add_argument(
        "--source-type",
        choices=["auto", "sections", "markdown"],
        default="auto",
        help="入力種別。auto は hierarchy.json だけ compose 対象にする。",
    )
    parser.add_argument(
        "--base-level",
        type=int,
        default=None,
        help="mdsplit compose 時の見出し基準レベル上書き。",
    )
    parser.add_argument(
        "--lang",
        choices=["en", "ja", "both"],
        default=None,
        help="言語別出力。en/ja のときだけ langfilter を実行し、both/未指定では保持。",
    )
    parser.add_argument(
        "--keep-lang-fences",
        action="store_true",
        help="langfilter 実行時に対象言語ブロックの fenced div マーカー行も残す。",
    )
    parser.add_argument(
        "-f",
        "--defs",
        action="append",
        default=None,
        metavar="PATH",
        help="glossary 定義ファイル。指定時だけ glossary resolve を実行。複数指定可。",
    )
    parser.add_argument(
        "--on-missing",
        choices=["error", "warn", "keep"],
        default="error",
        help="glossary 未定義 ID の扱い (既定: error)。",
    )
    parser.add_argument(
        "--work-dir",
        default=None,
        help="中間ファイルを残す作業ディレクトリ。未指定時は一時ディレクトリ。",
    )
    return parser


def main(argv: list[str] | None = None, *, prog: str = "mdtools build") -> int:
    parser = _build_parser(prog)
    args = parser.parse_args(argv)
    input_path = None if args.input == "-" else args.input
    options = dict(
        source_type=args.source_type, base_level=args.base_level, lang=args.lang,
        keep_lang_fences=args.keep_lang_fences, defs=args.defs,
    )
    try:
        compose_first = validate_build_options(input_path, **options)
    except BuildOptionsError as exc:
        parser.error(str(exc))

    # Keep the original single auto-detection before work-dir setup or stdin.
    options["source_type"] = "sections" if compose_first else "markdown"

    try:
        result = build_document(
            input_path,
            read_input=(lambda: read_text_or_stdin("-")) if input_path is None else None,
            on_missing=args.on_missing, work_dir=args.work_dir,
            suffix=_stage_suffix(args.input, args.output), **options,
        )
        write_text_or_stdout(result, args.output)
    except GlossaryError as exc:
        print(f"mdtools build: {exc}", file=sys.stderr)
        return 2
    except ResolveError as exc:
        print(f"mdtools build: glossary resolve failed: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"mdtools build: {exc}", file=sys.stderr)
        return 1
    return 0
