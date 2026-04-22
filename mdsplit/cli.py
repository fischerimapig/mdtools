"""CLI interface for mdsplit."""

from __future__ import annotations

import argparse
import sys

from .compose import compose
from .decompose import decompose


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mdsplit",
        description="Decompose and reassemble Markdown/QMD documents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # decompose
    p_decompose = subparsers.add_parser(
        "decompose",
        help="Split a markdown file into sections and hierarchy JSON.",
    )
    p_decompose.add_argument("input", help="Input .md or .qmd file")
    p_decompose.add_argument(
        "-o", "--output-dir",
        help="Output directory (default: <input_stem>_sections/)",
    )
    p_decompose.add_argument(
        "--flat", action="store_true",
        help="Use flat directory structure instead of nested",
    )

    # compose
    p_compose = subparsers.add_parser(
        "compose",
        help="Reassemble a markdown file from hierarchy JSON.",
    )
    p_compose.add_argument("hierarchy", help="Path to hierarchy.json")
    p_compose.add_argument(
        "-o", "--output",
        help="Output file path (default: stdout)",
    )
    p_compose.add_argument(
        "--base-level", type=int, default=None,
        help="Override base heading level",
    )

    # verify
    p_verify = subparsers.add_parser(
        "verify",
        help="Check that all section files referenced in hierarchy.json exist.",
    )
    p_verify.add_argument("hierarchy", help="Path to hierarchy.json")

    args = parser.parse_args(argv)

    if args.command == "decompose":
        doc_tree = decompose(args.input, args.output_dir, flat=args.flat)
        print(f"Decomposed into {_count_sections(doc_tree.sections)} sections.")
        print(f"Hierarchy saved to: {args.output_dir or 'auto'}/hierarchy.json")
        return 0

    elif args.command == "compose":
        result = compose(args.hierarchy, args.output, base_level=args.base_level)
        if not args.output:
            sys.stdout.write(result)
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
