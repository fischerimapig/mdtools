"""Minimal assembly route from Workspace loading to a shared diagnostic report."""

from pathlib import Path

from mdtools.core.diagnostics import CheckResult, Diagnostic, DiagnosticReport, Evidence
from mdtools.workspace import WorkspaceError, load_workspace, snapshot_sources


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
