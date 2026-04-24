"""TDD tests for mdtools.core.io (t-wada style: degenerate → roundtrip → edge)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mdtools.core.io import (
    StructuredFileError,
    dumps_json,
    read_json,
    read_structured_file,
    read_text_or_stdin,
    write_json,
    write_text_or_stdout,
)


# ── Phase 1: Degenerate ───────────────────────────────────────────


def test_read_stdin_on_dash(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("hello stdin"))
    result = read_text_or_stdin("-")
    assert result == "hello stdin"


def test_write_stdout_on_none(capsys):
    write_text_or_stdout("hello out", None)
    captured = capsys.readouterr()
    assert captured.out == "hello out"


def test_dumps_json_empty_dict():
    assert dumps_json({}) == "{}"


# ── Phase 2: Roundtrip ───────────────────────────────────────────


def test_read_write_json_roundtrip(tmp_path):
    obj = {"key": "value", "num": 42}
    p = tmp_path / "out.json"
    write_json(p, obj)
    loaded = read_json(p)
    assert loaded == obj


def test_write_json_is_utf8_and_non_ascii(tmp_path):
    obj = {"name": "日本語テスト"}
    p = tmp_path / "out.json"
    write_json(p, obj)
    raw = p.read_text(encoding="utf-8")
    assert "日本語テスト" in raw
    assert "\\u" not in raw


def test_write_json_indent_default_2(tmp_path):
    obj = {"a": 1}
    p = tmp_path / "out.json"
    write_json(p, obj)
    raw = p.read_text(encoding="utf-8")
    assert '  "a": 1' in raw


def test_read_text_utf8(tmp_path):
    p = tmp_path / "sample.txt"
    p.write_text("こんにちは\n世界", encoding="utf-8")
    result = read_text_or_stdin(p)
    assert result == "こんにちは\n世界"


# ── Phase 3: Structured file dispatch ───────────────────────────


def test_read_structured_json(tmp_path):
    p = tmp_path / "data.json"
    p.write_text('{"entries": []}', encoding="utf-8")
    result = read_structured_file(p)
    assert result == {"entries": []}


def test_read_structured_yaml(tmp_path):
    yaml = pytest.importorskip("yaml")
    p = tmp_path / "data.yaml"
    p.write_text("entries:\n  - id: foo\n", encoding="utf-8")
    result = read_structured_file(p)
    assert result == {"entries": [{"id": "foo"}]}


def test_read_structured_yml_extension(tmp_path):
    pytest.importorskip("yaml")
    p = tmp_path / "data.yml"
    p.write_text("key: value\n", encoding="utf-8")
    result = read_structured_file(p)
    assert result == {"key": "value"}


def test_read_structured_empty_yaml_returns_dict(tmp_path):
    pytest.importorskip("yaml")
    p = tmp_path / "empty.yaml"
    p.write_text("", encoding="utf-8")
    result = read_structured_file(p)
    assert result == {}


# ── Phase 4: Error handling ───────────────────────────────────────


def test_read_json_invalid_raises_structured_error(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json", encoding="utf-8")
    with pytest.raises(StructuredFileError):
        read_json(p)


def test_read_structured_unknown_extension_raises(tmp_path):
    p = tmp_path / "data.toml"
    p.write_text("key = 'value'", encoding="utf-8")
    with pytest.raises(StructuredFileError):
        read_structured_file(p)


def test_read_structured_missing_file_raises_file_not_found(tmp_path):
    p = tmp_path / "nonexistent.json"
    with pytest.raises(FileNotFoundError):
        read_structured_file(p)


def test_read_text_or_stdin_path_object(tmp_path):
    p = tmp_path / "text.txt"
    p.write_text("path object test", encoding="utf-8")
    result = read_text_or_stdin(p)
    assert result == "path object test"


def test_write_text_or_stdout_path_object(tmp_path):
    p = tmp_path / "out.txt"
    write_text_or_stdout("written", p)
    assert p.read_text(encoding="utf-8") == "written"
