"""Validate the public wire contract with the dev-only Draft 2020-12 validator."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from mdtools.core.diagnostics import (
    CheckResult, Diagnostic, DiagnosticLocation as Location, DiagnosticReport,
    Evidence, RelatedLocation, render_json,
)
from mdtools.core.source import SourceRef, SourceSnapshot
from mdtools.diagnostics import inspect_workspace

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope='module')
def validator():
    schema = json.loads((REPO / 'docs/spec/diagnostics-v1.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def full_report():
    path = Path('/原稿 日本😀\n".md')
    a = SourceSnapshot(path.as_uri(), '本文😀\r\n', path)
    b = SourceSnapshot('memory:other', a.text)
    newer = SourceSnapshot(a.uri, '更新後😀', path)
    original = Location('original', a.span())
    synthetic = Location('synthetic', b.span(), '生成見出し')
    unmapped = Location('unmapped', reason='map構築失敗')
    diagnostic = Diagnostic(
        'example.code', 'warning', 'user', '説明😀\n"\\\t', original,
        (RelatedLocation('別原稿', Location('original', b.span()), 'REQ-B'),
         RelatedLocation('新snapshot', Location('original', newer.span())),
         RelatedLocation('生成部分', synthetic), RelatedLocation('対応不明', unmapped)),
        'REQ-A', (Evidence('example.fact', '前提\r\n日本語', original),
                  Evidence('example.context', '根拠😀')),
    )
    categories = ('user', 'unsupported', 'unknown', 'not-run', 'tool-error')
    locations = (original, synthetic, unmapped, Location(), Location('unmapped', b.span(), '変換未対応'))
    diagnostics = (diagnostic, *(Diagnostic(f'example.code-{i}', 'info', category, '理由', location)
                                for i, (category, location) in enumerate(zip(categories, locations))))
    checks = tuple(CheckResult(f'example.check-{i}', status, '実施範囲・理由') for i, status in enumerate(
        ('not-run', 'passed', 'failed', 'unknown', 'unsupported', 'error')))
    return DiagnosticReport(diagnostics, checks, (a, b, newer))


def wire_report():
    # Small real serialized report for field-level contract mutation tests.
    diagnostic = Diagnostic(
        'example.code', 'error', 'user', '説明', Location('synthetic', reason='生成'),
        (RelatedLocation('関連', Location('unmapped', reason='未対応'), 'REQ-B'),),
        'REQ-A', (Evidence('example.fact', '根拠', Location('synthetic', reason='合成')),),
    )
    return json.loads(render_json(DiagnosticReport((diagnostic,), (CheckResult('example.check', 'unknown', '理由'),))))


@pytest.mark.parametrize('report', [DiagnosticReport(), full_report(), wire_report()], ids=['empty', 'full', 'locationless'])
def test_generated_json_conforms_to_public_schema(validator, report):
    data = report if isinstance(report, dict) else json.loads(render_json(report))
    validator.validate(data)


def test_workspace_generated_reports_conform_to_public_schema(validator, tmp_path):
    for settings in (REPO / 'docs/spec/examples/cancellation/mdtools.toml', tmp_path / 'missing.toml'):
        validator.validate(json.loads(render_json(inspect_workspace(settings))))


def changed(data, path, value):
    data = deepcopy(data)
    parent = data
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    return data


D = ('diagnostics', 0)
TEXT_FIELDS = [
    (D + ('message',), lambda value: Diagnostic('example.code', 'error', 'user', value)),
    (D + ('requirement_id',), lambda value: Diagnostic('example.code', 'error', 'user', '説明', requirement_id=value)),
    (D + ('primary', 'reason'), lambda value: Location('synthetic', reason=value)),
    (D + ('related', 0, 'message'), lambda value: RelatedLocation(value, Location())),
    (D + ('related', 0, 'requirement_id'), lambda value: RelatedLocation('関連', Location(), value)),
    (D + ('related', 0, 'location', 'reason'), lambda value: Location('unmapped', reason=value)),
    (D + ('evidence', 0, 'message'), lambda value: Evidence('example.fact', value)),
    (D + ('evidence', 0, 'location', 'reason'), lambda value: Location('synthetic', reason=value)),
    (('checks', 0, 'reason'), lambda value: CheckResult('example.check', 'unknown', value)),
]
# Python strip() includes C0 separators and Unicode whitespace beyond ECMAScript \s.
WHITESPACE = ('', ' \t\r\n', '\x1c\x1d\x1e\x1f', '\x85', '\xa0', '\u3000',
              ''.join(chr(c) for c in range(0x3100) if chr(c).isspace()))


@pytest.mark.parametrize('path,factory', TEXT_FIELDS, ids=lambda item: str(item) if isinstance(item, tuple) else '')
@pytest.mark.parametrize('value', WHITESPACE, ids=repr)
def test_schema_and_model_reject_blank_free_text(validator, path, factory, value):
    with pytest.raises(ValueError):
        factory(value)
    with pytest.raises(ValidationError):
        validator.validate(changed(wire_report(), path, value))


@pytest.mark.parametrize('path,factory', TEXT_FIELDS, ids=lambda item: str(item) if isinstance(item, tuple) else '')
@pytest.mark.parametrize('value', [' \t日本😀\r\n ', '\u200b', '\x00'])
def test_schema_and_model_allow_nonblank_text_without_trimming(validator, path, factory, value):
    factory(value)
    validator.validate(changed(wire_report(), path, value))


IDENTIFIER_FIELDS = [
    (D + ('code',), lambda value: Diagnostic(value, 'error', 'user', '説明')),
    (D + ('evidence', 0, 'kind'), lambda value: Evidence(value, '根拠')),
    (('checks', 0, 'check_id'), lambda value: CheckResult(value, 'passed')),
]


@pytest.mark.parametrize('path,factory', IDENTIFIER_FIELDS)
@pytest.mark.parametrize('value', ['example.code\n', 'example.code\r\n', 'example.code\u2028',
                                   'example.code\x00', 'example.code ', '\nexample.code', 'EXAMPLE.CODE'])
def test_schema_and_model_reject_nonidentifiers_including_final_newline(validator, path, factory, value):
    with pytest.raises(ValueError):
        factory(value)
    with pytest.raises(ValidationError):
        validator.validate(changed(wire_report(), path, value))


@pytest.mark.parametrize('status', ['not-run', 'passed', 'failed', 'unknown', 'unsupported', 'error'])
def test_all_check_reasons_reject_whitespace_even_when_optional(validator, status):
    with pytest.raises(ValueError):
        CheckResult('example.check', status, ' \t\n')
    data = wire_report()
    data['checks'][0].update(status=status, reason=' \t\n')
    with pytest.raises(ValidationError):
        validator.validate(data)


def test_schema_and_source_model_reject_digest_with_final_newline(validator):
    source = SourceSnapshot('memory:a', 'text')
    with pytest.raises(ValueError):
        SourceRef(source.uri, source.ref.snapshot + '\n')
    data = json.loads(render_json(DiagnosticReport(sources=(source,))))
    data['sources'][0]['snapshot'] += '\n'
    with pytest.raises(ValidationError):
        validator.validate(data)
