"""Resolve explicitly collected M2 inputs without rereading or selecting files."""

from __future__ import annotations

from collections.abc import Iterable

from mdtools.core.diagnostics import (
    CheckResult, Diagnostic, DiagnosticLocation, Evidence, RelatedLocation,
)
from ._resolution import ResolutionIndex
from .model import FieldSource
from .results import AnalysisChecks, LocalAnalysis, ReferenceResolution, ResolvedAnalysis, SpecGraph

# Priority is scoped to one check. Keep all reasons, including deferred work,
# even when a failure in the same scope takes precedence.
_PRIORITY = ('error', 'failed', 'unsupported', 'unknown', 'not-run', 'passed')
_DUPLICATE_CODES = {
    'requirement': 'spec.duplicate-id', 'model': 'spec.duplicate-id',
    'declaration': 'spec.duplicate-name', 'glossary': 'spec.duplicate-glossary',
}


def _aggregate(name, checks):
    checks = tuple(checks)
    status = min((check.status for check in checks), key=_PRIORITY.index)
    reasons = tuple(dict.fromkeys(check.reason for check in checks if check.reason))
    return CheckResult('spec.' + name, status, '; '.join(reasons) or None)


def _location(field: FieldSource) -> DiagnosticLocation:
    if field.location.kind == 'original':
        return field.location
    return DiagnosticLocation('unmapped', reason=field.location.reason or 'Exact field token is unavailable')


def _container(field: FieldSource) -> tuple[RelatedLocation, ...]:
    if field.location.kind != 'original' and field.container is not None:
        return (RelatedLocation('Known source container', DiagnosticLocation('original', field.container)),)
    return ()


def _related(message, field):
    return (RelatedLocation(message, _location(field)), *_container(field))


def _field(node, path):
    return next(field for field in node.fields if field.path == path)


def _name_field(node):
    return _field(node, '/name' if node.key.namespace == 'declaration' else '/id')


def _reported(code, current, previous, diagnostics):
    """Suppress only a proven same-snapshot pair, never merely the same code."""
    a, b = current.location, previous.location
    if a.kind != 'original' or b.kind != 'original':
        return False
    for diagnostic in diagnostics:
        if diagnostic.code == code:
            locations = (diagnostic.primary, *(item.location for item in diagnostic.related))
            if a in locations and b in locations:
                return True
    return False


