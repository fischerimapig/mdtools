"""Actual extraction from original files, including recovery and exact tokens."""

from hashlib import sha256
import json
from pathlib import Path

import pytest

from mdtools.core.source import SourcePosition, SourceSnapshot
from mdtools.spec.parser import parse_requirements
from mdtools.workspace import load_workspace, snapshot_sources


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


@pytest.mark.parametrize('newline', ['\n', '\r\n', '\r'])
def test_file_snapshot_unicode_escapes_and_every_field_are_exact(tmp_path, newline):
    model = {**MODEL, 'when': '日本語📚é\npaid', 'must': 'paid\t== true'}
    raw_json = json.dumps(model, ensure_ascii=False).replace('"paid"', '"\\u0070aid"')
    raw = requirement('説明📚é\n' + fence(raw_json)).replace('\n', newline)
    path = tmp_path / '日本語.md'
    path.write_bytes(raw.encode('utf-8'))
    source = SourceSnapshot.from_path(path)
    result = parse_requirements(source)
    assert result.completeness == 'complete'
    assert source.ref.path == path and source.ref.uri == path.as_uri()
    assert source.ref.snapshot == sha256(path.read_bytes()).hexdigest()
    req, = result.requirements
    assert req.bodies[0].text == '説明📚é' + newline
    assert req.bodies[0].span.start == SourcePosition(2, 1)
    assert source.position(raw.index('📚')) == SourcePosition(2, 3)
    for origin in req.model.fields:
        value = json.loads(source.slice(origin.location.span))
        key = origin.path[1:]
        assert value == (model['uses'][int(key.split('/')[1])] if key.startswith('uses/') else model[key])
    assert req.model.uses[0].name == 'paid'
    assert source.slice(req.model.uses[0].origin.location.span) == '"\\u0070aid"'
    assert req.model.when.text == model['when'] and req.model.must.text == model['must']
    assert_provenance(result)


def test_multilingual_and_interleaved_bodies_preserve_only_contiguous_raw_ranges():
    body = ('共通\n::: {lang=ja}\n日本語1\n:::\n' + fence()
            + '::: {lang=en}\nEnglish\n:::\n::: {lang=ja}\n日本語2\n:::\n末尾\n')
    result = parse(requirement(body))
    req, = result.requirements
    assert [b.language for b in req.bodies] == [None, 'ja', 'en', 'ja', None]
    assert [b.text for b in req.bodies] == ['共通\n', '日本語1\n', 'English\n', '日本語2\n', '末尾\n']
    assert len(result.nodes) == 2 and req.model is not None
    assert_provenance(result)


@pytest.mark.parametrize('wrap', [
    lambda s: '```markdown\n' + s + '```\n',
    lambda s: '````markdown\n' + s + fence() + '````\n',
    lambda s: '~~~~~\n' + s + '```mdspec\n{}\n```\n~~~~~\n',
    lambda s: '<!--\n' + s + '```\n-->\n',
    lambda s: 'text <!--\n' + s + '-->\n',
    lambda s: '<pre>\n' + s + '```\n# raw </pre>\n',
    lambda s: '  <PRE\nclass="example">\n' + s + '</PRE>\n',
    lambda s: '---\nexample: |\n' + s + '---\n',
    lambda s: '---\nexample: |\n' + s + '...\n',
    lambda s: ''.join('    ' + line for line in s.splitlines(keepends=True)),
    lambda s: ''.join('\t' + line for line in s.splitlines(keepends=True)),
])
def test_examples_comments_pre_and_front_matter_do_not_create_requirements(wrap):
    hidden = requirement(attrs='.requirement #REQ-HIDDEN spec-version=1')
    result = parse(wrap(hidden) + requirement())
    assert result.completeness == 'complete'
    assert [q.key.name for q in result.requirements] == ['REQ-A']


@pytest.mark.parametrize('prefix', [
    '説明中の<pre>です。\n', '`<pre>`\n', '\\<pre>\n', '<prefix>\n',
    '| `<pre>` | 説明 |\n', '`<!--`\n', '\\<!--\n',
    '<!-- <pre> -->\n', '```\n<pre>\n```\n', '<pre>example</pre>\n',
    '::: {.note value=".requirement"}\n:::\n',
    '::: {.requirement-example}\n:::\n',
])
def test_literal_mentions_do_not_hide_following_real_requirement(prefix):
    result = parse(prefix + requirement())
    assert result.completeness == 'complete' and len(result.requirements) == 1


