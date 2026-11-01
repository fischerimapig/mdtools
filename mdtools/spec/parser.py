"""Extract v1 requirements from one original SourceSnapshot, without I/O.

No composition, language filtering, glossary substitution, name resolution or
expression evaluation occurs here. Recovery requires a known block boundary;
an unclosed block owns the remainder of this snapshot, never another file.
"""

from __future__ import annotations

import re

from mdtools.core.diagnostics import CheckResult, Diagnostic, DiagnosticLocation, RelatedLocation
from mdtools.core.source import SourceSnapshot
from . import _markdown as md
from ._json import JsonError, parse_json
from .model import (
    Body, Expression, FieldSource, FormalModel, NodeKey, Reference,
    RejectedFragment, Requirement, identifier,
)
from .results import AnalysisChecks, LocalAnalysis


def _reserved(div: md.Div, text: str) -> bool:
    # Also recognize malformed .requirement#ID / .requirement=... tokens,
    # without reserving .requirement-example or a quoted attribute value.
    return any(re.match(r'\.requirement(?:$|[^A-Za-z0-9_.-])',
                        text[div.attr_offset + t.start:div.attr_offset + t.end])
               for t in div.attrs)


def _language(div: md.Div) -> bool:
    return any(t.name == 'lang' and t.kind in ('attribute', 'invalid') for t in div.attrs)


def _check(diagnostics) -> CheckResult:
    if any(d.category == 'user' for d in diagnostics):
        return CheckResult('spec.structure', 'failed', 'Invalid reserved syntax in this scope')
    if diagnostics:
        return CheckResult('spec.structure', 'unsupported', 'Unsupported reserved syntax in this scope')
    return CheckResult('spec.structure', 'passed')


