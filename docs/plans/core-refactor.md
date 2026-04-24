# mdtools.core リファクタ計画

## 背景

`mdtools` には現在 4 つのツール (`mdsplit` / `langfilter` / `mdhtml-rewrite` / `glossary`) があり、それぞれ独立パッケージとして実装されている。glossary の追加時点で以下の重複が顕在化した:

- **Markdown 行スキャン + コードフェンス除外の状態機械** が 3 実装ある ([langfilter/filter.py:22-117](../../langfilter/filter.py), [glossary/resolver.py:29-280](../../glossary/resolver.py), [mdsplit/parser.py:10-79](../../mdsplit/parser.py))
- **stdin/stdout + UTF-8 ファイル I/O** のヘルパが 4 ツールに散在
- **JSON シリアライズの定型句 `ensure_ascii=False, indent=2`** が 5 箇所以上
- **Pandoc/Quarto 属性 (`{ ... }`) の正規表現** が langfilter/glossary にそれぞれ別実装

本計画では `mdtools.core` サブパッケージを新設し、これらを **既存テストを一切変更せず** t-wada 式 TDD で段階的に統合する。

## 設計原則

1. **既存テスト凍結**: 120 件の既存テストは回帰ガードとして凍結。リファクタ中は一切変更しない。
2. **t-wada 式 TDD**: 新規 `mdtools/core/tests/` には degenerate → basic → edge の順でテストを**先に**全件書き、それから実装する。
3. **3 段階コミット**: 各 Stage は独立した PR として提出し、各 Stage 完了時点で `pytest` が 120 passed を維持する。
4. **最小侵襲**: 公開 API (各ツールの CLI, エントリポイント) は変更しない。内部実装のみ置換。
5. **コミット粒度**: Stage 内では「core モジュール実装」「caller #1 移行」「caller #2 移行」... と caller ごとにコミットを分ける。各コミットで全テストが緑であること。

## Stage 0: 既存テスト監査 (完了済み)

| スイート | テスト数 | 性質 | 凍結妥当性 |
|---------|---------|------|-----------|
| langfilter/tests | 60+ | 明示的に "t-wada style", phased | ◎ |
| mdsplit/tests | 25+ | unit + 7 件の roundtrip | ◎ |
| glossary/tests | 48 | loader/resolver/cli 全層 | ◎ |
| mdhtml_rewrite/tests | 7 | convert 中心 | △ (薄いが本リファクタで触る範囲は JSON I/O のみ) |

**結論**: 凍結ガードとして十分。

## Stage 1: `mdtools.core.io`

### 1.1 目的
stdin/stdout・UTF-8 ファイル I/O・JSON/YAML 読み書きのヘルパを 1 箇所に集約する。

### 1.2 作成する新規ファイル

```
mdtools/
  core/
    __init__.py           # 空
    io.py                 # 本体
    tests/
      __init__.py         # 空
      test_io.py          # TDD テスト
      fixtures/
        sample.json
        sample.yaml
```

### 1.3 `mdtools/core/io.py` の API

```python
"""I/O helpers shared across mdtools packages."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


class StructuredFileError(ValueError):
    """Raised when reading a structured (JSON/YAML) file fails for content reasons."""


def read_text_or_stdin(path: str | Path) -> str:
    """Read UTF-8 text from ``path``, or from stdin when ``path == '-'``.

    ``Path('-')`` is also treated as stdin for convenience.
    """
    if str(path) == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def write_text_or_stdout(text: str, path: str | Path | None) -> None:
    """Write UTF-8 text to ``path``, or to stdout when ``path`` is None."""
    if path is None:
        sys.stdout.write(text)
    else:
        Path(path).write_text(text, encoding="utf-8")


def read_json(path: str | Path) -> Any:
    """Read and parse a UTF-8 JSON file."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StructuredFileError(f"{path}: invalid JSON: {exc}") from exc


def write_json(path: str | Path, obj: Any, *, indent: int = 2) -> None:
    """Write ``obj`` to ``path`` as UTF-8 JSON (ensure_ascii=False, indented)."""
    Path(path).write_text(dumps_json(obj, indent=indent), encoding="utf-8")


def dumps_json(obj: Any, *, indent: int = 2) -> str:
    """Return ``obj`` as a JSON string in mdtools' standard form."""
    return json.dumps(obj, ensure_ascii=False, indent=indent)


def read_structured_file(path: str | Path) -> Any:
    """Read ``.json``, ``.yaml``, or ``.yml`` and return the parsed object.

    YAML requires the optional ``pyyaml`` dependency.
    Raises:
        FileNotFoundError: if the file does not exist.
        StructuredFileError: for unsupported extensions, parse errors, or
            missing PyYAML when a YAML file is requested.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".json":
        return read_json(p)
    if suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as exc:
            raise StructuredFileError(
                f"YAML support requires PyYAML (install with `pip install pyyaml`): {p}"
            ) from exc
        try:
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise StructuredFileError(f"{p}: invalid YAML: {exc}") from exc
    raise StructuredFileError(
        f"Unsupported file extension '{suffix}': {p}. Use .json, .yaml, or .yml."
    )
```

