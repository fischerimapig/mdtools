"""Independent boundaries and lossless ownership assertions for block parsing."""
import pytest

from mdtools.core.source import SourceSnapshot
from experiments.document_parser.blocks import parse_blocks
from experiments.document_parser.model import (
    ByteRange, DocumentParse, Limits, SourceIndex, validate_document,
)


def parse(text, limits=Limits()):
    index = SourceIndex(SourceSnapshot("memory:blocks", text))
    result = parse_blocks(index, limits)
    validate_document(DocumentParse(index, result.blocks, result.references,
                                    result.notices, result.coverage, result.status))
    return index, result


def test_small_div_preserves_bytes_attributes_and_nested_ownership():
    """Detect lost duplicate attributes, Unicode byte drift and nested boundary theft."""
    source = '::: {.note #日本 x="a b" x=c}\r\n本文\r\n::: {lang=en}\r\nx\r\n:::\r\n:::\r\n'
    index, result = parse(source)
    outer, = result.blocks
    assert result.status == "complete"
    assert outer.header == ByteRange(0, 33)
    assert [(a.kind, a.name, a.value) for a in outer.attributes] == [
        ("class", "note", "note"), ("id", "日本", "日本"),
        ("attribute", "x", "a b"), ("attribute", "x", "c")]
    assert [n.kind for n in outer.children] == ["paragraph", "div"]
    assert outer.children[0].span == ByteRange(33, 41)
    assert index.slice(outer.children[1].body) == "x\r\n"
    assert index.slice(outer.closing) == ":::\r\n"


def test_paragraph_heading_blank_and_comment_state_are_independent():
    """Detect inline comment state incorrectly swallowing subsequent Div boundaries."""
    index, result = parse("one <!--\ntwo\n# Heading\n\n::: {.box}\nx\n:::\n")
    assert [n.kind for n in result.blocks] == ["paragraph", "heading", "blank", "div"]
    assert index.slice(result.blocks[0].body) == "one <!--\ntwo\n"
    assert result.blocks[3].closure == "closed"


@pytest.mark.parametrize("opener, false_closes, close", [
    ("````lang", "```\n~~~~\n```` trailing\n", "`````  \t"),
    ("~~~", "```\n~~\n~~~ trailing\n", "~~~~"),
    ("```mdspec`", "", "```"),
])
def test_code_fences_require_symbol_length_and_blank_suffix(opener, false_closes, close):
    """Detect premature fence closure and consumer-specific info validation."""
    index, result = parse(opener + "\n::: {.hidden}\n" + false_closes + close + "\n# next\n")
    code, heading = result.blocks
    assert code.kind == "code_fence" and code.closure == "closed"
    assert index.slice(code.body) == "::: {.hidden}\n" + false_closes
    assert code.info == opener.lstrip("`~")
    assert heading.kind == "heading"
    if opener == "```mdspec`":
        assert not code.valid and result.status == "partial"
        assert [n.code for n in result.notices] == ["block.invalid-fence-info"]
    else:
        assert code.valid and result.status == "complete"


@pytest.mark.parametrize("prefix, kind", [
    ("<!--\n::: {.hidden}\n-->\n", "html_comment"),
    ('  <PRE\nclass="x">\n::: {.hidden}\n</PRE>\n', "pre"),
    ("---\n::: {.hidden}\n...\n", "front_matter"),
    ("    ::: {.hidden}\n\t:::\n", "indented_code"),
])
def test_literal_blocks_do_not_expose_child_markers(prefix, kind):
    """Detect structural extraction from examples and multiline literal regions."""
    _, result = parse(prefix + "::: {.real}\n:::\n")
    assert [n.kind for n in result.blocks] == [kind, "div"]
    assert result.blocks[0].children == () and result.blocks[1].valid


@pytest.mark.parametrize("source, kind", [("```\nx\n", "code_fence"), ("<!--\nx\n", "html_comment"), ("<pre>\nx\n", "pre")])
def test_literal_eof_is_complete_but_unclosed_div_is_partial(source, kind):
    """Detect conflation of valid literal EOF termination with malformed Div nesting."""
    _, literal = parse(source)
    assert literal.status == "complete" and literal.blocks[0].kind == kind
    assert literal.blocks[0].closure == "eof"
    _, div = parse("::: {.x}\nx\n")
    assert div.status == "partial" and div.blocks[0].valid
    assert div.blocks[0].closure == "eof"
    assert [n.code for n in div.notices] == ["block.unclosed-div"]


def test_invalid_div_candidates_keep_raw_and_do_not_close_parent():
    """Detect silent loss of malformed headers and four-colon closure recovery."""
    index, result = parse('::: {.x broken}\nx\n::::\n')
    node, = result.blocks
    assert not node.valid and node.closure == "eof"
    assert [(a.kind, a.value) for a in node.attributes] == [("class", "x"), ("invalid", "broken")]
    assert [n.kind for n in node.children] == ["paragraph", "invalid_closure"]
    assert index.slice(node.children[-1].span) == "::::\n"
    assert {n.code for n in result.notices} == {"block.invalid-header", "block.invalid-closure", "block.unclosed-div"}


