"""Diagnostic contracts: source identity, state, deterministic equivalent output."""

import json
from dataclasses import FrozenInstanceError, replace
from itertools import permutations
from pathlib import Path

import pytest

from mdtools.core.diagnostics import (
    CheckResult, Diagnostic, DiagnosticLocation as Location, DiagnosticReport,
    Evidence, RelatedLocation, render_json, render_text, report_to_dict,
)
from mdtools.core.source import SourceMapBuilder, SourcePosition, SourceRef, SourceSnapshot, SourceSpan


def test_multiple_manuscripts_and_versions_are_retained_after_edit(tmp_path):
    paths = [tmp_path / name for name in ('節 日本😀.md', '別節\n"\\.md')]
    for path in paths:
        path.write_bytes('日本😀\r\n次'.encode())
    a, b = (SourceSnapshot.from_path(path) for path in paths)
    paths[0].write_text('更新', encoding='utf-8')
    newer = SourceSnapshot.from_path(paths[0])
    diagnostic = Diagnostic(
        'example.conflict', 'error', 'user', '宣言の衝突😀\n"理由"\\\t',
        Location('original', a.span(1, 3)),
        (RelatedLocation('別の原稿', Location('original', b.span(1, 3)), 'REQ-B'),
         RelatedLocation('更新後', Location('original', newer.span()), 'REQ-A')),
        'REQ-A', (Evidence('example.assumption', '前提\r\npaid=true', Location('original', b.span())),),
    )
    report = DiagnosticReport((diagnostic,), (CheckResult('example.check', 'failed'),), (a, b, newer))
    assert report.sources == (a, b, newer)
    assert a.ref.snapshot == b.ref.snapshot
    assert a.ref != b.ref and a.ref != newer.ref
    assert a.slice(diagnostic.primary.span) == '本😀'
    with pytest.raises(FrozenInstanceError):
        diagnostic.message = 'changed'
    data = json.loads(render_json(report))
    assert data == report_to_dict(report)
    primary = data['diagnostics'][0]['primary']['span']
    assert primary == {
        'source': {'uri': a.uri, 'snapshot': a.ref.snapshot, 'path': str(a.path)},
        'start': {'line': 1, 'column': 2}, 'end': {'line': 1, 'column': 4},
    }
    assert {s['snapshot'] for s in data['sources']} == {a.ref.snapshot, newer.ref.snapshot}
    assert '節 日本😀.md' in render_text(report)
    assert '\\n\\"\\\\.md' in render_text(report)


def test_empty_report_and_explicit_check_states_never_infer_success():
    assert render_json(DiagnosticReport()) == (
        '{\n  "checks": [],\n  "diagnostics": [],\n  "schema_version": 1,\n  "sources": []\n}\n'
    )
    assert render_text(DiagnosticReport()) == 'diagnostics schema_version=1\ndiagnostic_count=0\n'
    statuses = ('not-run', 'passed', 'failed', 'unknown', 'unsupported', 'error')
    checks = tuple(CheckResult(f'example.check-{i}', status, '明示した理由') for i, status in enumerate(statuses))
    data = report_to_dict(DiagnosticReport(checks=checks))
    assert [c['status'] for c in data['checks']] == list(statuses)
    assert data['diagnostics'] == []
    assert 'status=not-run' in render_text(DiagnosticReport(checks=checks))
    assert 'status=passed' not in render_text(DiagnosticReport(checks=(checks[0],)))


@pytest.mark.parametrize('category', ['user', 'unsupported', 'unknown', 'not-run', 'tool-error'])
@pytest.mark.parametrize('severity', ['error', 'warning', 'info', 'hint'])
def test_independent_classification_and_optional_fields(category, severity):
    diagnostic = Diagnostic('example.code', severity, category, '説明')
    data = report_to_dict(DiagnosticReport((diagnostic,)))['diagnostics'][0]
    assert data == dict(code='example.code', severity=severity, category=category, message='説明',
                        primary={'kind': 'none'}, related=[], evidence=[])
    text = render_text(DiagnosticReport((diagnostic,)))
    assert f'severity={severity} category={category}' in text
    assert 'primary kind=none' in text