### 1.4 t-wada テスト仕様 (`mdtools/core/tests/test_io.py`)

以下のテストを**一括で先に書く** (全部 red の状態で)。それから `io.py` を実装する。

```python
# Phase 1: Degenerate
def test_read_stdin_on_dash(monkeypatch, capsys)          # '-' で stdin が読まれる
def test_write_stdout_on_none(capsys)                      # None で stdout に書かれる
def test_dumps_json_empty_dict()                           # {} → "{}"

# Phase 2: Roundtrip
def test_read_write_json_roundtrip(tmp_path)               # 書いて読むと等価
def test_write_json_is_utf8_and_non_ascii(tmp_path)        # ensure_ascii=False, 日本語保持
def test_write_json_indent_default_2(tmp_path)             # 既定 indent=2
def test_read_text_utf8(tmp_path)                          # UTF-8 BOM なしテキストを正しく読む

# Phase 3: Structured file dispatch
def test_read_structured_json(tmp_path)                    # .json ルート
def test_read_structured_yaml(tmp_path)                    # .yaml ルート (pyyaml 必要、importorskip)
def test_read_structured_yml_extension(tmp_path)           # .yml もサポート
def test_read_structured_empty_yaml_returns_dict(tmp_path) # 空 YAML → {}

# Phase 4: Error handling
def test_read_json_invalid_raises_structured_error(tmp_path)
def test_read_structured_unknown_extension_raises(tmp_path)
def test_read_structured_missing_file_raises_file_not_found(tmp_path)
def test_read_text_or_stdin_path_object(tmp_path)          # Path 型も受ける
def test_write_text_or_stdout_path_object(tmp_path)        # 同上
```

**期待件数: 15 件前後**。

### 1.5 移行対象と差分

1 コミット = 1 caller 移行 × テスト緑確認。

| # | 対象ファイル | 置き換え前 | 置き換え後 |
|---|-------------|-----------|-----------|
| 1 | [glossary/cli.py:16-26](../../glossary/cli.py) | `_read_input` / `_write_output` ローカル関数 | `read_text_or_stdin` / `write_text_or_stdout` import、ローカル関数削除 |
| 2 | [langfilter/cli.py:78-90](../../langfilter/cli.py) | `args.input == "-"` 分岐と書き込み分岐 | 同上 |
| 3 | [mdsplit/cli.py:86-91](../../mdsplit/cli.py) | compose の stdout 分岐 | `write_text_or_stdout` |
| 4 | [mdsplit/schema.py:64-76](../../mdsplit/schema.py) | `to_json` / `save` / `load` | 内部で `dumps_json` / `write_json` / `read_json` を使う (外部 API 維持) |
| 5 | [glossary/loader.py:49-66](../../glossary/loader.py) | `_load_file` 関数内の JSON/YAML 分岐 | `read_structured_file` 呼び出し。`GlossaryError` でラップして外向けの例外型を維持 |
| 6 | [glossary/lister.py:54-59](../../glossary/lister.py) | `json.dumps(..., ensure_ascii=False, indent=2)` | `dumps_json(obj)` |
| 7 | [mdhtml_rewrite/inventory.py:178](../../mdhtml_rewrite/inventory.py) | `json.dumps(inv, ensure_ascii=False, indent=2)` + write_text | `write_json(output_path, inv)` |
| 8 | [mdhtml_rewrite/rewrite.py:147-148](../../mdhtml_rewrite/rewrite.py) | inventory 読み込み `json.loads(Path(...).read_text(...))` | `read_json(inventory_path)` |
| 9 | [mdhtml_rewrite/rewrite.py:170](../../mdhtml_rewrite/rewrite.py) | report JSON 書き込み | `write_json(report_path, report)` |

**glossary/loader.py の移行補足**: 既存の `GlossaryError` は publicly visible なので維持する。実装は以下のように変える:
```python
# Before
def _load_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix == ".json": ...
    if suffix in (".yaml", ".yml"): ...

# After
from mdtools.core.io import read_structured_file, StructuredFileError

def _load_file(path: Path) -> dict[str, Any]:
    try:
        return read_structured_file(path)
    except StructuredFileError as exc:
        raise GlossaryError(str(exc)) from exc
```

