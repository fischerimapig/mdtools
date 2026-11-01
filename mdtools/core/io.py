"""I/O helpers shared across mdtools packages."""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any

from ._structured import Token, parse_json


class StructuredTextError(ValueError):
    """Syntax/capability error in original text, independent of spec semantics."""

    def __init__(self, message, start=0, end=0, *, unsupported=False, dependency=None):
        super().__init__(message)
        self.start, self.end = start, end
        self.unsupported, self.dependency = unsupported, dependency


def parse_structured_text(raw: str, *, format: str) -> Token:
    """Occurrence-preserving JSON or safe YAML tokens with original offsets.

    Mapping Token.value is a kind marker only; use members, never a decoded
    dict, for content. Legacy file readers below keep their original behavior.
    """
    if format == 'json':
        return parse_json(raw, preserve_duplicates=True)
    if format not in ('yaml', 'yml'):
        raise ValueError('format must be json, yaml or yml')
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:
        raise StructuredTextError('YAML requires optional dependency PyYAML',
                                  dependency='PyYAML', unsupported=True) from exc

    def fail(message, event, *, unsupported=False):
        raise StructuredTextError(message, event.start_mark.index, event.end_mark.index,
                                  unsupported=unsupported)

    try:
        # BaseLoader performs no implicit scalar resolution or object construction.
        # Check the entire stream before composing; aliases are never expanded.
        documents = 0
        for event in yaml.parse(raw, Loader=yaml.BaseLoader):
            if isinstance(event, yaml.DocumentStartEvent):
                documents += 1
                # Known limitation: PyYAML discards unknown directives (e.g.
                # %FOO) before these events. version/tags detect %YAML/%TAG only;
                # rejecting every directive would require scanner-token checks.
                if documents > 1 or event.version is not None or event.tags:
                    fail('Multiple YAML documents and directives are unsupported', event, unsupported=True)
            if (isinstance(event, yaml.AliasEvent) or getattr(event, 'anchor', None) is not None
                    or getattr(event, 'tag', None) is not None):
                fail('YAML anchors, aliases and explicit tags are unsupported', event, unsupported=True)
        root = yaml.compose(raw, Loader=yaml.BaseLoader)

        def scalar(node):
            if node.style is not None:
                return node.value
            value = node.value
            if value == '':  # YAML's omitted scalar, not an invented empty mapping.
                return None
            if value in ('true', 'false', 'null') or re.fullmatch(
                r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?', value
            ):
                try:
                    decoded = json.loads(value)
                except ValueError:
                    fail('YAML scalar exceeds decoder capacity', node, unsupported=True)
                if type(decoded) is float and not math.isfinite(decoded):
                    fail('Non-finite YAML number', node)
                return decoded
            return value  # yes/no, dates, hex, etc. are never implicitly typed.

        def token(node):
            start, end = node.start_mark.index, node.end_mark.index
            if isinstance(node, yaml.MappingNode):
                members = []
                for key, value in node.value:
                    if not isinstance(key, yaml.ScalarNode):
                        fail('YAML mapping keys must be scalar strings', key)
                    # Plain << is reserved merge syntax; quoted "<<" is data.
                    if key.style is None and key.value == '<<':
                        fail('YAML merge keys are unsupported', key, unsupported=True)
                    key_token = token(key)
                    if not isinstance(key_token.value, str):
                        fail('YAML mapping keys must be strings; quote ambiguous keys', key)
                    members.append((key_token, token(value)))
                return Token({}, start, end, tuple(members))
            if isinstance(node, yaml.SequenceNode):
                elements = tuple(token(item) for item in node.value)
                return Token([], start, end, elements=elements)
            value = scalar(node)
            if isinstance(value, str):
                try:
                    value.encode('utf-8')
                except UnicodeError:
                    fail('Unpaired surrogate in YAML scalar', node)
            return Token(value, start, end)

        return Token(None, 0, len(raw)) if root is None else token(root)
    except yaml.YAMLError as exc:
        mark = getattr(exc, 'problem_mark', None)
        start = mark.index if mark is not None else None
        raise StructuredTextError('Invalid YAML: ' + str(exc), start, start) from exc
    except RecursionError as exc:
        raise StructuredTextError('YAML nesting exceeds parser capacity', 0, len(raw),
                                  unsupported=True) from exc


class StructuredFileError(ValueError):
    """Raised when reading a structured (JSON/YAML) file fails for content reasons."""


def read_text_or_stdin(path: str | Path) -> str:
    """Read UTF-8 text from ``path``, or from stdin when ``path == '-'``."""
    if str(path) == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def write_text_or_stdout(text: str, path: str | Path | None) -> None:
    """Write UTF-8 text to ``path``, or to stdout when ``path`` is None."""
    if path is None:
        sys.stdout.write(text)
    else:
        Path(path).write_text(text, encoding="utf-8")


def dumps_json(obj: Any, *, indent: int = 2) -> str:
    """Return ``obj`` as a JSON string in mdtools' standard form."""
    return json.dumps(obj, ensure_ascii=False, indent=indent)


def read_json(path: str | Path) -> Any:
    """Read and parse a UTF-8 JSON file."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StructuredFileError(f"{path}: invalid JSON: {exc}") from exc


def write_json(path: str | Path, obj: Any, *, indent: int = 2) -> None:
    """Write ``obj`` to ``path`` as UTF-8 JSON (ensure_ascii=False, indented)."""
    Path(path).write_text(dumps_json(obj, indent=indent), encoding="utf-8")


def read_structured_file(path: str | Path) -> Any:
    """Read ``.json``, ``.yaml``, or ``.yml`` and return the parsed object."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    suffix = p.suffix.lower()
    if suffix == ".json":
        return read_json(p)
    if suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as exc:
            raise StructuredFileError(
                f"YAML support requires PyYAML (install with `pip install pyyaml`): {p}"
            ) from exc
        try:
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise StructuredFileError(f"{p}: invalid YAML: {exc}") from exc
    raise StructuredFileError(
        f"Unsupported file extension '{suffix}': {p}. Use .json, .yaml, or .yml."
    )
