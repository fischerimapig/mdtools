from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal, Optional

from .model import ConversionResult

# ---------------------------------------------------------------------------
# External tool detection
# ---------------------------------------------------------------------------

def check_tools() -> dict[str, Optional[str]]:
    """Return paths for external conversion tools (None if missing)."""
    return {
        "gs": shutil.which("gs"),
        "dvisvgm": shutil.which("dvisvgm"),
    }


# ---------------------------------------------------------------------------
# EPS type detection
# ---------------------------------------------------------------------------

_RASTER_CREATORS = {"pnmtops", "imagemagick"}


def detect_eps_type(eps_path: Path) -> Literal["vector", "raster"]:
    """Classify an EPS file as vector or raster based on its Creator header."""
    with open(eps_path, "rb") as f:
        for _ in range(15):
            line = f.readline()
            if not line:
                break
            try:
                text = line.decode("ascii", errors="ignore")
            except Exception:
                continue
            if text.startswith("%%Creator:"):
                creator = text.split(":", 1)[1].strip().lower()
                if any(rc in creator for rc in _RASTER_CREATORS):
                    return "raster"
                return "vector"
    return "vector"  # default to vector if no Creator found


# ---------------------------------------------------------------------------
# Single-file conversion
# ---------------------------------------------------------------------------

_SUBPROCESS_TIMEOUT = 300  # seconds


def _run(cmd: list[str], timeout: int = _SUBPROCESS_TIMEOUT) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def _summarize_process_output(r: subprocess.CompletedProcess[bytes], limit: int = 240) -> str:
    """Return a compact single-string summary from a subprocess result."""
    chunks: list[str] = []
    for stream in (r.stderr, r.stdout):
        if not stream:
            continue
        text = stream.decode(errors="replace").strip()
        if text:
            chunks.append(text)

    if not chunks:
        return "no output"

    text = "\n".join(chunks)
    if len(text) > limit:
        text = text[:limit].rstrip() + "..."
    return text


def _convert_vector_to_svg(eps_path: Path, svg_path: Path, tools: dict[str, Optional[str]]) -> Optional[str]:
    """Convert a vector EPS to SVG.  Returns error string or None on success."""
    dvisvgm = tools.get("dvisvgm")
    if dvisvgm:
        r = _run([dvisvgm, "--eps", "--output=%s" % str(svg_path), str(eps_path)])
        if r.returncode == 0 and svg_path.exists():
            return None
        return f"dvisvgm failed (rc={r.returncode}): {_summarize_process_output(r)}"

    return "dvisvgm not found"


def _convert_raster_to_png(eps_path: Path, png_path: Path, tools: dict[str, Optional[str]], dpi: int = 150) -> Optional[str]:
    """Convert a raster EPS to PNG via Ghostscript.  Returns error string or None."""
    gs = tools.get("gs")
    if not gs:
        return "gs (Ghostscript) not found"

    r = _run([
        gs, "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER",
        "-sDEVICE=png16m",
        f"-r{dpi}",
        f"-sOutputFile={png_path}",
        str(eps_path),
    ])
    if r.returncode == 0 and png_path.exists():
        return None
    return f"gs failed (rc={r.returncode}): {_summarize_process_output(r)}"


