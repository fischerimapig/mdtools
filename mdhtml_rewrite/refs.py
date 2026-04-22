from __future__ import annotations

import re

A_REF_RE = re.compile(
    r'<a\s+[^>]*href="#(?P<id>[^"]+)"[^>]*data-reference-type="ref"[^>]*>.*?</a>',
    re.DOTALL,
)


def rewrite_ref_links(text: str) -> str:
    """Rewrite pandoc HTML ref links to Quarto crossref style @id."""

    def repl(m: re.Match[str]) -> str:
        return f"@{m.group('id')}"

    return A_REF_RE.sub(repl, text)