def test_mapped_locations_preserve_original_and_artifact_without_guessing():
    source = SourceSnapshot('memory:section', '日😀\r\n')
    builder = SourceMapBuilder()
    builder.add_synthetic('# Heading\n', 'heading')
    builder.add_source(source, normalize_newlines=True)
    builder.add_unmapped('changed', 'unsupported-transform')
    mapped = builder.build('memory:composed')
    locations = [Location.from_mapping(part) for part in mapped.resolve(mapped.artifact.span())]
    assert [loc.kind for loc in locations] == ['synthetic', 'original', 'original', 'unmapped']
    assert [loc.span.source for loc in locations] == [mapped.artifact.ref, source.ref, source.ref, mapped.artifact.ref]
    assert source.slice(locations[2].span) == '\r\n'
    diagnostic = Diagnostic('example.mapping', 'warning', 'unsupported', '部分対応', locations[0],
                            tuple(RelatedLocation('断片', loc) for loc in locations[1:]))
    report = DiagnosticReport((diagnostic,), sources=(*mapped.inputs, mapped.artifact))
    text = render_text(report)
    assert 'kind=synthetic' in text and 'kind=unmapped' in text
    assert 'reason="unsupported-transform"' in text
    assert report_to_dict(report)['diagnostics'][0]['primary']['span']['source']['uri'] == 'memory:composed'
    no_map = Diagnostic('example.mapping-failed', 'error', 'tool-error', 'map構築失敗',
                        Location('unmapped', reason='issue #31: no map was produced'))
    assert 'span' not in report_to_dict(DiagnosticReport((no_map,)))['diagnostics'][0]['primary']


def test_total_order_including_ties_nested_order_and_duplicates():
    a = SourceSnapshot('memory:a', 'ab')
    b = SourceSnapshot('memory:b', 'ab')
    base = Diagnostic('example.a', 'error', 'user', 'z', Location('original', a.span(0, 1)))
    related = (RelatedLocation('z', Location('original', b.span())),
               RelatedLocation('a', Location('original', a.span())))
    evidence = (Evidence('example.z', 'z'), Evidence('example.a', 'a'))
    items = (
        replace(base, primary=Location('original', b.span())),
        replace(base, primary=Location('original', a.span(1))),
        replace(base, code='example.b'),
        replace(base, requirement_id='REQ-B'),
        replace(base, message='a', related=related, evidence=evidence),
        base,
        replace(base, primary=Location()),
    )
    expected = render_json(DiagnosticReport(items, sources=(a, b)))
    expected_text = render_text(DiagnosticReport(items, sources=(a, b)))
    # All permutations of diagnostic insertion order, plus reversed nested inputs.
    for permuted in permutations(items):
        permuted = tuple(replace(d, related=tuple(reversed(d.related)), evidence=tuple(reversed(d.evidence)))
                         for d in permuted)
        report = DiagnosticReport(permuted, sources=(b, a))
        assert render_json(report) == expected
        assert render_text(report) == expected_text
    ordered = json.loads(expected)['diagnostics']
    assert ordered[:2] == [report_to_dict(DiagnosticReport((d,), sources=(a, b)))['diagnostics'][0]
                           for d in (base, items[4])]
    assert ordered[-1]['primary']['kind'] == 'none'
    assert len(report_to_dict(DiagnosticReport((base, base), sources=(a,)))['diagnostics']) == 2
    checks = (CheckResult('example.b', 'passed'), CheckResult('example.a', 'not-run', '未実行'))
    assert render_text(DiagnosticReport(checks=checks)) == render_text(DiagnosticReport(checks=checks[::-1]))


# A test-side reader verifies every field of the readable format independently.
# Production only promises output, not a text-input protocol.
def fields(text):
    result = {}
    while text:
        key, text = text.split('=', 1)
        if text.startswith('"'):
            value, consumed = json.JSONDecoder().raw_decode(text)
            text = text[consumed:].lstrip()
        else:
            value, _, text = text.partition(' ')
        result[key] = value
    return result


def location_fields(location):
    result = {'kind': location['kind']}
    if 'span' in location:
        span = location['span']
        result.update(span['source'])
        a, b = span['start'], span['end']
        result['range'] = f"[{a['line']}:{a['column']},{b['line']}:{b['column']})"
    if 'reason' in location:
        result['reason'] = location['reason']
    return result


