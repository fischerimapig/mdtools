"""Frozen baseline observations and independent prototype compatibility contracts."""
import json
from pathlib import Path

import pytest

from mdtools.core.source import SourceSnapshot
from experiments.document_parser.tests.legacy_adapter import BASELINE_SHA, observe

ROOT = Path(__file__).resolve().parents[3]
CORPUS = json.loads((Path(__file__).parents[1] / 'corpus/m2.json').read_text())
CASES = CORPUS['cases']


def manuscript(case):
    value = case['input']
    return (ROOT / value['fixture']).read_bytes().decode('utf-8') if 'fixture' in value else value['raw']


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['id'])
def test_frozen_legacy_observation(case):
    """Detect fixture or baseline drift without using the legacy parser as a fallback."""
    assert CORPUS['baseline_sha'] == BASELINE_SHA
    assert observe(manuscript(case)) == case['legacy']


@pytest.mark.parametrize('case', [c for c in CASES if c['expected'] is not None], ids=lambda c: c['id'])
def test_prototype_declared_contract(case):
    """Detect candidate loss, ordering, body/language/model ownership or original byte-span drift."""
    from experiments.document_parser.parser import parse_document
    from experiments.document_parser.projection import summary_dict

    document = parse_document(SourceSnapshot('memory:corpus', manuscript(case)))
    actual = summary_dict(document)
    assert actual['status'] != 'failed'
    assert actual['semantic_checks'] == dict.fromkeys(
        ('json', 'references', 'expressions', 'requirement_validation'), 'not-run')
    expected = case['expected']
    assert actual['status'] == expected['document_status']
    assert [c['id'] for c in actual['candidates']] == expected['ids']
    # The declared field set is fixed in JSON, never the runtime intersection.
    assert [{key: candidate[key] for key in case['compare_fields']} for candidate in actual['candidates']] == expected['candidates']


@pytest.mark.parametrize('case', [c for c in CASES if c['id'].startswith('I-51')], ids=lambda c: c['id'])
def test_issue_51_independent_original_span(case):
    """Require REQ-A at its source marker, independently of either parser's result."""
    text = manuscript(case)
    start = text.encode('utf-8').index(b'::: {.requirement #REQ-A')
    assert case['legacy']['candidates'] == []
    assert case['expected']['ids'] == ['REQ-A']
    assert case['expected']['candidates'][0]['span'] == [start, len(text.encode('utf-8'))]
