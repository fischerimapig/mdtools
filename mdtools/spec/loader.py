"""Strict, local definition collection from one original snapshot.

No file reads, Workspace imports, reference resolution, CLI or display merging.
Recovery is at complete declaration/entry boundaries, never guessed syntax.
"""

from typing import Literal

from mdtools.core._structured import JsonError, Token
from mdtools.core.io import StructuredTextError, parse_structured_text
from mdtools.core.diagnostics import CheckResult, Diagnostic, DiagnosticLocation, Evidence, RelatedLocation
from mdtools.core.source import SourceSnapshot
from .model import Declaration, FieldSource, GlossaryEntry, JsonObject, NodeKey, Reference, RejectedFragment, identifier
from .results import AnalysisChecks, LocalAnalysis


def _pointer(name):
    return name.replace('~', '~0').replace('/', '~1')


class _Loader:
    def __init__(self, source, kind):
        self.source, self.kind = source, kind
        self.code = 'spec.invalid-definition' if kind == 'spec' else 'spec.invalid-glossary'
        self.diagnostics, self.rejected = [], []
        self.declarations, self.glossary = [], []
        self.issues = {'structure': [], 'declarations': []}
        self.ordinal = 0
        self.visited_mappings = set()

    def span(self, token):
        return self.source.span(token.start, token.end)

    def location(self, token):
        try:
            return DiagnosticLocation('original', self.span(token))
        except ValueError:
            return DiagnosticLocation('unmapped', reason='Parser offset has no exact source coordinate')

    def diagnose(self, message, token, *, code=None, previous=None, check='structure', category='user', evidence=()):
        location = (self.location(token) if token is not None else
                    DiagnosticLocation('unmapped', reason='No source token was examined'))
        related = []
        if previous is not None:
            related.append(RelatedLocation('Previous occurrence', self.location(previous)))
        if location.kind == 'unmapped':
            related.append(RelatedLocation('Known source container',
                                           DiagnosticLocation('original', self.source.span())))
        diagnostic = Diagnostic(code or self.code, 'error', category, message, location,
                                tuple(related), evidence=evidence)
        self.diagnostics.append(diagnostic)
        self.issues[check].append(category)
        return diagnostic

    def reject(self, token, diagnostics):
        try:
            span = self.span(token)
        except ValueError:
            span = self.source.span()
        self.rejected.append(RejectedFragment('definition' if self.kind == 'spec' else 'glossary',
                                             span, self.source.slice(span),
                                             tuple(dict.fromkeys(d.code for d in diagnostics))))

    def field(self, path, token, container):
        return FieldSource(path, self.location(token), container)

    def key(self, name):
        key = NodeKey('declaration' if self.kind == 'spec' else 'glossary',
                      name, self.source.ref, self.ordinal)
        self.ordinal += 1
        return key

    def members(self, token):
        """Diagnose duplicates without choosing any winning occurrence."""
        if id(token) in self.visited_mappings:
            return token.members
        self.visited_mappings.add(id(token))
        seen = {}
        for key, value in token.members:
            if key.value in seen:
                self.diagnose('Duplicate mapping key: ' + key.value, key, previous=seen[key.value])
            else:
                seen[key.value] = key
        return token.members

    def remaining_duplicates(self, root):
        """Also inspect unknown/rejected fields, without interpreting their meaning."""
        pending = [root]
        while pending:
            token = pending.pop()
            if isinstance(token.value, dict):
                self.members(token)
                pending.extend(value for key, value in reversed(token.members))
            else:
                pending.extend(reversed(token.elements))

    def object(self, token, allowed, required):
        """Unique record fields only; caller rejects an ambiguous record."""
        if not isinstance(token.value, dict):
            self.diagnose('Expected an object', token)
            return {}
        pairs = self.members(token)
        found = {}
        for key, value in pairs:
            if key.value not in allowed:
                self.diagnose('Unknown field: ' + key.value, key)
            if key.value not in found:
                found[key.value] = value
        for name in required:
            if name not in found:
                self.diagnose('Missing required field: ' + name, token)
        return found

    def declaration(self, name, token, kind):
        start = len(self.diagnostics)
        whole = Token(None, name.start, token.end)
        allowed = ({'kind', 'values', 'glossary'} if kind == 'type' else
                   {'type', 'min', 'max', 'glossary', 'role' if kind == 'variable' else 'value'})
        required = ('kind', 'values') if kind == 'type' else ('type', 'role' if kind == 'variable' else 'value')
        found = self.object(token, allowed, required)
        try:
            identifier(name.value, declaration=kind != 'type')
            if name.value in ('bool', 'int'):
                raise ValueError('Builtin type names cannot be redeclared')
        except ValueError as exc:
            self.diagnose(str(exc), name, check='declarations')
        if len(self.diagnostics) != start:
            self.reject(whole, self.diagnostics[start:])
            return
        span = self.span(whole)
        fields = [self.field('/name', name, span)]
        fields.extend(self.field('/' + key.value, value, span) for key, value in token.members)

        def invalid(message, field):
            self.diagnose(message, found[field], check='declarations')

        link = found.get('glossary')
        if link is not None and (not isinstance(link.value, str) or not link.value):
            invalid('glossary must be a nonempty string ID', 'glossary')
        kwargs = {}
        if kind == 'type':
            if found['kind'].value != 'enum':
                invalid('Type kind must be enum', 'kind')
            values = found['values']
            if not isinstance(values.value, list) or not values.elements:
                invalid('Enum values must be a nonempty array', 'values')
            else:
                seen = {}
                for index, item in enumerate(values.elements):
                    fields.append(self.field('/values/' + str(index), item, span))
                    if not isinstance(item.value, str) or not item.value:
                        self.diagnose('Enum values must be nonempty strings', item, check='declarations')
                    elif item.value in seen:
                        self.diagnose('Duplicate enum value: ' + item.value, item,
                                      previous=seen[item.value], check='declarations')
                    else:
                        seen[item.value] = item
                kwargs['values'] = tuple(item.value for item in values.elements)
        else:
            type_token = found['type']
            try:
                identifier(type_token.value)
            except (ValueError, AttributeError):
                invalid('type must be a valid type name', 'type')
            if kind == 'variable':
                if found['role'].value not in ('input', 'output'):
                    invalid('role must be input or output', 'role')
                kwargs['role'] = found['role'].value
            if type_token.value == 'int':
                for bound in ('min', 'max'):
                    if bound not in found:
                        self.diagnose('int requires ' + bound, token, check='declarations')
                    elif type(found[bound].value) is not int:
                        invalid('int bounds must be integers, not bool', bound)
                if (all(bound in found and type(found[bound].value) is int for bound in ('min', 'max'))
                        and found['min'].value > found['max'].value):
                    self.diagnose('min must not exceed max', found['max'], previous=found['min'], check='declarations')
            elif 'min' in found or 'max' in found:
                for bound in ('min', 'max'):
                    if bound in found:
                        invalid('Bounds are only allowed for int', bound)
            kwargs['minimum'] = found['min'].value if 'min' in found else None
            kwargs['maximum'] = found['max'].value if 'max' in found else None
            if kind == 'constant':
                value = found['value'].value
                expected = bool if type_token.value == 'bool' else int if type_token.value == 'int' else str
                if type(value) is not expected:
                    invalid('Constant literal does not match its declared type', 'value')
                elif (expected is int and all(bound in found and type(found[bound].value) is int
                                             for bound in ('min', 'max'))
                      and not found['min'].value <= value <= found['max'].value):
                    invalid('Constant value is outside its integer bounds', 'value')
                kwargs['value'] = value
        if len(self.diagnostics) != start:
            self.reject(whole, self.diagnostics[start:])
            return
        origins = {field.path: field for field in fields}
        if kind != 'type':
            kwargs['type_ref'] = Reference('type', found['type'].value, origins['/type'])
        if link is not None:
            kwargs['glossary'] = Reference('glossary', link.value, origins['/glossary'])
        self.declarations.append(Declaration(self.key(name.value), span, tuple(fields), kind, **kwargs))

    def freeze(self, token, path, fields, span):
        fields.append(self.field(path, token, span))
        if isinstance(token.value, dict):
            pairs = self.members(token)
            if len({key.value for key, value in pairs}) != len(pairs):
                return None  # The whole entry will be rejected, including this raw object.
            return JsonObject(tuple((key.value, self.freeze(value, path + '/' + _pointer(key.value), fields, span))
                                    for key, value in pairs))
        if isinstance(token.value, list):
            return tuple(self.freeze(value, path + '/' + str(i), fields, span)
                         for i, value in enumerate(token.elements))
        return token.value

    def entry(self, token):
        start = len(self.diagnostics)
        if not isinstance(token.value, dict):
            self.diagnose('Glossary entry must be an object', token)
            self.reject(token, self.diagnostics[start:])
            return
        found = self.object(token, {key.value for key, value in token.members}, ('id', 'kind'))
        if 'id' in found and (not isinstance(found['id'].value, str) or not found['id'].value):
            self.diagnose('Glossary ID must be a nonempty string', found['id'])
        if 'kind' in found and found['kind'].value not in ('term', 'const', 'symbol'):
            self.diagnose('Glossary kind must be term, const or symbol', found['kind'])
        if len(self.diagnostics) != start:
            self.reject(token, self.diagnostics[start:])
            return
        fields, data = [], []
        span = self.span(token)
        for key, value in token.members:
            frozen = self.freeze(value, '/' + _pointer(key.value), fields, span)
            if key.value not in ('id', 'kind'):
                data.append((key.value, frozen))
        if len(self.diagnostics) != start:
            self.reject(token, self.diagnostics[start:])
            return
        self.glossary.append(GlossaryEntry(self.key(found['id'].value), span, tuple(fields),
                                          found['kind'].value, JsonObject(tuple(data))))

    def collect(self, root):
        if not isinstance(root.value, dict):
            self.diagnose('Definition document must be an object', root)
            self.reject(root, self.diagnostics)
            return False
        if self.kind == 'spec':
            versions = [value for key, value in root.members if key.value == 'version']
            if len(versions) != 1 or type(versions[0].value) is not int:
                self.members(root)
                self.diagnose('Exactly one integer version is required', root)
                self.reject(root, self.diagnostics)
                return False
            if versions[0].value != 1:
                self.diagnose('Only definition version 1 is supported', versions[0],
                              code='spec.unsupported-version', category='unsupported')
                self.reject(root, self.diagnostics)
                return False
            allowed = ('version', 'types', 'variables', 'constants')
        else:
            allowed = ('entries',)
        self.members(root)
        present = {key.value for key, value in root.members}
        for field in allowed:
            if field not in present:
                diagnostic = self.diagnose('Missing required field: ' + field, root)
                self.reject(root, (diagnostic,))
        for key, value in root.members:
            if key.value not in allowed:
                diagnostic = self.diagnose('Unknown field: ' + key.value, key)
                self.reject(Token(None, key.start, value.end), (diagnostic,))
            elif key.value == 'version':
                continue
            elif self.kind == 'spec':
                if not isinstance(value.value, dict):
                    diagnostic = self.diagnose(key.value + ' must be an object', value)
                    self.reject(Token(None, key.start, value.end), (diagnostic,))
                    continue
                self.members(value)
                kind = {'types': 'type', 'variables': 'variable', 'constants': 'constant'}[key.value]
                for name, declaration in value.members:
                    self.declaration(name, declaration, kind)
            else:
                if not isinstance(value.value, list):
                    diagnostic = self.diagnose('entries must be an array', value)
                    self.reject(Token(None, key.start, value.end), (diagnostic,))
                    continue
                for entry in value.elements:
                    self.entry(entry)
        seen = {}
        for node in (*self.declarations, *self.glossary):
            name_field = next(field for field in node.fields if field.path == ('/name' if self.kind == 'spec' else '/id'))
            token = Token(None, *self.source.offsets(name_field.location.span))
            if node.key.name in seen:
                self.diagnose('Duplicate declaration: ' + node.key.name, token,
                              code='spec.duplicate-name' if self.kind == 'spec' else 'spec.duplicate-glossary',
                              previous=seen[node.key.name], check='declarations')
            else:
                seen[node.key.name] = token
        return True

    def result(self, *, collected, unavailable=False):
        def check(name):
            categories = self.issues[name]
            if name == 'declarations' and not collected:
                return CheckResult('spec.' + name, 'not-run', 'No interpretable definition document')
            status = ('error' if 'tool-error' in categories else 'failed' if 'user' in categories else
                      'unsupported' if categories else 'passed')
            return CheckResult('spec.' + name, status,
                               None if status == 'passed' else 'See definition diagnostics for this scope')
        checks = AnalysisChecks(check('structure'), check('declarations'),
                                CheckResult('spec.references', 'not-run', 'Workspace resolution belongs to #38'))
        completeness = 'unavailable' if unavailable else 'partial' if self.diagnostics else 'complete'
        return LocalAnalysis(self.source, checks, completeness, declarations=tuple(self.declarations),
                             glossary=tuple(self.glossary), rejected=tuple(self.rejected),
                             diagnostics=tuple(self.diagnostics))


