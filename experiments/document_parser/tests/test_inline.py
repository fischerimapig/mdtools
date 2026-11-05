"""Independent source-range checks for the inline prototype."""
import pytest

from mdtools.core.source import SourceSnapshot
from experiments.document_parser.inline import parse_inlines
from experiments.document_parser.links import parse_reference_definition
from experiments.document_parser.model import ByteRange, Limits, SourceIndex


def make(text):
    return SourceIndex(SourceSnapshot("test:inline", text))


@pytest.mark.parametrize("source,kind,target", [
    ('[説明](https://example.com "<!--")', 'link', 'https://example.com'),
    ('![画像](https://example.com/image.png "<!--")', 'image', 'https://example.com/image.png'),
])
def test_comment_like_title_is_literal(source, kind, target):
    """Detect comment openers being consumed inside link and image titles."""
    index = make(source + ' OUTSIDE -->')
    owner = index.byte_range(0, len(source))
    result = parse_inlines(index, owner, (), Limits())
    assert result.complete
    assert len(result.inlines) == 1
    node = result.inlines[0]
    assert node.kind == kind
    assert node.span == ByteRange(0, len(source.encode()))
    assert index.slice(node.target) == target
    assert index.slice(node.title) == '<!--'
    assert all(owner.start <= x.start <= x.end <= owner.end for x in (node.span, node.target, node.title))


def test_reference_definition_and_first_resolution():
    """Detect lost comment-like titles, normalization, and duplicate resolution."""
    text = '[説明][ ReF ]\n[ref]: https://example.com "<!--"\n[REF]: /later\n'
    index = make(text)
    lines = index.lines
    refs = tuple(parse_reference_definition(index, line.start, line.end) for line in lines[1:])
    assert refs[0].label == 'ref'
    assert index.slice(refs[0].destination) == 'https://example.com'
    assert index.slice(refs[0].title) == '<!--'
    owner = index.byte_range(lines[0].start, lines[0].content_end)
    result = parse_inlines(index, owner, refs, Limits())
    node = result.inlines[0]
    assert node.kind == 'link' and node.reference == 'ref'
    assert node.target == refs[0].destination and node.title == refs[0].title
    assert node.span == owner
    assert refs[0].span.end <= index.byte_length


@pytest.mark.parametrize('delimiter', ['"', "'", '('])
def test_definition_title_delimiters(delimiter):
    """Detect missing supported title forms while retaining exact content."""
    close = ')' if delimiter == '(' else delimiter
    text = f'[A]: <dest> {delimiter}literal{close}\n'
    index = make(text)
    ref = parse_reference_definition(index, 0, len(text))
    assert ref.label == 'a'
    assert index.slice(ref.destination) == 'dest'
    assert index.slice(ref.title) == 'literal'


def test_code_comment_html_and_escape():
    """Detect false comments inside code and quoted HTML, and escaped delimiters."""
    text = '`<!--` <!-- real --> <a title="<!-- >"> \\[x]'
    index = make(text)
    result = parse_inlines(index, index.byte_range(0, len(text)), (), Limits())
    assert [(n.kind, index.slice(n.span)) for n in result.inlines if n.kind != 'text'] == [
        ('code', '`<!--`'), ('html_comment', '<!-- real -->'),
        ('html', '<a title="<!-- >">'), ('escape', '\\[')]


def test_lookahead_stays_within_owner():
    """Detect a closing delimiter outside a leaf changing its inline parse."""
    text = '[x](url "<!--' + '")'
    index = make(text)
    owner = index.byte_range(0, len(text) - 2)
    result = parse_inlines(index, owner, (), Limits())
    assert result.complete
    assert all(n.kind != 'link' and n.span.end <= owner.end for n in result.inlines)


def test_limits_are_explicit():
    """Detect an inline limit being reported as an empty successful parse."""
    index = make('abcdef')
    result = parse_inlines(index, index.byte_range(0, 6), (), Limits(max_inline_chars=3))
    assert not result.complete and result.notices[0].code == 'inline-limit'


