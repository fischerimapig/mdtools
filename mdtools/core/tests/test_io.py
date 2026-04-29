"""TDD tests for mdtools.core.io (t-wada style: degenerate -> basic -> edge)."""

from __future__ import annotations

import io
import sys
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


# ---------------------------------------------------------------------------
# Phase 1: Degenerate
# ---------------------------------------------------------------------------

def test_read_stdin_on_dash(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("piped text\n"))
    assert read_text_or_stdin("-") == "piped text\n"


def test_write_stdout_on_none(capsys):
    write_text_or_stdout("hello", None)
    captured = capsys.readouterr()
    assert captured.out == "hello"


def test_dumps_json_empty_dict():
    assert dumps_json({}) == "{}"


# ---------------------------------------------------------------------------
# Phase 2: Roundtrip
# ---------------------------------------------------------------------------

def test_read_write_json_roundtrip(tmp_path):
    path = tmp_path / "data.json"
    obj = {"a": 1, "b": [1, 2, 3], "c": {"nested": True}}
    write_json(path, obj)
    assert read_json(path) == obj


def test_write_json_is_utf8_and_non_ascii(tmp_path):
    path = tmp_path / "ja.json"
    write_json(path, {"greeting": "こんにちは"})
    raw = path.read_text(encoding="utf-8")
    assert "こんにちは" in raw
    assert "\\u" not in raw


def test_write_json_indent_default_2(tmp_path):
    path = tmp_path / "indent.json"
    write_json(path, {"a": 1})
    raw = path.read_text(encoding="utf-8")
    assert '  "a": 1' in raw


def test_read_text_utf8(tmp_path):
    path = tmp_path / "text.md"
    path.write_text("日本語テキスト\n", encoding="utf-8")
    assert read_text_or_stdin(path) == "日本語テキスト\n"


# ---------------------------------------------------------------------------
# Phase 3: Structured file dispatch
# ---------------------------------------------------------------------------

def test_read_structured_json(tmp_path):
    path = tmp_path / "defs.json"
    path.write_text('{"key": "value"}', encoding="utf-8")
    assert read_structured_file(path) == {"key": "value"}


def test_read_structured_yaml(tmp_path):
    pytest.importorskip("yaml")
    path = tmp_path / "defs.yaml"
    path.write_text("key: value\nitems:\n  - a\n  - b\n", encoding="utf-8")
    assert read_structured_file(path) == {"key": "value", "items": ["a", "b"]}


def test_read_structured_yml_extension(tmp_path):
    pytest.importorskip("yaml")
    path = tmp_path / "defs.yml"
    path.write_text("x: 1\n", encoding="utf-8")
    assert read_structured_file(path) == {"x": 1}


def test_read_structured_empty_yaml_returns_dict(tmp_path):
    pytest.importorskip("yaml")
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    assert read_structured_file(path) == {}


# ---------------------------------------------------------------------------
# Phase 4: Error handling
# ---------------------------------------------------------------------------

def test_read_json_invalid_raises_structured_error(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{invalid", encoding="utf-8")
    with pytest.raises(StructuredFileError):
        read_json(path)


def test_read_structured_unknown_extension_raises(tmp_path):
    path = tmp_path / "weird.txt"
    path.write_text("foo", encoding="utf-8")
    with pytest.raises(StructuredFileError):
        read_structured_file(path)


def test_read_structured_missing_file_raises_file_not_found(tmp_path):
    path = tmp_path / "nope.json"
    with pytest.raises(FileNotFoundError):
        read_structured_file(path)


def test_read_text_or_stdin_path_object(tmp_path):
    path = tmp_path / "t.md"
    path.write_text("abc", encoding="utf-8")
    assert read_text_or_stdin(path) == "abc"


def test_write_text_or_stdout_path_object(tmp_path):
    path = tmp_path / "out.md"
    write_text_or_stdout("xyz", path)
    assert path.read_text(encoding="utf-8") == "xyz"
