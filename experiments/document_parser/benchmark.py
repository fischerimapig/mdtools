"""Small reproducible baseline; timings are observations, not CI thresholds."""
from __future__ import annotations

import argparse
import gc
import json
import platform
from statistics import median
from time import perf_counter
import tracemalloc

from mdtools.core.source import SourceSnapshot

from .model import Limits, walk
from .parser import parse_document
from .projection import summarize_requirements


def manuscript(size, kind):
    if kind == "long-line":
        return "x" * (size - 1) + "\n"
    body = "日本語😀éの本文。\n" if kind == "multilingual" else "A short original body.\n"
    unit = "::: {.requirement #REQ-A spec-version=1}\n" + body + ":::\n\n"
    count = max(1, size // len(unit.encode("utf-8")))
    return unit * count


def run(repeats=3, sizes=(102_400, 1_048_576)):
    rows = []
    for kind in ("requirements", "multilingual", "long-line"):
        for size in sizes:
            raw = manuscript(size, kind)
            start = perf_counter()
            source = SourceSnapshot("memory:benchmark", raw)
            snapshot_ms = (perf_counter() - start) * 1000
            parse_ms, projection_ms, bridge_ms = [], [], []
            for _ in range(repeats):
                gc.collect()
                start = perf_counter()
                document = parse_document(source)
                parse_ms.append((perf_counter() - start) * 1000)
                if document.status != "complete":
                    raise RuntimeError(f"benchmark not complete: {document.notices}")
                sample = [node.span for node in walk(document.blocks)][:1000]
                start = perf_counter()
                for span in sample:
                    document.index.span(span)
                bridge_ms.append((perf_counter() - start) * 1000)
                start = perf_counter()
                summary = summarize_requirements(document)
                projection_ms.append((perf_counter() - start) * 1000)
            # Separate run: tracemalloc instrumentation must not pollute timings.
            del document, summary
            gc.collect()
            tracemalloc.start()
            document = parse_document(source)
            parse_peak = tracemalloc.get_traced_memory()[1]
            tracemalloc.reset_peak()
            before_projection = tracemalloc.get_traced_memory()[0]
            summary = summarize_requirements(document)
            projection_extra_peak = max(0, tracemalloc.get_traced_memory()[1] - before_projection)
            tracemalloc.stop()
            rows.append({"kind": kind, "bytes": len(raw.encode("utf-8")),
                         "code_points": len(raw), "repeats": repeats,
                         "snapshot_ms": snapshot_ms,
                         "parse_ms_median": median(parse_ms), "parse_ms_samples": parse_ms,
                         "projection_ms_median": median(projection_ms),
                         "bridge_ms_median": median(bridge_ms), "bridge_calls": len(sample),
                         "parse_peak_bytes": parse_peak,
                         "projection_extra_peak_bytes": projection_extra_peak,
                         "candidates": len(summary.candidates), "status": document.status})
    return {"python": platform.python_version(), "platform": platform.platform(),
            "method": "SourceSnapshot creation separate; parse includes index, block, inline, validation; "
                      "projection separate; bridge is extra sampled conversions; "
                      "memory is Python tracemalloc in an untimed separate run, excludes original snapshot; "
                      "no legacy timing comparison", "limits": vars(Limits()), "measurements": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    print(json.dumps(run(args.repeats), indent=2, ensure_ascii=False))
