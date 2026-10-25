"""Use real M1 examples and existing document pipelines with Workspace selection."""

from pathlib import Path

from mdsplit.compose import compose
from mdsplit.decompose import decompose
from mdtools.build_cli import main as build
from mdtools.workspace import load_workspace


REPO = Path(__file__).resolve().parents[2]


def test_cancellation_workspace_registers_exact_m1_originals(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    workspace = load_workspace(REPO / "docs/spec/examples/cancellation/mdtools.toml")
    assert tuple(p.name for p in workspace.analysis_files) == (
        "cancel-allow.md", "cancel-deny.md", "guidance.md",
    )
    assert [(d.kind, d.path.name) for d in workspace.definitions] == [("spec", "definitions.json")]
    original = workspace.analysis_files[0].read_text(encoding="utf-8")
    assert "lang=en" in original and "lang=ja" in original and "mdspec" in original


def test_sectioned_workspace_matches_compose_order_and_preserves_build_originals(tmp_path):
    text = ('---\ntitle: Test\n---\n\nPreamble 原典\n\n# Title\n\n'
            '::: {lang=en}\nEnglish\n:::\n\n::: {lang=ja}\n日本語\n:::\n\n'
            '## Child\n\nChild original\n')
    canonical = tmp_path / "manual.qmd"
    canonical.write_text(text, encoding="utf-8")
    tree = decompose(canonical, tmp_path / "manuscript")
    settings = tmp_path / "mdtools.toml"
    settings.write_text(
        'version = 1\ngenerated = ["dist/manual.en.qmd"]\n'
        '[[documents]]\nkind = "hierarchy"\npath = "manuscript/hierarchy.json"\n'
        'canonical = "manual.qmd"\n', encoding="utf-8",
    )
    workspace = load_workspace(settings)
    base = tmp_path / "manuscript"
    assert workspace.analysis_files == (
        base / tree.metadata["preamble_file"],
        base / tree.sections[0].file,
        base / tree.sections[0].children[0].file,
    )
    assert workspace.documents[0].tree == tree
    assert compose(base / "hierarchy.json") == text
    before = {p: p.read_bytes() for p in workspace.analysis_files}
    output = tmp_path / "dist/manual.en.qmd"
    output.parent.mkdir()
    assert build([str(base / "hierarchy.json"), "--lang", "en", "-o", str(output)]) == 0
    assert "English" in output.read_text(encoding="utf-8")
    assert "日本語" not in output.read_text(encoding="utf-8")
    assert {p: p.read_bytes() for p in workspace.analysis_files} == before
    assert load_workspace(settings) == workspace
    assert canonical not in workspace.analysis_files and output not in workspace.analysis_files


def test_contract_section_tree_can_be_registered_without_scanning_canonical(tmp_path):
    settings = tmp_path / "mdtools.toml"
    settings.write_text(
        f'version = 1\nroot = "{REPO.as_posix()}"\n'
        '[[documents]]\nkind = "hierarchy"\npath = "docs/spec/contract-v1_sections/hierarchy.json"\n'
        'canonical = "docs/spec/contract-v1.md"\n', encoding="utf-8",
    )
    workspace = load_workspace(settings)
    assert len(workspace.analysis_files) >= 14
    assert all(p.is_relative_to(REPO / "docs/spec/contract-v1_sections") for p in workspace.analysis_files)
    assert (REPO / "docs/spec/contract-v1.md") not in workspace.analysis_files
    assert compose(workspace.documents[0].path) == (REPO / "docs/spec/contract-v1.md").read_text(encoding="utf-8")
