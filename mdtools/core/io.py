"""I/O helpers shared across mdtools packages."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


class StructuredFileError(ValueError):
    """Raised when reading a structured (JSON/YAML) file fails for content reasons."""


def read_text_or_stdin(path: str | Path) -> str:
    """Read UTF-8 text from ``path``, or from stdin when ``path == '-'``."""
    if str(path) == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def write_text_or_stdout(text: str, path: str | Path | None) -> None:
    """Write UTF-8 text to ``path``, or to stdout when ``path`` is None."""
    if path is None:
        sys.stdout.write(text)
    else:
        Path(path).write_text(text, encoding="utf-8")


def read_json(path: str | Path) -> Any:
    """Read and parse a UTF-8 JSON file."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StructuredFileError(f"{path}: invalid JSON: {exc}") from exc


def write_json(path: str | Path, obj: Any, *, indent: int = 2) -> None:
    """Write ``obj`` to ``path`` as UTF-8 JSON (ensure_ascii=False, indented)."""
    Path(path).write_text(dumps_json(obj, indent=indent), encoding="utf-8")


def dumps_json(obj: Any, *, indent: int = 2) -> str:
    """Return ``obj`` as a JSON string in mdtools' standard form."""
    return json.dumps(obj, ensure_ascii=False, indent=indent)


def read_structured_file(path: str | Path) -> Any:
    """Read ``.json``, ``.yaml``, or ``.yml`` and return the parsed object.

    Raises:
        FileNotFoundError: if the file does not exist.
        StructuredFileError: for unsupported extensions, parse errors, or
            missing PyYAML when a YAML file is requested.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No such file or directory: '{p}'")
    suffix = p.suffix.lower()
    if suffix == ".json":
        return read_json(p)
    if suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as exc:
            raise StructuredFileError(
                f"YAML support requires PyYAML (install with `pip install pyyaml`): {p}"
            ) from exc
        try:
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise StructuredFileError(f"{p}: invalid YAML: {exc}") from exc
    raise StructuredFileError(
        f"Unsupported file extension '{suffix}': {p}. Use .json, .yaml, or .yml."
    )
