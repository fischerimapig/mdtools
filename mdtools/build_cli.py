"""Official staged document build command."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from glossary.loader import GlossaryError, load
from glossary.resolver import ResolveError, resolve
from langfilter.filter import filter_lang
from mdsplit.compose import compose

from mdtools.core.io import read_text_or_stdin, write_text_or_stdout


@contextmanager
def _build_work_dir(path: str | None) -> Iterator[Path]:
    if path:
        work_dir = Path(path)
        work_dir.mkdir(parents=True, exist_ok=True)
        yield work_dir
        return

    with tempfile.TemporaryDirectory(prefix="mdtools-build-") as tmp:
        yield Path(tmp)


def _looks_like_hierarchy_json(path: Path) -> bool:
    if path.name == "hierarchy.json":
        return True
    if path.suffix.lower() != ".json":
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(data, dict) and isinstance(data.get("sections"), list)


def _should_compose(input_arg: str, source_type: str) -> bool:
    if input_arg == "-":
        return False
    if source_type == "sections":
        return True
    if source_type == "markdown":
        return False
    return _looks_like_hierarchy_json(Path(input_arg))


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


def _write_stage(
    work_dir: Path,
    index: int,
    name: str,
    suffix: str,
    text: str,
) -> Path:
    path = work_dir / f"{index:02d}-{name}{suffix}"
    path.write_text(text, encoding="utf-8")
    return path


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

    compose_first = _should_compose(args.input, args.source_type)
    run_langfilter = args.lang in ("en", "ja")
    run_glossary = bool(args.defs)

    if args.base_level is not None and not compose_first:
        parser.error("--base-level can only be used when INPUT is hierarchy.json")
    if args.keep_lang_fences and not run_langfilter:
        parser.error("--keep-lang-fences requires --lang en or --lang ja")
    if run_glossary and args.lang not in ("en", "ja"):
        parser.error("-f/--defs requires --lang en or --lang ja")

    suffix = _stage_suffix(args.input, args.output)
    current_path: Path | None = None
    current_text: str | None = None

    def read_current() -> str:
        if current_path is not None:
            return current_path.read_text(encoding="utf-8")
        if current_text is not None:
            return current_text
        return read_text_or_stdin(args.input)

    try:
        with _build_work_dir(args.work_dir) as work_dir:
            stage_index = 1

            if compose_first:
                current_text = None
                composed = compose(args.input, base_level=args.base_level)
                current_path = _write_stage(
                    work_dir, stage_index, "compose", suffix, composed
                )
                stage_index += 1
            elif args.input == "-":
                current_text = read_text_or_stdin("-")
            else:
                current_path = Path(args.input)

            if run_langfilter:
                filtered = filter_lang(
                    read_current(),
                    args.lang,
                    keep_fences=args.keep_lang_fences,
                )
                current_path = _write_stage(
                    work_dir, stage_index, "langfilter", suffix, filtered
                )
                current_text = None
                stage_index += 1

            if run_glossary:
                try:
                    entries = load(args.defs)
                except GlossaryError as exc:
                    print(f"mdtools build: {exc}", file=sys.stderr)
                    return 2
                try:
                    resolved = resolve(
                        read_current(),
                        entries,
                        args.lang,
                        on_missing=args.on_missing,
                    )
                except ResolveError as exc:
                    print(
                        f"mdtools build: glossary resolve failed: {exc}",
                        file=sys.stderr,
                    )
                    return 1
                current_path = _write_stage(
                    work_dir, stage_index, "glossary", suffix, resolved
                )
                current_text = None

            write_text_or_stdout(read_current(), args.output)
    except OSError as exc:
        print(f"mdtools build: {exc}", file=sys.stderr)
        return 1

    return 0
