"""Internal block boundaries over unchanged manuscript offsets.

This is a reservation scanner, not a renderer or a second specification model.
Literal blocks own their contents until their actual closing boundary or EOF.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from mdtools.core.mdscan import PRE_OPEN_RE, PRE_CLOSE_RE
from mdtools.core.pandoc import AttrToken, CODE_FENCE_RE, tokenize_attrs


@dataclass
class Text:
    start: int
    end: int


@dataclass
class Code:
    start: int
    end: int
    body_start: int
    body_end: int
    info: str
    closed: bool


@dataclass
class Div:
    start: int
    end: int
    header_end: int
    attr_offset: int
    attrs: tuple[AttrToken, ...]
    valid: bool
    closed: bool = False
    children: list[Text | Code | Div] = field(default_factory=list)


def _attributes(tail: str, offset: int):
    leading = len(tail) - len(tail.lstrip())
    tail = tail[leading:]
    offset += leading
    if not tail.startswith('{'):
        return offset, tokenize_attrs(tail), False, offset
    quote = None
    escaped = False
    for i in range(1, len(tail)):
        c = tail[i]
        if escaped:
            escaped = False
        elif quote and c == '\\':
            escaped = True
        elif quote:
            if c == quote:
                quote = None
        elif c in '\"\'':
            quote = c
        elif c == '}':
            suffix = tail[i + 1:]
            return offset + 1, tokenize_attrs(tail[1:i]), not suffix.strip(), offset + i + 1
        elif tail.startswith('<!--', i):
            # Outside a quoted value this is a real comment, even after a
            # malformed header. Do not tokenize its contents as attributes.
            return offset + 1, tokenize_attrs(tail[1:i]), False, offset + i
    return offset + 1, tokenize_attrs(tail[1:]), False, None


# HTML tags are tokens: comment-looking text inside quoted values is literal.
_HTML_TAG = re.compile(
    r"</?[A-Za-z][A-Za-z0-9-]*"
    r"(?:[ \t\r\n]+[A-Za-z_:][A-Za-z0-9_.:-]*"
    r"(?:[ \t\r\n]*=[ \t\r\n]*(?:\"[^\"]*\"|'[^']*'|[^ \t\r\n\"'=<>`]+))?)*"
    r"[ \t\r\n]*/?>"
)
_BLOCK_START = re.compile(
    r"^ {0,3}(?:\#{1,6}(?:[ \t]|$)|:{3,}|`{3,}|~{3,}|>"
    r"|[-+*][ \t]|[0-9]+[.)][ \t]|(?:-\s*){3,}$|(?:_\s*){3,}$|(?:\*\s*){3,}$)"
)


class _Inline:
    """Track literal tokens across soft line breaks, within a paragraph only.

    An unmatched backtick remains prose. A matched token protects its complete
    raw range, so continuation lines cannot start blocks or HTML comments.
    """

    def __init__(self, text):
        self.text = text
        self.protected_until = 0

    def comments(self, start, end, active, limit):
        i = max(start, self.protected_until)
        while i < end:
            if active:
                closing = self.text.find('-->', i, end)
                if closing < 0:
                    return True
                i, active = closing + 3, False
            elif self.text[i] == '\\':
                i += 2
            elif self.text.startswith('<!--', i):
                i, active = i + 4, True
            elif self.text[i] == '`':
                run = re.match(r'`+', self.text[i:end])[0]
                closing = re.compile(r'(?<!`)' + re.escape(run) + r'(?!`)').search(
                    self.text, i + len(run), limit)
                if closing:
                    self.protected_until = closing.end()
                    i = closing.end()
                else:
                    i += len(run)
            elif self.text[i] == '<' and (tag := _HTML_TAG.match(self.text, i, limit)):
                self.protected_until = tag.end()
                i = tag.end()
            else:
                i += 1
        return active


def scan(text: str) -> list[Text | Code | Div]:
    # Unlike splitlines(), Unicode separators are content, not source newlines.
    lines = list(re.finditer(r'[^\r\n]*(?:\r\n|\r|\n|\Z)', text))
    if lines and not lines[-1][0]:
        lines.pop()
    # Cache each line's paragraph limit; lookahead never crosses a blank line
    # or a Markdown block opener (including requirement and code fences).
    limits = [len(text)] * len(lines)
    for j in range(len(lines) - 2, -1, -1):
        following = lines[j + 1][0].rstrip('\r\n')
        if not following.strip() or _BLOCK_START.match(following) or PRE_OPEN_RE.match(following):
            limits[j] = lines[j].end()
        else:
            limits[j] = limits[j + 1]
    inline = _Inline(text)
    root = []
    stack: list[Div] = []
    comment = pre = False
    i = 0
    front_end = -1
    if lines and lines[0][0].rstrip('\r\n').rstrip() == '---':
        front_end = next((j for j in range(1, len(lines))
                          if lines[j][0].strip() in ('---', '...')), -1)

    def append(block):
        (stack[-1].children if stack else root).append(block)

    while i < len(lines):
        line_match = lines[i]
        start, end = line_match.span()
        line = line_match[0].rstrip('\r\n')
        i += 1
        if i - 1 <= front_end:
            append(Text(start, end))
            continue
        if pre:
            pre = PRE_CLOSE_RE.search(line) is None
            append(Text(start, end))
            continue
        if comment:
            comment = inline.comments(start, end, True, limits[i - 1])
            append(Text(start, end))
            continue
        if inline.protected_until > start:
            comment = inline.comments(start, end, False, limits[i - 1])
            append(Text(start, end))
            continue
        # Up to three leading spaces are ordinary Markdown block positions.
        # Four spaces or a tab introduce literal indented code instead.
        stripped = line.lstrip(' ')
        indent = len(line[:len(line) - len(line.lstrip(' \t'))].expandtabs(4))
        fence = CODE_FENCE_RE.match(stripped) if indent <= 3 else None
        if fence:
            marker = fence[1]
            info = stripped[len(marker):].strip()
            # A backtick in a backtick info string is not a normal code opener.
            # Still retain malformed reserved mdspec for a structural diagnostic.
            if marker[0] != '`' or '`' not in info or info.startswith('mdspec'):
                body_start, body_end, closed = end, len(text), False
                closing = re.compile(r'^ {0,3}' + re.escape(marker[0])
                                     + '{' + str(len(marker)) + r',}[ \t]*$')
                while i < len(lines):
                    candidate = lines[i]
                    i += 1
                    if closing.fullmatch(candidate[0].rstrip('\r\n')):
                        body_end, end, closed = candidate.start(), candidate.end(), True
                        break
                if not closed:
                    end = len(text)
                append(Code(start, end, body_start, body_end, info, closed))
                continue
        if PRE_OPEN_RE.match(line):
            pre = PRE_CLOSE_RE.search(line) is None
            append(Text(start, end))
            continue
        # Div headers are interpreted before inline comment syntax, so quoted
        # attribute strings cannot start a comment outside their own header.
        div = re.match(r'^ {0,3}(:{3,})(.*)$', line)
        if div:
            marker, tail = div.groups()
            if not tail.strip():
                if marker == ':::' and stack:
                    current = stack.pop()
                    current.end, current.closed = end, True
                else:
                    append(Text(start, end))
                continue
            offset, attrs, valid, suffix = _attributes(tail, start + div.start(2))
            comment = (inline.comments(suffix, end, False, limits[i - 1])
                       if suffix is not None else False)
            current = Div(start, len(text), end, offset, attrs, valid and marker == ':::')
            append(current)
            stack.append(current)
            continue
        # Indented prose/code cannot create multiline HTML comment state.
        if indent < 4:
            comment = inline.comments(start, end, False, limits[i - 1])
        append(Text(start, end))
    return root
