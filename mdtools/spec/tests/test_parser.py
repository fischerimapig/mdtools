"""Structural extraction from actual fixtures, attributes and model JSON."""

import json
import pytest
from mdtools.core.source import SourceSnapshot
from mdtools.spec.parser import parse_requirements
from mdtools.workspace import load_workspace
from mdtools.workspace import snapshot_sources

from mdtools.spec.tests._parser_helpers import (
    EXAMPLES, MODEL, parse, fence, requirement, assert_provenance,
)


@pytest.mark.parametrize('filename,expected', json.loads(
    (EXAMPLES / 'model-contract/expectations.json').read_text()).items())
def test_contract_manuscripts_are_really_parsed(filename, expected):
    source = SourceSnapshot.from_path(EXAMPLES / 'model-contract' / filename)
    result = parse_requirements(source)
    assert result.source is source
    assert result.completeness == expected['completeness']
    assert {d.code for d in result.diagnostics} == ({expected['diagnostic']} if expected['diagnostic'] else set())
    if expected['formalization'] is None:
        assert result.requirements == ()
    else:
        req, = result.requirements
        assert req.formalization == expected['formalization']
        assert [b.language for b in req.bodies] == expected['languages']
    if filename == 'invalid.md':
        assert result.requirements[0].key.name == 'REQ-RECOVER'
    if filename == 'unchecked.md':
        model = result.requirements[0].model
        assert model.when.text == 'paid and (' and model.uses == ()
        assert model.must.text == 'paid == true'
        assert source.slice(model.must.origin.location.span) == '"\\u0070aid == true"'
    assert_provenance(result)


def test_cancellation_workspace_extracts_both_real_models_and_natural_guidance():
    workspace = load_workspace(EXAMPLES / 'cancellation/mdtools.toml')
    results = tuple(map(parse_requirements, snapshot_sources(workspace)))
    requirements = [q for r in results for q in r.requirements]
    assert [q.key.name for q in requirements] == ['REQ-CANCEL-ALLOW', 'REQ-CANCEL-DENY', 'REQ-CANCEL-GUIDANCE']
    allow, deny, guidance = requirements
    assert [b.language for b in allow.bodies] == ['ja', 'en']
    assert allow.model.key.name == 'MODEL-CANCEL-ALLOW'
    assert allow.model.when.text == 'paid and not shipped'
    assert allow.model.must.text == 'cancel_allowed == true'
    assert deny.model.must.text == 'cancel_allowed == false'
    assert deny.refs[0].name == allow.key.name
    assert guidance.formalization == 'natural-only'
    for result in results:
        assert result.completeness == 'complete'
        assert_provenance(result)
        for req in result.requirements:
            for ref in req.refs:
                assert result.source.slice(ref.origin.location.span) == ref.name
            if req.model:
                for ref in req.model.uses:
                    assert json.loads(result.source.slice(ref.origin.location.span)) == ref.name


def test_attribute_order_quotes_repeated_refs_and_precise_defaults():
    raw = requirement(attrs='status=active refs="REQ-B REQ-B" spec-version=\'1\' #REQ-A .requirement')
    result = parse(raw)
    req, = result.requirements
    assert result.completeness == 'complete'
    assert req.status == 'active'
    fields = {f.path: f for f in req.fields}
    assert result.source.slice(fields['/id'].location.span) == 'REQ-A'
    assert result.source.slice(fields['/spec-version'].location.span) == "'1'"
    assert result.source.slice(fields['/refs'].location.span) == '"REQ-B REQ-B"'
    assert [r.name for r in req.refs] == ['REQ-B', 'REQ-B']
    assert req.refs[0].origin.location.span != req.refs[1].origin.location.span
    for ref in req.refs:
        assert result.source.slice(ref.origin.location.span) == 'REQ-B'
    default = parse(requirement()).requirements[0]
    origin = next(f for f in default.fields if f.path == '/status')
    assert default.status == 'draft' and origin.location.span is None
    assert origin.location.reason and origin.container == default.span


