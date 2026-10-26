"""Legacy hierarchy reference checks, independent of CLI presentation.

This checks existence only, in stored traversal order. Workspace registration
has a separate, stricter contract; do not substitute its validation here.
"""

from dataclasses import dataclass
from pathlib import Path

from .schema import DocumentTree, SectionNode


@dataclass(frozen=True)
class VerificationResult:
    section_count: int
    missing_files: tuple[str, ...]


def verify(hierarchy_path: str | Path) -> VerificationResult:
    """Return missing section/preamble references without printing or exiting.

    Preserve duplicate references, stored order and exists() semantics (including
    directories). Loading/format errors propagate as in the existing CLI.
    """
    path = Path(hierarchy_path)
    tree = DocumentTree.load(path)
    missing: list[str] = []

    def check(sections: list[SectionNode]) -> int:
        count = len(sections)
        for section in sections:
            if not (path.parent / section.file).exists():
                missing.append(section.file)
            count += check(section.children)
        return count

    total = check(tree.sections)
    preamble = tree.metadata.get("preamble_file")
    if preamble and not (path.parent / preamble).exists():
        missing.append(preamble)
    return VerificationResult(total, tuple(missing))