def resolve_analyses(inputs: Iterable[LocalAnalysis]) -> ResolvedAnalysis:
    """Build a graph from all collected occurrences, in supplied input order.

    API misuse raises TypeError (non-local elements) or ValueError (duplicate
    SourceRef). Invalid manuscript content remains in diagnostics/partial output.
    Pending edges, implicit dependencies and M3 checks are never produced here.
    """
    inputs = tuple(inputs)
    if any(not isinstance(item, LocalAnalysis) for item in inputs):
        raise TypeError('resolve_analyses requires LocalAnalysis inputs')
    if len({item.source.ref for item in inputs}) != len(inputs):
        raise ValueError('duplicate source snapshot in resolver inputs')

    nodes = tuple(key for item in inputs for key in item.nodes)
    declarations = tuple(declaration for item in inputs for declaration in item.declarations)
    index = ResolutionIndex(nodes, declarations)
    objects = {}
    requirement_ids = {}
    for item in inputs:
        for requirement in item.requirements:
            objects[requirement.key] = requirement
            requirement_ids[requirement.key] = requirement.key.name
            if requirement.model is not None:
                objects[requirement.model.key] = requirement.model
                requirement_ids[requirement.model.key] = requirement.key.name
        objects.update((node.key, node) for node in (*item.declarations, *item.glossary))

    diagnostics = []
    local_diagnostics = tuple(d for item in inputs for d in item.diagnostics)
    declaration_checks = [item.checks.declarations for item in inputs]
    for keys in index.collisions:
        code = _DUPLICATE_CODES[keys[0].namespace]
        for position, current in enumerate(keys[1:], 1):
            field = _name_field(objects[current])
            previous = tuple(key for key in keys[:position] if key.source != current.source or not _reported(
                code, field, _name_field(objects[key]), local_diagnostics))
            if previous:
                diagnostics.append(Diagnostic(
                    code, 'error', 'user', f'Duplicate {current.namespace} name: {current.name}',
                    _location(field), (*_container(field), *(related for key in previous
                        for related in _related('Previous definition', _name_field(objects[key])))),
                    requirement_id=requirement_ids.get(current),
                ))
        if keys[0].namespace in ('declaration', 'glossary'):
            declaration_checks.append(CheckResult('spec.declarations', 'failed',
                                                   f'Colliding {keys[0].namespace} name: {keys[0].name}'))

    edges = []
    for item in inputs:
        for owner, reference in item.references:
            status, candidates, builtin = index.classify(reference)
            edge = ReferenceResolution(owner, reference, status, candidates, builtin)
            edges.append(edge)
            if status == 'resolved':
                continue
            code = ('spec.undefined-glossary' if reference.kind == 'glossary' else 'spec.undefined-reference')
            if status == 'ambiguous':
                code = 'spec.ambiguous-reference'
            elif status == 'wrong-kind':
                code = 'spec.wrong-reference-kind'
            evidence = []
            related = list(_container(reference.origin))
            for key in candidates:
                related.extend(_related('Candidate definition', _name_field(objects[key])))
            if builtin is not None:
                evidence.append(Evidence('spec.builtin', f'{builtin} is a builtin type; uses requires a variable or constant'))
            declaration = index.declarations.get(owner)
            if (reference.kind == 'type' and declaration is not None
                    and declaration.kind == 'constant' and reference.name not in ('bool', 'int')):
                value = _field(declaration, '/value')
                reason = f'Enum membership not run for {declaration.key.name}: type reference is {status}'
                evidence.append(Evidence('spec.enum-membership', f'{reason}; value={declaration.value!r}', _location(value)))
                related.extend(_container(value))
                declaration_checks.append(CheckResult('spec.declarations', 'not-run', reason))
            diagnostics.append(Diagnostic(
                code, 'error', 'user', f'{status} {reference.kind} reference: {reference.name}',
                _location(reference.origin),
                tuple(related),
                requirement_id=requirement_ids.get(owner), evidence=tuple(evidence),
            ))

    by_reference = {(edge.owner, edge.reference): edge for edge in edges}
    for declaration in declarations:
        if declaration.kind != 'constant' or declaration.type_ref.name in ('bool', 'int'):
            continue
        edge = by_reference[declaration.key, declaration.type_ref]
        if edge.status != 'resolved':
            continue  # The type diagnostic already records the skipped value check.
        target = index.declarations[edge.candidates[0]]
        if declaration.value not in target.values:
            field = _field(declaration, '/value')
            reason = f'Constant {declaration.key.name} is outside enum {target.key.name}'
            declaration_checks.append(CheckResult('spec.declarations', 'failed', reason))
            diagnostics.append(Diagnostic(
                'spec.invalid-definition', 'error', 'user', reason,
                _location(field), (*_container(field),
                    *_related('Enum type definition', _name_field(target)),
                    *_related('Allowed enum values', _field(target, '/values'))),
                evidence=(Evidence('spec.enum-membership', f'value={declaration.value!r}; allowed={target.values!r}'),),
            ))

    unavailable = not inputs or all(item.completeness == 'unavailable' for item in inputs)
    if unavailable:
        checks = AnalysisChecks(
            _aggregate('structure', [item.checks.structure for item in inputs]) if inputs
            else CheckResult('spec.structure', 'not-run', 'No analysis inputs'),
            _aggregate('declarations', declaration_checks) if declaration_checks
            else CheckResult('spec.declarations', 'not-run', 'No analysis inputs'),
            CheckResult('spec.references', 'not-run', 'No available analysis inputs'),
        )
    else:
        bad_references = index.collisions or any(edge.status != 'resolved' for edge in edges)
        references = ('failed' if bad_references else 'unknown'
                      if any(item.completeness != 'complete' for item in inputs) else 'passed')
        checks = AnalysisChecks(
            _aggregate('structure', [item.checks.structure for item in inputs]),
            _aggregate('declarations', declaration_checks),
            CheckResult('spec.references', references,
                        'Invalid references or colliding names' if bad_references else
                        'Resolution covers collected nodes only; local inputs are incomplete' if references == 'unknown' else None),
        )
    completeness = ('unavailable' if unavailable else 'complete'
                    if all(item.completeness == 'complete' for item in inputs)
                    and all(check.status == 'passed' for check in checks.as_tuple()[:3])
                    and not any(item.rejected for item in inputs)
                    and not any(d.severity == 'error' for d in (*local_diagnostics, *diagnostics)) else 'partial')
    return ResolvedAnalysis(inputs, SpecGraph(nodes, tuple(edges)), checks, completeness, tuple(diagnostics))