### 1.6 Stage 1 の完了条件

1. `mdtools/core/io.py` が 15 件程度の新規テストで緑
2. 上記 9 件の caller 移行が全て完了
3. `uv run python -m pytest -q` が **120 + 15 = 135 件** (目安) で passed
4. 既存テストファイルに一切差分がない (`git diff master -- '**/tests/test_*.py'` が空)
5. `pyproject.toml` の `[tool.hatch.build.targets.wheel] packages` に `"mdtools"` が既にあるので追加変更不要 (mdtools/core は自動的に含まれる)

### 1.7 ブランチ・PR

- ブランチ: `feat/core-stage1-io`
- PR タイトル: `Stage 1: Extract mdtools.core.io shared helpers`
- ベース: `master`
- コミット順序 (例):
  1. `Add mdtools.core.io with TDD test suite`
  2. `Migrate glossary.cli to mdtools.core.io`
  3. `Migrate langfilter.cli to mdtools.core.io`
  4. `Migrate mdsplit.cli to mdtools.core.io`
  5. `Migrate mdsplit.schema JSON persistence to mdtools.core.io`
  6. `Migrate glossary.loader to read_structured_file`
  7. `Migrate glossary.lister to dumps_json`
  8. `Migrate mdhtml_rewrite JSON I/O to mdtools.core.io`

各コミット後に `uv run python -m pytest -q` を走らせ、135 passed を確認してから次へ進む。

---

## Stage 2: `mdtools.core.mdscan`

### 2.1 目的
Markdown 行スキャナと、コードフェンス内かどうかの状態管理を 1 本に統合する。末尾改行保全のヘルパも同梱する。

### 2.2 作成する新規ファイル

```
mdtools/
  core/
    mdscan.py
    tests/
      test_mdscan.py
```

### 2.3 `mdtools/core/mdscan.py` の API

