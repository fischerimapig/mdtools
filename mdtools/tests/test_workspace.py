"""Workspace registration errors, path boundaries and deterministic selection."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mdtools.workspace import WorkspaceError, load_workspace


def write(path: Path, text: str = "原稿\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def config(root: Path, text: str) -> Path:
    return write(root / "mdtools.toml", text)


def markdown(path: str = "doc.md") -> str:
    return f'[[documents]]\nkind = "markdown"\npath = "{path}"\n'


def hierarchy_config(canonical: str = "doc.md") -> str:
    return ('[[documents]]\nkind = "hierarchy"\npath = "parts/hierarchy.json"\n'
            f'canonical = "{canonical}"\n')


def hierarchy(root: Path, **overrides) -> Path:
    data = {"source_file": "ignored-name.md", "sections": [
        {"title": "本文", "file": "section.md", "order": 0, "children": []},
    ]}
    data.update(overrides)
    write(root / "parts/section.md")
    return write(root / "parts/hierarchy.json", json.dumps(data, ensure_ascii=False))


def error(path: Path, code: str) -> WorkspaceError:
    with pytest.raises(WorkspaceError) as caught:
        load_workspace(path)
    assert caught.value.code == code
    assert code in str(caught.value)
    assert caught.value.path.is_absolute()
    return caught.value


@pytest.mark.parametrize("suffix", ["md", "qmd", "QMD"])
def test_single_document_is_explicit_and_cwd_independent(tmp_path, monkeypatch, suffix):
    source = write(tmp_path / f"doc.{suffix}")
    write(tmp_path / "unregistered.md")
    settings = config(tmp_path, "version = 1\n" + markdown(source.name))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    workspace = load_workspace(settings)
    assert workspace.version == 1
    assert workspace.config_path == settings
    assert workspace.root == tmp_path
    assert workspace.analysis_files == (source,)
    assert workspace.documents[0].tree is None
    assert workspace.definitions == workspace.generated == ()


def test_root_is_relative_to_config_and_registrations_to_root(tmp_path, monkeypatch):
    source = write(tmp_path / "project/doc.md")
    definition = write(tmp_path / "project/shared/defs.yaml", "not parsed at M1 #23")
    settings = config(tmp_path / "settings", 'version = 1\nroot = "../project"\n' + markdown()
                      + '[[definitions]]\nkind = "spec"\npath = "shared/defs.yaml"\n')
    monkeypatch.chdir(tmp_path.parent)
    workspace = load_workspace(settings)
    assert workspace.analysis_files == (source,)
    assert workspace.definitions[0].path == definition
    assert workspace.definitions[0].kind == "spec"


def test_hierarchy_uses_preamble_and_stable_depth_first_compose_order(tmp_path):
    hierarchy(tmp_path, metadata={"front_matter": "---\nreserved: example\n---", "preamble_file": "pre.md"},
              sections=[
                  {"title": "B", "file": "b.md", "order": 1},
                  {"title": "A", "file": "a.qmd", "order": 0, "children": [
                      {"title": "子", "file": "child.md", "order": 0},
                  ]},
                  {"title": "C", "file": "c.md", "order": 1},
              ])
    names = ["parts/pre.md", "parts/a.qmd", "parts/child.md", "parts/b.md", "parts/c.md", "last.md"]
    expected = tuple(write(tmp_path / name) for name in names)
    write(tmp_path / "doc.md", "generated")
    write(tmp_path / "ignored-name.md", "source_file is not a path registration")
    write(tmp_path / "parts/unreferenced.md")
    settings = config(tmp_path, "version = 1\n" + hierarchy_config() + markdown("last.md"))
    first = load_workspace(settings)
    assert first.analysis_files == expected
    assert first == load_workspace(settings)
    assert first.generated == (tmp_path / "doc.md",)
    assert first.documents[0].canonical == tmp_path / "doc.md"
    assert first.documents[0].tree.metadata["front_matter"].startswith("---")
    assert first.documents[0].tree.source_file == "ignored-name.md"


def test_hierarchy_reference_may_use_parent_within_explicit_root(tmp_path):
    hierarchy(tmp_path, metadata={"preamble_file": "../shared.md"})
    shared = write(tmp_path / "shared.md")
    workspace = load_workspace(config(tmp_path, "version = 1\n" + hierarchy_config()))
    assert workspace.analysis_files == (shared, tmp_path / "parts/section.md")
    assert not workspace.generated[0].exists()


def test_definition_roles_order_and_generated_outputs_are_separate(tmp_path):
    source = write(tmp_path / "doc.md")
    defs = [write(tmp_path / name, "contents not loaded") for name in ("display.json", "types.yml")]
    settings = config(tmp_path, 'version = 1\ngenerated = ["build/out.en.md"]\n' + markdown()
                      + '[[definitions]]\nkind = "glossary"\npath = "display.json"\n'
                      + '[[definitions]]\nkind = "spec"\npath = "types.yml"\n')
    workspace = load_workspace(settings)
    assert workspace.analysis_files == (source,)
    assert tuple(d.path for d in workspace.definitions) == tuple(defs)
    assert tuple(d.kind for d in workspace.definitions) == ("glossary", "spec")
    assert workspace.generated == (tmp_path / "build/out.en.md",)
    assert not (tmp_path / "build").exists()  # Loading never writes outputs.


@pytest.mark.parametrize("text,code", [
    ('documents = []', "invalid-config"),
    ('version = 2\ndocuments = []', "unsupported-version"),
    ('version = true\ndocuments = []', "unsupported-version"),
    ('version = "1"\ndocuments = []', "unsupported-version"),
    ('version = 1.0\ndocuments = []', "unsupported-version"),
    ('version = 1\nversion = 1', "invalid-config"),
    ('version = 1\n[', "invalid-config"),
    ('version = 1\nunknown = true\ndocuments = []', "invalid-config"),
    ('version = 1\ndocuments = []', "invalid-config"),
    ('version = 1\ndocuments = {}', "invalid-config"),
    ('version = 1\ndocuments = ["doc.md"]', "invalid-config"),
    ('version = 1\nroot = 1\n' + markdown(), "invalid-config"),
    ('version = 1\n' + markdown().replace('"markdown"', '"guess"'), "invalid-config"),
    ('version = 1\n' + markdown(""), "invalid-config"),
    ('version = 1\n' + markdown() + 'canonical = "out.md"', "invalid-config"),
    ('version = 1\n' + hierarchy_config().replace('canonical = "doc.md"\n', ''), "invalid-config"),
    ('version = 1\n' + markdown() + 'typo = "x"', "invalid-config"),
    ('version = 1\ndefinitions = ["defs.json"]\n' + markdown(), "invalid-config"),
    ('version = 1\n' + markdown() + '[[definitions]]\nkind = "other"\npath = "x.json"', "invalid-config"),
    ('version = 1\ngenerated = "out.md"\n' + markdown(), "invalid-config"),
    ('version = 1\ngenerated = [1]\n' + markdown(), "invalid-config"),
])
def test_invalid_configuration_is_diagnosed(tmp_path, text, code):
    error(config(tmp_path, text), "workspace." + code)


@pytest.mark.parametrize("text,code", [
    ("version = 1\n" + markdown("absent.md"), "missing-file"),
    ("version = 1\nroot = 'missing'\n" + markdown(), "missing-file"),
    ("version = 1\nroot = 'doc.md'\n" + markdown(), "not-directory"),
    ("version = 1\n" + markdown("parts.md"), "not-file"),
    ("version = 1\n" + markdown("other.txt"), "invalid-extension"),
    ("version = 1\n" + markdown("../outside.md"), "outside-root"),
    ("version = 1\ngenerated = ['../out.md']\n" + markdown(), "outside-root"),
    ("version = 1\ngenerated = ['parts.md']\n" + markdown(), "not-file"),
    ("version = 1\n" + hierarchy_config("../out.md"), "outside-root"),
    ("version = 1\n" + hierarchy_config("out.txt"), "invalid-extension"),
    ("version = 1\n" + markdown() + '[[definitions]]\nkind = "spec"\npath = "missing.json"', "missing-file"),
    ("version = 1\n" + markdown() + '[[definitions]]\nkind = "glossary"\npath = "../defs.json"', "outside-root"),
])
def test_invalid_paths_are_diagnosed(tmp_path, text, code):
    write(tmp_path / "doc.md")
    write(tmp_path / "other.txt")
    (tmp_path / "parts.md").mkdir()
    hierarchy(tmp_path)
    error(config(tmp_path, text), "workspace." + code)


@pytest.mark.parametrize("field,value", [
    ("metadata", []), ("metadata", {"preamble_file": 1}),
    ("metadata", {"front_matter": []}), ("source_file", 1),
    ("base_level", True), ("sections", {}), ("sections", [1]),
    ("sections", [{"title": "A", "file": "section.md", "order": "0"}]),
    ("sections", [{"title": "A", "file": "section.md", "order": True}]),
    ("sections", [{"title": "A", "file": "section.md", "order": 0, "children": {}}]),
    ("sections", [{"title": "A", "file": "section.md", "order": 0, "extra": 1}]),
    ("sections", [{"title": "A", "file": ""}]), ("unknown", True),
])
def test_invalid_hierarchy_shapes_do_not_escape_as_python_errors(tmp_path, field, value):
    hierarchy(tmp_path, **{field: value})
    error(config(tmp_path, "version = 1\n" + hierarchy_config()), "workspace.invalid-hierarchy")


@pytest.mark.parametrize("text", ['{"sections": [}', '{"sections": [], "sections": []}', '[]'])
def test_malformed_hierarchy_json(tmp_path, text):
    write(tmp_path / "parts/hierarchy.json", text)
    error(config(tmp_path, "version = 1\n" + hierarchy_config()), "workspace.invalid-hierarchy")


@pytest.mark.parametrize("reference,code", [("absent.md", "missing-file"), ("../../outside.md", "outside-root")])
@pytest.mark.parametrize("role", ["preamble", "section"])
def test_hierarchy_bad_references(tmp_path, reference, code, role):
    if role == "preamble":
        hierarchy(tmp_path, metadata={"preamble_file": reference})
    else:
        hierarchy(tmp_path, sections=[{"title": "A", "file": reference, "order": 0}])
    error(config(tmp_path, "version = 1\n" + hierarchy_config()), "workspace." + code)


@pytest.mark.parametrize("alias", ["doc.md", "./doc.md", "sub/../doc.md", "symlink.md", "hardlink.md"])
def test_duplicate_documents_include_path_symlink_and_hardlink_aliases(tmp_path, alias):
    source = write(tmp_path / "doc.md")
    (tmp_path / "sub").mkdir()
    (tmp_path / "symlink.md").symlink_to(source)
    os.link(source, tmp_path / "hardlink.md")
    settings = config(tmp_path, "version = 1\n" + markdown() + markdown(alias))
    error(settings, "workspace.duplicate-input")


@pytest.mark.parametrize("canonical_exists", [True, False])
@pytest.mark.parametrize("canonical_first", [True, False])
def test_canonical_cannot_be_a_document_in_either_registration_order(tmp_path, canonical_exists, canonical_first):
    hierarchy(tmp_path)
    if canonical_exists:
        write(tmp_path / "doc.md")
    docs = [markdown(), hierarchy_config()]
    if not canonical_first:
        docs.reverse()
    error(config(tmp_path, "version = 1\n" + "".join(docs)), "workspace.generated-input")


def test_generated_alias_cannot_be_a_section(tmp_path):
    hierarchy(tmp_path)
    (tmp_path / "doc.md").symlink_to(tmp_path / "parts/section.md")
    error(config(tmp_path, "version = 1\n" + hierarchy_config()), "workspace.generated-input")


@pytest.mark.parametrize("extra", [
    markdown("parts/section.md"), hierarchy_config("other.md"),
])
def test_repeated_sections_or_hierarchies_are_rejected(tmp_path, extra):
    hierarchy(tmp_path)
    error(config(tmp_path, "version = 1\n" + hierarchy_config() + extra), "workspace.duplicate-input")


def test_repeated_reference_inside_hierarchy_is_not_silently_deduplicated(tmp_path):
    hierarchy(tmp_path, metadata={"preamble_file": "section.md"})
    error(config(tmp_path, "version = 1\n" + hierarchy_config()), "workspace.duplicate-input")


def test_definitions_cannot_be_registered_in_two_roles(tmp_path):
    write(tmp_path / "doc.md")
    write(tmp_path / "defs.json", "{}")
    settings = config(tmp_path, "version = 1\n" + markdown()
                      + '[[definitions]]\nkind = "spec"\npath = "defs.json"\n'
                      + '[[definitions]]\nkind = "glossary"\npath = "defs.json"\n')
    error(settings, "workspace.duplicate-input")


def test_symlink_cannot_escape_root(tmp_path):
    outside = write(tmp_path / "outside.md")
    root = tmp_path / "project"
    root.mkdir()
    (root / "doc.md").symlink_to(outside)
    assert error(config(root, "version = 1\n" + markdown()), "workspace.outside-root").path == outside


def test_missing_config_and_invalid_utf8_are_diagnosed(tmp_path):
    error(tmp_path / "absent.toml", "workspace.missing-file")
    settings = tmp_path / "mdtools.toml"
    settings.write_bytes(b"\xff")
    error(settings, "workspace.invalid-config")


def test_read_error_is_wrapped(tmp_path, monkeypatch):
    settings = config(tmp_path, "version = 1\n" + markdown())

    def denied(*args, **kwargs):
        raise PermissionError("permission denied")

    monkeypatch.setattr(Path, "read_text", denied)
    error(settings, "workspace.read-error")


def test_multiple_hierarchies_do_not_infer_canonical_from_source_file(tmp_path):
    hierarchy(tmp_path / "first")
    hierarchy(tmp_path / "second")
    settings = config(tmp_path, "version = 1\n"
                      + hierarchy_config("first.qmd").replace('"parts/hierarchy.json"', '"first/parts/hierarchy.json"')
                      + hierarchy_config("second.qmd").replace('"parts/hierarchy.json"', '"second/parts/hierarchy.json"'))
    workspace = load_workspace(settings)
    assert workspace.analysis_files == (
        tmp_path / "first/parts/section.md", tmp_path / "second/parts/section.md",
    )
    assert workspace.generated == (tmp_path / "first.qmd", tmp_path / "second.qmd")


def test_repeated_generated_registration_is_rejected_even_before_generation(tmp_path):
    hierarchy(tmp_path)
    error(config(tmp_path, 'version = 1\ngenerated = ["doc.md"]\n' + hierarchy_config()),
          "workspace.duplicate-input")


def test_generated_definition_and_registered_hierarchy_are_not_inputs(tmp_path):
    hierarchy(tmp_path)
    error(config(tmp_path, 'version = 1\ngenerated = ["parts/hierarchy.json"]\n' + hierarchy_config()),
          "workspace.generated-input")


def test_empty_referenced_originals_are_kept_and_metadata_only_tree_is_allowed(tmp_path):
    hierarchy(tmp_path, metadata={"preamble_file": "empty.md"})
    write(tmp_path / "parts/empty.md", "")
    write(tmp_path / "parts/section.md", "")
    settings = config(tmp_path, "version = 1\n" + hierarchy_config())
    assert load_workspace(settings).analysis_files == (
        tmp_path / "parts/empty.md", tmp_path / "parts/section.md",
    )
    hierarchy(tmp_path, metadata={"front_matter": "---\ntitle: Empty\n---"}, sections=[])
    assert load_workspace(settings).analysis_files == ()


def test_hierarchy_symlink_references_are_relative_to_resolved_location(tmp_path):
    hierarchy(tmp_path)
    (tmp_path / "entry.json").symlink_to(tmp_path / "parts/hierarchy.json")
    settings = config(tmp_path, 'version = 1\n' + hierarchy_config().replace('"parts/hierarchy.json"', '"entry.json"'))
    assert load_workspace(settings).analysis_files == (tmp_path / "parts/section.md",)


def test_invalid_path_string_and_symlink_loop_are_diagnosed(tmp_path):
    # TOML escapes decode to a NUL character, which cannot name a filesystem path.
    error(config(tmp_path, 'version = 1\n' + markdown('bad\\u0000.md')), "workspace.invalid-path")
    (tmp_path / "loop.md").symlink_to("loop.md")
    error(config(tmp_path, 'version = 1\n' + markdown('loop.md')), "workspace.invalid-path")


def test_hierarchy_invalid_encoding_and_io_errors_are_diagnosed(tmp_path, monkeypatch):
    tree_path = hierarchy(tmp_path)
    settings = config(tmp_path, "version = 1\n" + hierarchy_config())
    tree_path.write_bytes(b"\xff")
    error(settings, "workspace.invalid-hierarchy")
    read_text = Path.read_text

    def denied(path, *args, **kwargs):
        if path == tree_path:
            raise PermissionError("hierarchy permission denied")
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", denied)
    error(settings, "workspace.read-error")
