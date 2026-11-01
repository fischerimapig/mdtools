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
        return offset, tokenize_attrs(tail), False, _comments(tail, False)
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
            return offset + 1, tokenize_attrs(tail[1:i]), not suffix.strip(), _comments(suffix, False)
        elif tail.startswith('<!--', i):
            # Outside a quoted value this is a real comment, even after a
            # malformed header. Do not tokenize its contents as attributes.
            return offset + 1, tokenize_attrs(tail[1:i]), False, _comments(tail[i:], False)
    return offset + 1, tokenize_attrs(tail[1:]), False, False


def _comments(line: str, active: bool) -> bool:
    """Track actual comments, skipping escaped markers and inline code spans."""
    i = 0
    while i < len(line):
        if active:
            end = line.find('-->', i)
            if end < 0:
                return True
            i, active = end + 3, False
        elif line[i] == '\\':
            i += 2
        elif line.startswith('<!--', i):
            i, active = i + 4, True
        elif line[i] == '`':
            run = re.match(r'`+', line[i:])[0]
            end = re.search(r'(?<!`)' + re.escape(run) + r'(?!`)', line[i + len(run):])
            i += len(run) + (end.end() if end else 0)
        else:
            i += 1
    return active


def scan(text: str) -> list[Text | Code | Div]:
    # Unlike splitlines(), Unicode separators are content, not source newlines.
    lines = list(re.finditer(r'[^\r\n]*(?:\r\n|\r|\n|\Z)', text))
    if lines and not lines[-1][0]:
        lines.pop()
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
            comment = _comments(line, True)
            append(Text(start, end))
            continue
        # Up to three leading spaces are ordinary Markdown block positions.
        # Four spaces or a tab introduce literal indented code instead.
        stripped = line.lstrip(' ')
        indent = len(line) - len(stripped)
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
            offset, attrs, valid, comment = _attributes(tail, start + div.start(2))
            current = Div(start, len(text), end, offset, attrs, valid and marker == ':::')
            append(current)
            stack.append(current)
            continue
        # Indented prose/code cannot create multiline HTML comment state.
        if indent < 4 and not line.startswith('\t'):
            comment = _comments(line, False)
        append(Text(start, end))
    return root
