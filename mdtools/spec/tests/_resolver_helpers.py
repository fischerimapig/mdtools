"""Resolver inputs come from real text, not manufactured graph values."""

import json

from mdtools.core.source import SourceSnapshot
from mdtools.spec.loader import load_definitions
from mdtools.spec.parser import parse_requirements
from ._loader_helpers import document


def definitions(raw=None, *, uri='memory:definitions', kind='spec', **updates):
    if raw is None:
        raw = document(**updates)
    if not isinstance(raw, str):
        raw = json.dumps(raw, ensure_ascii=False)
    return load_definitions(SourceSnapshot(uri, raw), kind=kind, format='json')


def manuscript(*, name='REQ-A', refs=(), uses=None, model='MODEL-A', heading='', uri='memory:manuscript'):
    raw = f'{heading}::: {{.requirement #{name} spec-version=1 refs="{" ".join(refs)}"}}\n本文📚é\n'
    if uses is not None:
        raw += '```mdspec\n' + json.dumps(dict(version=1, id=model, kind='constraint', uses=uses,
                                              when='unexamined and (', must='true')) + '\n```\n'
    return parse_requirements(SourceSnapshot(uri, raw + ':::\n'))


def signature(result):
    return {(edge.owner.namespace, edge.owner.name, edge.reference.kind, edge.reference.name,
             edge.status, frozenset((key.namespace, key.name) for key in edge.candidates), edge.builtin)
            for edge in result.graph.edges}
