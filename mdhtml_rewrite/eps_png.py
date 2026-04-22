from __future__ import annotations

from pathlib import Path

_DISPLAY_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


def resolve_display_image(src: str, base_dir: Path, prefer_png: bool = True) -> tuple[str, str]:
    """Resolve figure source to a display-friendly format when possible.

    Returns:
        (path, status)
        status in {"display_ext", "svg_found", "png_found", "kept_original", "missing"}
    """
    path = Path(src)
    ext = path.suffix.lower()
    if ext in _DISPLAY_EXTS:
        return src, "display_ext"

    def _find_web_format(p: Path) -> tuple[str, str] | None:
        """Check for SVG first, then PNG sibling."""
        svg_rel = str(p.with_suffix(".svg"))
        if (base_dir / svg_rel).exists():
            return svg_rel, "svg_found"
        png_rel = str(p.with_suffix(".png"))
        if (base_dir / png_rel).exists():
            return png_rel, "png_found"
        return None

    candidate = base_dir / src
    if not candidate.exists():
        if prefer_png and ext in {".eps", ".ps", ".pdf"}:
            found = _find_web_format(path)
            if found:
                return found
        return src, "missing"

    if prefer_png and ext in {".eps", ".ps", ".pdf"}:
        found = _find_web_format(path)
        if found:
            return found

    return src, "kept_original"
