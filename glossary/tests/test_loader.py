"""Tests for glossary.loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from glossary.loader import GlossaryError, Entry, load


FIXTURES = Path(__file__).parent / "fixtures"


def test_load_json_returns_entries():
    entries = load([FIXTURES / "defs.json"])
    assert set(entries.keys()) == {"unit", "EMAX_WIDTH", "D"}
    assert entries["unit"].kind == "term"
    assert entries["EMAX_WIDTH"].kind == "const"
    assert entries["D"].kind == "symbol"


def test_entry_get_returns_data_field():
    entries = load([FIXTURES / "defs.json"])
    names = entries["unit"].get("names")
    assert isinstance(names, dict)
    assert names["en"] == "Processing Unit"


def test_load_yaml_via_pyyaml(tmp_path):
    pytest.importorskip("yaml")
    entries = load([FIXTURES / "extra.yaml"])
    assert "CONF_BITS" in entries
    assert entries["CONF_BITS"].get("value") == 256


def test_load_merges_multiple_files():
    pytest.importorskip("yaml")
    entries = load([FIXTURES / "defs.json", FIXTURES / "extra.yaml"])
    assert set(entries.keys()) == {"unit", "EMAX_WIDTH", "D", "CONF_BITS"}


def test_load_overrides_later_file_wins(tmp_path, capsys):
    pytest.importorskip("yaml")
    override = tmp_path / "override.yaml"
    override.write_text("entries:\n  - id: unit\n    kind: term\n    names: {en: Overridden}\n")
    entries = load([FIXTURES / "defs.json", override])
    assert entries["unit"].get("names") == {"en": "Overridden"}
    captured = capsys.readouterr()
    assert "overrides earlier definition" in captured.err


def test_load_rejects_missing_file(tmp_path):
    with pytest.raises(GlossaryError, match="not found"):
        load([tmp_path / "nope.json"])


def test_load_rejects_empty_list():
    with pytest.raises(GlossaryError, match="No definition files"):
        load([])


def test_load_rejects_invalid_kind(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"entries": [{"id": "x", "kind": "weird"}]}))
    with pytest.raises(GlossaryError, match="invalid kind"):
        load([bad])


def test_load_rejects_missing_id(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"entries": [{"kind": "term"}]}))
    with pytest.raises(GlossaryError, match="missing required"):
        load([bad])


def test_load_rejects_missing_entries_key(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"foo": []}))
    with pytest.raises(GlossaryError, match="missing or invalid 'entries'"):
        load([bad])


def test_load_rejects_unknown_extension(tmp_path):
    bad = tmp_path / "bad.txt"
    bad.write_text("entries: []")
    with pytest.raises(GlossaryError, match="Unsupported"):
        load([bad])


def test_load_rejects_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(GlossaryError, match="invalid JSON"):
        load([bad])
