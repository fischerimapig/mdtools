"""Presentation adapter for the shared Workspace analysis service."""

from __future__ import annotations

import argparse
import json
import sys

from mdtools.analysis import analyze_workspace
from mdtools.core.diagnostics import (
    CheckResult, Diagnostic, DiagnosticReport, render_text, report_to_dict,
)
from mdtools.spec.ir import ir_to_dict
from mdtools.spec.model import expression_checks, identifier


def _requirement_id(value):
    try:
        identifier(value)
    except (ValueError, UnicodeError) as exc:
        raise argparse.ArgumentTypeError('invalid requirement ID') from exc
    return value


def _parser(prog):
    parser = argparse.ArgumentParser(
        prog=prog, description='登録原典の要件・参照・出典とM2検査状態を表示します。',
        epilog=f'例: {prog} index --project mdtools.toml --format json\n'
               f'    {prog} show REQ-NORMAL --project mdtools.toml\n'
               'README 原典: README.md「spec」\n'
               'M3の式・型・論理検査は実行しません。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest='command', required=True)
    for name, description in (('index', 'Workspace全体のSpecIRを表示'),
                              ('show', '指定要件と関連定義を表示')):
        child = commands.add_parser(
            name, description=description,
            epilog=f'例: {prog} {name}' + (' REQ-NORMAL' if name == 'show' else '')
                   + ' --project mdtools.toml --format json\nREADME 原典: README.md「spec」',
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        if name == 'show':
            child.add_argument('requirement_id', type=_requirement_id, metavar='ID', help='要件ID（大小文字を区別）')
        child.add_argument('--project', required=True, metavar='PATH', help='Workspace設定を明示指定')
        child.add_argument('--format', choices=('text', 'json'), default='text', help='表示形式（既定: text）')
    return parser


def _key(value):
    # Include the complete occurrence identity, never just the semantic name.
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _select(data, name):
    requirements = [r for r in data['requirements'] if r['key']['name'] == name]
    if not requirements:
        return None
    owners = {_key(r['key']) for r in requirements}
    model_keys = {_key(r['model']) for r in requirements if 'model' in r}
    owners.update(model_keys)
    # Traverse only explicit uses/type/glossary candidates already resolved by
    # the service. refs candidates remain keys; their bodies are never expanded.
    declarations, glossary = set(), set()
    pending = list(owners)
    edges = {}
    for edge in data['references']:
        edges.setdefault(_key(edge['owner']), []).append(edge)
    while pending:
        owner = pending.pop()
        for edge in edges.get(owner, ()):
            kind = edge['reference']['kind']
            namespace = {'uses': 'declaration', 'type': 'declaration', 'glossary': 'glossary'}.get(kind)
            for candidate in edge['candidates']:
                if candidate['namespace'] != namespace:
                    continue
                key = _key(candidate)
                (glossary if namespace == 'glossary' else declarations).add(key)
                if key not in owners:
                    owners.add(key)
                    pending.append(key)
    def contained(fragment):
        span = fragment['span']
        point = lambda p: (p['line'], p['column'])
        return any(span['source'] == r['span']['source']
                   and point(r['span']['start']) <= point(span['start'])
                   and point(span['end']) <= point(r['span']['end']) for r in requirements)
    return {
        'requirements': requirements,
        'models': [m for m in data['models'] if _key(m['key']) in model_keys],
        'declarations': [d for d in data['declarations'] if _key(d['key']) in declarations],
        'glossary': [g for g in data['glossary'] if _key(g['key']) in glossary],
        'references': [e for e in data['references'] if _key(e['owner']) in owners],
        'rejected': [r for r in data['rejected'] if contained(r)],
    }


def _exit_code(status, report, unknown):
    if any(d.category == 'tool-error' for d in report.diagnostics) or any(c.status == 'error' for c in report.checks):
        return 4
    if any(d.code == 'spec.missing-dependency' for d in report.diagnostics):
        return 5
    if (status != 'complete'
            or any(d.severity == 'error' and d.code != 'spec.unknown-id' for d in report.diagnostics)
            or any(c.status != 'passed' for c in report.checks
                   if c.check_id in ('workspace.sources', 'spec.structure', 'spec.declarations', 'spec.references', 'spec.ir'))):
        return 1
    return 3 if unknown else 0


def _text_tree(value, prefix=''):
    """Lossless field display; JSON quoting keeps body/control characters clear."""
    if isinstance(value, dict) and value:
        return ''.join(_text_tree(v, prefix + str(k) + '.') for k, v in value.items())
    if isinstance(value, list) and value:
        return ''.join(_text_tree(v, prefix + f'[{n}].') for n, v in enumerate(value))
    return prefix.rstrip('.') + ' = ' + json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n'


def main(argv=None, *, prog='mdtools spec') -> int:
    args = _parser(prog).parse_args(argv)
    analysis = None
    result = None
    unknown = False
    try:
        analysis = analyze_workspace(args.project)
        status, report = analysis.completeness, analysis.report
        if analysis.ir is not None:
            result = ir_to_dict(analysis.ir)
            if args.command == 'show':
                result = _select(result, args.requirement_id)
                unknown = result is None
                if unknown:
                    diagnostic = Diagnostic('spec.unknown-id', 'error', 'user',
                                            f'Requirement ID not found in analyzed requirements: {args.requirement_id}',
                                            requirement_id=args.requirement_id)
                    report = DiagnosticReport((*report.diagnostics, diagnostic), report.checks, report.sources)
        code = _exit_code(status, report, unknown)
    except Exception as exc:
        # The CLI is the final host boundary. Preserve any completed analysis;
        # an adapter failure must not erase acquired diagnostics or snapshots.
        status = analysis.completeness if analysis else 'unavailable'
        previous = analysis.report if analysis else DiagnosticReport(
            checks=tuple(CheckResult('spec.' + n, 'not-run', 'Analysis did not complete')
                         for n in ('structure', 'declarations', 'references')) + expression_checks())
        report = DiagnosticReport(
            (*previous.diagnostics, Diagnostic('spec.execution-error', 'error', 'tool-error', f'{type(exc).__name__}: {exc}')),
            (*previous.checks, CheckResult('spec.cli', 'error', 'CLI analysis or selection failed')), previous.sources)
        result, code = None, 4
    envelope = dict(schema_version=1, command=args.command, status=status, exit_code=code,
                    result=result, report=report_to_dict(report))
    if args.command == 'show':
        envelope['query'] = {'requirement_id': args.requirement_id}
    if args.format == 'json':
        output = json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'
    else:
        # index's IR report is identical to the envelope report; render it once
        # with the common renderer, keeping all other IR fields in the display.
        display = {k: v for k, v in envelope.items() if k != 'report'}
        if args.command == 'index' and result is not None:
            display['result'] = {k: v for k, v in result.items() if k != 'report'}
        output = _text_tree(display) + render_text(report)
    sys.stdout.write(output)
    return code
