from __future__ import annotations

import argparse
import json

from pathlib import Path

from .inventory import build_inventory
from .rewrite import rewrite_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mdhtml-rewrite",
        description="HTML 混在 Markdown/QMD の調査・整形・画像変換を行うユーティリティ。",
        epilog=(
            "最小例:\n"
            "  mdhtml-rewrite inventory input.md -o inventory.json\n"
            "\n"
            "よく使う例:\n"
            "  mdhtml-rewrite inventory input.md -o inventory.json\n"
            "  mdhtml-rewrite rewrite input.md -o output.qmd --inventory inventory.json --report rewrite_report.json\n"
            "  mdhtml-rewrite convert figures --dry-run\n"
            "  mdhtml-rewrite convert figures --format svg --report convert_svg_report.json\n"
            "  mdhtml-rewrite convert figures --format png --dpi 300 --report convert_png_report.json\n"
            "\n"
            "失敗しやすいケース回避例:\n"
            "  # inventory を先に生成してから rewrite に渡し、判定の揺れを減らす\n"
            "  mdhtml-rewrite inventory input.md -o inventory.json && \\\n"
            "  mdhtml-rewrite rewrite input.md -o output.qmd --inventory inventory.json\n"
            "  # convert は先に --dry-run で対象確認。SVG 優先か PNG+高DPI かを用途で切り替える\n"
            "  mdhtml-rewrite convert figures --dry-run && \\\n"
            "  mdhtml-rewrite convert figures --format svg && \\\n"
            "  mdhtml-rewrite convert figures --format png --dpi 300"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_inv = sub.add_parser(
        "inventory",
        help="要素インベントリ JSON を生成する",
        description="入力 Markdown/QMD 内の HTML 由来要素を集計し、JSON レポートとして出力します。",
    )
    p_inv.add_argument("input", help="入力 Markdown/QMD ファイル。")
    p_inv.add_argument("-o", "--output", required=True, help="インベントリ JSON の出力パス（必須）。")

    p_rw = sub.add_parser(
        "rewrite",
        help="HTML 混在 Markdown/QMD を整形する",
        description="HTML 由来記法を QMD 互換の Markdown に書き換え、必要に応じて処理レポートを出力します。",
    )
    p_rw.add_argument("input", help="入力 Markdown/QMD ファイル。")
    p_rw.add_argument("-o", "--output", required=True, help="整形後 Markdown/QMD の出力パス（必須）。")
    p_rw.add_argument("--inventory", default=None, help="inventory サブコマンドで生成した JSON パス。指定時は集計情報を再利用。")
    p_rw.add_argument("--report", default=None, help="書き換え内容を記録する JSON レポートの出力パス。")
    p_rw.add_argument("--no-prefer-png", action="store_true", help="画像出力で PNG 優先を無効化（既定は PNG 優先）。")

    p_conv = sub.add_parser(
        "convert",
        help="EPS 画像を Web 向け形式へ変換する",
        description="ディレクトリ内の EPS を SVG/PNG に変換し、結果を集計します。",
    )
    p_conv.add_argument("directory", help="EPS ファイルを含む入力ディレクトリ。")
    p_conv.add_argument("--force", action="store_true", help="出力先が存在しても再変換を実行する。")
    p_conv.add_argument("--dry-run", action="store_true", help="変換は行わず、実行予定の処理内容のみ表示する。")
    p_conv.add_argument("--format", choices=["auto", "svg", "png"], default="auto",
                        help="出力形式。既定値 auto は EPS 内容に応じて SVG/PNG を自動選択。")
    p_conv.add_argument("--dpi", type=int, default=150,
                        help="PNG などラスタ変換時の DPI（既定値: 150）。")
    p_conv.add_argument("--report", default=None, help="変換結果レポート JSON の出力パス。")

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