def test_text_json_full_content_equivalence_and_control_escaping():
    message = '日本😀e\u0301\n\r\t"\\\x00\x1b\x85\u2028\u202e'
    path = Path('/原稿 😀\n"\\.md')
    source = SourceSnapshot(path.as_uri(), '日😀\r\n', path)
    loc = Location('original', source.span())
    d = Diagnostic('example.code', 'warning', 'unknown', message, loc,
                   (RelatedLocation(message, Location('synthetic', source.span(0, 0), message), message),
                    RelatedLocation('位置なし', Location())), message,
                   (Evidence('example.fact', message, loc), Evidence('example.context', message)))
    report = DiagnosticReport((d,), (CheckResult('example.check', 'unknown', message),), (source,))
    data = json.loads(render_json(report))
    lines = iter(render_text(report).splitlines())
    assert next(lines) == 'diagnostics schema_version=1'
    assert fields(next(lines).removeprefix('source ')) == data['sources'][0]
    check = data['checks'][0]
    assert fields(next(lines).removeprefix('check ' + check['check_id'] + ' ')) == {
        'status': check['status'], 'reason': check['reason'],
    }
    assert next(lines) == 'diagnostic_count=1'
    diagnostic = data['diagnostics'][0]
    assert fields(next(lines).removeprefix(diagnostic['code'] + ' ')) == {
        key: diagnostic[key] for key in ('severity', 'category', 'message')
    }
    assert fields(next(lines).strip()) == {'requirement_id': diagnostic['requirement_id']}
    assert fields(next(lines).removeprefix('  primary ')) == location_fields(diagnostic['primary'])
    for related in diagnostic['related']:
        expected = {'message': related['message'], **location_fields(related['location'])}
        if 'requirement_id' in related:
            expected['requirement_id'] = related['requirement_id']
        assert fields(next(lines).removeprefix('  related ')) == expected
    for evidence in diagnostic['evidence']:
        expected = {'message': evidence['message']}
        if 'location' in evidence:
            expected.update(location_fields(evidence['location']))
        assert fields(next(lines).removeprefix('  evidence ' + evidence['kind'] + ' ')) == expected
    assert list(lines) == []
    rendered = render_text(report)
    assert '\x1b' not in rendered and '\u202e' not in rendered
    assert '\\u001b' in rendered and '\\u202e' in rendered
    assert '日本😀e\u0301' in rendered


@pytest.mark.parametrize('factory', [
    lambda: Diagnostic('BAD CODE', 'error', 'user', 'x'),
    lambda: Diagnostic('example.code', 'fatal', 'user', 'x'),
    lambda: Diagnostic('example.code', 'error', 'failed', 'x'),
    lambda: Diagnostic('example.code', 'error', 'user', ''),
    lambda: Diagnostic('example.code', 'error', 'user', '\ud800'),
    lambda: Diagnostic('example.code', 'error', 'user', 'x', requirement_id=''),
    lambda: Diagnostic('example.code', 'error', 'user', 'x', related=[]),
    lambda: Location('original'), lambda: Location('none', reason='x'),
    lambda: Location('synthetic'), lambda: Location('unmapped', reason=''),
    lambda: Location('bad'), lambda: Location('original', 'fake'),
    lambda: Evidence('example.fact', ''), lambda: Evidence('bad kind', 'x'),
    lambda: Evidence('example.fact', 'x', location='fake'),
    lambda: RelatedLocation('x', 'fake'),
    lambda: CheckResult('example.check', 'unknown'),
    lambda: CheckResult('example.check', 'unsupported'),
    lambda: CheckResult('example.check', 'error'),
    lambda: CheckResult('example.check', 'not-run'),
    lambda: CheckResult('example.check', 'invalid'),
    lambda: DiagnosticReport(checks=(CheckResult('example.a', 'passed'), CheckResult('example.a', 'failed'))),
    lambda: DiagnosticReport(sources=[SourceSnapshot('memory:a', '')]),
])
def test_invalid_models_are_rejected(factory):
    with pytest.raises((ValueError, UnicodeError)):
        factory()


def test_report_rejects_missing_wrong_snapshot_and_nonexistent_ranges():
    a = SourceSnapshot('memory:a', 'a\r\n')
    b = SourceSnapshot('memory:a', 'changed')
    diagnostic = Diagnostic('example.code', 'error', 'user', 'x', Location('original', a.span()))
    for sources in ((), (b,), (a, a)):
        with pytest.raises(ValueError):
            DiagnosticReport((diagnostic,), sources=sources)
    outside = SourceSpan(a.ref, SourcePosition(1, 1), SourcePosition(1, 9))
    with pytest.raises(ValueError, match='column'):
        DiagnosticReport((replace(diagnostic, primary=Location('original', outside)),), sources=(a,))
    # The optional path hint does not change identity or require rereading a file.
    ref = SourceRef(a.uri, a.ref.snapshot)
    span = SourceSpan(ref, a.span().start, a.span().end)
    assert DiagnosticReport((replace(diagnostic, primary=Location('original', span)),), sources=(a,))
