"""Convert heading titles to filesystem-safe filenames."""

from __future__ import annotations

import re
import unicodedata


def slugify(title: str, max_length: int = 40) -> str:
    """Convert a heading title to a filesystem-safe slug.

    For ASCII-heavy titles, produce a lowercase hyphenated slug.
    For titles that are mostly non-ASCII, use 'section' as fallback.
    """
    # Normalize unicode
    text = unicodedata.normalize("NFKC", title)

    # Try ASCII transliteration: keep alphanumeric and spaces
    ascii_chars = []
    for ch in text:
        if ch.isascii() and (ch.isalnum() or ch in " -_"):
            ascii_chars.append(ch)
        elif ch == " ":
            ascii_chars.append(" ")

    slug = "".join(ascii_chars).strip().lower()
    # Replace whitespace/underscores with hyphens, collapse runs
    slug = re.sub(r"[\s_]+", "-", slug)
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    # Collapse multiple hyphens
    slug = re.sub(r"-{2,}", "-", slug)

    if not slug:
        slug = "section"

    # Truncate
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")

    return slug


def make_filename(order: int, title: str, ext: str = ".md") -> str:
    """Generate a numbered filename like '01-background.md'."""
    slug = slugify(title)
    return f"{order + 1:02d}-{slug}{ext}"