def test_trailing_header_comment_is_explicit_invalid_candidate():
    """Keep the compatibility question visible instead of silently discarding suffix text."""
    index, result = parse("::: {.box} <!-- note -->\nx\n:::\n")
    node, = result.blocks
    assert not node.valid and node.closure == "closed" and result.status == "partial"
    assert index.slice(node.header) == "::: {.box} <!-- note -->\n"


def test_closed_front_matter_only_and_unsupported_container_retention():
    """Detect speculative YAML EOF ownership and false success for ambiguous list content."""
    index, result = parse("---\nplain\n\n- item\n  ::: {.ambiguous}\n  :::\n\n# safe\n")
    assert result.blocks[0].kind == "paragraph"
    unsupported = result.blocks[2]
    assert unsupported.kind == "unsupported"
    assert index.slice(unsupported.span) == "- item\n  ::: {.ambiguous}\n  :::\n"
    assert result.status == "partial"
    assert [c.state for c in result.coverage] == ["recognized", "recognized", "unsupported", "recognized", "recognized"]


def test_reference_definitions_are_collected_in_order_outside_literals():
    """Detect dropped duplicate definitions and reference collection inside code examples."""
    index, result = parse('[A]: /first "one"\n```\n[A]: /hidden\n```\n[a]: /last\n')
    assert [r.label for r in result.references] == ["a", "a"]
    assert [index.slice(r.destination) for r in result.references] == ["/first", "/last"]
    assert [n.kind for n in result.blocks] == ["reference_definition", "code_fence", "reference_definition"]


@pytest.mark.parametrize("limits, code", [(Limits(max_nodes=1), "limit.nodes"), (Limits(max_depth=1), "limit.depth")])
def test_limits_leave_remaining_source_unparsed(limits, code):
    """Detect success or missing bytes when bounded parsing stops inside a Div."""
    index, result = parse("::: {.x}\n::: {.y}\nx\n:::\n:::\n", limits)
    assert result.status == "partial" and result.blocks[0].closure == "limit"
    assert result.coverage[-1].state == "unparsed"
    assert index.slice(result.coverage[-1].span) == "::: {.y}\nx\n:::\n:::\n"
    assert result.notices[-1].code == code


def test_node_budget_allows_existing_div_to_close_without_creating_node():
    """Detect counting a closing delimiter as an extra tree node."""
    _, result = parse("::: {.x}\n:::\n", Limits(max_nodes=1))
    assert result.status == "complete" and result.blocks[0].closure == "closed"


def test_source_limit_rejects_with_full_unparsed_partition():
    """Detect silent empty success on oversized multibyte input."""
    _, result = parse("日本", Limits(max_bytes=5))
    assert result.status == "rejected" and result.blocks == ()
    assert result.coverage[0].span == ByteRange(0, 6)
    assert result.coverage[0].state == "unparsed"


def test_setext_heading_ends_before_following_div_and_html_stops_paragraph():
    """Detect paragraph continuation through setext boundaries or opaque HTML starts."""
    index, result = parse("title\n===\n::: {.box}\n:::\nparagraph\n<script>\n::: {.hidden}\n\n")
    assert [n.kind for n in result.blocks] == ["heading", "div", "paragraph", "unsupported"]
    assert index.slice(result.blocks[0].span) == "title\n===\n"
    assert index.slice(result.blocks[3].span) == "<script>\n::: {.hidden}\n\n"
    assert result.blocks[3].closure == "eof"


@pytest.mark.parametrize("header, expected, valid", [
    ('::: {.requirement #REQ-A spec-version=1} trailing', [("class", "requirement"), ("id", "REQ-A"), ("attribute", "1")], False),
    ('::: {.requirement #REQ-A spec-version=1', [("class", "requirement"), ("id", "REQ-A"), ("attribute", "1")], False),
    ('::: .requirement #REQ-A broken', [("class", "requirement"), ("id", "REQ-A"), ("invalid", "broken")], False),
    ('::: {.box value="a}b" next=c} suffix', [("class", "box"), ("attribute", "a}b"), ("attribute", "c")], False),
    ('::: {.box value="a}b" next=c}', [("class", "box"), ("attribute", "a}b"), ("attribute", "c")], True),
])
def test_malformed_headers_retain_all_attribute_occurrences(header, expected, valid):
    """Detect lost recoverable tokens and incorrect brace termination inside quotes."""
    index, result = parse(header + "\nbody\n:::\n")
    node, = result.blocks
    assert [(a.kind, a.value) for a in node.attributes] == expected
    assert node.valid is valid and node.closure == "closed"
    assert index.slice(node.header) == header + "\n"
    assert result.status == ("complete" if valid else "partial")