@pytest.mark.parametrize('attrs', [
    '.requirement spec-version=1', '.requirement #REQ-A',
    '.requirement #7bad spec-version=1', '.requirement #REQ-A #REQ-B spec-version=1',
    '.requirement .requirement #REQ-A spec-version=1', '.requirement .note #REQ-A spec-version=1',
    '.requirement #REQ-A spec-version=1 extra=yes', '.requirement #REQ-A spec-version=1 status=done',
    '.requirement #REQ-A spec-version=1 status=draft status=active',
    '.requirement #REQ-A spec-version=1 spec-version=1',
    '.requirement #REQ-A spec-version=1 refs="REQ-B" refs="REQ-C"',
    '.requirement #REQ-A spec-version=1 refs="REQ-B 2bad"',
    '.requirement #REQ-A spec-version=', '.requirement #REQ-A spec-version=""',
    '.requirement #REQ-A spec-version="1',
    '.requirement #REQ-A spec-version="1"junk', '.requirement=oops #REQ-A spec-version=1',
    '.requirement#REQ-A spec-version=1', '.requirement id=REQ-A spec-version=1',
])
def test_bad_attributes_are_rejected_and_recovery_preserves_failure(attrs):
    bad = requirement(attrs=attrs)
    result = parse(bad + requirement(attrs='.requirement #REQ-GOOD spec-version=1'))
    assert result.completeness == 'partial' and result.checks.structure.status == 'failed'
    assert [r.key.name for r in result.requirements] == ['REQ-GOOD']
    assert result.rejected[0].text == bad
    assert_provenance(result)


@pytest.mark.parametrize('header', [
    ':::: {.requirement #REQ-A spec-version=1}',
    '::: {.requirement #REQ-A spec-version=1} trailing',
    '::: {.requirement #REQ-A spec-version=1',
    '::: .requirement #REQ-A spec-version=1',
])
def test_malformed_reserved_headers_are_not_discarded(header):
    result = parse(header + '\n本文\n:::\n' + requirement())
    assert result.completeness == 'partial'
    assert result.rejected and len(result.requirements) == 1


@pytest.mark.parametrize('body', ['', ' \n\t\n', fence(), '::: {lang=ja}\n \n:::\n'])
def test_empty_body_is_not_synthesized(body):
    result = parse(requirement(body))
    assert result.requirements == () and result.completeness == 'partial'
    assert any('body' in d.message for d in result.diagnostics)
    assert_provenance(result)


@pytest.mark.parametrize('field,value,code', [
    ('version', True, 'spec.invalid-model'), ('version', '1', 'spec.invalid-model'),
    ('version', 1.0, 'spec.invalid-model'), ('version', 2, 'spec.unsupported-version'),
    ('id', '', 'spec.invalid-model'), ('id', '1bad', 'spec.invalid-model'), ('id', [], 'spec.invalid-model'),
    ('kind', 3, 'spec.invalid-model'), ('kind', '', 'spec.invalid-model'),
    ('kind', 'future', 'spec.unsupported-syntax'),
    ('uses', 'paid', 'spec.invalid-model'), ('uses', [False], 'spec.invalid-model'),
    ('uses', ['paid', 'paid'], 'spec.invalid-model'), ('uses', ['true'], 'spec.invalid-model'),
    ('uses', ['has-dash'], 'spec.invalid-model'), ('uses', [''], 'spec.invalid-model'),
    ('when', '', 'spec.invalid-model'), ('when', ' \t', 'spec.invalid-model'),
    ('when', False, 'spec.invalid-model'), ('must', None, 'spec.invalid-model'),
    ('must', [], 'spec.invalid-model'), ('extra', 'ignored?', 'spec.invalid-model'),
])
def test_model_fields_are_validated_without_downgrading_to_natural_only(field, value, code):
    model = {**MODEL, field: value}
    result = parse(requirement('本文\n' + fence(json.dumps(model))))
    req, = result.requirements
    assert req.formalization == 'present' and req.model is None
    assert result.completeness == 'partial'
    assert code in {d.code for d in result.diagnostics}
    assert_provenance(result)


@pytest.mark.parametrize('missing', list(MODEL))
def test_exactly_six_required_model_fields(missing):
    model = {k: v for k, v in MODEL.items() if k != missing}
    result = parse(requirement('本文\n' + fence(json.dumps(model))))
    assert result.requirements[0].model is None
    assert any('Missing model field: ' + missing == d.message for d in result.diagnostics)


