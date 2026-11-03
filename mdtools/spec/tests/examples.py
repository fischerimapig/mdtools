"""Hand-authored contract values, NOT an extractor or a definition loader.

Every token/body selector below is supplied explicitly by a test author.
The actual production parsing of these fixtures belongs to #36 and #37.
"""

from pathlib import Path

from mdtools.core.diagnostics import CheckResult, Diagnostic, DiagnosticLocation
from mdtools.core.source import SourceSnapshot
from mdtools.spec.model import (
    Body, Declaration, Expression, FieldSource, FormalModel, GlossaryEntry,
    JsonObject, NodeKey, Reference, RejectedFragment, Requirement,
)
from mdtools.spec.results import AnalysisChecks, LocalAnalysis

FIXTURES = Path(__file__).resolve().parents[3] / 'docs/spec/examples/model-contract'


def checks(structure='passed', declarations='passed', references='not-run'):
    def check(name, status):
        return CheckResult('spec.' + name, status,
                           'Deferred or unavailable in this scope' if status in ('not-run', 'error', 'unsupported', 'unknown') else None)
    return AnalysisChecks(check('structure', structure), check('declarations', declarations),
                          check('references', references))


def span(source, raw, *, container=None):
    start, end = source.offsets(container) if container is not None else (0, len(source.text))
    offset = source.text.index(raw, start, end)
    return source.span(offset, offset + len(raw))


def origin(source, path, raw=None, *, container=None):
    location = (DiagnosticLocation('original', span(source, raw, container=container)) if raw is not None
                else DiagnosticLocation('unmapped', reason='No exact token mapping available'))
    return FieldSource(path, location, container)


def requirement(source, name, body_parts, *, model=None, formalization=None,
                structural='passed', active=False, block=None):
    block = block or source.span()
    origins = (
        origin(source, '/id', name, container=block),
        origin(source, '/spec-version', 'spec-version=1', container=block),
        origin(source, '/status', 'status=active' if active else None, container=block),
    )
    return Requirement(NodeKey('requirement', name, source.ref, 0), block, origins,
                       tuple(Body(lang, raw, span(source, raw, container=block)) for lang, raw in body_parts),
                       CheckResult('spec.structure', structural),
                       formalization or ('present' if model else 'natural-only'), model,
                       status='active' if active else 'draft')


def normal_model(source, name, when, must, *, uses=(), raw_must=None):
    import json
    start = source.text.index('{\n')
    block = source.span(start, source.text.index('\n```', start))
    origins = tuple(origin(source, path, raw, container=block) for path, raw in (
        ('/version', '"version": 1'), ('/id', json.dumps(name)),
        ('/kind', '"kind": "constraint"'), ('/uses', '"uses": ' + json.dumps(list(uses))),
        ('/when', '"when": ' + json.dumps(when)),
        ('/must', '"must": ' + (raw_must or json.dumps(must))),
    ))
    refs = tuple(Reference('uses', value, origin(source, f'/uses/{i}', json.dumps(value), container=block))
                 for i, value in enumerate(uses))
    return FormalModel(NodeKey('model', name, source.ref, 1), block, origins, refs,
                       Expression(when, origins[4]), Expression(must, origins[5]))