def test_front_matter_trailing_closer_space_and_tab_stop_indentation():
    """Detect premature front matter escape and character-count based code indentation."""
    index, result = parse("---\n::: {.hidden}\n...  \t\n \t::: {.also-hidden}\n \t:::\n::: {.real}\n:::\n")
    assert [n.kind for n in result.blocks] == ["front_matter", "indented_code", "div"]
    assert index.slice(result.blocks[0].closing) == "...  \t\n"
    assert index.slice(result.blocks[1].span) == " \t::: {.also-hidden}\n \t:::\n"
    assert result.status == "complete"


@pytest.mark.parametrize("tag", ["script", "style", "textarea"])
def test_unsupported_raw_html_keeps_blank_lines_until_explicit_closure(tag):
    """Detect hidden Div leakage after blank lines inside unknown raw-text HTML."""
    prefix = f'<{tag}>\n\n::: {{.hidden}}\n:::\n</{tag}>\n'
    index, result = parse(prefix + "::: {.real}\n:::\n")
    assert [n.kind for n in result.blocks] == ["unsupported", "div"]
    assert index.slice(result.blocks[0].span) == prefix
    assert result.blocks[0].closure == "closed" and result.status == "partial"
    assert result.blocks[1].attributes[0].value == "real"


def test_multiline_inline_attributes_without_block_starts_remain_one_leaf():
    """Keep ordinary multiline attributes available to the leaf-owned inline parser."""
    prefix = '<span title="first\ncontinued">text</span>\n'
    index, result = parse(prefix + "::: {.real}\n:::\n")
    assert [n.kind for n in result.blocks] == ["paragraph", "div"]
    assert index.slice(result.blocks[0].body) == prefix
    assert result.status == "complete"


@pytest.mark.parametrize("boundary, expected_kinds", [
    ("\n", ["paragraph", "blank", "paragraph", "div"]),
    ("# Heading\n", ["paragraph", "heading", "paragraph", "div"]),
    ("::: {.middle}\n:::\n", ["paragraph", "div", "paragraph", "div"]),
])
def test_inline_quote_cannot_consume_independent_block_boundaries(boundary, expected_kinds):
    """Detect an inline HTML quote moving Block ownership over blank, heading or Div."""
    index, result = parse('<span title="first\n' + boundary + 'last">text</span>\n::: {.real}\n:::\n')
    assert [n.kind for n in result.blocks] == expected_kinds
    assert index.slice(result.blocks[0].body) == '<span title="first\n'
    assert result.blocks[-1].attributes[0].value == "real"
    assert result.blocks[-1].closure == "closed"
    if expected_kinds[1] == "div":
        assert result.blocks[1].attributes[0].value == "middle"
        assert result.blocks[1].closure == "closed"
    assert result.status == "complete"


@pytest.mark.parametrize("definition", [
    '[a]: /url\n "title"\n',
    '[a]: /url\n \'title\'\n',
    '[a]: /url\n (title)\n',
    '[a]:\n /url\n',
    '[a]:\n /url\n "title"\n',
])
def test_multiline_reference_candidates_are_unsupported_and_do_not_resolve(definition):
    """Detect false complete status or missing titles resolving unsupported definitions."""
    from experiments.document_parser.parser import parse_document

    text = '[a] [ok]\n\n' + definition + '::: {.real}\n:::\n[ok]: /good\n'
    document = parse_document(SourceSnapshot("memory:multiref", text))
    validate_document(document)
    assert document.status == "partial"
    assert [r.label for r in document.references] == ["ok"]
    unsupported = [n for n in document.blocks if n.kind == "unsupported"]
    assert len(unsupported) == 1
    assert document.slice(unsupported[0].span) == definition
    assert any(c.state == "unsupported" and c.span == unsupported[0].span for c in document.coverage)
    assert [n.code for n in document.notices] == ["block.unsupported-reference"]
    div = next(n for n in document.blocks if n.kind == "div")
    assert div.attributes[0].value == "real" and div.closure == "closed"
    links = [item for item in document.blocks[0].inlines if item.kind == "link"]
    assert len(links) == 1 and links[0].reference == "ok"
    assert document.slice(links[0].target) == "/good"
    assert any(item.kind == "text" and "[a]" in document.slice(item.span)
               for item in document.blocks[0].inlines)


def test_multiline_reference_probe_stops_at_blank_and_independent_div():
    """Prevent unsupported-reference recovery from swallowing unrelated later blocks."""
    index, result = parse('[a]: /url\n\n"ordinary"\n::: {.one}\n:::\n[b]:\n::: {.two}\n:::\n')
    assert result.status == "complete"
    assert [r.label for r in result.references] == ["a"]
    assert [n.attributes[0].value for n in result.blocks if n.kind == "div"] == ["one", "two"]
    assert not any(n.kind == "unsupported" for n in result.blocks)
    assert index.slice(result.blocks[0].span) == '[a]: /url\n'
