"""Immutable values shared by independent requirement and definition producers.

Constructors validate representations, not manuscript syntax or name resolution.
Invalid input that cannot inhabit these values belongs in RejectedFragment.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
import math
import re
from typing import Literal

from mdtools.core.diagnostics import CheckResult, DiagnosticLocation
from mdtools.core.source import SourceRef, SourceSpan

Namespace = Literal['requirement', 'model', 'declaration', 'glossary']
ReferenceKind = Literal['refs', 'uses', 'type', 'glossary']
NAMESPACES = ('requirement', 'model', 'declaration', 'glossary')
REFERENCE_NAMESPACES = {
    'refs': 'requirement', 'uses': 'declaration',
    'type': 'declaration', 'glossary': 'glossary',
}
EXPRESSION_CHECKS = ('spec.expression-syntax', 'spec.expression-types',
                     'spec.expression-uses', 'spec.logic')
_ID = re.compile(r'[A-Za-z][A-Za-z0-9_.-]*\Z')
_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')
_RESERVED = {'true', 'false', 'not', 'and', 'or'}


def text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError('expected nonempty text')
    value.encode('utf-8')


def typed_tuple(value: tuple, cls: type) -> None:
    if not isinstance(value, tuple) or any(not isinstance(item, cls) for item in value):
        raise ValueError(f'expected tuple of {cls.__name__}')


def identifier(value: str, *, declaration: bool = False) -> None:
    text(value)
    if not (_NAME if declaration else _ID).fullmatch(value):
        raise ValueError('invalid identifier')
    if declaration and value in _RESERVED:
        raise ValueError('reserved declaration name')


def expression_checks() -> tuple[CheckResult, ...]:
    return tuple(CheckResult(name, 'not-run', 'M3 check; not executed by M2')
                 for name in EXPRESSION_CHECKS)


@dataclass(frozen=True)
class NodeKey:
    """Occurrence identity, NOT a regenerated semantic ID.

    Ordinals are unique across node kinds within one snapshot, in source order.
    The name is the author-provided semantic ID. Duplicates retain distinct keys.
    """

    namespace: Namespace
    name: str
    source: SourceRef
    ordinal: int

    def __post_init__(self) -> None:
        if self.namespace not in NAMESPACES or not isinstance(self.source, SourceRef):
            raise ValueError('invalid node namespace/source')
        if self.namespace == 'glossary':
            if not isinstance(self.name, str) or not self.name:
                raise ValueError('glossary ID must be a nonempty string')
            self.name.encode('utf-8')
        else:
            text(self.name)
        if self.namespace in ('requirement', 'model'):
            identifier(self.name)
        if type(self.ordinal) is not int or self.ordinal < 0:
            raise ValueError('ordinal must be a nonnegative integer')


@dataclass(frozen=True)
class FieldSource:
    """Field identity plus M1 provenance, with an optional known manuscript range.

    Paths are RFC 6901 pointers relative to the represented object; requirement
    attributes use /id, /spec-version, /status and /refs. Declaration names use
    /name (a normalized model field, not a claim about an input JSON key).
    """

    path: str
    location: DiagnosticLocation
    container: SourceSpan | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or (self.path and not self.path.startswith('/')):
            raise ValueError('field path must be a JSON pointer')
        if re.search(r'~(?![01])', self.path):
            raise ValueError('invalid JSON pointer escape')
        self.path.encode('utf-8')
        if not isinstance(self.location, DiagnosticLocation):
            raise ValueError('field location requires DiagnosticLocation')
        if self.container is not None and not isinstance(self.container, SourceSpan):
            raise ValueError('field container requires SourceSpan')
        if self.location.kind == 'original' and self.container is not None:
            span = self.location.span
            if (span.source != self.container.source
                    or span.start < self.container.start or span.end > self.container.end):
                raise ValueError('original field is outside its container')


@dataclass(frozen=True)
class Reference:
    kind: ReferenceKind
    name: str
    origin: FieldSource

    def __post_init__(self) -> None:
        if self.kind not in REFERENCE_NAMESPACES or not isinstance(self.origin, FieldSource):
            raise ValueError('invalid reference kind/origin')
        if self.kind == 'glossary':
            if not isinstance(self.name, str) or not self.name:
                raise ValueError('glossary ID must be a nonempty string')
            self.name.encode('utf-8')
        else:
            text(self.name)
        if self.kind == 'refs':
            identifier(self.name)
        elif self.kind == 'uses':
            identifier(self.name, declaration=True)
        elif self.kind == 'type':
            identifier(self.name)


@dataclass(frozen=True)
class Body:
    language: str | None
    text: str
    span: SourceSpan

    def __post_init__(self) -> None:
        if self.language is not None:
            text(self.language)
        if not isinstance(self.text, str) or not isinstance(self.span, SourceSpan):
            raise ValueError('body requires text and original span')
        self.text.encode('utf-8')


@dataclass(frozen=True)
class Expression:
    text: str
    origin: FieldSource

    def __post_init__(self) -> None:
        text(self.text)
        if not isinstance(self.origin, FieldSource):
            raise ValueError('expression requires field provenance')


def _node(key, span, origins, namespace, required) -> None:
    if not isinstance(key, NodeKey) or key.namespace != namespace:
        raise ValueError('node has wrong namespace')
    if not isinstance(span, SourceSpan) or span.source != key.source:
        raise ValueError('node span does not belong to its snapshot')
    typed_tuple(origins, FieldSource)
    paths = [item.path for item in origins]
    if len(set(paths)) != len(paths) or not set(required) <= set(paths):
        raise ValueError('missing or duplicate field provenance')
    for origin in origins:
        _origin_in_span(origin, span)


def _origin_in_span(origin, span) -> None:
    ranges = (origin.container, origin.location.span if origin.location.kind == 'original' else None)
    for item in ranges:
        if item is not None and (item.source != span.source or item.start < span.start or item.end > span.end):
            raise ValueError('field provenance is outside its node')


def _references(items, kind) -> None:
    typed_tuple(items, Reference)
    if any(item.kind != kind for item in items):
        raise ValueError('wrong reference kind')
    if kind == 'uses' and len({item.name for item in items}) != len(items):
        raise ValueError('duplicate explicit reference')


@dataclass(frozen=True)
class FormalModel:
    key: NodeKey
    span: SourceSpan
    fields: tuple[FieldSource, ...]
    uses: tuple[Reference, ...]
    when: Expression
    must: Expression
    version: int = 1
    kind: str = 'constraint'
    checks: tuple[CheckResult, ...] = field(default_factory=expression_checks)

    def __post_init__(self) -> None:
        _node(self.key, self.span, self.fields, 'model',
              ('/version', '/id', '/kind', '/uses', '/when', '/must'))
        if type(self.version) is not int or self.version != 1 or self.kind != 'constraint':
            raise ValueError('only model v1 constraint is representable')
        _references(self.uses, 'uses')
        if any(ref.origin.path != f'/uses/{index}' for index, ref in enumerate(self.uses)):
            raise ValueError('uses requires per-element field provenance')
        for ref in self.uses:
            _origin_in_span(ref.origin, self.span)
        if not isinstance(self.when, Expression) or not isinstance(self.must, Expression):
            raise ValueError('model requires expressions')
        if self.when.origin.path != '/when' or self.must.origin.path != '/must':
            raise ValueError('wrong expression field')
        if self.when.origin not in self.fields or self.must.origin not in self.fields:
            raise ValueError('expression and model provenance disagree')
        typed_tuple(self.checks, CheckResult)
        if {c.check_id for c in self.checks} != set(EXPRESSION_CHECKS) or len(self.checks) != 4:
            raise ValueError('model requires all four explicit M3 checks')
        if any(c.status != 'not-run' for c in self.checks):
            raise ValueError('M2 cannot claim execution of M3 checks')


@dataclass(frozen=True)
class Requirement:
    key: NodeKey
    span: SourceSpan
    fields: tuple[FieldSource, ...]
    bodies: tuple[Body, ...]
    structure: CheckResult
    formalization: Literal['natural-only', 'present']
    model: FormalModel | None = None
    refs: tuple[Reference, ...] = ()
    version: int = 1
    status: Literal['draft', 'active', 'deprecated'] = 'draft'

    def __post_init__(self) -> None:
        _node(self.key, self.span, self.fields, 'requirement', ('/id', '/spec-version', '/status'))
        typed_tuple(self.bodies, Body)
        if not self.bodies or not any(b.text.strip() for b in self.bodies):
            raise ValueError('requirement body must not be empty')
        if any(b.span.source != self.key.source or b.span.start < self.span.start
               or b.span.end > self.span.end for b in self.bodies):
            raise ValueError('body must belong to its requirement')
        _references(self.refs, 'refs')
        if self.refs and '/refs' not in {item.path for item in self.fields}:
            raise ValueError('refs requires attribute provenance')
        if any(ref.origin.path != f'/refs/{index}' for index, ref in enumerate(self.refs)):
            raise ValueError('refs requires per-element field provenance')
        for ref in self.refs:
            _origin_in_span(ref.origin, self.span)
        if type(self.version) is not int or self.version != 1:
            raise ValueError('only requirement v1 is representable')
        if self.status not in ('draft', 'active', 'deprecated'):
            raise ValueError('invalid lifecycle status')
        if not isinstance(self.structure, CheckResult) or self.structure.check_id != 'spec.structure':
            raise ValueError('requirement requires structural check')
        if self.formalization not in ('natural-only', 'present'):
            raise ValueError('invalid formalization state')
        if self.model is not None:
            if not isinstance(self.model, FormalModel) or self.formalization != 'present':
                raise ValueError('model requires present formalization')
            if (self.model.key.source != self.key.source
                    or self.model.span.start < self.span.start or self.model.span.end > self.span.end):
                raise ValueError('model must belong to its requirement')
        elif self.formalization == 'present' and self.structure.status == 'passed':
            raise ValueError('broken formal model must not pass structure')


@dataclass(frozen=True)
class JsonObject:
    """Immutable JSON object for glossary data; tuples alone represent arrays."""

    items: tuple[tuple[str, JsonValue], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple):
            raise ValueError('object items must be a tuple')
        keys = []
        for pair in self.items:
            if not isinstance(pair, tuple) or len(pair) != 2 or not isinstance(pair[0], str):
                raise ValueError('invalid JSON object member')
            pair[0].encode('utf-8')
            keys.append(pair[0])
            _json_value(pair[1])
        if len(set(keys)) != len(keys):
            raise ValueError('duplicate JSON object key')


type JsonValue = None | bool | int | float | str | tuple[JsonValue, ...] | JsonObject


def _json_value(value) -> None:
    if value is None or type(value) in (bool, int) or isinstance(value, JsonObject):
        return
    if type(value) is float and math.isfinite(value):
        return
    if isinstance(value, str):
        value.encode('utf-8')
        return
    if isinstance(value, tuple):
        for item in value:
            _json_value(item)
        return
    raise ValueError('expected immutable finite JSON value')


@dataclass(frozen=True)
class GlossaryEntry:
    key: NodeKey
    span: SourceSpan
    fields: tuple[FieldSource, ...]
    kind: Literal['term', 'const', 'symbol']
    data: JsonObject

    def __post_init__(self) -> None:
        _node(self.key, self.span, self.fields, 'glossary', ('/id', '/kind'))
        if self.kind not in ('term', 'const', 'symbol') or not isinstance(self.data, JsonObject):
            raise ValueError('invalid glossary kind/data')
        if any(name in ('id', 'kind') for name, value in self.data.items):
            raise ValueError('id/kind belong to glossary fields, not data')


@dataclass(frozen=True)
class Declaration:
    key: NodeKey
    span: SourceSpan
    fields: tuple[FieldSource, ...]
    kind: Literal['type', 'variable', 'constant']
    type_ref: Reference | None = None
    role: Literal['input', 'output'] | None = None
    minimum: int | None = None
    maximum: int | None = None
    values: tuple[str, ...] = ()
    value: bool | int | str | None = None
    glossary: Reference | None = None

    def __post_init__(self) -> None:
        _node(self.key, self.span, self.fields, 'declaration', ('/name',))
        if self.kind not in ('type', 'variable', 'constant'):
            raise ValueError('invalid declaration kind')
        identifier(self.key.name, declaration=self.kind != 'type')
        if self.key.name in ('bool', 'int'):
            raise ValueError('builtin type names cannot be redeclared')
        typed_tuple(self.values, str)
        if self.glossary is not None and (not isinstance(self.glossary, Reference) or self.glossary.kind != 'glossary'):
            raise ValueError('invalid glossary association')
        if self.glossary is not None and (self.glossary.origin.path != '/glossary'
                                         or self.glossary.origin not in self.fields):
            raise ValueError('glossary association requires matching field provenance')
        if self.kind == 'type':
            if (not self.values or len(set(self.values)) != len(self.values)
                    or any(not value for value in self.values)
                    or any(v is not None for v in (self.type_ref, self.role, self.minimum, self.maximum, self.value))):
                raise ValueError('enum type requires distinct nonempty string values only')
            for value in self.values:
                value.encode('utf-8')
            _required_fields(self.fields, ('/kind', '/values'))
        else:
            if not isinstance(self.type_ref, Reference) or self.type_ref.kind != 'type' or self.values:
                raise ValueError('variable/constant requires a type reference')
            if self.type_ref.origin.path != '/type' or self.type_ref.origin not in self.fields:
                raise ValueError('type reference requires matching field provenance')
            _required_fields(self.fields, ('/type',))
            if self.kind == 'variable':
                if self.role not in ('input', 'output') or self.value is not None:
                    raise ValueError('variable requires input/output role and no value')
                _required_fields(self.fields, ('/role',))
            else:
                if self.role is not None or type(self.value) not in (bool, int, str):
                    raise ValueError('constant requires a bool/int/string literal and no role')
                _required_fields(self.fields, ('/value',))
                if isinstance(self.value, str):
                    self.value.encode('utf-8')
            if self.type_ref.name == 'int':
                if (type(self.minimum) is not int or type(self.maximum) is not int
                        or self.minimum > self.maximum):
                    raise ValueError('int requires ordered integer bounds')
                _required_fields(self.fields, ('/min', '/max'))
                if self.kind == 'constant' and (type(self.value) is not int
                                              or not self.minimum <= self.value <= self.maximum):
                    raise ValueError('integer constant outside declared domain')
            elif self.minimum is not None or self.maximum is not None:
                raise ValueError('bounds are only valid for int')
            if self.kind == 'constant':
                expected = bool if self.type_ref.name == 'bool' else str
                if self.type_ref.name != 'int' and type(self.value) is not expected:
                    raise ValueError('constant literal does not match declared type')


def _required_fields(origins, required) -> None:
    if not set(required) <= {origin.path for origin in origins}:
        raise ValueError('missing declaration field provenance')


@dataclass(frozen=True)
class RejectedFragment:
    """Raw reserved input that could not become a valid typed record."""

    kind: Literal['requirement', 'model', 'definition', 'glossary']
    span: SourceSpan
    text: str
    diagnostic_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.kind not in ('requirement', 'model', 'definition', 'glossary'):
            raise ValueError('invalid rejected fragment kind')
        if not isinstance(self.span, SourceSpan) or not isinstance(self.text, str):
            raise ValueError('rejected fragment requires original text/span')
        typed_tuple(self.diagnostic_codes, str)
        if not self.diagnostic_codes:
            raise ValueError('rejected input requires diagnostics')


def walk_values(value):
    """Walk contract values for snapshot validation; never read source files."""
    yield value
    if isinstance(value, (SourceSpan, SourceRef)):
        return
    if is_dataclass(value):
        for item in fields(value):
            yield from walk_values(getattr(value, item.name))
    elif isinstance(value, tuple):
        for item in value:
            yield from walk_values(item)