@pytest.mark.parametrize('marker', ['```', '~~~~', '`````'])
def test_model_closes_only_with_same_symbol_and_sufficient_length(marker):
    raw = requirement('本文\n' + fence(marker=marker).replace('\n' + marker + '\n', '\n' + marker + marker[0] + '  \n'))
    assert parse(raw).completeness == 'complete'
    wrong = '~' * len(marker) if marker[0] == '`' else '`' * len(marker)
    for closing in (wrong, marker[:-1], marker + ' trailing'):
        raw = requirement('本文\n' + marker + 'mdspec\n' + json.dumps(MODEL) + '\n' + closing + '\n')
        result = parse(raw + requirement(attrs='.requirement #REQ-NOT-RECOVERED spec-version=1'))
        assert result.completeness == 'partial'
        assert [q.key.name for q in result.requirements] == ['REQ-A']
        assert result.requirements[0].model is None
        assert any('not closed' in d.message for d in result.diagnostics)


def test_ordinary_code_does_not_close_on_trailing_info_or_become_spec_error():
    raw = '```python\n' + requirement() + '``` trailing\n' + requirement() + '```\n'
    result = parse(raw + requirement(attrs='.requirement #REQ-REAL spec-version=1'))
    assert result.completeness == 'complete'
    assert [q.key.name for q in result.requirements] == ['REQ-REAL']
    assert parse('```python\n' + requirement()).completeness == 'complete'
    assert parse('```python\n' + requirement()).requirements == ()


@pytest.mark.parametrize('info', ['mdspec extra', 'mdspecification', 'mdspec {#x}', 'mdspec`'])
def test_bad_reserved_info_is_rejected_but_closed_block_allows_recovery(info):
    result = parse(requirement('本文\n' + fence(info=info)) + requirement())
    assert result.completeness == 'partial' and len(result.requirements) == 2
    assert result.requirements[0].formalization == 'present'
    assert result.requirements[0].model is None
    assert result.rejected[0].kind == 'model'


def test_orphan_model_and_multiple_models_keep_all_rejected_text():
    first, second = fence(), fence(json.dumps({**MODEL, 'id': 'MODEL-B'}))
    orphan = parse(first + requirement())
    assert orphan.completeness == 'partial' and orphan.rejected[0].text == first
    result = parse(requirement('本文\n' + first + second))
    req, = result.requirements
    assert req.formalization == 'present' and req.model is None
    assert req.structure.status == 'unsupported'
    assert [r.text for r in result.rejected] == [first, second]


def test_nesting_language_model_and_mixed_failure_states():
    nested = parse(requirement('親\n' + requirement(attrs='.requirement #REQ-INNER spec-version=1')))
    assert len(nested.requirements) == 1 and nested.checks.structure.status == 'unsupported'
    assert nested.rejected[0].kind == 'requirement'
    outer_lang = parse('::: {lang=ja}\n' + requirement() + ':::\n' + requirement())
    assert len(outer_lang.requirements) == 1 and outer_lang.completeness == 'partial'
    wrong = parse(requirement('本文\n::: {lang=ja}\n説明\n' + fence() + ':::\n'))
    assert wrong.requirements[0].formalization == 'present' and wrong.requirements[0].model is None
    assert wrong.checks.structure.status == 'failed'
    mixed = parse(requirement('本文\n' + fence() + '::: {lang=ja}\n' + fence() + ':::\n'))
    assert {d.category for d in mixed.diagnostics} == {'user', 'unsupported'}
    assert mixed.checks.structure.status == 'failed' and mixed.completeness == 'partial'


def test_unclosed_requirement_does_not_guess_a_sibling_boundary():
    raw = requirement(close=False) + requirement(attrs='.requirement #REQ-AMBIGUOUS spec-version=1')
    result = parse(raw)
    assert [q.key.name for q in result.requirements] == ['REQ-A']
    assert result.completeness == 'partial' and result.checks.structure.status == 'failed'
    assert result.requirements[0].span.end == result.source.position(len(raw))
    assert_provenance(result)


