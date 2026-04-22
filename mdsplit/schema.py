"""Data structures for the document hierarchy."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SectionNode:
    """A single section in the document tree."""

    title: str
    file: str
    order: int
    children: list[SectionNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "file": self.file,
            "order": self.order,
            "children": [c.to_dict() for c in self.children],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SectionNode:
        return cls(
            title=d["title"],
            file=d["file"],
            order=d["order"],
            children=[cls.from_dict(c) for c in d.get("children", [])],
        )


@dataclass
class DocumentTree:
    """The full document hierarchy with metadata."""

    source_file: str
    base_level: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
    sections: list[SectionNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "base_level": self.base_level,
            "metadata": self.metadata,
            "sections": [s.to_dict() for s in self.sections],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DocumentTree:
        return cls(
            source_file=d.get("source_file", ""),
            base_level=d.get("base_level", 1),
            metadata=d.get("metadata", {}),
            sections=[SectionNode.from_dict(s) for s in d.get("sections", [])],
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> DocumentTree:
        return cls.from_dict(json.loads(text))

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> DocumentTree:
        return cls.from_json(Path(path).read_text(encoding="utf-8"))
