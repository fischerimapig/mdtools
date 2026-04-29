"""Pandoc/Quarto syntax primitives shared across mdtools."""

from __future__ import annotations

import re
from dataclasses import dataclass


# Code fence (3+ backticks or tildes). Used by mdscan and callers that need
# to avoid touching code-fenced content.
CODE_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")

# Closing fence of a Pandoc fenced div: bare ``:::`` with optional trailing space.
FENCE_CLOSE_RE = re.compile(r"^:::\s*$")

# Opening fence of a Pandoc fenced div: ``::: {...}``. Group 1 captures the
# attribute content between the braces.
DIV_OPEN_RE = re.compile(r"^:::\s*\{([^}]*)\}\s*$")

# Pandoc bracketed span: ``[label]{...}``. Group 1 is the label (possibly empty),
# group 2 is the attribute content.
BRACKETED_SPAN_RE = re.compile(r"\[([^\[\]]*)\]\{([^{}]+)\}")


_ATTR_CLASS_RE = re.compile(r"\.(\S+)")
_ATTR_KV_RE = re.compile(r'(\w+)\s*=\s*("([^"]*)"|(\S+))')


@dataclass(frozen=True)
class PandocAttrs:
    """Parsed attributes of a Pandoc span or fenced div."""

    classes: list[str]
    kv: dict[str, str]

    def has_class(self, name: str) -> bool:
        return name in self.classes

    def first_class_in(self, candidates: frozenset[str] | set[str]) -> str | None:
        for c in self.classes:
            if c in candidates:
                return c
        return None


def parse_attrs(s: str) -> PandocAttrs:
    """Parse the contents of ``{...}`` in a Pandoc span or fenced div.

    Recognizes:
        - ``.classname`` -> classes (duplicates preserved in order)
        - ``key=value`` or ``key="quoted value"`` -> kv (later wins on duplicate)
    """
    classes = list(_ATTR_CLASS_RE.findall(s))
    kv: dict[str, str] = {}
    for m in _ATTR_KV_RE.finditer(s):
        key = m.group(1)
        value = m.group(3) if m.group(3) is not None else m.group(4)
        kv[key] = value
    return PandocAttrs(classes=classes, kv=kv)