def fixture_result(name):
    source = SourceSnapshot.from_path(FIXTURES / name)
    if name == 'normal.md':
        model = normal_model(source, 'MODEL-NORMAL', 'paid', 'paid == true', uses=('paid',))
        req = requirement(source, 'REQ-NORMAL', ((None, '支払い済みなら処理を許可する。\n'),), model=model, active=True)
    elif name == 'unchecked.md':
        model = normal_model(source, 'MODEL-UNCHECKED', 'paid and (', 'paid == true', raw_must='"\\u0070aid == true"')
        req = requirement(source, 'REQ-UNCHECKED', ((None, '式はM3で検査する。\n'),), model=model)
    elif name == 'natural-only.md':
        req = requirement(source, 'REQ-NATURAL', ((None, '利用者に処理状況を表示する。\n'),))
    elif name == 'multilingual.md':
        req = requirement(source, 'REQ-MULTILINGUAL', (
            ('ja', '処理状況を表示する。📚\n'), ('en', 'Show the processing status.\n')))
    elif name == 'invalid.md':
        bad = span(source, '::: {.requirement spec-version=1}\nIDが欠落している。\n:::\n')
        good = source.span(source.text.index('::: {.requirement #REQ-RECOVER'))
        req = requirement(source, 'REQ-RECOVER', ((None, '回復後もこの要件を保持する。\n'),), block=good)
        diagnostic = Diagnostic('spec.invalid-requirement', 'error', 'user', 'Missing requirement ID',
                                DiagnosticLocation('original', bad))
        rejected = RejectedFragment('requirement', bad, source.slice(bad), (diagnostic.code,))
        return LocalAnalysis(source, checks('failed'), 'partial', (req,), rejected=(rejected,), diagnostics=(diagnostic,))
    elif name == 'broken-model.md':
        bad = span(source, '{"version": 1, "id": "MODEL-BROKEN", "kind": "constraint", "uses": []}')
        req = requirement(source, 'REQ-BROKEN', ((None, '形式記述が壊れていてもnatural-onlyにしない。\n'),),
                          structural='failed', formalization='present')
        diagnostic = Diagnostic('spec.invalid-model', 'error', 'user', 'Missing when and must',
                                DiagnosticLocation('original', bad), requirement_id='REQ-BROKEN')
        rejected = RejectedFragment('model', bad, source.slice(bad), (diagnostic.code,))
        return LocalAnalysis(source, checks('failed'), 'partial', (req,), rejected=(rejected,), diagnostics=(diagnostic,))
    elif name == 'unsupported.md':
        diagnostic = Diagnostic('spec.unsupported-version', 'error', 'unsupported', 'Unsupported spec-version=2',
                                DiagnosticLocation('original', source.span()))
        rejected = RejectedFragment('requirement', source.span(), source.text, (diagnostic.code,))
        return LocalAnalysis(source, checks('unsupported'), 'partial', rejected=(rejected,), diagnostics=(diagnostic,))
    else:
        raise AssertionError('No hand-authored expectation for ' + name)
    return LocalAnalysis(source, checks(), 'complete', (req,))


def definition_results():
    source = SourceSnapshot.from_path(FIXTURES / 'definitions.json')

    def declaration(name, ordinal, kind, raw, members, *, type_name=None, glossary=None, **kwargs):
        block = span(source, raw)
        origins = tuple(origin(source, path, token, container=block) for path, token in (('/name', '"' + name + '"'), *members))
        type_ref = Reference('type', type_name, next(o for o in origins if o.path == '/type')) if type_name else None
        glossary_ref = Reference('glossary', glossary, next(o for o in origins if o.path == '/glossary')) if glossary else None
        return Declaration(NodeKey('declaration', name, source.ref, ordinal), block, origins, kind,
                           type_ref=type_ref, glossary=glossary_ref, **kwargs)

    state = declaration('OrderState', 0, 'type',
                        '"OrderState": {"kind": "enum", "values": ["new", "paid"], "glossary": "order-state"}',
                        (('/kind', '"enum"'), ('/values', '["new", "paid"]'), ('/glossary', '"order-state"')),
                        values=('new', 'paid'), glossary='order-state')
    paid = declaration('paid', 1, 'variable',
                       '"paid": {"type": "bool", "role": "input", "glossary": "paid label"}',
                       (('/type', '"bool"'), ('/role', '"input"'), ('/glossary', '"paid label"')),
                       type_name='bool', role='input', glossary='paid label')
    window = declaration('window', 2, 'constant',
                         '"window": {"type": "int", "min": 0, "max": 30, "value": 14}',
                         (('/type', '"int"'), ('/min', '0'), ('/max', '30'), ('/value', '14')),
                         type_name='int', minimum=0, maximum=30, value=14)
    initial = declaration('initial', 3, 'constant',
                          '"initial": {"type": "OrderState", "value": "new", "glossary": "order-state"}',
                          (('/type', '"OrderState"'), ('/value', '"new"'), ('/glossary', '"order-state"')),
                          type_name='OrderState', value='new', glossary='order-state')
    definitions = LocalAnalysis(source, checks(), 'complete', declarations=(state, paid, window, initial))
    source = SourceSnapshot.from_path(FIXTURES / 'glossary.json')
    entries = []
    for ordinal, (name, kind, raw, data) in enumerate((
        ('paid label', 'term', '{"id": "paid label", "kind": "term", "names": {"ja": "支払い済み", "en": "Paid"}}',
         JsonObject((('names', JsonObject((('ja', '支払い済み'), ('en', 'Paid')))),))),
        ('order-state', 'symbol', '{"id": "order-state", "kind": "symbol", "symbol": "S"}',
         JsonObject((('symbol', 'S'),))),
    )):
        block = span(source, raw)
        origins = (origin(source, '/id', '"' + name + '"', container=block), origin(source, '/kind', '"' + kind + '"', container=block))
        entries.append(GlossaryEntry(NodeKey('glossary', name, source.ref, ordinal), block, origins, kind, data))
    glossary = LocalAnalysis(source, checks(), 'complete', glossary=tuple(entries))
    return definitions, glossary
