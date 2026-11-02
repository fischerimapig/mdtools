"""CLI-free Workspace/I/O assembly. No expression evaluation or backend calls."""
from dataclasses import dataclass
from pathlib import Path

from mdtools.core.diagnostics import CheckResult, Diagnostic, DiagnosticReport, Evidence
from mdtools.core.source import SourceSnapshot
from mdtools.workspace import Workspace, WorkspaceError, load_workspace
from mdtools.spec.parser import parse_requirements
from mdtools.spec.loader import load_definitions
from mdtools.spec.resolver import resolve_analyses
from mdtools.spec.results import LocalAnalysis, ResolvedAnalysis
from mdtools.spec.model import expression_checks
from mdtools.spec.ir import InputManifest, ManifestEntry, SpecIR, build_spec_ir


@dataclass(frozen=True)
class WorkspaceAnalysis:
    workspace: Workspace | None
    manifest: InputManifest
    inputs: tuple[LocalAnalysis, ...]
    resolved: ResolvedAnalysis | None
    ir: SpecIR | None
    report: DiagnosticReport
    completeness: str


class _ReadFailure(Exception):
    """Keep snapshot failures distinct from Workspace syntax validation."""
    def __init__(self, path, detail, *, changed=False):
        self.path, self.changed = path, changed
        super().__init__(detail)


def analyze_workspace(config_path: str | Path) -> WorkspaceAnalysis:
    """Analyze explicitly registered originals, freezing each read independently.

    Expected input failures return reports, never fake LocalAnalysis values.
    This is neither an atomic filesystem snapshot nor a freshness check.
    """
    entries, snapshots, locals_, diagnostics = [], [], [], []
    workspace = resolved = ir = None
    config = Path(config_path).absolute()

    def read(path, role):
        try:
            if path.resolve() != path:
                raise _ReadFailure(path, 'Selected path changed before reading', changed=True)
            source = SourceSnapshot.from_path(path)
            if source.path != path or path.resolve() != path:
                raise _ReadFailure(path, 'Selected path changed during reading', changed=True)
        except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
            raise _ReadFailure(path, f'{type(exc).__name__}: {exc}') from exc
        snapshots.append(source)
        entries.append(ManifestEntry(role, path.as_uri(), path, 'read', source.ref))
        return source

    def selection_text(path):
        # Workspace invokes this once for config and once per registered hierarchy.
        role = 'workspace' if not entries else 'hierarchy'
        return read(path, role).text

    def failure(code, path, message, category='tool-error'):
        diagnostics.append(Diagnostic(code, 'error', category, message,
                                      evidence=(Evidence('spec.path', str(path)),)))

    selection_status = 'passed'
    try:
        workspace = load_workspace(config_path, read_text=selection_text)
    except _ReadFailure as exc:
        role = 'workspace' if not entries else 'hierarchy'
        entries.append(ManifestEntry(role, exc.path.as_uri(), exc.path, 'read-error', reason=str(exc)))
        selection_status = 'unknown' if exc.changed else 'error'
        failure('workspace.changed-input' if exc.changed else 'spec.read-error', exc.path, str(exc),
                'unknown' if exc.changed else 'tool-error')
    except WorkspaceError as exc:
        selection_status = ('error' if exc.code == 'workspace.read-error' else 'unsupported'
                            if exc.code == 'workspace.unsupported-version' else 'failed')
        failure(exc.code, exc.path, str(exc), 'tool-error' if selection_status == 'error' else
                'unsupported' if selection_status == 'unsupported' else 'user')

    missing = False
    if workspace is not None:
        selected = [(p, 'body') for p in workspace.analysis_files]
        selected += [(d.path, d.kind) for d in workspace.definitions]
        for path, role in selected:
            try:
                source = read(path, role)
            except _ReadFailure as exc:
                missing = True
                entries.append(ManifestEntry(role, path.as_uri(), path, 'read-error', reason=str(exc)))
                failure('workspace.changed-input' if exc.changed else 'spec.read-error', path, str(exc),
                        'unknown' if exc.changed else 'tool-error')
                continue
            try:
                local = (parse_requirements(source) if role == 'body' else
                         load_definitions(source, kind=role, format=path.suffix.lower()[1:]))
                locals_.append(local)
                entries[-1] = ManifestEntry(role, path.as_uri(), path, 'analyzed', source.ref)
            except Exception as exc:
                # Includes the known deep-glossary loader capacity limitation;
                # this boundary reports failure, it does not repair the loader.
                missing = True
                reason = f'{type(exc).__name__}: {exc}'
                entries[-1] = ManifestEntry(role, path.as_uri(), path, 'analysis-error', source.ref, reason)
                failure('spec.execution-error', path, reason)
        try:
            resolved = resolve_analyses(locals_)
        except Exception as exc:
            failure('spec.execution-error', workspace.config_path, f'{type(exc).__name__}: {exc}')

    available = any(i.completeness != 'unavailable' for i in locals_)
    completeness = 'partial' if available else 'unavailable'
    if workspace is None:
        checks = tuple(CheckResult('spec.' + name, 'not-run', 'Workspace selection did not complete')
                       for name in ('structure', 'declarations', 'references')) + expression_checks()
    elif resolved is None:
        checks = (CheckResult('spec.structure', 'unknown', 'Resolution failed; see local results'),
                  CheckResult('spec.declarations', 'unknown', 'Workspace declaration checks did not complete'),
                  CheckResult('spec.references', 'error', 'Resolver execution failed'), *expression_checks())
    else:
        checks = resolved.checks.as_tuple()
        if missing:
            priority = ('error', 'failed', 'unsupported', 'unknown', 'not-run', 'passed')
            additions = ('error' if any(d.category == 'tool-error' for d in diagnostics) else 'unknown',
                         'unknown' if available else 'not-run', 'unknown' if available else 'not-run')
            checks = tuple(CheckResult(c.check_id, min((c.status, s), key=priority.index),
                                       '; '.join(filter(None, (c.reason, 'Registered inputs were not analyzed; collected inputs only'))))
                           for c, s in zip(checks[:3], additions)) + checks[3:]
        if not missing and resolved.completeness == 'complete':
            completeness = 'complete'
    source_status = selection_status
    if workspace is not None and any(e.state == 'read-error' for e in entries):
        source_status = 'error' if any(d.category == 'tool-error' for d in diagnostics) else 'unknown'
    source_check = CheckResult('workspace.sources', source_status,
                              None if source_status == 'passed' else 'Input selection or snapshot acquisition failed')
    all_diagnostics = (tuple(d for i in locals_ for d in i.diagnostics) if resolved is None
                       else resolved.report.diagnostics) + tuple(diagnostics)
    report = DiagnosticReport(all_diagnostics, (source_check, *checks), tuple(snapshots))
    manifest = InputManifest(tuple(entries), workspace.version if workspace else None,
                             workspace.root if workspace else None,
                             tuple((d.kind, d.path, d.canonical) for d in workspace.documents) if workspace else (),
                             workspace.generated if workspace else ())
    if resolved is not None:
        try:
            ir = build_spec_ir(resolved, manifest, report=report, completeness=completeness)
        except Exception as exc:
            failure('spec.execution-error', config, f'IR construction failed: {type(exc).__name__}: {exc}')
            completeness = 'partial' if available else 'unavailable'
            report = DiagnosticReport(all_diagnostics + (diagnostics[-1],),
                                      (source_check, CheckResult('spec.ir', 'error', str(exc)), *checks), tuple(snapshots))
    return WorkspaceAnalysis(workspace, manifest, tuple(locals_), resolved, ir, report, completeness)
