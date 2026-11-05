"""Reproducible review observations from fixed corpus; no baseline regeneration.

Run from the repository root with python -m experiments.document_parser.tests.report.
Only this test/report directory is allowed to compare the legacy observations.
"""
from __future__ import annotations

import json
from pathlib import Path

from mdtools.core.source import SourceSnapshot
from experiments.document_parser.dump import document_dict
from experiments.document_parser.model import Limits
from experiments.document_parser.parser import parse_document
from experiments.document_parser.projection import summary_dict

ROOT = Path(__file__).resolve().parents[3]
TRACE_CASES = {'C-normal', 'C-literal-comment', 'C-malformed-header', 'C-unclosed-div',
               'I-51-link-title', 'I-51-image-title', 'I-51-reference-title',
               'I-pending-paragraph-comment', 'I-pending-div-tail-comment'}


def report():
    corpus = json.loads((Path(__file__).parents[1] / 'corpus/m2.json').read_text())
    rows = []
    for case in corpus['cases']:
        raw = ((ROOT / case['input']['fixture']).read_bytes().decode('utf-8')
               if 'fixture' in case['input'] else case['input']['raw'])
        source = SourceSnapshot('memory:corpus/' + case['id'], raw)
        document = parse_document(source)
        review = summary_dict(document)
        expected = case['expected']
        comparison = 'unapproved-observation'
        if expected is not None:
            projected = [{key: c[key] for key in case['compare_fields']} for c in review['candidates']]
            good = (projected == expected['candidates']
                    and [c['id'] for c in review['candidates']] == expected['ids']
                    and review['status'] == expected['document_status'])
            comparison = 'matched' if good else 'mismatch'
        row = {'case_id': case['id'], 'classification': case['classification'],
               'input': raw, 'snapshot': source.ref.snapshot,
               'compare_fields': case['compare_fields'], 'comparison': comparison,
               'legacy': case['legacy'], 'expected': expected, 'observed': review,
               'difference_reason': case['difference_reason'],
               'unsupported_reason': case.get('unsupported_reason'),
               'notices': document_dict(document)['notices']}
        if case['id'] in TRACE_CASES:
            row['trace'] = document_dict(document, trace=True)
        rows.append(row)
    req = '::: {.requirement #REQ-A spec-version=1}\n本文\n:::\n'
    unsupported_raw = '[a]\n\n[a]: /url\n "title"\n\n' + req
    unsupported = parse_document(SourceSnapshot('memory:multiline-reference', unsupported_raw))
    limited = parse_document(SourceSnapshot('memory:limited', req), limits=Limits(max_nodes=1))
    return {'baseline_sha': corpus['baseline_sha'],
            'normalization': 'Source URI is memory:corpus/<case-id>. Original UTF-8 bytes, snapshots, '
                             'IDs, order, bodies and diagnostics are not removed or rounded.',
            'cases': rows,
            'failure_traces': {'node_limit': document_dict(limited, trace=True),
                               'multiline_reference_unsupported': document_dict(unsupported, trace=True)}}


if __name__ == '__main__':
    result = report()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if any(c['comparison'] == 'mismatch' for c in result['cases']) else 0)
