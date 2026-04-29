"""CLI interface for mdsplit."""

from __future__ import annotations

import argparse

from mdtools.core.io import write_text_or_stdout

from .compose import compose
from .decompose import decompose


def main(argv: list[str] | None = None, *, prog: str = "mdsplit") -> int:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Markdown/QMD ドキュメントを分割・再構成するツール。",
        epilog=(
            "最小例:\n"
            f"  {prog} decompose manuscript.qmd\n"
            "\n"
            "よく使う例:\n"
            f"  {prog} decompose manuscript.qmd -o manuscript_sections\n"
            f"  {prog} compose manuscript_sections/hierarchy.json -o rebuilt.qmd\n"
            f"  {prog} compose manuscript_sections/hierarchy.json > rebuilt.qmd\n"
            f"  {prog} verify manuscript_sections/hierarchy.json\n"
            "\n"
            "README 原典:\n"
            "  README.md「使い方」\n"
            "  mdsplit/README.md「主要コマンド例（--help の epilog と同期）」"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # decompose
    p_decompose = subparsers.add_parser(
        "decompose",
        help="Markdown/QMD をセクション群へ分割する",
        description="入力の Markdown/QMD を見出し構造ごとに分割し、hierarchy.json を生成します。",
    )
    p_decompose.add_argument("input", help="入力 Markdown/QMD ファイル（.md / .qmd）。")
    p_decompose.add_argument(
        "-o", "--output-dir",
        help="分割結果の出力先ディレクトリ。未指定時は <入力名>_sections/ を自動作成。",
    )
    p_decompose.add_argument(
        "--flat", action="store_true",
        help="階層ディレクトリではなくフラット構造で出力（ファイル配置のみ変更）。",
    )

    # compose
    p_compose = subparsers.add_parser(
        "compose",
        help="hierarchy.json から Markdown/QMD を再構成する",
        description="decompose で作成した hierarchy.json とセクション群から文書を再構成します。",
    )
    p_compose.add_argument("hierarchy", help="入力 hierarchy.json のパス。")
    p_compose.add_argument(
        "-o", "--output",
        help="再構成後の出力ファイルパス。未指定時は標準出力へ書き出し。",
    )
    p_compose.add_argument(
        "--base-level", type=int, default=None,
        help="見出しの基準レベルを上書き（例: 2 で ## から開始）。",
    )

    # verify
    p_verify = subparsers.add_parser(
        "verify",
        help="hierarchy.json の参照ファイル存在を検証する",
        description="hierarchy.json が参照するセクション Markdown/QMD ファイルの存在を検証します。",
    )
    p_verify.add_argument("hierarchy", help="検証対象の hierarchy.json パス。")

    args = parser.parse_args(argv)

    if args.command == "decompose":
        doc_tree = decompose(args.input, args.output_dir, flat=args.flat)
        print(f"Decomposed into {_count_sections(doc_tree.sections)} sections.")
        print(f"Hierarchy saved to: {args.output_dir or 'auto'}/hierarchy.json")
        return 0

    elif args.command == "compose":
        result = compose(args.hierarchy, args.output, base_level=args.base_level)
        if not args.output:
            write_text_or_stdout(result, None)
        else:
            print(f"Composed document written to: {args.output}")
        return 0

    elif args.command == "verify":
        return _verify(args.hierarchy)

    return 1


def _count_sections(sections) -> int:
    count = len(sections)
    for s in sections:
        count += _count_sections(s.children)
    return count


def _verify(hierarchy_path: str) -> int:
    from pathlib import Path
    from .schema import DocumentTree

    path = Path(hierarchy_path)
    base_dir = path.parent
    doc_tree = DocumentTree.load(path)

    missing = []
    _check_files(doc_tree.sections, base_dir, missing)

    # Check preamble
    preamble_file = doc_tree.metadata.get("preamble_file")
    if preamble_file and not (base_dir / preamble_file).exists():
        missing.append(preamble_file)

    if missing:
        print(f"Missing {len(missing)} file(s):")
        for f in missing:
            print(f"  - {f}")
        return 1
    else:
        total = _count_sections(doc_tree.sections)
        print(f"All {total} section files verified OK.")
        return 0


def _check_files(sections, base_dir, missing: list) -> None:
    from pathlib import Path
    for s in sections:
        if not (base_dir / s.file).exists():
            missing.append(s.file)
        _check_files(s.children, base_dir, missing)
