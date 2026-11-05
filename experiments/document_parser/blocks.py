"""Bounded, source-preserving block recognition for the prototype profile.

Block ownership is fixed here, before any inline processing. This deliberately
small grammar reports ambiguous container syntax instead of guessing ownership.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re

from mdtools.core.pandoc import tokenize_attrs
from .model import Attribute, BlockResult, Coverage, Limits, Node, Notice, SourceIndex

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_DIV = re.compile(r"^ {0,3}(:{3,})(.*)$")
_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+|$)")
_PRE = re.compile(r"^ {0,3}<pre(?=[\s>]|$)", re.I)
_COMMENT = re.compile(r"^ {0,3}<!--")
# Block tags, unlike span/a/em, cannot be handed to the inline recognizer.
_HTML = re.compile(r"^ {0,3}</?(?:address|article|aside|base|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|link|main|menu|meta|nav|noframes|ol|optgroup|option|p|param|section|source|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul)(?=[\s/>]|$)|^ {0,3}<(?:!|\?)", re.I)
_RAW_HTML = re.compile(r"^ {0,3}<(script|style|textarea)(?=[\s>]|$)", re.I)
_REFERENCE_PREFIX = re.compile(r"^ {0,3}\[(?:\\.|[^\[\]\\\r\n]){1,999}\]:[ \t]*(.*)$")
_SETEXT = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
_UNSUPPORTED = re.compile(r"^ {0,3}(?:>|[-+*][ \t]+|\d+[.)][ \t]+|\|)")


@dataclass
class _Frame:
    start: int
    body_start: int
    attributes: tuple = ()
    valid: bool = True
    marker: str = ":::"
    children: list = field(default_factory=list)


def _indent_columns(raw):
    columns = 0
    for char in raw:
        if char == " ":
            columns += 1
        elif char == "\t":
            columns += 4 - columns % 4
        else:
            break
    return columns


def parse_blocks(index: SourceIndex, limits: Limits) -> BlockResult:
    """Recognize generic blocks without interpreting specification attributes."""
    from .links import destination, parse_reference_definition

    text, lines = index.source.text, index.lines
    br = index.byte_range
    notices, coverage, references = [], [], []
    root = _Frame(0, 0)
    stack = [root]
    count = 0
    partial = False
    stopped = False

    def cover(a, b, state="recognized", reason=None):
        if a != b:
            coverage.append(Coverage(br(a, b), state, reason))

    def notice(code, message, a, b):
        nonlocal partial
        partial = True
        notices.append(Notice(code, message, br(a, b)))

    def add(node):
        nonlocal count
        stack[-1].children.append(node)
        count += 1

    def line_text(i):
        return text[lines[i].start:lines[i].content_end]

    def finish_frame(end, closing=None, closure="eof"):
        frame = stack.pop()
        body_end = closing.start if closing else end
        node = Node("div", br(frame.start, end), br(frame.body_start, body_end),
                    header=br(frame.start, frame.body_start),
                    closing=br(closing.start, closing.end) if closing else None,
                    children=tuple(frame.children), attributes=frame.attributes,
                    marker=frame.marker, closure=closure,
                    valid=frame.valid)
        stack[-1].children.append(node)
        if closure == "eof":
            notice("block.unclosed-div", "Div reaches EOF without a closing marker", frame.start, end)

    def special(i):
        raw = line_text(i)
        return (not raw.strip() or _FENCE.match(raw) or _DIV.match(raw)
                or _HEADING.match(raw) or _PRE.match(raw) or _COMMENT.match(raw)
                or _UNSUPPORTED.match(raw) or _HTML.match(raw) or _RAW_HTML.match(raw))

    def unsupported_reference_end(i, ref=None):
        """Recognize bounded continuation candidates without accepting a definition.

        Only the immediately adjacent destination/title line is reserved. A
        blank or independent block start always stops this conservative probe.
        The shared lexer validates destination shape; no second label parser is
        used for accepted definitions.
        """
        if i + 1 >= len(lines) or special(i + 1):
            return None
        next_raw = line_text(i + 1)
        if _indent_columns(next_raw) >= 4:
            return None
        continued = next_raw.lstrip(" \t")
        if not continued:
            return None
        if ref is not None:
            if ref.title is None and continued[0] in "\"'(":
                return i + 2
            return None
        prefix = _REFERENCE_PREFIX.match(line_text(i))
        if prefix is None or prefix[1]:
            return None
        parsed = destination(continued, 0, len(continued))
        if parsed is None:
            return None
        _, _, end = parsed
        # A following title may occur on this destination line; this whole
        # candidate remains unsupported regardless of title validity.
        if end < len(continued) and not continued[end].isspace():
            return None
        end_line = i + 2
        if end == len(continued.rstrip(" \t")) and end_line < len(lines) and not special(end_line):
            possible_title = line_text(end_line)
            if _indent_columns(possible_title) < 4 and possible_title.lstrip(" \t").startswith(('"', "'", "(")):
                end_line += 1
        return end_line

    if index.byte_length > limits.max_bytes:
        cover(0, len(text), "unparsed", "maximum source bytes exceeded")
        notices.append(Notice("limit.bytes", "Maximum source bytes exceeded", br(0, len(text))))
        return BlockResult((), (), tuple(notices), tuple(coverage), "rejected")

    i = 0
    while i < len(lines):
        line = lines[i]
        raw = line_text(i)
        div = _DIV.match(raw)
        is_close = div and div[1] == ":::" and not div[2].strip() and len(stack) > 1
        if count >= limits.max_nodes and not is_close:
            cover(line.start, len(text), "unparsed", "maximum block nodes exceeded")
            notice("limit.nodes", "Maximum block nodes exceeded", line.start, len(text))
            stopped = True
            break
        if div:
            marker, tail = div.groups()
            if marker == ":::" and not tail.strip() and len(stack) > 1:
                cover(line.start, line.end)
                finish_frame(line.end, line, "closed")
                i += 1
                continue
            if not tail.strip():
                add(Node("invalid_closure", br(line.start, line.end), br(line.start, line.end),
                         marker=marker, valid=False))
                cover(line.start, line.end)
                notice("block.invalid-closure", "Unexpected or invalid Div closing marker", line.start, line.end)
                i += 1
                continue
            if len(stack) > limits.max_depth:
                cover(line.start, len(text), "unparsed", "maximum Div depth exceeded")
                notice("limit.depth", "Maximum Div depth exceeded", line.start, len(text))
                stopped = True
                break
            # Recover the attribute token stream even when braces or suffixes are
            # malformed; only an unquoted closing brace ends the attribute area.
            a = div.start(2)
            while a < len(raw) and raw[a].isspace():
                a += 1
            has_open = a < len(raw) and raw[a] == "{"
            attr_start = a + 1 if has_open else a
            quote = None
            escaped = False
            closing = None
            for pos in range(attr_start, len(raw)):
                char = raw[pos]
                if quote:
                    if escaped:
                        escaped = False
                    elif char == "\\":
                        escaped = True
                    elif char == quote:
                        quote = None
                elif char in ("'", '"'):
                    quote = char
                elif char == "}":
                    closing = pos
                    break
            attr_end = closing if closing is not None else len(raw)
            tokens = tokenize_attrs(raw[attr_start:attr_end])
            attrs = tuple(Attribute(t.kind, t.name, t.value,
                                    br(line.start + attr_start + t.start, line.start + attr_start + t.end),
                                    br(line.start + attr_start + t.value_start, line.start + attr_start + t.value_end))
                          for t in tokens)
            valid = (marker == ":::" and has_open and closing is not None
                     and not raw[closing + 1:].strip()
                     and all(t.kind != "invalid" for t in tokens))
            if not valid:
                notice("block.invalid-header", "Invalid generic Div header", line.start, line.end)
            stack.append(_Frame(line.start, line.end, attrs, valid, marker))
            count += 1
            cover(line.start, line.end)
            i += 1
            continue
        # Closed front matter is reserved only at the beginning of the snapshot.
        if i == 0 and raw == "---":
            end = next((j for j in range(1, len(lines)) if line_text(j).rstrip(" \t") in ("---", "...")), None)
            if end is not None:
                close = lines[end]
                add(Node("front_matter", br(0, close.end), br(line.end, close.start),
                         header=br(0, line.end), closing=br(close.start, close.end), closure="closed"))
                cover(0, close.end)
                i = end + 1
                continue
        fence = _FENCE.match(raw)
        if fence:
            marker, info = fence.groups()
            closer = re.compile(r"^ {0,3}" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}[ \t]*$")
            j = i + 1
            while j < len(lines) and not closer.match(line_text(j)):
                j += 1
            close = lines[j] if j < len(lines) else None
            end = close.end if close else len(text)
            a = line.start + fence.start(2)
            left = len(info) - len(info.lstrip())
            right = len(info.rstrip())
            valid_info = marker[0] != "`" or "`" not in info
            if not valid_info:
                notice("block.invalid-fence-info", "Backtick in backtick fence info", line.start, line.end)
            add(Node("code_fence", br(line.start, end), br(line.end, close.start if close else end),
                     header=br(line.start, line.end), closing=br(close.start, close.end) if close else None,
                     info=info.strip(), info_span=br(a + left, a + max(left, right)), marker=marker,
                     closure="closed" if close else "eof", valid=valid_info))
            cover(line.start, end)
            i = j + 1
            continue
        literal_kind = "pre" if _PRE.match(raw) else "html_comment" if _COMMENT.match(raw) else None
        if literal_kind:
            closing = re.compile(r"</pre\s*>", re.I) if literal_kind == "pre" else re.compile(r"-->")
            j = i
            while j < len(lines) and not closing.search(line_text(j)):
                j += 1
            end = lines[j].end if j < len(lines) else len(text)
            add(Node(literal_kind, br(line.start, end), br(line.start, end),
                     closure="closed" if j < len(lines) else "eof"))
            cover(line.start, end)
            i = j + 1
            continue
        raw_html = _RAW_HTML.match(raw)
        if raw_html:
            closer = re.compile(r"</" + raw_html[1] + r"\s*>", re.I)
            j = i
            while j < len(lines) and not closer.search(line_text(j)):
                j += 1
            end = lines[j].end if j < len(lines) else len(text)
            reason = "raw HTML block outside prototype profile"
            add(Node("unsupported", br(line.start, end), br(line.start, end),
                     closure="closed" if j < len(lines) else "eof", valid=False))
            cover(line.start, end, "unsupported", reason)
            notice("block.unsupported", reason, line.start, end)
            i = j + 1
            continue
        ref = parse_reference_definition(index, line.start, line.content_end)
        unsupported_end = unsupported_reference_end(i, ref)
        if unsupported_end is not None:
            end = lines[unsupported_end - 1].end
            reason = "multiline reference definition outside single-line prototype profile"
            add(Node("unsupported", br(line.start, end), br(line.start, end), valid=False))
            cover(line.start, end, "unsupported", reason)
            notice("block.unsupported-reference", reason, line.start, end)
            i = unsupported_end
            continue
        if ref is not None:
            references.append(ref)
            add(Node("reference_definition", br(line.start, line.end), br(line.start, line.content_end)))
            cover(line.start, line.end)
            i += 1
            continue
        j = i + 1
        state, reason = "recognized", None
        if not raw.strip():
            kind = "blank"
            while j < len(lines) and not line_text(j).strip():
                j += 1
        elif _indent_columns(raw) >= 4:
            kind = "indented_code"
            while j < len(lines) and (not line_text(j).strip() or _indent_columns(line_text(j)) >= 4):
                j += 1
        elif _HEADING.match(raw):
            kind = "heading"
        elif _UNSUPPORTED.match(raw) or _HTML.match(raw):
            kind, state, reason = "unsupported", "unsupported", "container or HTML grammar outside prototype profile"
            # Keep all nonblank continuation lines opaque: their ownership is unknown.
            while j < len(lines) and line_text(j).strip():
                j += 1
            notice("block.unsupported", reason, line.start, lines[j - 1].end)
        else:
            kind = "paragraph"
            while j < len(lines) and not special(j):
                if _SETEXT.match(line_text(j)):
                    kind = "heading"
                    j += 1
                    break
                next_ref = parse_reference_definition(index, lines[j].start, lines[j].content_end)
                if next_ref is not None or unsupported_reference_end(j) is not None:
                    break
                j += 1
        end = lines[j - 1].end
        add(Node(kind, br(line.start, end), br(line.start, end), valid=state == "recognized"))
        cover(line.start, end, state, reason)
        i = j

    while len(stack) > 1:
        finish_frame(len(text), closure="limit" if stopped else "eof")
    return BlockResult(tuple(root.children), tuple(references), tuple(notices), tuple(coverage),
                       "partial" if partial else "complete")
