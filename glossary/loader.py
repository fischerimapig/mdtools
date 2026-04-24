"""Loader for glossary definition files.

Supports JSON (``.json``) and YAML (``.yaml`` / ``.yml``) definition files,
merges multiple files into a single dict keyed by ``id``, and performs
minimal schema validation.

Schema (see glossary/README.md for full details)::

    {
      "entries": [
        {
          "id": "<identifier>",
          "kind": "term" | "const" | "symbol",
          ...kind-specific fields
        }
      ]
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


VALID_KINDS = ("term", "const", "symbol")


class GlossaryError(Exception):
    """Raised for schema, format, or merge errors while loading definitions."""


@dataclass
class Entry:
    """One registered term, constant, or symbol."""

    id: str
    kind: str
    data: dict[str, Any] = field(default_factory=dict)
    source_file: str | None = None

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


def _load_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")

    if suffix == ".json":
        return json.loads(text)

    if suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as exc:
            raise GlossaryError(
                f"YAML support requires PyYAML. Install with: "
                f"pip install pyyaml  (source: {path})"
            ) from exc
        return yaml.safe_load(text) or {}

    raise GlossaryError(
        f"Unsupported definition file extension '{suffix}': {path}. "
        f"Use .json, .yaml, or .yml."
    )


def _validate_entry(raw: dict[str, Any], source: Path) -> Entry:
    if not isinstance(raw, dict):
        raise GlossaryError(f"{source}: entry must be an object, got {type(raw).__name__}")

    eid = raw.get("id")
    if not isinstance(eid, str) or not eid:
        raise GlossaryError(f"{source}: entry missing required string field 'id'")

    kind = raw.get("kind")
    if kind not in VALID_KINDS:
        raise GlossaryError(
            f"{source}: entry '{eid}' has invalid kind {kind!r} "
            f"(expected one of {VALID_KINDS})"
        )

    data = {k: v for k, v in raw.items() if k not in ("id", "kind")}
    return Entry(id=eid, kind=kind, data=data, source_file=str(source))


def load(paths: list[str | Path]) -> dict[str, Entry]:
    """Load and merge definitions from one or more files.

    Later files override earlier ones on id conflicts (with a warning printed
    to stderr).

    Args:
        paths: List of file paths (JSON or YAML).

    Returns:
        Dict mapping entry id → Entry.

    Raises:
        GlossaryError: on parse, schema, or format error.
    """
    import sys

    if not paths:
        raise GlossaryError("No definition files provided")

    merged: dict[str, Entry] = {}

    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_file():
            raise GlossaryError(f"Definition file not found: {path}")

        try:
            doc = _load_file(path)
        except json.JSONDecodeError as exc:
            raise GlossaryError(f"{path}: invalid JSON: {exc}") from exc

        if not isinstance(doc, dict):
            raise GlossaryError(f"{path}: top-level must be an object")

        entries = doc.get("entries")
        if not isinstance(entries, list):
            raise GlossaryError(f"{path}: missing or invalid 'entries' list")

        for raw in entries:
            entry = _validate_entry(raw, path)
            if entry.id in merged:
                prev = merged[entry.id].source_file
                print(
                    f"warning: id '{entry.id}' in {path} overrides earlier "
                    f"definition from {prev}",
                    file=sys.stderr,
                )
            merged[entry.id] = entry

    return merged