def test_code_backslash_does_not_escape_closing_backtick():
    """Detect backslash incorrectly hiding a code span's closing delimiter."""
    index = make('`a\\` after')
    result = parse_inlines(index, index.byte_range(0, len(index.source.text)), (), Limits())
    assert result.complete
    assert [(n.kind, index.slice(n.span)) for n in result.inlines] == [('code', '`a\\`'), ('text', ' after')]


def test_node_limit_after_plain_text():
    """Detect flush followed by emit exceeding the configured node budget."""
    index = make('plain `code` tail')
    result = parse_inlines(index, index.byte_range(0, len(index.source.text)), (), Limits(max_nodes=1))
    assert len(result.inlines) == 1 and index.slice(result.inlines[0].span) == 'plain '
    assert not result.complete and result.notices[0].code == 'inline-node-limit'
    assert index.slice(result.notices[0].span) == '`code` tail'


def test_many_non_candidates_and_links_fit_work_budget():
    """Detect charging the remaining leaf for ordinary less-than signs or absent titles."""
    text = ('< ' * 200) + ('[x](/url ) ' * 200)
    index = make(text)
    result = parse_inlines(index, index.byte_range(0, len(text)), (), Limits())
    assert result.complete
    assert sum(n.kind == 'link' for n in result.inlines) == 200


def test_reference_lookup_is_reusable_mapping():
    """Detect lookup reconstruction and preserve first-definition resolution."""
    from collections.abc import Mapping
    from experiments.document_parser.links import build_reference_lookup
    text = '[a]: /first\n[a]: /second\n[a]'
    index = make(text)
    refs = tuple(parse_reference_definition(index, line.start, line.end) for line in index.lines[:2])
    lookup = build_reference_lookup(refs)
    class Lookup(Mapping):
        def __getitem__(self, key): return lookup[key]
        def __iter__(self): raise AssertionError('mapping must not be rebuilt')
        def __len__(self): return len(lookup)
    result = parse_inlines(index, index.byte_range(index.lines[2].start, index.lines[2].end), Lookup(), Limits())
    assert result.complete and index.slice(result.inlines[0].target) == '/first'


def test_nested_brackets_stop_before_unbounded_label_copies(monkeypatch):
    """Detect normalizing a label after the cumulative work budget is exhausted."""
    import experiments.document_parser.inline as inline
    original = inline.normalize_label
    sizes = []
    def record(label):
        sizes.append(len(label))
        return original(label)
    monkeypatch.setattr(inline, 'normalize_label', record)
    text = '[' * 1000 + ']' * 1000
    index = make(text)
    result = parse_inlines(index, index.byte_range(0, len(text)), (), Limits())
    assert not result.complete and result.notices[0].code == 'inline-work-limit'
    assert sum(sizes) <= len(text) * 8


def test_code_span_brackets_do_not_close_link_label():
    """Detect a closing bracket inside code taking ownership of a link label."""
    text = '[a `]` b](/url) and \\[not a link]'
    index = make(text)
    result = parse_inlines(index, index.byte_range(0, len(text)), (), Limits())
    assert result.complete
    assert result.inlines[0].kind == 'link'
    assert index.slice(result.inlines[0].span) == '[a `]` b](/url)'
    assert index.slice(result.inlines[0].target) == '/url'
    assert any(n.kind == 'escape' and index.slice(n.span) == '\\[' for n in result.inlines)


@pytest.mark.parametrize('text,title_text', [('[x]()', None), ('[x]( "title")', 'title')])
def test_empty_link_destination(text, title_text):
    """Detect empty destinations and their optional quoted title being lost."""
    index = make(text)
    result = parse_inlines(index, index.byte_range(0, len(text)), (), Limits())
    assert result.complete and len(result.inlines) == 1
    item = result.inlines[0]
    assert item.kind == 'link' and index.slice(item.span) == text
    assert item.target.start == item.target.end and index.slice(item.target) == ''
    assert (index.slice(item.title) if item.title else None) == title_text
