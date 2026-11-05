"""Bounded lexical helpers for reference definitions and inline links.

Labels use Unicode casefold and collapse ASCII whitespace, matching the
case-insensitive, whitespace-insensitive intent without changing source ranges.
"""
from __future__ import annotations

import re
from .model import ReferenceDefinition, SourceIndex


def normalize_label(label: str) -> str:
    return re.sub(r"[ \t\r\n]+", " ", label.strip(" \t\r\n")).casefold()


def destination(text: str, pos: int, end: int):
    if pos >= end:
        return None
    if text[pos] == "<":
        start = pos + 1
        pos = start
        while pos < end:
            if text[pos] == "\\" and pos + 1 < end:
                pos += 2
            elif text[pos] == ">":
                return start, pos, pos + 1
            elif text[pos] in "<\r\n":
                return None
            else:
                pos += 1
        return None
    start = pos
    depth = 0
    while pos < end:
        c = text[pos]
        if c == "\\" and pos + 1 < end:
            pos += 2
            continue
        if c.isspace() or ord(c) < 32:
            break
        if c == "(":
            depth += 1
            if depth > 32:
                return None
        elif c == ")":
            if not depth:
                break
            depth -= 1
        pos += 1
    return (start, pos, pos) if pos > start and depth == 0 else None


def title(text: str, pos: int, end: int):
    if pos >= end or text[pos] not in "\"' (".replace(" ", ""):
        return None
    close = ")" if text[pos] == "(" else text[pos]
    start = pos + 1
    pos = start
    while pos < end:
        if text[pos] == "\\" and pos + 1 < end:
            pos += 2
        elif text[pos] == close:
            return start, pos, pos + 1
        elif close == ")" and text[pos] == "(":
            return None
        else:
            pos += 1
    return None


def parse_reference_definition(index: SourceIndex, cp_start: int, cp_end: int):
    """Parse one physical line; spans exclude destination/title delimiters."""
    text = index.source.text
    if not 0 <= cp_start <= cp_end <= len(text):
        raise ValueError("definition bounds outside source")
    end = cp_end
    while end > cp_start and text[end - 1] in "\r\n":
        end -= 1
    pos = cp_start
    while pos < end and text[pos] == " " and pos - cp_start < 3:
        pos += 1
    if pos >= end or text[pos] != "[":
        return None
    label_start = pos + 1
    pos = label_start
    while pos < end and pos - label_start <= 999:
        if text[pos] == "\\" and pos + 1 < end:
            pos += 2
        elif text[pos] == "]":
            break
        elif text[pos] == "[":
            return None
        else:
            pos += 1
    if pos >= end or pos - label_start > 999 or pos + 1 >= end or text[pos:pos + 2] != "]:":
        return None
    label = normalize_label(text[label_start:pos])
    if not label:
        return None
    pos += 2
    while pos < end and text[pos] in " \t":
        pos += 1
    parsed = destination(text, pos, end)
    if parsed is None:
        return None
    ds, de, pos = parsed
    ws = pos
    while pos < end and text[pos] in " \t":
        pos += 1
    ts = te = None
    if pos < end and pos > ws:
        parsed_title = title(text, pos, end)
        if parsed_title:
            ts, te, pos = parsed_title
            while pos < end and text[pos] in " \t":
                pos += 1
    if pos != end:
        return None
    return ReferenceDefinition(label, index.byte_range(cp_start, cp_end), index.byte_range(ds, de),
                               index.byte_range(ts, te) if ts is not None else None)


def build_reference_lookup(references):
    """Index all definitions once; the earliest normalized label wins."""
    result = {}
    for ref in references:
        result.setdefault(ref.label, ref)
    return result
