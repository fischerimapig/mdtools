"""Real text builders and assertions; no hand-built declaration models."""

import json
from pathlib import Path

from mdtools.core.diagnostics import DiagnosticLocation
from mdtools.core.source import SourceSnapshot, SourceSpan
from mdtools.spec.loader import load_definitions
from mdtools.spec.model import FieldSource, walk_values

EXAMPLES = Path(__file__).resolve().parents[3] / 'docs/spec/examples'


def document(**updates):
    return {'version': 1, 'types': {}, 'variables': {}, 'constants': {}, **updates}


def load(raw, *, kind='spec', format='json'):
    if not isinstance(raw, str):
        raw = json.dumps(raw, ensure_ascii=False)
    result = load_definitions(SourceSnapshot('memory:definitions', raw), kind=kind, format=format)
    assert_provenance(result)
    return result


def assert_provenance(result):
    source = result.source
    for value in walk_values(result):
        if isinstance(value, SourceSpan):
            assert value.source == source.ref
            source.offsets(value)
        if isinstance(value, DiagnosticLocation):
            if value.kind == 'unmapped':
                assert value.span is None and value.reason
        if isinstance(value, FieldSource):
            assert value.container is not None
    for item in result.rejected:
        assert source.slice(item.span) == item.text
        assert set(item.diagnostic_codes) <= {d.code for d in result.diagnostics}
    assert len({key.ordinal for key in result.nodes}) == len(result.nodes)
    assert [key.ordinal for key in result.nodes] == sorted(key.ordinal for key in result.nodes)
    for check in (result.checks.references, *result.checks.expressions):
        assert check.status == 'not-run' and check.reason
    result.report


def meanings(result):
    return [(d.kind, d.key.name, d.type_ref.name if d.type_ref else None, d.role,
             d.minimum, d.maximum, d.values, d.value, d.glossary.name if d.glossary else None)
            for d in result.declarations]
