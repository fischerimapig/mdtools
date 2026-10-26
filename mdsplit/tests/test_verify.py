"""Legacy existence checks stay distinct from strict Workspace registration."""

import pytest

from mdtools.core.io import StructuredFileError
from mdsplit.cli import main
from mdsplit.schema import DocumentTree, SectionNode
from mdsplit.verify import VerificationResult, verify


def test_verify_returns_missing_in_stored_order_with_duplicates_and_preamble(tmp_path, capsys):
    hierarchy = tmp_path / 'hierarchy.json'
    DocumentTree('source.md', metadata={'preamble_file': 'preamble.md'}, sections=[
        SectionNode('Second', 'second.md', 2, [SectionNode('Child', 'child.md', 0)]),
        SectionNode('First', 'second.md', 0),
    ]).save(hierarchy)
    assert verify(hierarchy) == VerificationResult(3, ('second.md', 'child.md', 'second.md', 'preamble.md'))
    assert capsys.readouterr() == ('', '')
    assert main(['verify', str(hierarchy)]) == 1
    assert capsys.readouterr() == ('Missing 4 file(s):\n  - second.md\n  - child.md\n  - second.md\n  - preamble.md\n', '')


def test_verify_counts_sections_only_and_keeps_exists_semantics(tmp_path, capsys):
    (tmp_path / 'directory').mkdir()
    (tmp_path / 'preamble.md').write_text('')
    hierarchy = tmp_path / 'hierarchy.json'
    DocumentTree('source.md', metadata={'preamble_file': 'preamble.md'},
                 sections=[SectionNode('Directory', 'directory', 0)]).save(hierarchy)
    assert verify(hierarchy) == VerificationResult(1, ())
    assert main(['verify', str(hierarchy)]) == 0
    assert capsys.readouterr() == ('All 1 section files verified OK.\n', '')


def test_verify_empty_tree(tmp_path, capsys):
    hierarchy = tmp_path / 'hierarchy.json'
    DocumentTree('source.md').save(hierarchy)
    assert verify(hierarchy) == VerificationResult(0, ())
    assert main(['verify', str(hierarchy)]) == 0
    assert capsys.readouterr() == ('All 0 section files verified OK.\n', '')


def test_verify_preserves_loading_errors(tmp_path):
    hierarchy = tmp_path / 'missing.json'
    with pytest.raises(OSError):
        verify(hierarchy)
    hierarchy.write_text('{')
    with pytest.raises(StructuredFileError):
        verify(hierarchy)