def convert_single(
    eps_path: Path,
    *,
    force: bool = False,
    target_format: str = "auto",
    dpi: int = 150,
    tools: Optional[dict[str, Optional[str]]] = None,
) -> ConversionResult:
    """Convert a single EPS file.  Returns a ConversionResult."""
    if tools is None:
        tools = check_tools()

    eps_type = detect_eps_type(eps_path)

    # Determine target format
    if target_format == "auto":
        fmt: Literal["svg", "png"] = "svg" if eps_type == "vector" and tools.get("dvisvgm") else "png"
    else:
        fmt = "svg" if target_format == "svg" else "png"

    target_path = eps_path.with_suffix(f".{fmt}")

    # Skip if target already exists and is newer
    if not force and target_path.exists():
        if target_path.stat().st_mtime >= eps_path.stat().st_mtime:
            return ConversionResult(
                source=str(eps_path),
                target=str(target_path),
                eps_type=eps_type,
                target_format=fmt,
                status="skipped",
            )

    # Convert
    if fmt == "svg":
        svg_err = _convert_vector_to_svg(eps_path, target_path, tools)
        if svg_err is None:
            err = None
        elif target_format == "auto" and tools.get("gs"):
            png_path = target_path.with_suffix(".png")
            png_err = _convert_raster_to_png(eps_path, png_path, tools, dpi=dpi)
            if png_err is None:
                return ConversionResult(
                    source=str(eps_path),
                    target=str(png_path),
                    eps_type=eps_type,
                    target_format="png",
                    status="converted",
                    fallback_from="svg",
                    warning=svg_err,
                )
            err = f"{svg_err}; fallback to PNG failed: {png_err}"
        else:
            err = svg_err
    else:
        err = _convert_raster_to_png(eps_path, target_path, tools, dpi=dpi)

    if err:
        return ConversionResult(
            source=str(eps_path),
            target=str(target_path),
            eps_type=eps_type,
            target_format=fmt,
            status="failed",
            error=err,
        )

    return ConversionResult(
        source=str(eps_path),
        target=str(target_path),
        eps_type=eps_type,
        target_format=fmt,
        status="converted",
    )


# ---------------------------------------------------------------------------
# Directory-level conversion
# ---------------------------------------------------------------------------

def convert_directory(
    dir_path: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
    target_format: str = "auto",
    dpi: int = 150,
) -> list[ConversionResult]:
    """Convert all EPS files in *dir_path*.  Returns list of results."""
    tools = check_tools()
    eps_files = sorted(dir_path.glob("*.eps"))

    if not eps_files:
        print(f"No .eps files found in {dir_path}", file=sys.stderr)
        return []

    results: list[ConversionResult] = []
    for eps_path in eps_files:
        eps_type = detect_eps_type(eps_path)
        if target_format == "auto":
            fmt = "svg" if eps_type == "vector" and tools.get("dvisvgm") else "png"
        elif target_format == "svg":
            fmt = "svg"
        else:
            fmt = "png"
        target_path = eps_path.with_suffix(f".{fmt}")

        if dry_run:
            status = "skipped" if (not force and target_path.exists() and target_path.stat().st_mtime >= eps_path.stat().st_mtime) else "dry_run"
            results.append(ConversionResult(
                source=str(eps_path),
                target=str(target_path),
                eps_type=eps_type,
                target_format=fmt,
                status=status,
            ))
            continue

        r = convert_single(eps_path, force=force, target_format=target_format, dpi=dpi, tools=tools)
        results.append(r)
        # Progress output
        mark = "✓" if r.status == "converted" else "–" if r.status == "skipped" else "✗"
        print(f"  {mark} {eps_path.name} → {Path(r.target).name}  [{r.status}]")

    return results


def write_report(results: list[ConversionResult], report_path: str) -> None:
    """Write conversion results as JSON."""
    data = {
        "summary": {
            "total": len(results),
            "converted": sum(1 for r in results if r.status == "converted"),
            "skipped": sum(1 for r in results if r.status == "skipped"),
            "failed": sum(1 for r in results if r.status == "failed"),
            "dry_run": sum(1 for r in results if r.status == "dry_run"),
        },
        "results": [
            {
                "source": r.source,
                "target": r.target,
                "eps_type": r.eps_type,
                "target_format": r.target_format,
                "status": r.status,
                **({"error": r.error} if r.error else {}),
                **({"fallback_from": r.fallback_from} if r.fallback_from else {}),
                **({"warning": r.warning} if r.warning else {}),
            }
            for r in results
        ],
    }
    Path(report_path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
