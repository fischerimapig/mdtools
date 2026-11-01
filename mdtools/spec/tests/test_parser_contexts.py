"""Reservation boundaries: examples, literals, divs, fences and recovery."""

import json
import pytest

from mdtools.spec.tests._parser_helpers import (
    MODEL, parse, fence, requirement, assert_provenance,
)


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


def test_orphan_unclosed_malformed_model_reports_each_boundary_problem():
    result = parse('```mdspec extra\n{}\n')
    assert result.requirements == () and len(result.rejected) == 1
    assert len(result.diagnostics) == 3
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


def test_review_numbered_continuation_keeps_code_span_and_real_requirement():
    raw = ('The comment marker is `<!--\n2. not a real comment`.\n\n'
           + requirement(attrs='.requirement #REQ-REAL spec-version=1'))
    result = parse(raw)
    assert [q.key.name for q in result.requirements] == ['REQ-REAL']
    assert result.diagnostics == () and result.completeness == 'complete'
    assert_provenance(result)


@pytest.mark.parametrize('line,visible', [
    pytest.param('2) continuation', True, id='other-number-parenthesis-continues'),
    pytest.param('1. new item', False, id='nonempty-first-item-interrupts'),
    pytest.param('1. ', True, id='empty-first-item-does-not-interrupt'),
])
def test_ordered_marker_boundary_distinguishes_continuation_from_interruption(line, visible):
    raw = 'The marker is `<!--\n' + line + '\nend`.\n\n' + requirement()
    result = parse(raw)
    assert [q.key.name for q in result.requirements] == (['REQ-A'] if visible else [])
    assert result.diagnostics == () and result.completeness == 'complete'
    assert_provenance(result)