def test_duplicate_ids_are_occurrences_not_local_resolution_or_overwriting():
    result = parse(requirement('本文\n' + fence()) * 2)
    assert result.completeness == 'complete'
    assert [k.name for k in result.nodes] == ['REQ-A', 'MODEL-A', 'REQ-A', 'MODEL-A']
    assert [k.ordinal for k in result.nodes] == [0, 1, 2, 3]
    assert result.checks.references.status == 'not-run'
    assert result == parse_requirements(result.source)


def test_workspace_sections_are_independent_originals_not_composed_or_filtered(tmp_path):
    first = requirement('::: {lang=ja}\n日本語\n:::\n', close=False)
    second = ':::\n' + requirement('::: {lang=en}\nEnglish []{.term id=unit}\n:::\n')
    (tmp_path / 'a.md').write_bytes(first.replace('\n', '\r\n').encode())
    (tmp_path / 'b.md').write_text(second)
    (tmp_path / 'canonical.md').write_text(requirement(attrs='.requirement #REQ-GENERATED spec-version=1'))
    (tmp_path / 'unused.md').write_text(requirement(attrs='.requirement #REQ-UNUSED spec-version=1'))
    hierarchy = {'sections': [{'title': title, 'file': name, 'order': i, 'children': []}
                              for i, (title, name) in enumerate([('A', 'a.md'), ('B', 'b.md')])]}
    (tmp_path / 'hierarchy.json').write_text(json.dumps(hierarchy))
    config = tmp_path / 'mdtools.toml'
    config.write_text('version=1\n[[documents]]\nkind="hierarchy"\npath="hierarchy.json"\ncanonical="canonical.md"\n')
    snapshots = snapshot_sources(load_workspace(config))
    assert [s.path.name for s in snapshots] == ['a.md', 'b.md']
    a, b = map(parse_requirements, snapshots)
    assert a.completeness == 'partial' and b.completeness == 'complete'
    assert a.requirements[0].bodies[0].text == '日本語\r\n'
    assert b.requirements[0].bodies[0].text == 'English []{.term id=unit}\n'
    assert a.diagnostics[0].primary.span.source.path == tmp_path / 'a.md'
    assert [a.requirements[0].key.name, b.requirements[0].key.name] == ['REQ-A', 'REQ-A']
    assert_provenance(a)
    assert_provenance(b)


def test_eof_and_source_changes_keep_exact_source_identity():
    raw = requirement().rstrip('\n')
    before = parse(raw)
    after = parse(raw.replace('説明', '変更'))
    assert before.requirements[0].span.end == SourcePosition(3, 4)
    assert before.source.ref.uri == after.source.ref.uri
    assert before.source.ref.snapshot != after.source.ref.snapshot
    assert before.requirements[0].key.name == after.requirements[0].key.name
    with pytest.raises(TypeError):
        parse_requirements(raw)


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


def test_escaped_attribute_reference_has_its_own_raw_token_range():
    result = parse(requirement(attrs='.requirement #REQ-A spec-version=1 refs="REQ-\\B REQ-B"'))
    req, = result.requirements
    assert [r.name for r in req.refs] == ['REQ-B', 'REQ-B']
    assert [result.source.slice(r.origin.location.span) for r in req.refs] == ['REQ-\\B', 'REQ-B']


@pytest.mark.parametrize('header', ['::: {lang=}', '::: {lang=ja lang=en}', '::: {lang=ja} trailing'])
def test_malformed_language_wrapper_is_not_structurally_successful(header):
    result = parse(requirement(header + '\n本文\n:::\n'))
    assert result.completeness == 'partial' and result.checks.structure.status == 'failed'
    assert result.requirements == () and result.rejected[0].kind == 'requirement'
    assert_provenance(result)


def test_unclosed_language_and_invalid_requirement_closer_are_diagnosed():
    for raw in (requirement('::: {lang=ja}\n本文\n', close=False),
                requirement().replace('\n:::\n', '\n::::\n')):
        result = parse(raw)
        assert result.completeness == 'partial' and result.checks.structure.status == 'failed'
        assert_provenance(result)


@pytest.mark.parametrize('indent', ['', ' ', '   '])
def test_ordinary_block_whitespace_is_allowed(indent):
    raw = '\n'.join(indent + line + '  ' for line in requirement('本文\n' + fence()).splitlines())
    assert parse(raw).completeness == 'complete'


