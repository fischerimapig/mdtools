"""Explicit Workspace registration and source selection (no content analysis).

This assembly layer may use DocumentTree; core and the existing document tools
do not depend on it. WorkspaceError is local to configuration loading, pending
the shared source/diagnostic models in M1 #24/#25.
"""

from __future__ import annotations

import errno
import json
import stat
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from mdsplit.schema import DocumentTree, SectionNode


class WorkspaceError(ValueError):
    """A failed registration; no partial Workspace is returned."""

    def __init__(self, code: str, path: Path, detail: str):
        self.code = code
        self.path = path
        super().__init__(f"{path}: {code}: {detail}")


@dataclass(frozen=True)
class DocumentInput:
    kind: Literal["markdown", "hierarchy"]
    path: Path
    canonical: Path | None = None
    tree: DocumentTree | None = None


@dataclass(frozen=True)
class DefinitionInput:
    kind: Literal["spec", "glossary"]
    path: Path


@dataclass(frozen=True)
class Workspace:
    version: int
    config_path: Path
    root: Path
    documents: tuple[DocumentInput, ...]
    definitions: tuple[DefinitionInput, ...]
    generated: tuple[Path, ...]
    analysis_files: tuple[Path, ...]


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _fields(value: Any, allowed: set[str], required: set[str], label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a table/object")
    unknown = value.keys() - allowed
    missing = required - value.keys()
    if unknown or missing:
        raise ValueError(f"{label}: unknown fields {sorted(unknown)}, missing fields {sorted(missing)}")
    return value


def _array(value: Any, label: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _config(data: dict) -> None:
    _fields(data, {"version", "root", "documents", "definitions", "generated"},
            {"version", "documents"}, "Workspace")
    _string(data.get("root", "."), "root")
    documents = _array(data["documents"], "documents")
    if not documents:
        raise ValueError("documents must contain at least one document")
    for i, doc in enumerate(documents):
        label = f"documents[{i}]"
        _fields(doc, {"kind", "path", "canonical"}, {"kind", "path"}, label)
        if doc["kind"] not in ("markdown", "hierarchy"):
            raise ValueError(f"{label}.kind must be markdown or hierarchy")
        _string(doc["path"], f"{label}.path")
        if doc["kind"] == "hierarchy":
            _string(doc.get("canonical"), f"{label}.canonical")
        elif "canonical" in doc:
            raise ValueError(f"{label}.canonical is only allowed for hierarchy inputs")
    for i, definition in enumerate(_array(data.get("definitions", []), "definitions")):
        label = f"definitions[{i}]"
        _fields(definition, {"kind", "path"}, {"kind", "path"}, label)
        if definition["kind"] not in ("spec", "glossary"):
            raise ValueError(f"{label}.kind must be spec or glossary")
        _string(definition["path"], f"{label}.path")
    for i, path in enumerate(_array(data.get("generated", []), "generated")):
        _string(path, f"generated[{i}]")


def _resolve(base: Path, value: str) -> Path:
    try:
        return (base / value).resolve()
    except (OSError, ValueError, RuntimeError) as exc:
        raise WorkspaceError("workspace.invalid-path", base, f"{value!r}: {exc}") from exc


def _within(root: Path, base: Path, value: str) -> Path:
    path = _resolve(base, value)
    if not path.is_relative_to(root):
        raise WorkspaceError("workspace.outside-root", path, f"reference from {base} escapes {root}")
    return path


def _stat(path: Path, *, required: bool = True):
    try:
        return path.stat()
    except FileNotFoundError as exc:
        if not required:
            return None
        raise WorkspaceError("workspace.missing-file", path, "registered file does not exist") from exc
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise WorkspaceError("workspace.invalid-path", path, "symlink loop") from exc
        raise WorkspaceError("workspace.read-error", path, str(exc)) from exc


def _file(path: Path, extensions: tuple[str, ...]) -> None:
    info = _stat(path)
    if not stat.S_ISREG(info.st_mode):
        raise WorkspaceError("workspace.not-file", path, "expected a regular file")
    if path.suffix.lower() not in extensions:
        raise WorkspaceError("workspace.invalid-extension", path, f"expected one of {extensions}")


class _Registry:
    """Detect path, symlink and hard-link aliases across all registered roles."""

    def __init__(self):
        self.paths: dict[Path, tuple[Path, bool]] = {}
        self.inodes: dict[tuple[int, int], tuple[Path, bool]] = {}

    def add(self, path: Path, *, generated: bool = False) -> None:
        previous = self.paths.get(path)
        info = _stat(path, required=not generated and previous is None)
        inode = (info.st_dev, info.st_ino) if info is not None else None
        if previous is None and inode is not None:
            previous = self.inodes.get(inode)
        if previous is not None:
            old_path, was_generated = previous
            code = "workspace.generated-input" if was_generated != generated else "workspace.duplicate-input"
            raise WorkspaceError(code, path, f"already registered as {old_path}")
        self.paths[path] = (path, generated)
        if inode is not None:
            self.inodes[inode] = (path, generated)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _hierarchy(path: Path) -> DocumentTree:
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        _fields(data, {"source_file", "base_level", "metadata", "sections"}, set(), "hierarchy")
        if not isinstance(data.get("source_file", ""), str):
            raise ValueError("source_file must be a string")
        if type(data.get("base_level", 1)) is not int:
            raise ValueError("base_level must be an integer")
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be an object")
        if "preamble_file" in metadata:
            _string(metadata["preamble_file"], "metadata.preamble_file")
        if "front_matter" in metadata and not isinstance(metadata["front_matter"], str):
            raise ValueError("metadata.front_matter must be a string")

        def validate(nodes: Any) -> None:
            for node in _array(nodes, "sections/children"):
                _fields(node, {"title", "file", "order", "children"},
                        {"title", "file", "order"}, "section")
                if not isinstance(node["title"], str) or type(node["order"]) is not int:
                    raise ValueError("section title/order must be a string/integer")
                _string(node["file"], "section.file")
                validate(node.get("children", []))

        validate(data.get("sections", []))
        return DocumentTree.from_dict(data)
    except (ValueError, RecursionError) as exc:
        raise WorkspaceError("workspace.invalid-hierarchy", path, str(exc)) from exc
    except OSError as exc:
        raise WorkspaceError("workspace.read-error", path, str(exc)) from exc


def load_workspace(config_path: str | Path) -> Workspace:
    """Load TOML v1 and select original files in explicit, deterministic order.

    Paths in the result are absolute and resolved. Definitions are registered
    separately and their contents are not parsed. Generated files need not exist.
    Invalid settings/references raise WorkspaceError, never a partial result.
    """
    config_path = _resolve(Path.cwd(), str(config_path))
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkspaceError("workspace.missing-file", config_path, str(exc)) from exc
    except (ValueError, UnicodeError) as exc:
        raise WorkspaceError("workspace.invalid-config", config_path, str(exc)) from exc
    except OSError as exc:
        raise WorkspaceError("workspace.read-error", config_path, str(exc)) from exc

    if "version" not in data:
        raise WorkspaceError("workspace.invalid-config", config_path, "version is required")
    if type(data["version"]) is not int or data["version"] != 1:
        raise WorkspaceError("workspace.unsupported-version", config_path, "expected integer version = 1")
    try:
        _config(data)
    except ValueError as exc:
        raise WorkspaceError("workspace.invalid-config", config_path, str(exc)) from exc

    root = _resolve(config_path.parent, data.get("root", "."))
    if not stat.S_ISDIR(_stat(root).st_mode):
        raise WorkspaceError("workspace.not-directory", root, "root must be a directory")

    registry = _Registry()
    generated: list[Path] = []
    # Reserve all output identities before any inputs, independent of input order.
    outputs = [doc["canonical"] for doc in data["documents"] if doc["kind"] == "hierarchy"]
    for value in outputs + data.get("generated", []):
        path = _within(root, root, value)
        info = _stat(path, required=False)
        if info is not None and not stat.S_ISREG(info.st_mode):
            raise WorkspaceError("workspace.not-file", path, "generated output must be a file")
        registry.add(path, generated=True)
        generated.append(path)

    analysis_files: list[Path] = []

    def add_text(base: Path, value: str) -> Path:
        path = _within(root, base, value)
        registry.add(path)
        _file(path, (".md", ".qmd"))
        analysis_files.append(path)
        return path

    documents: list[DocumentInput] = []
    for doc in data["documents"]:
        if doc["kind"] == "markdown":
            documents.append(DocumentInput("markdown", add_text(root, doc["path"])))
            continue
        path = _within(root, root, doc["path"])
        registry.add(path)
        _file(path, (".json",))
        tree = _hierarchy(path)
        canonical = _within(root, root, doc["canonical"])
        _check_canonical_extension(canonical)
        documents.append(DocumentInput("hierarchy", path, canonical, tree))
        if "preamble_file" in tree.metadata:
            add_text(path.parent, tree.metadata["preamble_file"])

        def visit(nodes: list[SectionNode]) -> None:
            for node in sorted(nodes, key=lambda node: node.order):
                add_text(path.parent, node.file)
                visit(node.children)

        visit(tree.sections)

    definitions: list[DefinitionInput] = []
    for definition in data.get("definitions", []):
        path = _within(root, root, definition["path"])
        registry.add(path)
        _file(path, (".json", ".yaml", ".yml"))
        definitions.append(DefinitionInput(definition["kind"], path))

    return Workspace(1, config_path, root, tuple(documents), tuple(definitions),
                     tuple(generated), tuple(analysis_files))


def _check_canonical_extension(path: Path) -> None:
    if path.suffix.lower() not in (".md", ".qmd"):
        raise WorkspaceError("workspace.invalid-extension", path, "canonical must be Markdown/QMD")
