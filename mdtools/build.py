"""Document build assembly, reusable without a CLI or specification analysis.

Keep stage files and their UTF-8 universal-newline rereads: they are part of the
existing build behavior. This API deliberately uses compose(), not source maps.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from glossary.loader import load
from glossary.resolver import resolve
from langfilter.filter import filter_lang
from mdsplit.compose import compose


class BuildOptionsError(ValueError):
    """Invalid stage options, distinct from errors while probing an input file."""


@contextmanager
def _build_work_dir(path: str | Path | None) -> Iterator[Path]:
    if path:
        work_dir = Path(path)
        work_dir.mkdir(parents=True, exist_ok=True)
        yield work_dir
        return

    with tempfile.TemporaryDirectory(prefix="mdtools-build-") as tmp:
        yield Path(tmp)


def _looks_like_hierarchy_json(path: Path) -> bool:
    if path.name == "hierarchy.json":
        return True
    if path.suffix.lower() != ".json":
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(data, dict) and isinstance(data.get("sections"), list)


def _should_compose(input_arg: str | Path | None, source_type: str) -> bool:
    if input_arg is None:
        return False
    if source_type == "sections":
        return True
    if source_type == "markdown":
        return False
    return _looks_like_hierarchy_json(Path(input_arg))


def _write_stage(
    work_dir: Path,
    index: int,
    name: str,
    suffix: str,
    text: str,
) -> Path:
    path = work_dir / f"{index:02d}-{name}{suffix}"
    path.write_text(text, encoding="utf-8")
    return path


def validate_build_options(
    input_path: str | Path | None,
    *,
    source_type: str = "auto",
    base_level: int | None = None,
    lang: str | None = None,
    keep_lang_fences: bool = False,
    defs: list[str | Path] | None = None,
) -> bool:
    """Validate stage selection, returning whether composition is needed.

    None denotes caller-supplied text. No stdin is read here, so CLI argument
    errors can still be reported before reading a pipe.
    """
    if source_type not in ("auto", "sections", "markdown"):
        raise BuildOptionsError(f"invalid source_type: {source_type!r}")
    if lang not in (None, "en", "ja", "both"):
        raise BuildOptionsError(f"invalid lang: {lang!r}")
    compose_first = _should_compose(input_path, source_type)
    if base_level is not None and not compose_first:
        raise BuildOptionsError("--base-level can only be used when INPUT is hierarchy.json")
    if keep_lang_fences and lang not in ("en", "ja"):
        raise BuildOptionsError("--keep-lang-fences requires --lang en or --lang ja")
    if defs and lang not in ("en", "ja"):
        raise BuildOptionsError("-f/--defs requires --lang en or --lang ja")
    return compose_first


def build_document(
    input_path: str | Path | None = None,
    *,
    input_text: str | None = None,
    read_input: Callable[[], str] | None = None,
    source_type: str = "auto",
    base_level: int | None = None,
    lang: str | None = None,
    keep_lang_fences: bool = False,
    defs: list[str | Path] | None = None,
    on_missing: str = "error",
    work_dir: str | Path | None = None,
    suffix: str = ".md",
) -> str:
    """Return compose -> langfilter -> glossary output, selecting needed stages.

    Supply a file path, input_text, or a lazy read_input callback. Final output
    and stdin are owned by the caller. The callback preserves CLI read timing
    after work-directory setup. An explicit work_dir keeps numbered stage files;
    otherwise they are temporary. suffix only names those files. Glossary's
    existing override/missing warnings are preserved. ValueError, OSError,
    GlossaryError and ResolveError are left for the host to handle.
    """
    if sum(value is not None for value in (input_path, input_text, read_input)) != 1:
        raise ValueError("provide exactly one of input_path, input_text and read_input")
    compose_first = validate_build_options(
        input_path, source_type=source_type, base_level=base_level, lang=lang,
        keep_lang_fences=keep_lang_fences, defs=defs,
    )
    if on_missing not in ("error", "warn", "keep"):
        raise ValueError(f"invalid on_missing: {on_missing!r}")
    run_langfilter = lang in ("en", "ja")
    run_glossary = bool(defs)
    current_path: Path | None = None
    current_text: str | None = None

    def read_current() -> str:
        if current_path is not None:
            return current_path.read_text(encoding="utf-8")
        if current_text is not None:
            return current_text
        raise RuntimeError("build has no current input")

    with _build_work_dir(work_dir) as work_dir:
        stage_index = 1

        if compose_first:
            current_text = None
            composed = compose(input_path, base_level=base_level)
            current_path = _write_stage(
                work_dir, stage_index, "compose", suffix, composed
            )
            stage_index += 1
        elif input_path is None:
            current_text = read_input() if read_input is not None else input_text
        else:
            current_path = Path(input_path)

        if run_langfilter:
            filtered = filter_lang(
                read_current(),
                lang,
                keep_fences=keep_lang_fences,
            )
            current_path = _write_stage(
                work_dir, stage_index, "langfilter", suffix, filtered
            )
            current_text = None
            stage_index += 1

        if run_glossary:
            entries = load(defs)
            resolved = resolve(
                read_current(), entries, lang, on_missing=on_missing,
            )
            current_path = _write_stage(
                work_dir, stage_index, "glossary", suffix, resolved
            )
            current_text = None

        return read_current()