@pytest.mark.parametrize('raw', [
    '[]', 'null', '42', '"not an object"', '{', '{} trailing',
    '{"version": 1,}', '{"uses": ["paid",]}', '{"version": 01}',
    '{"version": NaN}', '{"version": Infinity}', '{"version": 1e999}',
    '{"id": "\\ud800"}', '{"when": "literal\nnewline"}',
    '{"version": 1, "version": 1}', '{"version": 1, "\\u0076ersion": 1}',
    '{"extra": {"x": 1, "x": 2}}',
])
def test_invalid_json_and_duplicate_keys_recover_at_closed_fence(raw):
    result = parse(requirement('本文\n' + fence(raw)) + requirement(attrs='.requirement #REQ-NEXT spec-version=1'))
    assert [r.key.name for r in result.requirements] == ['REQ-A', 'REQ-NEXT']
    assert result.requirements[0].formalization == 'present'
    assert result.requirements[0].model is None
    assert result.requirements[1].structure.status == 'passed'
    assert result.checks.structure.status == 'failed' and result.completeness == 'partial'
    assert_provenance(result)


def test_duplicate_key_and_uses_diagnostics_point_to_both_original_tokens():
    result = parse(requirement('本文\n' + fence('{"version":1,"\\u0076ersion":2}')))
    duplicate = result.diagnostics[0]
    assert result.source.slice(duplicate.primary.span) == '"\\u0076ersion"'
    assert result.source.slice(duplicate.related[0].location.span) == '"version"'
    raw = json.dumps({**MODEL, 'uses': ['paid', 'paid']}).replace('"paid", "paid"', '"paid", "\\u0070aid"')
    result = parse(requirement('本文\n' + fence(raw)))
    duplicate = next(d for d in result.diagnostics if 'Duplicate uses' in d.message)
    assert result.source.slice(duplicate.primary.span) == '"\\u0070aid"'
    assert result.source.slice(duplicate.related[0].location.span) == '"paid"'


def test_duplicate_ids_are_occurrences_not_local_resolution_or_overwriting():
    result = parse(requirement('本文\n' + fence()) * 2)
    assert result.completeness == 'complete'
    assert [k.name for k in result.nodes] == ['REQ-A', 'MODEL-A', 'REQ-A', 'MODEL-A']
    assert [k.ordinal for k in result.nodes] == [0, 1, 2, 3]
    assert result.checks.references.status == 'not-run'
    assert result == parse_requirements(result.source)


def test_unknown_versions_do_not_apply_v1_to_their_contents():
    result = parse(requirement(fence('not JSON'), attrs='.requirement #REQ-A spec-version=2'))
    assert [d.code for d in result.diagnostics] == ['spec.unsupported-version']
    assert result.requirements == () and len(result.rejected) == 1
    result = parse(requirement('本文\n' + fence('{"version":2,"future":true}')))
    assert [d.code for d in result.diagnostics] == ['spec.unsupported-version']
    assert result.requirements[0].formalization == 'present'
    assert result.requirements[0].structure.status == 'unsupported'


@pytest.mark.parametrize('raw', ['[' * 1500 + '0' + ']' * 1500, '9' * 5000])
def test_json_capacity_errors_become_diagnostics_and_allow_following_requirements(raw):
    result = parse(requirement('本文\n' + fence(raw)) + requirement())
    assert result.completeness == 'partial' and len(result.requirements) == 2
    assert result.requirements[0].model is None
    assert result.requirements[0].structure.status == 'unsupported'
    assert result.requirements[0].structure.reason
    assert result.requirements[1].structure.status == 'passed'
    assert_provenance(result)


@pytest.mark.parametrize('header', ['::: {lang=}', '::: {lang=ja lang=en}', '::: {lang=ja} trailing'])
def test_malformed_language_wrapper_is_not_structurally_successful(header):
    result = parse(requirement(header + '\n本文\n:::\n'))
    assert result.completeness == 'partial' and result.checks.structure.status == 'failed'
    assert result.requirements == () and result.rejected[0].kind == 'requirement'
    assert_provenance(result)


def test_rejected_nodes_do_not_consume_retained_occurrence_ordinals():
    result = parse(requirement(fence()) + requirement('本文\n' + fence()))
    assert [key.ordinal for key in result.nodes] == [0, 1]
    assert result.completeness == 'partial'
