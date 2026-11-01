"""Raw manuscript builders and provenance assertions shared by extraction tests.

These helpers never manufacture Requirement or FormalModel values.
"""

import json
from pathlib import Path

from mdtools.core.source import SourceSnapshot
from mdtools.spec.parser import parse_requirements


EXAMPLES = Path(__file__).resolve().parents[3] / 'docs/spec/examples'
MODEL = {'version': 1, 'id': 'MODEL-A', 'kind': 'constraint',
         'uses': ['paid'], 'when': 'paid', 'must': 'paid == true'}


def parse(raw):
    return parse_requirements(SourceSnapshot('memory:parser', raw))


def fence(raw=None, marker='```', info='mdspec'):
    return f'{marker}{info}\n{json.dumps(MODEL) if raw is None else raw}\n{marker}\n'


def requirement(body='説明。📚\n', attrs='.requirement #REQ-A spec-version=1', close=True):
    return f'::: {{{attrs}}}\n{body}' + (':::\n' if close else '')


def assert_provenance(result):
    source = result.source
    for req in result.requirements:
        assert req.key.source == source.ref
        assert source.slice(req.span).startswith((':::', ' '))
        for body in req.bodies:
            assert source.slice(body.span) == body.text
        for node in (req, *((req.model,) if req.model else ())):
            for origin in node.fields:
                if origin.location.kind == 'original':
                    assert origin.location.span.source == source.ref
                    source.offsets(origin.location.span)
                else:
                    assert origin.location.kind == 'unmapped' and origin.location.reason
                    assert origin.location.span is None
                    assert origin.container is not None
        assert all(c.status == 'not-run' and c.reason for c in result.checks.expressions)
        if req.model:
            assert all(c.status == 'not-run' and c.reason for c in req.model.checks)
    for item in result.rejected:
        assert source.slice(item.span) == item.text
        assert set(item.diagnostic_codes) <= {d.code for d in result.diagnostics}
    for diagnostic in result.diagnostics:
        assert diagnostic.primary.span.source == source.ref
        source.offsets(diagnostic.primary.span)
    assert result.checks.references.status == 'not-run' and result.checks.references.reason