def test_language_div_can_have_ordinary_pandoc_presentation_attributes():
    result = parse(requirement('::: {.note lang=ja #translation}\n日本語\n:::\n'))
    assert result.completeness == 'complete'
    assert result.requirements[0].bodies[0].language == 'ja'


def test_unicode_separators_do_not_renumber_source_lines():
    result = parse(requirement('A\u2028B\u0085C\n'))
    body = result.requirements[0].bodies[0]
    assert body.text == 'A\u2028B\u0085C\n'
    assert body.span.start == SourcePosition(2, 1) and body.span.end == SourcePosition(3, 1)


def test_orphan_unclosed_malformed_model_reports_each_boundary_problem():
    result = parse('```mdspec extra\n{}\n')
    assert result.requirements == () and len(result.rejected) == 1
    assert len(result.diagnostics) == 3
    assert result.completeness == 'partial'


def test_rejected_nodes_do_not_consume_retained_occurrence_ordinals():
    result = parse(requirement(fence()) + requirement('本文\n' + fence()))
    assert [key.ordinal for key in result.nodes] == [0, 1]
    assert result.completeness == 'partial'


@pytest.mark.parametrize('header', ['::: {.note} <!--', '::: note <!--', '::: {.note <!--'])
def test_comments_after_div_headers_hide_reserved_syntax(header):
    hidden = requirement(attrs='.requirement #REQ-HIDDEN spec-version=1')
    result = parse(header + '\n' + hidden + '-->\n:::\n' + requirement())
    assert result.completeness == 'complete'
    assert [q.key.name for q in result.requirements] == ['REQ-A']


def test_comment_literal_inside_quoted_div_attribute_does_not_open_comment():
    result = parse('::: {.note title="<!--"}\n' + requirement() + ':::\n')
    assert result.completeness == 'complete' and len(result.requirements) == 1


@pytest.mark.parametrize('prefix', [
    'The comment marker is `<!--\nnot a real comment`.\n\n',
    'The marker is ``<!-- `\nnot a comment``.\n\n',
    '<span title="<!--">example</span>\n\n',
    "<span title='<!--'>example</span>\n\n",
    '<span title="<!--\ncontinued">example</span>\n\n',
    ' \t<!-- an indented literal\n\n',
    '  \t<!-- an indented literal\n\n',
])
@pytest.mark.parametrize('newline', ['\n', '\r\n'])
def test_comment_literals_in_multiline_code_html_attributes_and_tab_indentation(prefix, newline):
    raw = (prefix + requirement()).replace('\n', newline)
    result = parse(raw)
    assert result.completeness == 'complete' and result.diagnostics == ()
    assert [q.key.name for q in result.requirements] == ['REQ-A']
    assert_provenance(result)


@pytest.mark.parametrize('prefix', [
    'Unmatched ` then <!--\n',
    'Unmatched `\n\n<!--\n',
    '<span title="literal"> <!--\n',
    '`literal\nends here` <!--\n',
])
def test_real_comments_after_literals_still_hide_requirements(prefix):
    result = parse(prefix + requirement(attrs='.requirement #REQ-HIDDEN spec-version=1')
                   + '-->\n' + requirement())
    assert result.completeness == 'complete'
    assert [q.key.name for q in result.requirements] == ['REQ-A']


def test_unmatched_code_delimiter_does_not_cross_requirement_block_boundary():
    raw = 'Unmatched `\n' + requirement('本文と `<!--` の例\n')
    result = parse(raw)
    assert result.completeness == 'complete' and len(result.requirements) == 1


@pytest.mark.parametrize('literal_marker', ['---', '...'])
@pytest.mark.parametrize('ending', ['---', '...  '])
@pytest.mark.parametrize('newline', ['\n', '\r\n', '\r'])
def test_front_matter_scalar_delimiters_do_not_end_metadata(literal_marker, ending, newline):
    hidden = requirement(attrs='.requirement #REQ-HIDDEN spec-version=1')
    scalar = ''.join('  ' + line for line in hidden.splitlines(keepends=True))
    raw = ('---\nexample: |\n  ' + literal_marker + '\n' + scalar
           + ending + '\n' + requirement()).replace('\n', newline)
    result = parse(raw)
    assert result.completeness == 'complete' and result.diagnostics == ()
    assert [q.key.name for q in result.requirements] == ['REQ-A']
    assert_provenance(result)
