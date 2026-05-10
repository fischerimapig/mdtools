"""Tests for the official staged build command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mdtools.build_cli import main
from mdsplit.schema import DocumentTree, SectionNode


def _write_defs(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "id": "unit",
                        "kind": "term",
                        "names": {
                            "en": "Processing Unit",
                            "ja": "プロセッシングユニット",
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_build_from_hierarchy_runs_needed_stages(tmp_path):
    sections_dir = tmp_path / "sections"
    sections_dir.mkdir()
    (sections_dir / "01-title.md").write_text(
        "\n".join(
            [
                "",
                "Shared intro.",
                "",
                "::: {lang=en}",
                "Hello []{.term id=unit}.",
                ":::",
                "",
                "::: {lang=ja}",
                "こんにちは []{.term id=unit}。",
                ":::",
                "",
            ]
        ),
        encoding="utf-8",
    )
    doc = DocumentTree(
        source_file="manuscript.qmd",
        base_level=1,
        sections=[
            SectionNode(title="Title", file="sections/01-title.md", order=0),
        ],
    )
    hierarchy = tmp_path / "hierarchy.json"
    doc.save(hierarchy)

    defs = tmp_path / "defs.json"
    _write_defs(defs)
    out = tmp_path / "out.en.qmd"
    work_dir = tmp_path / "build"

    rc = main([
        str(hierarchy),
        "--lang",
        "en",
        "-f",
        str(defs),
        "-o",
        str(out),
        "--work-dir",
        str(work_dir),
    ])

    assert rc == 0
    result = out.read_text(encoding="utf-8")
    assert "# Title" in result
    assert "Shared intro." in result
    assert "Hello Processing Unit." in result
    assert "こんにちは" not in result
    assert "[]{.term" not in result
    assert "::: {lang=" not in result

    composed = work_dir / "01-compose.qmd"
    filtered = work_dir / "02-langfilter.qmd"
    resolved = work_dir / "03-glossary.qmd"
    assert composed.exists()
    assert filtered.exists()
    assert resolved.exists()
    assert "::: {lang=en}" in composed.read_text(encoding="utf-8")
    assert "[]{.term id=unit}" in filtered.read_text(encoding="utf-8")
    assert "::: {lang=" not in filtered.read_text(encoding="utf-8")
    assert resolved.read_text(encoding="utf-8") == result


def test_build_markdown_input_skips_compose_and_glossary(tmp_path):
    src = tmp_path / "input.md"
    src.write_text(
        "Shared\n\n::: {lang=ja}\n日本語\n:::\n\n::: {lang=en}\nEnglish\n:::\n",
        encoding="utf-8",
    )
    out = tmp_path / "out.md"
    work_dir = tmp_path / "build"

    rc = main([
        str(src),
        "--lang",
        "ja",
        "-o",
        str(out),
        "--work-dir",
        str(work_dir),
    ])

    assert rc == 0
    assert out.read_text(encoding="utf-8") == "Shared\n\n日本語\n\n"
    assert sorted(p.name for p in work_dir.iterdir()) == ["01-langfilter.md"]


def test_build_glossary_requires_language(tmp_path):
    src = tmp_path / "input.md"
    src.write_text("[]{.term id=unit}\n", encoding="utf-8")
    defs = tmp_path / "defs.json"
    _write_defs(defs)

    with pytest.raises(SystemExit) as excinfo:
        main([str(src), "-f", str(defs)])

    assert excinfo.value.code == 2