def load_definitions(source: SourceSnapshot, *, kind: Literal['spec', 'glossary'],
                     format: Literal['json', 'yaml', 'yml']) -> LocalAnalysis:
    """Collect one explicitly selected definition snapshot; never resolve names.

    Bad source data is returned as diagnostics/rejected input. API misuse raises
    TypeError/ValueError. JSON does not import PyYAML. No rereads or output occur.
    """
    if not isinstance(source, SourceSnapshot):
        raise TypeError('load_definitions requires an original SourceSnapshot')
    if kind not in ('spec', 'glossary') or format not in ('json', 'yaml', 'yml'):
        raise ValueError('Expected spec/glossary kind and json/yaml/yml format')
    loader = _Loader(source, kind)
    try:
        root = parse_structured_text(source.text, format=format)
    except (JsonError, StructuredTextError) as exc:
        dependency = getattr(exc, 'dependency', None)
        code = ('spec.missing-dependency' if dependency else 'spec.unsupported-syntax'
                if exc.unsupported else loader.code)
        evidence = (Evidence('spec.dependency', dependency),) if dependency else ()
        loader.diagnose(str(exc), None if dependency else Token(None, exc.start, exc.end), code=code,
                        category='unsupported' if exc.unsupported else 'user', evidence=evidence)
        loader.reject(Token(None, 0, len(source.text)), loader.diagnostics)
        return loader.result(collected=False, unavailable=bool(dependency))
    try:
        collected = loader.collect(root)
    except RecursionError:
        # Discard partially constructed nodes rather than claiming completeness.
        loader.declarations.clear()
        loader.glossary.clear()
        diagnostic = loader.diagnose('Definition traversal exceeds capacity', root,
                                     code='spec.unsupported-syntax', category='unsupported')
        loader.reject(root, (diagnostic,))
        collected = False
    loader.remaining_duplicates(root)
    return loader.result(collected=collected)
