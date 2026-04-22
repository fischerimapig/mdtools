from __future__ import annotations

import argparse
import json

from pathlib import Path

from .inventory import build_inventory
from .rewrite import rewrite_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mdhtml-rewrite")
    sub = parser.add_subparsers(dest="command", required=True)

    p_inv = sub.add_parser("inventory", help="Create element inventory JSON")
    p_inv.add_argument("input")
    p_inv.add_argument("-o", "--output", required=True)

    p_rw = sub.add_parser("rewrite", help="Rewrite HTML-ish markdown to qmd-friendly markdown")
    p_rw.add_argument("input")
    p_rw.add_argument("-o", "--output", required=True)
    p_rw.add_argument("--inventory", default=None)
    p_rw.add_argument("--report", default=None)
    p_rw.add_argument("--no-prefer-png", action="store_true")

    p_conv = sub.add_parser("convert", help="Convert EPS files to web-friendly formats (SVG/PNG)")
    p_conv.add_argument("directory", help="Directory containing EPS files")
    p_conv.add_argument("--force", action="store_true", help="Re-convert even if target exists")
    p_conv.add_argument("--dry-run", action="store_true", help="Show what would be converted")
    p_conv.add_argument("--format", choices=["auto", "svg", "png"], default="auto",
                        help="Target format (default: auto-detect based on EPS content)")
    p_conv.add_argument("--dpi", type=int, default=150,
                        help="DPI for raster conversion (default: 150)")
    p_conv.add_argument("--report", default=None, help="Write conversion report JSON")

    args = parser.parse_args(argv)

    if args.command == "inventory":
        inv = build_inventory(args.input, output_path=args.output)
        print(json.dumps(inv["counts"], ensure_ascii=False, indent=2))
        return 0

    if args.command == "rewrite":
        rep = rewrite_file(
            input_path=args.input,
            output_path=args.output,
            inventory_path=args.inventory,
            report_path=args.report,
            prefer_png=not args.no_prefer_png,
        )
        print(json.dumps({
            "output": rep["output"],
            "screen_divs_converted": rep["screen_divs_converted"],
            "table_wrappers_converted": rep["table_wrappers_converted"],
        }, ensure_ascii=False, indent=2))
        return 0

    if args.command == "convert":
        from .convert import check_tools, convert_directory, write_report

        tools = check_tools()
        missing = [name for name, path in tools.items() if path is None]
        if missing:
            print(f"Warning: missing tools: {', '.join(missing)}", file=__import__('sys').stderr)
            if not tools.get("gs"):
                print("Error: gs (Ghostscript) is required", file=__import__('sys').stderr)
                return 1

        dir_path = Path(args.directory)
        if not dir_path.is_dir():
            print(f"Error: {args.directory} is not a directory", file=__import__('sys').stderr)
            return 1

        results = convert_directory(
            dir_path,
            force=args.force,
            dry_run=args.dry_run,
            target_format=args.format,
            dpi=args.dpi,
        )

        summary = {
            "total": len(results),
            "converted": sum(1 for r in results if r.status == "converted"),
            "skipped": sum(1 for r in results if r.status == "skipped"),
            "failed": sum(1 for r in results if r.status == "failed"),
            "dry_run": sum(1 for r in results if r.status == "dry_run"),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))

        if args.report:
            write_report(results, args.report)
            print(f"Report written to {args.report}")

        return 1 if summary["failed"] > 0 else 0

    return 1
