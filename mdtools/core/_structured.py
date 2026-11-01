"""Strict JSON tokens with offsets in the *encoded* input, never decoded text.

Only scalar decoding uses the standard library. Container traversal retains
member occurrences long enough to diagnose duplicate (including escaped) keys.
"""

from dataclasses import dataclass
import json
import math


class JsonError(ValueError):
    def __init__(self, message, start, end, previous=None, *, unsupported=False):
        super().__init__(message)
        self.start, self.end, self.previous = start, end, previous
        self.unsupported = unsupported


@dataclass(frozen=True)
class Token:
    value: object
    start: int
    end: int
    members: tuple[tuple['Token', 'Token'], ...] = ()
    elements: tuple['Token', ...] = ()


def parse_json(raw: str, *, preserve_duplicates: bool = False) -> Token:
    decoder = json.JSONDecoder()
    i = 0

    def whitespace():
        nonlocal i
        while i < len(raw) and raw[i] in ' \t\r\n':
            i += 1

    def error(message, start=None, end=None, previous=None):
        raise JsonError(message, i if start is None else start,
                        i if end is None else end, previous)

    def value():
        nonlocal i
        whitespace()
        start = i
        if i == len(raw):
            error('Expected a JSON value')
        if raw[i] in '[{':
            opening = raw[i]
            closing = '}' if opening == '{' else ']'
            i += 1
            whitespace()
            members, elements, seen = [], [], {}
            if i < len(raw) and raw[i] == closing:
                i += 1
            else:
                while True:
                    whitespace()
                    if opening == '{':
                        if i == len(raw) or raw[i] != '"':
                            error('Expected a quoted JSON object key')
                        key = value()
                        if key.value in seen and not preserve_duplicates:
                            old = seen[key.value]
                            error('Duplicate JSON key: ' + key.value, key.start, key.end,
                                  (old.start, old.end))
                        seen[key.value] = key
                        whitespace()
                        if i == len(raw) or raw[i] != ':':
                            error('Expected colon after JSON object key')
                        i += 1
                        members.append((key, value()))
                    else:
                        elements.append(value())
                    whitespace()
                    if i < len(raw) and raw[i] == closing:
                        i += 1
                        break
                    if i == len(raw) or raw[i] != ',':
                        error('Expected comma or closing JSON delimiter')
                    i += 1
            # In occurrence mode the mapping value is only a kind marker.
            # All content lives in members; no duplicate is overwritten.
            decoded = (({} if preserve_duplicates else {k.value: v.value for k, v in members})
                       if opening == '{' else [v.value for v in elements])
            return Token(decoded, start, i, tuple(members), tuple(elements))
        try:
            decoded, end = decoder.raw_decode(raw, i)
        except json.JSONDecodeError as exc:
            error(exc.msg, exc.pos, exc.pos)
        except ValueError:
            raise JsonError('JSON scalar exceeds decoder capacity', start, len(raw), unsupported=True) from None
        if isinstance(decoded, float) and not math.isfinite(decoded):
            error('Non-finite numbers are not JSON values', start, end)
        if isinstance(decoded, str):
            try:
                decoded.encode('utf-8')
            except UnicodeEncodeError:
                error('Unpaired surrogate in JSON string', start, end)
        # The standard decoder enforces scalar syntax; its non-JSON numeric
        # extensions were rejected by the finite-number check above.
        i = end
        return Token(decoded, start, end)

    try:
        result = value()
    except RecursionError:
        raise JsonError('JSON nesting exceeds parser capacity', 0, len(raw), unsupported=True) from None
    whitespace()
    if i != len(raw):
        error('Unexpected content after JSON value')
    return result
