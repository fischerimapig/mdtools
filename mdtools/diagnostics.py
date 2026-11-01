"""Minimal assembly route from Workspace loading to a shared diagnostic report."""

from pathlib import Path

from mdtools.core.diagnostics import CheckResult, Diagnostic, DiagnosticReport, Evidence
from mdtools.core.source import SourceSnapshot
from mdtools.workspace import WorkspaceError, load_workspace, snapshot_sources


class DefinitionReadError(ValueError):
    """Pre-snapshot read failure, carrying the existing common report type."""

    def __init__(self, path, detail):
        message = f'{path}: {detail}'
        super().__init__(message)
        self.report = DiagnosticReport(
            (Diagnostic('spec.read-error', 'error', 'tool-error', message,
                        evidence=(Evidence('spec.path', str(path)),)),),
            (CheckResult('spec.structure', 'error', message),
             CheckResult('spec.declarations', 'not-run', 'Definition snapshot could not be read'),
             CheckResult('spec.references', 'not-run', 'Workspace resolution belongs to #38'),
             *(CheckResult('spec.' + name, 'not-run', 'M3 check; not executed by M2')
               for name in ('expression-syntax', 'expression-types', 'expression-uses', 'logic'))),
        )


def read_definition_source(path: str | Path) -> SourceSnapshot:
    """Read a Workspace-selected definition without inventing a failed snapshot.

    This thin host boundary does not parse content or import spec. Registration
    and selection belong to Workspace; callers pass its DefinitionInput.path.
    """
    try:
        source = SourceSnapshot.from_path(path)
    except (OSError, UnicodeError) as exc:
        raise DefinitionReadError(path, str(exc)) from exc
    return source


def inspect_workspace(config_path: str | Path) -> DiagnosticReport:
    """Inspect registration/body readability only, without analyzing specifications.

    Loading failures have no known source span/snapshot. Preserve the path as
    evidence rather than rereading files or inventing a line/column.
    """
    try:
        sources = snapshot_sources(load_workspace(config_path))
    except WorkspaceError as exc:
        if exc.code == "workspace.read-error":
            category, status = "tool-error", "error"
        elif exc.code == "workspace.unsupported-version":
            category, status = "unsupported", "unsupported"
        elif exc.code == "workspace.changed-input":
            category, status = "unknown", "unknown"
        else:
            category, status = "user", "failed"
        diagnostic = Diagnostic(
            exc.code, "error", category, str(exc),
            evidence=(Evidence("workspace.path", str(exc.path)),),
        )
        return DiagnosticReport((diagnostic,), (CheckResult("workspace.sources", status, str(exc)),))
    return DiagnosticReport(checks=(CheckResult("workspace.sources", "passed"),), sources=sources)
