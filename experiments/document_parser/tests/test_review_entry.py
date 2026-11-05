"""Public prototype entry, serialization and ownership failure regressions."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

from mdtools.core.source import SourceSnapshot
from experiments.document_parser import parser
from experiments.document_parser.dump import document_dict
from experiments.document_parser.model import ByteRange, BlockResult, Coverage, Node, validate_document
from experiments.document_parser.projection import summary_dict

ROOT = Path(__file__).resolve().parents[3]
REQ = '::: {.requirement #REQ-A spec-version=1}\n本文\n:::\n'


def test_recognized_bytes_cannot_disappear_with_a_removed_node():
    """Detect a missing block even when coverage still claims the whole input was recognized."""
    document = parser.parse_document(SourceSnapshot('memory:missing', REQ))
    validate_document(document)
    with pytest.raises(ValueError, match='no structural owner'):
        validate_document(replace(document, blocks=()))
    outer, = document.blocks
    with pytest.raises(ValueError, match='no structural owner'):
        validate_document(replace(document, blocks=(replace(outer, children=()),)))


def test_invariant_failure_is_a_serializable_failed_result(monkeypatch):
    """An engine returning impossible ranges must not crash dump or fabricate valid coordinates."""
    def invalid(index, limits):
        bad = Node('paragraph', ByteRange(0, 999), ByteRange(0, 999))
        return BlockResult((bad,), coverage=(Coverage(ByteRange(0, index.byte_length), 'recognized'),))
    monkeypatch.setattr(parser, 'parse_blocks', invalid)
    document = parser.parse_document(SourceSnapshot('memory:broken', REQ))
    assert document.status == 'failed' and document.blocks == ()
    assert document.notices[-1].code == 'document.execution'
    assert summary_dict(document)['candidates'] == []
    assert document_dict(document, trace=True)['coverage'][0]['span']['raw'] == REQ


def test_duplicate_id_attributes_are_preserved_as_ambiguous_candidates():
    """Keep colliding ID occurrences rather than silently taking the first or last attribute."""
    raw = REQ.replace('#REQ-A', '#REQ-A #REQ-B')
    review = summary_dict(parser.parse_document(SourceSnapshot('memory:duplicates', raw)))
    candidate, = review['candidates']
    assert candidate['id'] is None and candidate['ids'] == ['REQ-A', 'REQ-B']
    assert review['semantic_checks']['requirement_validation'] == 'not-run'


@pytest.mark.parametrize('raw, code, status', [(REQ, 0, 'complete'), (REQ[:-4], 2, 'partial')])
def test_cli_dump_has_real_ids_locations_and_non_success_for_partial(tmp_path, raw, code, status):
    """Exercise file input through the runnable dump entry and check content, positions and exit status."""
    path = tmp_path / 'input.md'
    path.write_bytes(raw.encode('utf-8'))
    process = subprocess.run([sys.executable, '-S', '-m', 'experiments.document_parser', str(path), '--trace'],
                             cwd=ROOT, capture_output=True, text=True)
    assert process.returncode == code, process.stderr
    result = json.loads(process.stdout)
    assert result['document']['status'] == status
    assert result['review']['candidates'][0]['id'] == 'REQ-A'
    assert result['document']['nodes'][0]['span']['raw'] == raw
    assert result['review']['candidates'][0]['span'] == [0, len(raw.encode('utf-8'))]
