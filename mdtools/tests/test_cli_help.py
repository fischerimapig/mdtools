"""Tests for mdtools CLI help routing and text."""

from __future__ import annotations

import pytest

from langfilter.cli import main as langfilter_main
from mdsplit.cli import main as mdsplit_main
from mdtools.main import main as mdtools_main


def _help_output(capsys: pytest.CaptureFixture[str], func, argv, **kwargs) -> str:
    with pytest.raises(SystemExit) as excinfo:
        func(argv, **kwargs)
    assert excinfo.value.code == 0
    return capsys.readouterr().out


def test_mdtools_top_help_prefers_unified_entrypoint(capsys):
    out = _help_output(capsys, mdtools_main, ["--help"])

    assert "通常は mdtools <tool> から使います" in out
    assert "例: mdtools mdsplit decompose --help" in out
    assert "mdsplit / langfilter / mdhtml-rewrite / glossary" in out
    assert "rewrite" in out
    assert "mdhtml-rewrite" in out
    assert "mdtools mdsplit split --help" not in out


@pytest.mark.parametrize(
    ("argv", "usage", "example"),
    [
        (["mdsplit", "--help"], "usage: mdtools mdsplit", "mdtools mdsplit decompose manuscript.qmd"),
        (["langfilter", "--help"], "usage: mdtools langfilter", "mdtools langfilter filter manuscript.qmd"),
        (["rewrite", "--help"], "usage: mdtools rewrite", "mdtools rewrite inventory input.md"),
        (["glossary", "--help"], "usage: mdtools glossary", "mdtools glossary resolve manuscript.md"),
    ],
)
def test_mdtools_delegated_help_uses_unified_prog(capsys, argv, usage, example):
    out = _help_output(capsys, mdtools_main, argv)

    assert usage in out
    assert example in out
    assert "README 原典:" in out


def test_direct_mdsplit_help_keeps_individual_prog(capsys):
    out = _help_output(capsys, mdsplit_main, ["--help"])

    assert "usage: mdsplit" in out
    assert "usage: mdtools mdsplit" not in out
    assert "mdsplit decompose manuscript.qmd" in out


def test_mdtools_delegated_subcommand_help_keeps_full_prog(capsys):
    out = _help_output(capsys, mdtools_main, ["mdsplit", "decompose", "--help"])

    assert "usage: mdtools mdsplit decompose" in out
    assert "入力 Markdown/QMD ファイル" in out


def test_langfilter_help_documents_current_fenced_div_edges(capsys):
    out = _help_output(capsys, langfilter_main, ["--help"], prog="mdtools langfilter")

    assert "::: {.note lang=en}" in out
    assert "trailing text" in out
    assert "通常行として残ります" in out
