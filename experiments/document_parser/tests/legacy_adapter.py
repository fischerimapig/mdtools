"""Test-only observation of the frozen M2 baseline; never a parser fallback."""
from mdtools.core.source import SourceSnapshot
from mdtools.spec import _markdown as md
from mdtools.spec.parser import parse_requirements, _reserved

BASELINE_SHA = 'b11368128d4e2a476f2204af40bdfdc947f1cc88'


def observe(text):
    source = SourceSnapshot('memory:corpus', text)
    result = parse_requirements(source)
    def span(a, b):
        return [len(text[:a].encode('utf-8')), len(text[:b].encode('utf-8'))]
    def original(s):
        return span(source.offset(s.start), source.offset(s.end))
    retained = {tuple(original(r.span)): r for r in result.requirements}
    candidates = []
    pending = list(reversed(md.scan(text)))
    while pending:
        block = pending.pop()
        if not isinstance(block, md.Div):
            continue
        if not _reserved(block, text):
            pending.extend(reversed(block.children))
            continue
        ids = [t.value for t in block.attrs if t.kind == 'id']
        item = dict(id=ids[0] if ids else None, ids=ids, span=span(block.start, block.end),
                    header_valid=block.valid, closure='closed' if block.closed else 'eof', bodies=[], mdspec=[])
        requirement = retained.get(tuple(item['span']))
        if requirement:
            item['bodies'] = [dict(language=b.language, span=original(b.span), text=b.text) for b in requirement.bodies]
        else:
            bodies = []
            todo = [(c, None, True) for c in reversed(block.children)]
            while todo:
                child, language, direct = todo.pop()
                if isinstance(child, md.Div):
                    lang = next((t.value for t in child.attrs if t.name == 'lang'), language)
                    todo.extend((c, lang, False) for c in reversed(child.children))
                elif not (isinstance(child, md.Code) and child.info.startswith('mdspec')):
                    if bodies and bodies[-1][0] == language and bodies[-1][2] == child.start:
                        bodies[-1] = (language, bodies[-1][1], child.end)
                    else:
                        bodies.append((language, child.start, child.end))
            item['bodies'] = [dict(language=lang, span=span(a,b), text=text[a:b]) for lang,a,b in bodies if text[a:b].strip()]
        todo = [(c, True) for c in reversed(block.children)]
        while todo:
            child, direct = todo.pop()
            if isinstance(child, md.Div):
                todo.extend((c, False) for c in reversed(child.children))
            elif isinstance(child, md.Code) and child.info.startswith('mdspec'):
                item['mdspec'].append(dict(span=span(child.start,child.end), body=span(child.body_start,child.body_end), info=child.info, direct=direct, closure='closed' if child.closed else 'eof'))
        candidates.append(item)
    def location(value):
        return dict(kind=value.kind, span=original(value.span) if value.span else None,
                    reason=value.reason)
    diagnostics = [dict(code=d.code, severity=d.severity, category=d.category,
                        message=d.message, primary=location(d.primary),
                        related=[dict(message=r.message, location=location(r.location)) for r in d.related],
                        requirement_id=d.requirement_id) for d in result.diagnostics]
    return dict(candidates=candidates, public=dict(
        ids=[r.key.name for r in result.requirements], completeness=result.completeness,
        diagnostics=diagnostics,
        rejected=[dict(kind=r.kind, span=original(r.span), text=r.text,
                       diagnostic_codes=list(r.diagnostic_codes)) for r in result.rejected]))
