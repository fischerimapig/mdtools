from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class Embed:
    src: str
    width_pct: Optional[float] = None


@dataclass
class FigureBlock:
    start: int
    end: int
    raw: str
    id: Optional[str]
    caption: Optional[str]
    embeds: list[Embed] = field(default_factory=list)
    kind: Literal["image", "code", "caption_only", "mixed"] = "mixed"


@dataclass
class DivBlock:
    start: int
    end: int
    raw: str
    div_id: Optional[str]
    div_class: Optional[str]
    kind: Literal["screen", "description", "table_wrapper", "other"] = "other"


@dataclass
class RefLink:
    start: int
    end: int
    raw: str
    target_id: str
    ref_type: Optional[str]


@dataclass
class ConversionResult:
    source: str
    target: str
    eps_type: Literal["vector", "raster"]
    target_format: Literal["svg", "png"]
    status: Literal["converted", "skipped", "failed", "dry_run"]
    error: Optional[str] = None
    fallback_from: Optional[Literal["svg"]] = None
    warning: Optional[str] = None
