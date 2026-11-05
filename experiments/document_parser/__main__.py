"""python -m experiments.document_parser INPUT.md [--trace]."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from mdtools.core.source import SourceSnapshot

from .dump import document_dict
from .model import Limits, PROFILE
from .parser import parse_document
from .projection import summary_dict


def main(argv=None):
    cli = argparse.ArgumentParser(description="Isolated document structure and requirement candidate review")
    cli.add_argument("input", type=Path)
    cli.add_argument("--trace", action="store_true", help="include original slices in the structure dump")
    cli.add_argument("--profile", default=PROFILE)
    cli.add_argument("--max-bytes", type=int, default=Limits().max_bytes)
    cli.add_argument("--max-nodes", type=int, default=Limits().max_nodes)
    cli.add_argument("--max-depth", type=int, default=Limits().max_depth)
    args = cli.parse_args(argv)
    try:
        limits = Limits(max_bytes=args.max_bytes, max_nodes=args.max_nodes, max_depth=args.max_depth)
        source = SourceSnapshot.from_path(args.input)
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"status": "failed", "stage": "input", "reason": f"{type(exc).__name__}: {exc}"},
                         ensure_ascii=False), file=sys.stderr)
        return 3
    document = parse_document(source, profile=args.profile, limits=limits)
    print(json.dumps({"document": document_dict(document, trace=args.trace),
                      "review": summary_dict(document)}, ensure_ascii=False, indent=2))
    return 0 if document.status == "complete" else 3 if document.status == "failed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
