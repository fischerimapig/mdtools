"""Parse inline constructs within an already established leaf range."""
from __future__ import annotations

from collections.abc import Mapping
from .links import build_reference_lookup, destination, normalize_label, title
from .model import Inline, InlineResult, Notice


def parse_inlines(index, owner, references, limits):
    start, end = index.offsets(owner)
    text = index.source.text
    if end - start > limits.max_inline_chars:
        return InlineResult((), (Notice("inline-limit", "inline character limit exceeded", owner),), False)
    refs = references if isinstance(references, Mapping) else build_reference_lookup(references)
    # Index matching brackets and equal-length backtick runs once. This keeps
    # unmatched delimiters from repeatedly scanning the remainder of a leaf.
    brackets, stack, runs = {}, [], {}
    p = start
    while p < end:
        if text[p] == "`":
            q = p + 1
            while q < end and text[q] == "`":
                q += 1
            runs.setdefault(q - p, []).append((p, q))
            p = q
        else:
            p += 1
    ticks = {}
    for entries in runs.values():
        for a, b in zip(entries, entries[1:]):
            ticks[a[0]] = b
    p = start
    while p < end:
        c = text[p]
        if c == "\\" and p + 1 < end:
            p += 2
            continue
        if c == "`":
            close = ticks.get(p)
            if close:
                p = close[1]
                continue
            while p < end and text[p] == "`":
                p += 1
            continue
        if c == "[":
            stack.append(p)
        elif c == "]" and stack:
            brackets[stack.pop()] = p
        p += 1
    items = []
    notices = []
    pos = start
    plain = start
    budget = max(1, (end - start) * 8)
    overflow = None

    def emit(kind, a, b, target=None, title_span=None, reference=None):
        nonlocal overflow
        if len(items) >= limits.max_nodes:
            if overflow is None:
                overflow = a
            return
        items.append(Inline(kind, index.byte_range(a, b), target, title_span, reference))

    def flush(stop):
        nonlocal plain
        if plain < stop:
            emit("text", plain, stop)
        plain = stop

    while pos < end:
        if overflow is not None or len(items) >= limits.max_nodes:
            notices.append(Notice("inline-node-limit", "inline node limit exceeded", index.byte_range(overflow if overflow is not None else plain, end)))
            return InlineResult(tuple(items), tuple(notices), False)
        c = text[pos]
        if c == "\\" and pos + 1 < end and text[pos + 1] in r'''!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~''':
            flush(pos)
            emit("escape", pos, pos + 2)
            pos += 2
            plain = pos
            continue
        if c == "`":
            q = pos + 1
            while q < end and text[q] == "`":
                q += 1
            close = ticks.get(pos)
            if close:
                flush(pos)
                emit("code", pos, close[1])
                pos = close[1]
                plain = pos
            else:
                pos = q
            continue
        opening = pos + 1 if c == "!" and pos + 1 < end and text[pos + 1] == "[" else pos
        if text[opening] == "[" and opening in brackets:
            label_end = brackets[opening]
            after = label_end + 1
            budget -= label_end - opening + 1
            parsed = None
            if budget < 0:
                flush(pos)
                notices.append(Notice("inline-work-limit", "inline lookahead limit exceeded", index.byte_range(pos, end)))
                return InlineResult(tuple(items), tuple(notices), False)
            if after < end and text[after] == "(":
                q = after + 1
                while q < end and text[q] in " \t\r\n":
                    q += 1
                # Empty destinations use a zero-width source range. A title
                # without a destination needs whitespace after the opening (.
                if q < end and text[q] == ")":
                    parsed = (q + 1, index.byte_range(q, q), None, None)
                elif q > after + 1 and q < end and text[q] in "\"'":
                    t = title(text, q, end)
                    budget -= (t[2] if t else end) - q
                    if t:
                        tail = t[2]
                        while tail < end and text[tail] in " \t\r\n":
                            tail += 1
                        if tail < end and text[tail] == ")":
                            parsed = (tail + 1, index.byte_range(q, q),
                                      index.byte_range(t[0], t[1]), None)
                # Charge lookahead against a fixed per-owner budget.
                dest_start = q
                d = destination(text, q, end) if parsed is None else None
                if parsed is None:
                    budget -= (d[2] if d else end) - dest_start
                if d:
                    ds, de, q = d
                    ws = q
                    while q < end and text[q] in " \t\r\n":
                        q += 1
                    ts = None
                    if q > ws and q < end and text[q] in "\"'(":
                        t = title(text, q, end)
                        budget -= (t[2] if t else end) - q
                        if t:
                            ts = index.byte_range(t[0], t[1])
                            q = t[2]
                            while q < end and text[q] in " \t\r\n":
                                q += 1
                    if q < end and text[q] == ")":
                        parsed = (q + 1, index.byte_range(ds, de), ts, None)
            if parsed is None:
                q = after
                label_a, label_b = opening + 1, label_end
                if q < end and text[q] == "[" and q in brackets:
                    label_a, label_b = q + 1, brackets[q]
                    q = label_b + 1
                    if label_a == label_b:
                        label_a, label_b = opening + 1, label_end
                budget -= label_b - label_a
                if budget < 0:
                    flush(pos)
                    notices.append(Notice("inline-work-limit", "inline lookahead limit exceeded", index.byte_range(pos, end)))
                    return InlineResult(tuple(items), tuple(notices), False)
                key = normalize_label(text[label_a:label_b])
                ref = refs.get(key)
                if ref:
                    parsed = (q, ref.destination, ref.title, key)
            if budget < 0:
                flush(pos)
                notices.append(Notice("inline-work-limit", "inline lookahead limit exceeded", index.byte_range(pos, end)))
                return InlineResult(tuple(items), tuple(notices), False)
            if parsed:
                flush(pos)
                emit("image" if opening != pos else "link", pos, *parsed)
                pos = parsed[0]
                plain = pos
                continue
        if c == "<":
            # HTML comments and tags are atomic; quoted > is not a terminator.
            q = pos + 1
            scanned = 1
            if text.startswith("<!--", pos, end):
                close = text.find("-->", q + 3, end)
                q = close + 3 if close >= 0 else pos
                scanned = q - pos if close >= 0 else end - pos
                kind = "html_comment"
            elif q < end and (text[q].isalpha() or text[q] in "/!?"):
                quote = None
                while q < end:
                    ch = text[q]
                    if quote:
                        if ch == quote:
                            quote = None
                    elif ch in "\"'":
                        quote = ch
                    elif ch == ">":
                        q += 1
                        break
                    elif ch in "\r\n":
                        scanned = q - pos + 1
                        q = pos
                        break
                    q += 1
                else:
                    scanned = end - pos
                    q = pos
                if q != pos:
                    scanned = q - pos
                kind = "html"
            else:
                q = pos
            budget -= scanned
            if budget < 0:
                flush(pos)
                notices.append(Notice("inline-work-limit", "inline lookahead limit exceeded", index.byte_range(pos, end)))
                return InlineResult(tuple(items), tuple(notices), False)
            if q > pos:
                flush(pos)
                emit(kind, pos, q)
                pos = q
                plain = pos
                continue
        pos += 1
    flush(end)
    if overflow is not None:
        return InlineResult(tuple(items), (Notice("inline-node-limit", "inline node limit exceeded", index.byte_range(overflow, end)),), False)
    return InlineResult(tuple(items), tuple(notices), True)
