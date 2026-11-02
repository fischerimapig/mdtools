"""Generate a stable illustrative IR, using in-memory text at fixed example URIs.

These snapshots are explicitly constructed values, not claims of filesystem reads.
The actual Workspace service is separately exercised on both repository examples.
"""
from pathlib import Path
from mdtools.core.source import SourceSnapshot
from mdtools.core.diagnostics import DiagnosticReport, CheckResult
from mdtools.spec.parser import parse_requirements
from mdtools.spec.resolver import resolve_analyses
from mdtools.spec.ir import InputManifest, ManifestEntry, build_spec_ir, render_ir_json


def example_json():
    config = SourceSnapshot('file:///example/mdtools.toml',
                            'version=1\n[[documents]]\nkind="markdown"\npath="natural.md"\n', Path('/example/mdtools.toml'))
    body = SourceSnapshot('file:///example/natural.md',
                          '::: {.requirement #REQ-NATURAL spec-version=1}\n日本語のみ。\n:::\n', Path('/example/natural.md'))
    resolved = resolve_analyses((parse_requirements(body),))
    manifest = InputManifest((ManifestEntry('workspace', config.uri, config.path, 'read', config.ref),
                              ManifestEntry('body', body.uri, body.path, 'analyzed', body.ref)),
                             1, Path('/example'), (('markdown', body.path, None),))
    report = DiagnosticReport(resolved.report.diagnostics,
                              (CheckResult('workspace.sources', 'passed'), *resolved.checks.as_tuple()),
                              (config, body))
    return render_ir_json(build_spec_ir(resolved, manifest, report=report, completeness='complete'))


if __name__ == '__main__':
    print(example_json(), end='')