```python
"""Markdown line scanner with code-fence state tracking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator


# Stage 3 で mdtools.core.pandoc に昇格予定。Stage 2 では本モジュール内に置く。
_CODE_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")


@dataclass(frozen=True)
class MdLine:
    """One Markdown line with its code-fence classification.

    Attributes:
        lineno: 1-based line number in the original text.
        text: The line content, without trailing newline.
        in_code_fence: True for fence-opening lines, for content inside a fenced
            code block, and for the fence-closing line. False for normal
            Markdown lines that should undergo further parsing.
    """

    lineno: int
    text: str
    in_code_fence: bool


def scan_md_lines(text: str) -> Iterator[MdLine]:
    """Yield :class:`MdLine` for each line of ``text``.

    Recognizes ``` and ~~~ fences of length 3 or more. A fence closes only on
    a line that starts with the same character and is at least as long as the
    opener.
    """
    fence_char: str | None = None
    fence_len = 0

    for idx, line in enumerate(text.split("\n"), start=1):
        m = _CODE_FENCE_RE.match(line)
        if fence_char is None:
            if m:
                fence_char = m.group(1)[0]
                fence_len = len(m.group(1))
                yield MdLine(idx, line, in_code_fence=True)
            else:
                yield MdLine(idx, line, in_code_fence=False)
        else:
            yield MdLine(idx, line, in_code_fence=True)
            if m and m.group(1)[0] == fence_char and len(m.group(1)) >= fence_len:
                fence_char = None
                fence_len = 0


def split_text_preserving_trailing_newline(text: str) -> tuple[list[str], bool]:
    """Split text by '\\n' while remembering whether a trailing newline existed.

    Python's ``str.split('\\n')`` turns ``'foo\\n'`` into ``['foo', '']``.
    This helper returns ``(['foo'], True)`` instead, so callers can faithfully
    round-trip via :func:`join_lines_preserving_trailing_newline`.
    """
    ends_with_newline = text.endswith("\n")
    lines = text.split("\n")
    if ends_with_newline and lines and lines[-1] == "":
        lines = lines[:-1]
    return lines, ends_with_newline


def join_lines_preserving_trailing_newline(
    lines: list[str], ends_with_newline: bool
) -> str:
    """Inverse of :func:`split_text_preserving_trailing_newline`."""
    result = "\n".join(lines)
    if ends_with_newline and result:
        result += "\n"
    return result
```

### 2.4 t-wada テスト仕様 (`mdtools/core/tests/test_mdscan.py`)

```python
# Phase 1: Degenerate
def test_scan_empty_yields_one_empty_line()                # "" → 1 件、lineno=1, text=""
def test_scan_single_line_no_newline()                     # "foo" → 1 件
def test_scan_single_line_with_newline()                   # "foo\n" → 2 件 (foo, "")

# Phase 2: Normal (no fences)
def test_scan_plain_text_all_not_in_fence()
def test_lineno_is_1_based_and_monotonic()

# Phase 3: Backtick fences
def test_scan_backtick_fence_open_and_close_marked_in_fence()
def test_scan_content_between_backtick_fences_in_fence()
def test_scan_after_close_returns_to_normal()
def test_longer_closing_fence_also_closes()                # ``` opens, ```` closes
def test_shorter_fence_inside_does_not_close()             # ```` opens, ``` inside does not close
def test_tilde_fence_independent_of_backtick()             # ``` inside ~~~ block stays in fence

# Phase 4: Tilde fences
def test_scan_tilde_fence()

# Phase 5: Round-trip helpers
def test_split_join_roundtrip_preserves_trailing_newline()
def test_split_join_roundtrip_no_trailing_newline()
def test_split_join_empty_string()
def test_split_yields_lines_without_trailing_empty_when_terminated()

# Phase 6: Integration
def test_scan_mixed_fence_and_plain()                      # 複数フェンス、間に平文
def test_unclosed_fence_keeps_in_fence_to_eof()            # 閉じられないフェンスは EOF まで in_fence
```

**期待件数: 17 件前後**。

### 2.5 移行対象と差分

#### 2.5.1 [langfilter/filter.py](../../langfilter/filter.py) の改修

**Before** (現状の状態機械):
```python
def filter_lang(text, lang):
    if lang == "both": return text
    lines = text.split("\n")
    ends_with_newline = text.endswith("\n")
    if ends_with_newline and lines and lines[-1] == "": lines = lines[:-1]
    out, state, code_fence_char, code_fence_len, current_lang = [], _State.NORMAL, None, 0, None
    for line in lines:
        if state == _State.NORMAL:
            m_code = CODE_FENCE_RE.match(line)
            if m_code: ...  # 状態遷移
            m_lang = LANG_OPEN_RE.match(line)
            if m_lang: ...
            out.append(line)
        elif state == _State.IN_CODE_FENCE: ...
        elif state == _State.IN_LANG_BLOCK: ...
    result = "\n".join(out)
    if ends_with_newline and result: result += "\n"
    return result
```

**After**:
```python
from mdtools.core.mdscan import (
    scan_md_lines,
    split_text_preserving_trailing_newline,
    join_lines_preserving_trailing_newline,
)

# LANG fenced div 開閉はこれまで通り (Stage 3 で core.pandoc に合流)
LANG_OPEN_RE = re.compile(r"^:::\s*\{\s*lang\s*=\s*\"?(\w+)\"?\s*\}")
LANG_CLOSE_RE = re.compile(r"^:::\s*$")

def filter_lang(text, lang):
    if lang == "both": return text
    lines, trailing = split_text_preserving_trailing_newline(text)
    out: list[str] = []
    current_lang: str | None = None
    for md in scan_md_lines("\n".join(lines)):
        line = md.text
        if md.in_code_fence:
            out.append(line); continue
        if current_lang is not None:
            if LANG_CLOSE_RE.match(line):
                if current_lang == lang: out.append(line)
                current_lang = None
            elif current_lang == lang:
                out.append(line)
            continue
        m_open = LANG_OPEN_RE.match(line)
        if m_open:
            current_lang = m_open.group(1)
            if current_lang == lang: out.append(line)
            continue
        out.append(line)
    return join_lines_preserving_trailing_newline(out, trailing)
```

注: `scan_md_lines` は内部で `text.split("\n")` を再度行うため、呼び出し側で先に `split_text_preserving_trailing_newline` して `"\n".join(lines)` で戻すのは二度手間に見える。API 統一のため `scan_md_lines` に `text` ではなく `lines: list[str]` を取る版を追加してもよい。**決定: `scan_md_lines_from_list(lines)` のオーバーロード版を最初から用意する** (下記 2.3 API に追加)。

追加するヘルパ:
```python
def scan_md_lines_from_list(lines: list[str]) -> Iterator[MdLine]:
    """Same as scan_md_lines but takes already-split lines (no trailing empty)."""
    # 実装は scan_md_lines から lineno と分類ロジックだけ再利用
```

#### 2.5.2 [glossary/resolver.py](../../glossary/resolver.py) の改修

`resolve` 関数と `find_missing` 関数の状態機械部分を `scan_md_lines_from_list` に置き換える。ただし `IN_GLOSSARY_BLOCK` 状態は Markdown 一般の概念ではないので resolver 内にローカル state として残す。

**Before** (resolver.py:250-300 付近の抜粋):
```python
state = _State.NORMAL
code_fence_char: str | None = None
...
for line in lines:
    if state == _State.NORMAL:
        m_code = CODE_FENCE_RE.match(line)
        if m_code: ...
        m_gloss = GLOSSARY_OPEN_RE.match(line)
        if m_gloss: ...
        out.append(substitute_spans(line))
    elif state == _State.IN_CODE_FENCE: ...
    elif state == _State.IN_GLOSSARY_BLOCK: ...
```

**After**:
```python
from mdtools.core.mdscan import (
    scan_md_lines_from_list,
    split_text_preserving_trailing_newline,
    join_lines_preserving_trailing_newline,
)

lines, trailing = split_text_preserving_trailing_newline(text)
out: list[str] = []
in_glossary_block = False
pending_block_attrs: Attrs | None = None

for md in scan_md_lines_from_list(lines):
    line = md.text
    if md.in_code_fence:
        out.append(line); continue
    if in_glossary_block:
        if FENCE_CLOSE_RE.match(line):
            rendered = render_glossary_block(entries, pending_block_attrs, lang)
            if rendered: out.extend(rendered.split("\n"))
            in_glossary_block = False
            pending_block_attrs = None
        continue
    m_gloss = GLOSSARY_OPEN_RE.match(line)
    if m_gloss:
        pending_block_attrs = parse_attrs(m_gloss.group(1))
        in_glossary_block = True
        continue
    out.append(substitute_spans(line))

return join_lines_preserving_trailing_newline(out, trailing)
```

`find_missing` も同様に `scan_md_lines_from_list` に移行する。ローカルの `_State` enum, `CODE_FENCE_RE` は削除。

#### 2.5.3 [mdsplit/parser.py](../../mdsplit/parser.py) の改修

mdsplit は **コードフェンス + `<pre>` ブロック** の 2 層追跡を行っている。`scan_md_lines_from_list` でコードフェンス層を置き換え、`<pre>` ブロック追跡は parser.py にローカルに残す。

**Before** (parser.py:65-90):
```python
in_code_fence = False
fence_marker = ""
in_pre_block = False
for i in range(start_idx, len(lines)):
    line = lines[i]
    if not in_pre_block:
        fence_match = FENCE_RE.match(line)
        if fence_match:
            if not in_code_fence: in_code_fence = True; fence_marker = fence_match.group(1)[0]
            elif line.rstrip().startswith(fence_marker): in_code_fence = False; fence_marker = ""
            current_content_lines.append(line); continue
    if not in_code_fence:
        if PRE_OPEN_RE.search(line): in_pre_block = True
        if PRE_CLOSE_RE.search(line): in_pre_block = False
    if not in_code_fence and not in_pre_block:
        heading_match = HEADING_RE.match(line)
        if heading_match: ...
```

**After**:
```python
from mdtools.core.mdscan import scan_md_lines_from_list

body_lines = lines[start_idx:]
in_pre_block = False
for offset, md in enumerate(scan_md_lines_from_list(body_lines)):
    i = start_idx + offset  # 絶対行番号
    line = md.text
    if md.in_code_fence:
        current_content_lines.append(line); continue
    if PRE_OPEN_RE.search(line): in_pre_block = True
    if PRE_CLOSE_RE.search(line): in_pre_block = False
    if not in_pre_block:
        heading_match = HEADING_RE.match(line)
        if heading_match: ...
    else:
        current_content_lines.append(line)
```

ローカル `FENCE_RE` は削除。`PRE_OPEN_RE` / `PRE_CLOSE_RE` / `HEADING_RE` は parser.py に残す。

### 2.6 Stage 2 の完了条件

1. `mdtools/core/mdscan.py` が 17 件程度の新規テストで緑
2. 上記 3 件の caller 移行が全て完了
3. `uv run python -m pytest -q` が **135 + 17 = 152 件** (目安) で passed
4. `langfilter/filter.py`, `glossary/resolver.py`, `mdsplit/parser.py` からローカル `CODE_FENCE_RE` / `FENCE_RE` / `_State` enum / `in_code_fence` ブール変数がいずれも削除されている (`rg 'CODE_FENCE_RE|FENCE_RE|in_code_fence' langfilter/ glossary/ mdsplit/` で該当行がない)
5. 既存テストファイルに差分なし

### 2.7 ブランチ・PR

- ブランチ: `feat/core-stage2-mdscan`
- PR タイトル: `Stage 2: Extract mdtools.core.mdscan shared line scanner`
- ベース: Stage 1 がマージ済みの `master`
- コミット順序:
  1. `Add mdtools.core.mdscan with TDD test suite`
  2. `Migrate langfilter.filter to mdtools.core.mdscan`
  3. `Migrate glossary.resolver to mdtools.core.mdscan`
  4. `Migrate mdsplit.parser to mdtools.core.mdscan`

---

## Stage 3: `mdtools.core.pandoc`

### 3.1 目的
Pandoc/Quarto 構文の正規表現と属性パーサを 1 箇所に集約する。Stage 2 で mdscan 内にローカル定義した `_CODE_FENCE_RE` もここに昇格させ、mdscan は core.pandoc から import する。

### 3.2 作成する新規ファイル

```
mdtools/
  core/
    pandoc.py
    tests/
      test_pandoc.py
```

### 3.3 `mdtools/core/pandoc.py` の API

```python
"""Pandoc/Quarto syntax primitives shared across mdtools."""

from __future__ import annotations

import re
from dataclasses import dataclass


# Code fence (3+ backticks or tildes). Used by mdscan and callers that need
# to avoid touching code-fenced content.
CODE_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")

# Closing fence of a Pandoc fenced div: bare ``:::`` with optional trailing space.
FENCE_CLOSE_RE = re.compile(r"^:::\s*$")

# Opening fence of a Pandoc fenced div: ``::: {...}``. Group 1 captures the
# attribute content between the braces.
DIV_OPEN_RE = re.compile(r"^:::\s*\{([^}]*)\}\s*$")

# Pandoc bracketed span: ``[label]{...}``. Group 1 is the label (possibly empty),
# group 2 is the attribute content.
BRACKETED_SPAN_RE = re.compile(r"\[([^\[\]]*)\]\{([^{}]+)\}")


_ATTR_CLASS_RE = re.compile(r"\.(\S+)")
_ATTR_KV_RE = re.compile(r'(\w+)\s*=\s*("([^"]*)"|(\S+))')


@dataclass(frozen=True)
class PandocAttrs:
    """Parsed attributes of a Pandoc span or fenced div."""

    classes: list[str]
    kv: dict[str, str]

    def has_class(self, name: str) -> bool:
        return name in self.classes

    def first_class_in(self, candidates: frozenset[str] | set[str]) -> str | None:
        for c in self.classes:
            if c in candidates:
                return c
        return None


def parse_attrs(s: str) -> PandocAttrs:
    """Parse the contents of ``{...}`` in a Pandoc span or fenced div.

    Recognizes:
        - ``.classname`` → classes (duplicates preserved in order)
        - ``key=value`` or ``key="quoted value"`` → kv (later wins on duplicate)

    Identifiers (``#id``) are **not** parsed as a separate field; use
    ``kv.get('id')`` for the common ``id=...`` form.
    """
    classes = _ATTR_CLASS_RE.findall(s)
    kv: dict[str, str] = {}
    for m in _ATTR_KV_RE.finditer(s):
        key = m.group(1)
        value = m.group(3) if m.group(3) is not None else m.group(4)
        kv[key] = value
    return PandocAttrs(classes=list(classes), kv=kv)
```

### 3.4 t-wada テスト仕様 (`mdtools/core/tests/test_pandoc.py`)

```python
# Phase 1: Degenerate
def test_parse_empty_string()                              # "" → no classes, no kv
def test_parse_whitespace_only()

# Phase 2: Classes
def test_parse_single_class()                              # ".foo"
def test_parse_multiple_classes()
def test_parse_class_with_hyphen()                         # ".callout-note"

# Phase 3: Key-value
def test_parse_single_kv()                                 # "id=unit"
def test_parse_quoted_value()                              # 'id="unit"'
def test_parse_quoted_value_with_spaces()                  # 'name="Processing Unit"'
def test_parse_multiple_kv()

# Phase 4: Mixed
def test_parse_class_and_kv()                              # ".term id=unit"
def test_parse_class_and_quoted_kv()

# Phase 5: Helper methods
def test_has_class_true()
def test_has_class_false()
def test_first_class_in_picks_earliest()
def test_first_class_in_none_when_no_match()

# Phase 6: Regex constants
def test_code_fence_re_matches_backtick_3()
def test_code_fence_re_matches_backtick_6()
def test_code_fence_re_matches_tilde_3()
def test_code_fence_re_does_not_match_backtick_2()
def test_fence_close_re_matches_bare_colons()
def test_fence_close_re_does_not_match_with_attrs()
def test_div_open_re_captures_attrs()
def test_bracketed_span_re_captures_label_and_attrs()
def test_bracketed_span_re_matches_empty_label()
```

**期待件数: 22 件前後**。

### 3.5 移行対象と差分

#### 3.5.1 [mdtools/core/mdscan.py](../../mdtools/core/mdscan.py) の更新

```python
# Before
_CODE_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")

# After
from .pandoc import CODE_FENCE_RE as _CODE_FENCE_RE
```

#### 3.5.2 [glossary/resolver.py](../../glossary/resolver.py) の改修

`SPAN_RE`, `FENCE_CLOSE_RE`, `_ATTR_KV_RE`, `_ATTR_CLASS_RE`, ローカル `parse_attrs`, ローカル `Attrs` dataclass を削除。`GLOSSARY_OPEN_RE` は `.glossary` 専用のままにするか、`DIV_OPEN_RE` + クラス判定に置き換えるかを選ぶ。**推奨: 後者**。

```python
# Before
SPAN_RE = re.compile(r"\[([^\[\]]*)\]\{([^{}]+)\}")
GLOSSARY_OPEN_RE = re.compile(r"^:::\s*\{\s*\.glossary\b([^}]*)\}\s*$")
FENCE_CLOSE_RE = re.compile(r"^:::\s*$")
@dataclass
class Attrs: ...
def parse_attrs(s: str) -> Attrs: ...

# After
from mdtools.core.pandoc import (
    BRACKETED_SPAN_RE,
    DIV_OPEN_RE,
    FENCE_CLOSE_RE,
    PandocAttrs,
    parse_attrs,
)

# 既存の Attrs を参照しているコードは PandocAttrs に差し替え
# .marker_class プロパティの代替: attrs.first_class_in(MARKER_CLASSES)
# ブロック検出: DIV_OPEN_RE + attrs.has_class("glossary") でフィルタ
```

glossary 固有の `.marker_class` プロパティは Stage 3 では `first_class_in(MARKER_CLASSES)` で代替する (読みやすさは同等)。

Glossary ブロック検出の書き換え:
```python
# Before
m_gloss = GLOSSARY_OPEN_RE.match(line)
if m_gloss:
    pending_block_attrs = parse_attrs(m_gloss.group(1))

# After
m_div = DIV_OPEN_RE.match(line)
if m_div:
    attrs = parse_attrs(m_div.group(1))
    if attrs.has_class("glossary"):
        pending_block_attrs = attrs
```

#### 3.5.3 [langfilter/filter.py](../../langfilter/filter.py) の改修

ローカル `LANG_OPEN_RE`, `LANG_CLOSE_RE` を `DIV_OPEN_RE` + `parse_attrs` + `FENCE_CLOSE_RE` に置き換える。

```python
# Before
LANG_OPEN_RE = re.compile(r"^:::\s*\{\s*lang\s*=\s*\"?(\w+)\"?\s*\}")
LANG_CLOSE_RE = re.compile(r"^:::\s*$")
...
m_lang = LANG_OPEN_RE.match(line)
if m_lang:
    current_lang = m_lang.group(1)

# After
from mdtools.core.pandoc import DIV_OPEN_RE, FENCE_CLOSE_RE, parse_attrs
...
m_div = DIV_OPEN_RE.match(line)
if m_div:
    attrs = parse_attrs(m_div.group(1))
    lang_value = attrs.kv.get("lang")
    if lang_value is not None:
        current_lang = lang_value
        ...
    else:
        # lang 属性を持たない fenced div (.callout-note 等) は素通し
        out.append(line)
        continue
```

**注意点**: langfilter の既存テストに「`{.callout-note}` 等の lang 非保持 fenced div は保持される」という項目がある ([langfilter/tests/test_filter.py の Phase 「非lang fenced div」](../../langfilter/tests/test_filter.py))。この挙動を壊さないように、`lang` キーがない div は `current_lang` を設定せず素通しする。

#### 3.5.4 [glossary/loader.py](../../glossary/loader.py) の `VALID_KINDS`

変更なし (pandoc と独立した概念)。

### 3.6 Stage 3 の完了条件

1. `mdtools/core/pandoc.py` が 22 件程度の新規テストで緑
2. 上記 3 件の caller 更新完了
3. `uv run python -m pytest -q` が **152 + 22 = 174 件** (目安) で passed
4. `langfilter/filter.py`, `glossary/resolver.py` に Pandoc 属性解析の重複コードがいずれも残っていない (`rg 'ATTR_KV_RE|ATTR_CLASS_RE' langfilter/ glossary/` が空)
5. `mdtools/core/mdscan.py` の `_CODE_FENCE_RE` が `from .pandoc import CODE_FENCE_RE` に置き換わっている
6. 既存テストファイルに差分なし

### 3.7 ブランチ・PR

- ブランチ: `feat/core-stage3-pandoc`
- PR タイトル: `Stage 3: Extract mdtools.core.pandoc for Pandoc/Quarto primitives`
- ベース: Stage 2 がマージ済みの `master`
- コミット順序:
  1. `Add mdtools.core.pandoc with TDD test suite`
  2. `Route mdtools.core.mdscan through core.pandoc.CODE_FENCE_RE`
  3. `Migrate glossary.resolver to mdtools.core.pandoc`
  4. `Migrate langfilter.filter to mdtools.core.pandoc`

---

## 共通運用ルール

### テスト実行
```bash
# 全件
uv run python -m pytest -q

# 1 モジュール
uv run python -m pytest glossary/tests/ -q

# Stage 中の回帰検出用 (既存テスト差分がないことを検証)
git diff master -- '**/tests/test_*.py'   # 空であるべき
```

### テストが落ちたときの対応原則
- **既存テストを触って緑にすることを禁止する**。テストはリファクタ後の公開挙動に対する契約。
- 落ちた原因は必ず新 core モジュールか caller 移行側にある。まず差分を巻き戻して 1 コミット粒度で二分探索する。
- 修正はコミットを分け、「Fix X regression introduced in Stage N」のメッセージで履歴に残す。

### コミットメッセージ形式
既存リポジトリの規約に倣い、Imperative / 72 char subject / 必要なら body。Co-Authored-By 署名は省略可。

例:
```
Add mdtools.core.io with TDD test suite

Provides read_text_or_stdin, write_text_or_stdout, read_json, write_json,
dumps_json, and read_structured_file (JSON/YAML). Introduces
StructuredFileError for content-level errors. 15 unit tests cover
stdin/stdout paths, UTF-8 handling, JSON round-trip, and error cases.
```

### PR ボディテンプレート
```markdown
## Summary
- [Stage N] <要点>
- 既存テスト 120 件 + 新規 N 件 = 全件 passed
- 既存テストファイルに差分なし

## Verification
- `uv run python -m pytest -q` → X passed
- `git diff master -- '**/tests/test_*.py'` → 空

## 次の Stage
(Stage 1/2 の PR では次の着手予定を書く)
```

### リスクと緩和
| リスク | 緩和 |
|--------|------|
| `scan_md_lines` の挙動差が既存テストに露呈 | Stage 2 の TDD で open/close/unclosed/tilde/nested を網羅 (§2.4) |
| glossary の `Attrs` → `PandocAttrs` への型差し替えで外部参照が壊れる | `Attrs` は glossary 内部型だった。`glossary.resolver.Attrs` を public に export している箇所がないことを `rg 'from glossary.resolver import Attrs'` で確認してから削除 |
| langfilter の「lang なし div は素通し」挙動の破壊 | Stage 3 の caller 移行時、langfilter の既存テストを該当セクションから Stage 実施前に 1 回走らせ期待を記録。完了後に突合する |
| core.io 導入時、mdsplit.schema の公開 API (`to_json`/`from_json`/`save`/`load`) 変化 | 外部シグネチャは維持。内部実装のみ差し替え |

---

## Stage 完了後の最終形 (参考)

```
mdtools/
├── main.py                      # 変更なし
├── core/
│   ├── __init__.py
│   ├── io.py                    # Stage 1
│   ├── mdscan.py                # Stage 2 (Stage 3 で pandoc に依存)
│   ├── pandoc.py                # Stage 3
│   └── tests/
│       ├── test_io.py
│       ├── test_mdscan.py
│       └── test_pandoc.py
├── langfilter/filter.py         # ~70 行に縮小 (元 116)
├── glossary/
│   ├── resolver.py              # ~330 行に縮小 (元 394)
│   ├── loader.py                # I/O を core.io に委譲 (~120 行)
│   └── lister.py                # ~55 行
├── mdsplit/
│   ├── parser.py                # ~150 行に縮小 (元 184)
│   └── schema.py                # ~60 行
└── mdhtml_rewrite/              # JSON I/O のみ core.io 経由
```

想定合計削減: **200 行前後の重複除去** + Pandoc regex の single source of truth 化。

## 将来の拡張余地 (本計画の範囲外)

本リファクタ完了後に検討する価値がある項目 (今は手を付けない):

- `mdtools.core.cli`: argparse の共通骨格 (`prog`, `epilog` テンプレ, `formatter_class`, 言語別の "最小例 / よく使う例 / 失敗しやすいケース" セクション)
- `mdtools.core.tree`: mdsplit の再帰ツリー走査 (`_count_sections`, `_check_files`, `_make_relative`) を汎用化
- `mdtools.core.html`: mdhtml_rewrite の `FIGURE_RE`, `ID_RE`, `CLASS_RE` 等を切り出し
- 各ツール `__main__.py` の共通化 (現状 7 行 × 4、統合すると読みやすさが損なわれるため保留)

これらは 2560 行のコードベースが倍以上に育ってから検討する。
