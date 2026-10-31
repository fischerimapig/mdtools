"""Local, unresolved collection versus workspace-wide resolution contracts.

These validate supplied values. They do not extract, load, resolve, build a
graph, serialize an IR, or decide a process exit code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from mdtools.core.diagnostics import CheckResult, Diagnostic, DiagnosticReport
from mdtools.core.source import SourceRef, SourceSnapshot, SourceSpan
from .model import (
    Body, Declaration, EXPRESSION_CHECKS, GlossaryEntry, NodeKey,
    Reference, REFERENCE_NAMESPACES, RejectedFragment, Requirement,
    expression_checks, typed_tuple, walk_values,
)

Completeness = Literal['complete', 'partial', 'unavailable']


@dataclass(frozen=True)
class AnalysisChecks:
    structure: CheckResult
    declarations: CheckResult
    references: CheckResult
    expressions: tuple[CheckResult, ...] = field(default_factory=expression_checks)

    def __post_init__(self) -> None:
        for name in ('structure', 'declarations', 'references'):
            check = getattr(self, name)
            if not isinstance(check, CheckResult) or check.check_id != f'spec.{name}':
                raise ValueError('incorrect analysis check ID')
        typed_tuple(self.expressions, CheckResult)
        if (len(self.expressions) != len(EXPRESSION_CHECKS)
                or {c.check_id for c in self.expressions} != set(EXPRESSION_CHECKS)
                or any(c.status != 'not-run' for c in self.expressions)):
            raise ValueError('M2 must explicitly leave all M3 checks unexecuted')

    def as_tuple(self) -> tuple[CheckResult, ...]:
        return (self.structure, self.declarations, self.references, *self.expressions)


def _provenance(values, sources) -> None:
    snapshots = {source.ref: source for source in sources}
    for value in walk_values(values):
        if isinstance(value, SourceRef) and value not in snapshots:
            raise ValueError('node snapshot is missing')
        if isinstance(value, SourceSpan):
            if value.source not in snapshots:
                raise ValueError('span snapshot is missing')
            snapshots[value.source].offsets(value)
        if isinstance(value, (Body, RejectedFragment)):
            if value.span.source not in snapshots:
                raise ValueError('raw text snapshot is missing')
            if snapshots[value.span.source].slice(value.span) != value.text:
                raise ValueError('raw text differs from its original snapshot span')


def _keys(nodes) -> None:
    typed_tuple(nodes, NodeKey)
    if len({(key.source, key.ordinal) for key in nodes}) != len(nodes):
        raise ValueError('node occurrence ordinals must be unique within each source')


def _completion(completeness, checks, diagnostics, rejected, nodes, *, local=False) -> None:
    if completeness not in ('complete', 'partial', 'unavailable'):
        raise ValueError('invalid completeness')
    if completeness == 'complete':
        checked = (checks.structure, checks.declarations) if local else checks.as_tuple()[:3]
        if any(c.status != 'passed' for c in checked):
            raise ValueError('complete result requires all applicable M2 checks to pass')
        if rejected or any(d.severity == 'error' for d in diagnostics):
            raise ValueError('complete result cannot hide rejected input or errors')
    if completeness == 'unavailable' and nodes:
        raise ValueError('unavailable result cannot contain collected nodes')
    if completeness != 'complete' and not any(
        c.status in ('failed', 'unsupported', 'error', 'unknown', 'not-run')
        for c in ((checks.structure, checks.declarations) if local else checks.as_tuple()[:3])
    ):
        raise ValueError('incomplete result requires an explicit incomplete M2 check')


@dataclass(frozen=True)
class LocalAnalysis:
    source: SourceSnapshot
    checks: AnalysisChecks
    completeness: Completeness
    requirements: tuple[Requirement, ...] = ()
    declarations: tuple[Declaration, ...] = ()
    glossary: tuple[GlossaryEntry, ...] = ()
    rejected: tuple[RejectedFragment, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source, SourceSnapshot) or not isinstance(self.checks, AnalysisChecks):
            raise ValueError('local analysis requires source and checks')
        for name, cls in (('requirements', Requirement), ('declarations', Declaration),
                          ('glossary', GlossaryEntry), ('rejected', RejectedFragment),
                          ('diagnostics', Diagnostic)):
            typed_tuple(getattr(self, name), cls)
        if self.checks.references.status != 'not-run':
            raise ValueError('local analysis must defer workspace reference resolution')
        _keys(self.nodes)
        self.report  # Validate diagnostic locations using the existing M1 model.
        _provenance((self.requirements, self.declarations, self.glossary, self.rejected), (self.source,))
        codes = {d.code for d in self.diagnostics}
        if any(not set(item.diagnostic_codes) <= codes for item in self.rejected):
            raise ValueError('rejected fragment diagnostic is missing')
        for requirement in self.requirements:
            if requirement.formalization == 'natural-only' and any(
                item.kind == 'model' and item.span.start >= requirement.span.start
                and item.span.end <= requirement.span.end for item in self.rejected
            ):
                raise ValueError('rejected formal model cannot become natural-only')
        if self.completeness == 'complete' and any(r.structure.status != 'passed' for r in self.requirements):
            raise ValueError('complete local analysis contains an incomplete requirement')
        _completion(self.completeness, self.checks, self.diagnostics, self.rejected, self.nodes, local=True)

    @property
    def nodes(self) -> tuple[NodeKey, ...]:
        nodes = []
        for requirement in self.requirements:
            nodes.append(requirement.key)
            if requirement.model is not None:
                nodes.append(requirement.model.key)
        nodes.extend(item.key for item in (*self.declarations, *self.glossary))
        return tuple(sorted(nodes, key=lambda key: key.ordinal))

    @property
    def references(self) -> tuple[tuple[NodeKey, Reference], ...]:
        result = []
        for requirement in self.requirements:
            result.extend((requirement.key, ref) for ref in requirement.refs)
            if requirement.model is not None:
                result.extend((requirement.model.key, ref) for ref in requirement.model.uses)
        for declaration in self.declarations:
            result.extend((declaration.key, ref) for ref in (declaration.type_ref, declaration.glossary)
                          if ref is not None)
        return tuple(result)

    @property
    def report(self) -> DiagnosticReport:
        return DiagnosticReport(self.diagnostics, self.checks.as_tuple(), (self.source,))


@dataclass(frozen=True)
class ReferenceResolution:
    owner: NodeKey
    reference: Reference
    status: Literal['pending', 'resolved', 'undefined', 'ambiguous', 'wrong-kind']
    candidates: tuple[NodeKey, ...] = ()
    builtin: Literal['bool', 'int'] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.owner, NodeKey) or not isinstance(self.reference, Reference):
            raise ValueError('resolution requires owner and reference')
        typed_tuple(self.candidates, NodeKey)
        if len(set(self.candidates)) != len(self.candidates):
            raise ValueError('duplicate resolution candidate')
        if self.status not in ('pending', 'resolved', 'undefined', 'ambiguous', 'wrong-kind'):
            raise ValueError('invalid resolution status')
        if any(key.name != self.reference.name for key in self.candidates):
            raise ValueError('candidate name differs from reference')
        if self.builtin is not None:
            if (self.status != 'resolved' or self.reference.kind != 'type'
                    or self.builtin not in ('bool', 'int') or self.reference.name != self.builtin
                    or self.candidates):
                raise ValueError('builtin resolution is only for builtin type references')
        elif self.status == 'resolved' and len(self.candidates) != 1:
            raise ValueError('resolved reference needs exactly one candidate')
        if self.status in ('pending', 'undefined') and (self.candidates or self.builtin is not None):
            raise ValueError('unresolved reference must not pretend to have a target')
        if self.status == 'ambiguous' and len(self.candidates) < 2:
            raise ValueError('ambiguous reference must preserve all candidate occurrences')
        if self.status == 'wrong-kind' and not self.candidates:
            raise ValueError('wrong-kind reference requires conflicting candidates')
        if self.status in ('resolved', 'ambiguous') and any(
            key.namespace != REFERENCE_NAMESPACES[self.reference.kind] for key in self.candidates
        ):
            raise ValueError('resolution crosses namespaces')


@dataclass(frozen=True)
class SpecGraph:
    """Supplied graph value only. Self edges and cycles are deliberately legal."""

    nodes: tuple[NodeKey, ...]
    edges: tuple[ReferenceResolution, ...]

    def __post_init__(self) -> None:
        _keys(self.nodes)
        typed_tuple(self.edges, ReferenceResolution)
        nodes = set(self.nodes)
        for edge in self.edges:
            if edge.owner not in nodes or any(key not in nodes for key in edge.candidates):
                raise ValueError('graph edge refers to an absent occurrence')
        if len({(e.owner, e.reference) for e in self.edges}) != len(self.edges):
            raise ValueError('duplicate graph edge')


@dataclass(frozen=True)
class ResolvedAnalysis:
    inputs: tuple[LocalAnalysis, ...]
    graph: SpecGraph
    checks: AnalysisChecks
    completeness: Completeness
    diagnostics: tuple[Diagnostic, ...] = ()  # Workspace-level additions only.

    def __post_init__(self) -> None:
        typed_tuple(self.inputs, LocalAnalysis)
        typed_tuple(self.diagnostics, Diagnostic)
        if not isinstance(self.graph, SpecGraph) or not isinstance(self.checks, AnalysisChecks):
            raise ValueError('resolved analysis requires graph and checks')
        report = self.report
        expected = tuple(key for item in self.inputs for key in item.nodes)
        if set(expected) != set(self.graph.nodes) or len(expected) != len(self.graph.nodes):
            raise ValueError('graph must retain every collected occurrence exactly once')
        refs = [(owner, ref) for item in self.inputs for owner, ref in item.references]
        if set(refs) != {(e.owner, e.reference) for e in self.graph.edges}:
            raise ValueError('graph must represent every explicit reference')
        _provenance(self.graph, report.sources)
        declarations = {d.key: d for item in self.inputs for d in item.declarations}
        for edge in self.graph.edges:
            matches = tuple(key for key in self.graph.nodes
                            if key.namespace == REFERENCE_NAMESPACES[edge.reference.kind]
                            and key.name == edge.reference.name)
            if edge.status == 'resolved' and edge.candidates and matches != edge.candidates:
                raise ValueError('resolved reference hides a name collision')
            if edge.status == 'ambiguous' and set(matches) != set(edge.candidates):
                raise ValueError('ambiguous reference must retain all name candidates')
            if edge.status == 'resolved' and edge.candidates and edge.reference.kind in ('uses', 'type'):
                target = declarations.get(edge.candidates[0])
                allowed = ('variable', 'constant') if edge.reference.kind == 'uses' else ('type',)
                if target is None or target.kind not in allowed:
                    raise ValueError('resolved declaration has the wrong kind')
        if self.completeness == 'complete':
            if any(item.completeness != 'complete' for item in self.inputs):
                raise ValueError('complete graph cannot hide incomplete local input')
            if any(edge.status != 'resolved' for edge in self.graph.edges):
                raise ValueError('complete graph contains unresolved references')
            names = [(key.namespace, key.name) for key in self.graph.nodes]
            if len(set(names)) != len(names):
                raise ValueError('complete graph contains colliding names')
        _completion(self.completeness, self.checks, report.diagnostics, (), self.graph.nodes)

    @property
    def report(self) -> DiagnosticReport:
        diagnostics = tuple(d for item in self.inputs for d in item.diagnostics) + self.diagnostics
        return DiagnosticReport(diagnostics, self.checks.as_tuple(), tuple(item.source for item in self.inputs))
