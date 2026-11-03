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


@dataclass(frozen=True)
class AttrToken:
    """Lossless attribute occurrence for strict consumers; offsets are in input s.

    Invalid tokens are retained, not silently skipped. value_ranges maps decoded
    characters to their raw ranges (including a backslash escape when present).
    This lexer imposes no consumer-specific names, uniqueness, or value rules.
    """

    kind: str  # class, id, attribute, invalid
    name: str
    value: str
    start: int
    end: int
    value_start: int
    value_end: int
    value_ranges: tuple[tuple[int, int], ...] = ()


def tokenize_attrs(s: str) -> tuple[AttrToken, ...]:
    """Tokenize Pandoc attributes without changing legacy parse_attrs semantics.

    Accept bare, single-quoted and double-quoted values and backslash escapes in
    quoted values. Preserve duplicates and malformed tokens for the caller.
    """
    tokens = []
    i = 0
    while i < len(s):
        if s[i].isspace():
            i += 1
            continue
        start = i
        if s[i] in '.#':
            kind = 'class' if s[i] == '.' else 'id'
            i += 1
            a = i
            while i < len(s) and not s[i].isspace():
                i += 1
            value = s[a:i]
            if not value or any(c in value for c in '{}\"\'='):
                kind = 'invalid'
            tokens.append(AttrToken(kind, value, value, start, i, a, i,
                                    tuple((p, p + 1) for p in range(a, i))))
            continue
        key = re.match(r'[A-Za-z_][A-Za-z0-9_-]*', s[i:])
        if key:
            name = key[0]
            i += len(name)
            while i < len(s) and s[i].isspace():
                i += 1
        else:
            name = ''
        if not key or i == len(s) or s[i] != '=':
            i = start
            while i < len(s) and not s[i].isspace():
                i += 1
            tokens.append(AttrToken('invalid', name, s[start:i], start, i, start, i))
            continue
        i += 1
        while i < len(s) and s[i].isspace():
            i += 1
        a = i
        chars, ranges = [], []
        valid = True
        if i < len(s) and s[i] in '\"\'':
            quote = s[i]
            i += 1
            while i < len(s) and s[i] != quote:
                left = i
                if s[i] == '\\' and i + 1 < len(s):
                    i += 1
                chars.append(s[i])
                i += 1
                ranges.append((left, i))
            if i == len(s):
                valid = False
            else:
                i += 1
        else:
            while i < len(s) and not s[i].isspace():
                chars.append(s[i])
                ranges.append((i, i + 1))
                i += 1
            valid = bool(chars) and not any(c in '{}\"\'' for c in chars)
        b = i
        if i < len(s) and not s[i].isspace():
            valid = False
            while i < len(s) and not s[i].isspace():
                i += 1
        tokens.append(AttrToken('attribute' if valid else 'invalid', name,
                                ''.join(chars), start, i, a, b, tuple(ranges)))
    return tuple(tokens)