class _Parser:
    def __init__(self, source):
        self.source = source
        self.diagnostics = []
        self.rejected = []
        self.requirements = []
        self.ordinal = 0

    def key(self, namespace, name):
        key = NodeKey(namespace, name, self.source.ref, self.ordinal)
        self.ordinal += 1
        return key

    def field(self, path, start, end, container):
        return FieldSource(path, DiagnosticLocation('original', self.source.span(start, end)), container)

    def diagnose(self, code, message, start, end, *, owner=None, previous=None):
        category = 'unsupported' if code.startswith('spec.unsupported-') else 'user'
        related = (() if previous is None else (
            RelatedLocation('Previous occurrence', DiagnosticLocation('original',
                            self.source.span(*previous))),))
        diagnostic = Diagnostic(code, 'error', category, message,
                                DiagnosticLocation('original', self.source.span(start, end)),
                                related, requirement_id=owner)
        self.diagnostics.append(diagnostic)
        return diagnostic

    def reject(self, kind, block, diagnostics):
        span = self.source.span(block.start, block.end)
        self.rejected.append(RejectedFragment(kind, span, self.source.slice(span),
                                             tuple(dict.fromkeys(d.code for d in diagnostics))))

    def attributes(self, div):
        start = len(self.diagnostics)
        span = self.source.span(div.start, div.end)
        found, fields, refs = {}, [], []
        if not div.valid:
            self.diagnose('spec.invalid-requirement',
                          'Expected ::: {attributes} with no trailing text', div.start, div.header_end)
        for token in div.attrs:
            a, b = div.attr_offset + token.start, div.attr_offset + token.end
            name = ('id' if token.kind == 'id' else '.requirement' if token.kind == 'class'
                    and token.value == 'requirement' else token.name)
            if (token.kind == 'invalid' or name not in ('id', '.requirement', 'spec-version', 'status', 'refs')
                    or token.kind == 'attribute' and name == 'id'
                    or token.kind == 'class' and token.value != 'requirement'):
                self.diagnose('spec.invalid-requirement', 'Unknown or malformed requirement attribute', a, b)
                continue
            if name in found:
                old = found[name]
                self.diagnose('spec.invalid-requirement', 'Duplicate requirement attribute: ' + name,
                              a, b, previous=(div.attr_offset + old.start, div.attr_offset + old.end))
                continue
            found[name] = token
            if name != '.requirement':
                fields.append(self.field('/' + name, div.attr_offset + token.value_start,
                                         div.attr_offset + token.value_end, span))
        for name in ('.requirement', 'id', 'spec-version'):
            if name not in found:
                self.diagnose('spec.invalid-requirement', 'Missing requirement attribute: ' + name,
                              div.start, div.header_end)
        for name, token in found.items():
            a, b = div.attr_offset + token.value_start, div.attr_offset + token.value_end
            if name == 'spec-version' and token.value != '1':
                if not token.value.strip():
                    self.diagnose('spec.invalid-requirement', 'spec-version must not be empty', a, b)
                else:
                    self.diagnose('spec.unsupported-version', 'Only spec-version=1 is supported', a, b)
            if name == 'status' and token.value not in ('draft', 'active', 'deprecated'):
                self.diagnose('spec.invalid-requirement', 'Unknown requirement status', a, b)
            if name == 'id':
                try:
                    identifier(token.value)
                except ValueError:
                    self.diagnose('spec.invalid-requirement', 'Invalid requirement ID', a, b)
            if name == 'refs':
                for i, match in enumerate(re.finditer(r'\S+', token.value)):
                    left = div.attr_offset + token.value_ranges[match.start()][0]
                    right = div.attr_offset + token.value_ranges[match.end() - 1][1]
                    origin = self.field(f'/refs/{i}', left, right, span)
                    try:
                        ref = Reference('refs', match[0], origin)
                    except ValueError:
                        self.diagnose('spec.invalid-requirement', 'Invalid requirement reference', left, right)
                    else:
                        refs.append(ref)
                        fields.append(origin)
        if 'status' not in found:
            fields.append(FieldSource('/status', DiagnosticLocation('unmapped',
                                      reason='Omitted status defaults to draft; no source token'), span))
        if len(self.diagnostics) != start:
            return None
        return found['id'].value, found['status'].value if 'status' in found else 'draft', tuple(fields), tuple(refs)

    def model(self, block, owner):
        initial = len(self.diagnostics)
        span = self.source.span(block.start, block.end)
        base = block.body_start
        try:
            root = parse_json(self.source.text[base:block.body_end])
        except JsonError as exc:
            code = 'spec.unsupported-syntax' if exc.unsupported else 'spec.invalid-model'
            self.diagnose(code, str(exc), base + exc.start, base + exc.end,
                          owner=owner, previous=(tuple(base + p for p in exc.previous)
                                                 if exc.previous else None))
            return None
        if not isinstance(root.value, dict):
            self.diagnose('spec.invalid-model', 'mdspec must contain a JSON object',
                          base + root.start, base + root.end, owner=owner)
            return None
        required = ('version', 'id', 'kind', 'uses', 'when', 'must')
        members = {key.value: value for key, value in root.members}
        version = members.get('version')
        if version is not None and type(version.value) is int and version.value != 1:
            self.diagnose('spec.unsupported-version', 'Only model version 1 is supported',
                          base + version.start, base + version.end, owner=owner)
            return None  # Do not apply the v1 field contract to an unknown version.
        for name in required:
            if name not in members:
                self.diagnose('spec.invalid-model', 'Missing model field: ' + name,
                              base + root.start, base + root.end, owner=owner)
        for key, value in root.members:
            if key.value not in required:
                self.diagnose('spec.invalid-model', 'Unknown model field: ' + key.value,
                              base + key.start, base + key.end, owner=owner)
        fields, refs = {}, []
        for name in required:
            if name not in members:
                continue
            token = members[name]
            value = token.value
            a, b = base + token.start, base + token.end
            fields[name] = self.field('/' + name, a, b, span)

            def invalid(message):
                self.diagnose('spec.invalid-model', message, a, b, owner=owner)

            if name == 'version':
                if type(value) is not int:
                    invalid('Model version must be an integer')
            elif name == 'kind':
                if not isinstance(value, str) or not value.strip():
                    invalid('Model kind must be a nonempty string')
                elif value != 'constraint':
                    self.diagnose('spec.unsupported-syntax', 'Only constraint models are supported', a, b, owner=owner)
            elif name == 'id':
                try:
                    identifier(value)
                except ValueError:
                    invalid('Invalid model ID')
            elif name in ('when', 'must'):
                if not isinstance(value, str) or not value.strip():
                    invalid(name + ' must be a nonempty expression string')
            elif name == 'uses':
                if not isinstance(value, list):
                    invalid('uses must be an array of unique declaration names')
                    continue
                seen = {}
                for i, element in enumerate(token.elements):
                    left, right = base + element.start, base + element.end
                    origin = self.field(f'/uses/{i}', left, right, span)
                    try:
                        reference = Reference('uses', element.value, origin)
                    except ValueError:
                        self.diagnose('spec.invalid-model', 'Invalid declaration name in uses', left, right, owner=owner)
                        continue
                    if reference.name in seen:
                        self.diagnose('spec.invalid-model', 'Duplicate uses name: ' + reference.name,
                                      left, right, owner=owner, previous=seen[reference.name])
                    else:
                        seen[reference.name] = (left, right)
                    refs.append(reference)
                    fields[f'uses/{i}'] = origin
        if len(self.diagnostics) != initial:
            return None
        return FormalModel(self.key('model', members['id'].value), span, tuple(fields.values()), tuple(refs),
                           Expression(members['when'].value, fields['when']),
                           Expression(members['must'].value, fields['must']))

    def requirement(self, div):
        initial = len(self.diagnostics)
        attrs = self.attributes(div)
        owner = attrs[0] if attrs else None
        if not div.closed:
            self.diagnose('spec.invalid-requirement', 'Requirement is not closed in this source snapshot',
                          div.start, div.header_end, owner=owner)
        if attrs is None:
            self.reject('requirement', div, self.diagnostics[initial:])
            return  # Preserve raw input without interpreting an unknown/invalid header.
        bodies, models = [], []
        invalid_language = False
        pending = [(child, None, True) for child in reversed(div.children)]
        while pending:
            block, language, direct = pending.pop()
            if isinstance(block, md.Div):
                if _reserved(block, self.source.text):
                    diagnostic = self.diagnose('spec.unsupported-syntax', 'Nested requirements are unsupported',
                                               block.start, block.header_end, owner=owner)
                    self.reject('requirement', block, (diagnostic,))
                    continue
                if not block.closed:
                    self.diagnose('spec.invalid-requirement', 'Unclosed child div in requirement',
                                  block.start, block.header_end, owner=owner)
                if _language(block):
                    langs = [t for t in block.attrs if t.name == 'lang']
                    if (not block.valid or len(langs) != 1 or langs[0].kind != 'attribute'
                            or not langs[0].value.strip()):
                        self.diagnose('spec.invalid-requirement', 'Malformed language div',
                                      block.start, block.header_end, owner=owner)
                        invalid_language = True
                    else:
                        language = langs[0].value
                pending.extend((child, language, False) for child in reversed(block.children))
            elif isinstance(block, md.Code) and block.info.startswith('mdspec'):
                models.append((block, direct))
            else:
                if bodies and bodies[-1][0] == language and bodies[-1][2] == block.start:
                    bodies[-1] = (language, bodies[-1][1], block.end)
                else:
                    bodies.append((language, block.start, block.end))
        bodies = tuple(Body(lang, self.source.text[a:b], self.source.span(a, b))
                       for lang, a, b in bodies if self.source.text[a:b].strip())
        if invalid_language:
            # There is no safe language assignment for this body's contents.
            self.reject('requirement', div, self.diagnostics[initial:])
            return
        if not bodies:
            self.diagnose('spec.invalid-requirement', 'Requirement body must not be empty',
                          div.start, div.end, owner=owner)
            self.reject('requirement', div, self.diagnostics[initial:])
            return
        # Allocate only retained nodes, with the requirement before its model.
        key = self.key('requirement', owner)
        model = None
        multiple = len(models) > 1
        for block, direct in models:
            model_initial = len(self.diagnostics)
            if multiple:
                self.diagnose('spec.unsupported-syntax', 'Multiple mdspec blocks in one requirement are unsupported',
                              block.start, block.body_start, owner=owner)
            if not direct:
                self.diagnose('spec.invalid-model', 'mdspec must belong directly to its requirement',
                              block.start, block.body_start, owner=owner)
            if block.info != 'mdspec':
                self.diagnose('spec.invalid-model', 'Reserved info string must be exactly mdspec',
                              block.start, block.body_start, owner=owner)
            if not block.closed:
                self.diagnose('spec.invalid-model', 'mdspec code fence is not closed in this source snapshot',
                              block.start, block.body_start, owner=owner)
            if len(self.diagnostics) == model_initial:
                model = self.model(block, owner)
            if len(self.diagnostics) != model_initial:
                self.reject('model', block, self.diagnostics[model_initial:])
        diagnostics = self.diagnostics[initial:]
        self.requirements.append(Requirement(key, self.source.span(div.start, div.end), attrs[2], bodies,
                                             _check(diagnostics), 'present' if models else 'natural-only',
                                             model, attrs[3], status=attrs[1]))

    def run(self):
        pending = [(block, False) for block in reversed(md.scan(self.source.text))]
        while pending:
            block, in_language = pending.pop()
            if isinstance(block, md.Div):
                if _reserved(block, self.source.text):
                    if in_language:
                        diagnostic = self.diagnose('spec.unsupported-syntax', 'Requirements inside language divs are unsupported',
                                                   block.start, block.header_end)
                        self.reject('requirement', block, (diagnostic,))
                    else:
                        self.requirement(block)
                else:
                    pending.extend((child, in_language or _language(block)) for child in reversed(block.children))
            elif isinstance(block, md.Code) and block.info.startswith('mdspec'):
                initial = len(self.diagnostics)
                self.diagnose('spec.invalid-model', 'mdspec has no containing requirement',
                              block.start, block.body_start)
                if block.info != 'mdspec':
                    self.diagnose('spec.invalid-model', 'Reserved info string must be exactly mdspec',
                                  block.start, block.body_start)
                if not block.closed:
                    self.diagnose('spec.invalid-model', 'mdspec code fence is not closed in this source snapshot',
                                  block.start, block.body_start)
                self.reject('model', block, self.diagnostics[initial:])
        checks = AnalysisChecks(
            _check(self.diagnostics),
            CheckResult('spec.declarations', 'passed', 'No shared declarations in this Markdown input scope'),
            CheckResult('spec.references', 'not-run', 'Workspace reference resolution belongs to #38'),
        )
        return LocalAnalysis(self.source, checks, 'partial' if self.diagnostics else 'complete',
                             tuple(self.requirements), rejected=tuple(sorted(self.rejected, key=lambda r: r.span.start)),
                             diagnostics=tuple(self.diagnostics))


def parse_requirements(source: SourceSnapshot) -> LocalAnalysis:
    """Parse one original Markdown/QMD snapshot using the v1 structural contract.

    Source errors are diagnostics and partial results, not exceptions. Callers
    select originals with Workspace and invoke this once per snapshot. Duplicate
    IDs remain separate occurrences; reference and all M3 checks are not-run.
    """
    if not isinstance(source, SourceSnapshot):
        raise TypeError('parse_requirements requires an original SourceSnapshot')
    return _Parser(source).run()
