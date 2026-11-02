"""Versioned, pure projection of existing M2 values; never reads originals."""
from dataclasses import dataclass, fields, is_dataclass
import json
from pathlib import Path

from mdtools.core.diagnostics import DiagnosticReport, report_to_dict
from mdtools.core.source import SourceRef
from .model import JsonObject
from .results import ResolvedAnalysis


@dataclass(frozen=True)
class ManifestEntry:
    role: str
    uri: str
    path: Path
    state: str
    source: SourceRef | None = None
    reason: str | None = None

    def __post_init__(self):
        if self.role not in ('workspace', 'hierarchy', 'body', 'spec', 'glossary'):
            raise ValueError('invalid manifest role')
        if self.path.as_uri() != self.uri:
            raise ValueError('manifest path/URI mismatch')
        if self.state not in ('read', 'analyzed', 'read-error', 'analysis-error', 'not-run'):
            raise ValueError('invalid manifest state')
        if self.state in ('read', 'analyzed', 'analysis-error') and self.source is None:
            raise ValueError('read input requires a snapshot')
        if self.source is not None and self.source.uri != self.uri:
            raise ValueError('manifest source mismatch')
        if self.state in ('read-error', 'not-run') and self.source is not None:
            raise ValueError('unread input cannot have a snapshot')
        if self.state in ('read-error', 'analysis-error', 'not-run') and not self.reason:
            raise ValueError('incomplete input requires a reason')


@dataclass(frozen=True)
class InputManifest:
    entries: tuple[ManifestEntry, ...]
    workspace_version: int | None = None
    root: Path | None = None
    # (kind, original, canonical); no mutable DocumentTree aliases.
    documents: tuple[tuple[str, Path, Path | None], ...] = ()
    generated: tuple[Path, ...] = ()
    consistency: str = 'per-file'

    def __post_init__(self):
        if not isinstance(self.entries, tuple) or any(not isinstance(e, ManifestEntry) for e in self.entries):
            raise ValueError('manifest entries must be an immutable tuple')
        if len({e.uri for e in self.entries}) != len(self.entries):
            raise ValueError('duplicate manifest input')
        if self.workspace_version is not None and (type(self.workspace_version) is not int or self.workspace_version != 1):
            raise ValueError('unsupported Workspace version')
        if self.consistency != 'per-file':
            raise ValueError('atomic snapshots are not supported')
        if self.root is not None and not self.root.is_absolute():
            raise ValueError('manifest root must be absolute')


@dataclass(frozen=True)
class SpecIR:
    resolved: ResolvedAnalysis
    manifest: InputManifest
    report: DiagnosticReport
    completeness: str

    def __post_init__(self):
        if self.completeness not in ('complete', 'partial', 'unavailable'):
            raise ValueError('invalid completeness')
        selected = [e for e in self.manifest.entries if e.role in ('body', 'spec', 'glossary')]
        actual = tuple(i.source.ref for i in self.resolved.inputs)
        if tuple(e.source for e in selected if e.state == 'analyzed') != actual:
            raise ValueError('manifest does not cover resolver inputs')
        sources = {s.ref for s in self.report.sources}
        if any(e.source is not None and e.source not in sources for e in self.manifest.entries):
            raise ValueError('manifest snapshot missing from report')
        if self.completeness == 'complete':
            required = {'workspace.sources', 'spec.structure', 'spec.declarations', 'spec.references'}
            if not required <= {c.check_id for c in self.report.checks}:
                raise ValueError('complete IR requires explicit service checks')
            if (self.resolved.completeness != 'complete'
                    or any(e.state != 'analyzed' for e in selected)
                    or any(c.status != 'passed' for c in self.report.checks
                           if c.check_id in ('workspace.sources', 'spec.structure', 'spec.declarations', 'spec.references'))
                    or any(d.severity == 'error' for d in self.report.diagnostics)):
                raise ValueError('complete IR hides incomplete inputs or checks')
        if self.completeness == 'unavailable' and self.resolved.graph.nodes:
            raise ValueError('unavailable IR contains nodes')


def build_spec_ir(resolved, manifest, *, report, completeness):
    return SpecIR(resolved, manifest, report, completeness)


def _value(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, JsonObject):
        return {key: _value(item) for key, item in value.items}
    if is_dataclass(value):
        return {f.name: _value(getattr(value, f.name)) for f in fields(value)
                if getattr(value, f.name) is not None}
    if isinstance(value, tuple):
        return [_value(item) for item in value]
    return value


def ir_to_dict(ir: SpecIR) -> dict:
    """Fresh JSON value. Semantic IDs remain names within full occurrence keys."""
    resolved = ir.resolved
    requirements = [r for i in resolved.inputs for r in i.requirements]
    models = [r.model for r in requirements if r.model is not None]
    reqs = []
    for r in requirements:
        item = _value(r)
        if r.model is not None:
            item['model'] = _value(r.model.key)
        for body, raw in zip(item['bodies'], r.bodies):
            body['language'] = raw.language
        reqs.append(item)
    rank = {i.source.ref: n for n, i in enumerate(resolved.inputs)}
    rejected = sorted((r for i in resolved.inputs for r in i.rejected),
                      key=lambda r: (rank[r.span.source], r.span.start, r.span.end, r.kind, r.diagnostic_codes))
    return {
        'schema_version': 1, 'contract': {'id': 'mdtools-spec', 'version': 1},
        'implementation': {'id': 'mdtools.spec', 'revision': 1},
        'manifest': _value(ir.manifest),
        'inputs': [{'source': _value(i.source.ref), 'completeness': i.completeness,
                    'checks': report_to_dict(i.report)['checks']} for i in resolved.inputs],
        'nodes': _value(resolved.graph.nodes), 'requirements': reqs, 'models': _value(tuple(models)),
        'declarations': _value(tuple(d for i in resolved.inputs for d in i.declarations)),
        'glossary': _value(tuple(g for i in resolved.inputs for g in i.glossary)),
        'references': _value(resolved.graph.edges), 'rejected': _value(tuple(rejected)),
        'resolution': {'scope': 'collected-inputs', 'completeness': resolved.completeness,
                       'checks': report_to_dict(resolved.report)['checks']},
        'completeness': ir.completeness, 'report': report_to_dict(ir.report),
    }


def render_ir_json(ir: SpecIR) -> str:
    return json.dumps(ir_to_dict(ir), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'
