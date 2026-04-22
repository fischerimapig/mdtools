"""Unified entry point for mdtools."""

from __future__ import annotations

import sys

_TOOLS: dict[str, tuple[str, str]] = {
    "mdsplit":    ("mdsplit.cli",        "Decompose and reassemble Markdown documents"),
    "langfilter": ("langfilter.cli",     "Filter bilingual Markdown by language"),
    "rewrite":    ("mdhtml_rewrite.cli", "Rewrite HTML-ish Markdown to QMD-friendly format"),
}


def _print_help(file=None) -> None:
    if file is None:
        file = sys.stdout
    tool_list = ",".join(_TOOLS)
    print(f"usage: mdtools [-h] [--version] {{{tool_list}}} ...", file=file)
    print("", file=file)
    print("Markdown tools collection.", file=file)
    print("", file=file)
    print("tools:", file=file)
    for name, (_, desc) in _TOOLS.items():
        print(f"  {name:<12} {desc}", file=file)
    print("", file=file)
    print("options:", file=file)
    print("  -h, --help   show this help message and exit", file=file)
    print("  --version    show version and exit", file=file)


def main() -> None:
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
        _print_help(file=sys.stderr)
        sys.exit(1)

    import importlib
    mod = importlib.import_module(_TOOLS[tool][0])
    sys.exit(mod.main(argv[1:]))
