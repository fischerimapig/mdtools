"""Tests for glossary.cli."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from glossary.cli import main


FIXTURES = Path(__file__).parent / "fixtures"


def test_resolve_reads_stdin_writes_stdout(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("[]{.term id=unit}\n"))
    rc = main(["resolve", "--lang", "en", "-f", str(FIXTURES / "defs.json")])
    assert rc == 0
    assert capsys.readouterr().out == "Processing Unit\n"


def test_resolve_writes_file(tmp_path):
    src = tmp_path / "in.md"
    src.write_text("width = []{.const id=EMAX_WIDTH}\n")
    dst = tmp_path / "out.md"
    rc = main([
        "resolve", str(src),
        "--lang", "en",
        "-f", str(FIXTURES / "defs.json"),
        "-o", str(dst),
    ])
    assert rc == 0
    assert dst.read_text() == "width = 4\n"


def test_resolve_undefined_exits_nonzero(tmp_path, capsys):
    src = tmp_path / "in.md"
    src.write_text("[]{.term id=missing}\n")
    rc = main([
        "resolve", str(src),
        "--lang", "en",
        "-f", str(FIXTURES / "defs.json"),
    ])
    assert rc == 1
    assert "undefined id 'missing'" in capsys.readouterr().err


def test_resolve_on_missing_keep(tmp_path, capsys):
    src = tmp_path / "in.md"
    src.write_text("[]{.term id=missing}\n")
    rc = main([
        "resolve", str(src),
        "--lang", "en",
        "-f", str(FIXTURES / "defs.json"),
        "--on-missing", "keep",
    ])
    assert rc == 0
    assert capsys.readouterr().out == "[]{.term id=missing}\n"


def test_list_text_default(capsys):
    rc = main(["list", "-f", str(FIXTURES / "defs.json")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "unit" in out
    assert "EMAX_WIDTH" in out
    assert "D" in out


def test_list_filter_by_kind(capsys):
    rc = main(["list", "-f", str(FIXTURES / "defs.json"), "--kind", "const"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "EMAX_WIDTH" in out
    assert "unit" not in out


def test_list_json_output(capsys):
    rc = main([
        "list", "-f", str(FIXTURES / "defs.json"),
        "--format", "json",
    ])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    ids = {e["id"] for e in data}
    assert ids == {"unit", "EMAX_WIDTH", "D"}


def test_verify_passes_when_all_defined(tmp_path):
    src = tmp_path / "in.md"
    src.write_text("OK: []{.term id=unit} and []{.const id=EMAX_WIDTH}.\n")
    rc = main(["verify", str(src), "-f", str(FIXTURES / "defs.json")])
    assert rc == 0


def test_verify_fails_on_undefined(tmp_path, capsys):
    src = tmp_path / "in.md"
    src.write_text("Bad: []{.term id=nonexistent}\n")
    rc = main(["verify", str(src), "-f", str(FIXTURES / "defs.json")])
    assert rc == 1
    err = capsys.readouterr().err
    assert "nonexistent" in err


def test_multiple_defs_files_merge(capsys):
    pytest.importorskip("yaml")
    rc = main([
        "list",
        "-f", str(FIXTURES / "defs.json"),
        "-f", str(FIXTURES / "extra.yaml"),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "CONF_BITS" in out
    assert "unit" in out


def test_bad_defs_file_exits_2(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{broken")
    rc = main(["list", "-f", str(bad)])
    assert rc == 2
    assert "invalid JSON" in capsys.readouterr().err
