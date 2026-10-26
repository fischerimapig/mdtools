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


@pytest.mark.parametrize('flags,message', [
    (['--base-level', '2'], '--base-level can only be used when INPUT is hierarchy.json'),
    (['--keep-lang-fences'], '--keep-lang-fences requires --lang en or --lang ja'),
    (['-f', 'defs.json'], '-f/--defs requires --lang en or --lang ja'),
])
def test_build_argument_errors_precede_stdin_read(flags, message, monkeypatch, capsys):
    import sys

    class UnreadableInput:
        def read(self):
            raise AssertionError('invalid arguments must not read stdin')

    monkeypatch.setattr(sys, 'stdin', UnreadableInput())
    with pytest.raises(SystemExit) as exc:
        main(['-', *flags])
    assert exc.value.code == 2
    out, err = capsys.readouterr()
    assert out == ''
    assert err.startswith('usage: mdtools build ')
    assert err.endswith(f'mdtools build: error: {message}\n')


def test_build_stdin_stdout_and_warnings_are_unchanged(tmp_path, monkeypatch, capsys):
    import io
    import sys

    defs = tmp_path / 'defs.json'
    _write_defs(defs)
    monkeypatch.setattr(sys, 'stdin', io.StringIO('[]{.term id=unit} []{.term id=absent}\n'))
    assert main(['-', '--lang', 'en', '-f', str(defs), '--on-missing', 'warn']) == 0
    assert capsys.readouterr() == ('Processing Unit []{.term id=absent}\n', "warning: undefined id 'absent' in marker '[]{.term id=absent}'\n")


def test_build_missing_definition_keeps_exit_2(tmp_path, capsys):
    source = tmp_path / 'source.md'
    source.write_text('Body\n')
    defs = tmp_path / 'absent.json'
    out = tmp_path / 'out.md'
    assert main([str(source), '--lang', 'en', '-f', str(defs), '-o', str(out)]) == 2
    assert capsys.readouterr() == ('', f'mdtools build: Definition file not found: {defs}\n')
    assert not out.exists()


def test_build_resolve_error_keeps_exit_1_and_final_output(tmp_path, capsys):
    source = tmp_path / 'source.md'
    source.write_text('[]{.term id=absent}\n')
    defs = tmp_path / 'defs.json'
    _write_defs(defs)
    out = tmp_path / 'out.md'
    out.write_text('previous output')
    assert main([str(source), '--lang', 'en', '-f', str(defs), '-o', str(out)]) == 1
    assert capsys.readouterr() == ('', "mdtools build: glossary resolve failed: undefined id 'absent' referenced by marker '[]{.term id=absent}'\n")
    assert out.read_text() == 'previous output'


@pytest.mark.parametrize('failure', ['read', 'stage', 'write'])
def test_build_io_failures_keep_exit_1(failure, tmp_path, capsys):
    source = tmp_path / 'source.md'
    if failure != 'read':
        source.write_text('Body\n')
    argv = [str(source)]
    if failure == 'stage':
        blocker = tmp_path / 'blocker'
        blocker.write_text('not a directory')
        argv += ['--work-dir', str(blocker), '--lang', 'en']
    if failure == 'write':
        argv += ['-o', str(tmp_path / 'absent/out.md')]
    assert main(argv) == 1
    out, err = capsys.readouterr()
    assert out == ''
    assert err.startswith('mdtools build: [Errno ')
    assert str(tmp_path) in err


def test_build_duplicate_glossary_keeps_warning_and_override(tmp_path, capsys):
    source = tmp_path / 'source.md'
    source.write_text('[]{.term id=unit}')
    first, second = tmp_path / 'first.json', tmp_path / 'second.json'
    _write_defs(first)
    _write_defs(second)
    second.write_text(second.read_text().replace('Processing Unit', 'Override'))
    assert main([str(source), '--lang', 'en', '-f', str(first), '-f', str(second)]) == 0
    assert capsys.readouterr() == ('Override', f"warning: id 'unit' in {second} overrides earlier definition from {first}\n")


def test_build_work_directory_error_precedes_stdin_read(tmp_path, monkeypatch, capsys):
    import sys

    class UnreadableInput:
        def read(self):
            raise AssertionError('work-directory setup must precede stdin read')

    monkeypatch.setattr(sys, 'stdin', UnreadableInput())
    blocker = tmp_path / 'blocker'
    blocker.write_text('not a directory')
    assert main(['-', '--work-dir', str(blocker)]) == 1
    out, err = capsys.readouterr()
    assert out == ''
    assert err.startswith('mdtools build: [Errno ')


def test_build_input_probe_error_is_not_reclassified_as_argument_error(tmp_path, capsys):
    source = tmp_path / 'source.json'
    source.write_bytes(b'\xff')
    # The legacy auto probe propagates this content error before stage setup.
    with pytest.raises(UnicodeDecodeError):
        main([str(source)])
    assert capsys.readouterr() == ('', '')
