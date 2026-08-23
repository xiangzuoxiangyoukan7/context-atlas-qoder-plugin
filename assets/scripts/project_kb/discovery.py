"""发现知识库中的可治理 Markdown 记录。"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .frontmatter import FrontMatterError, parse_document
from .model import DocumentRecord, Issue


def is_excluded(path: Path, root: Path, excluded_directories: Iterable[str]) -> bool:
    """判断路径是否位于工作区或历史归档等排除目录。"""

    excluded = frozenset(excluded_directories)
    return any(part in excluded for part in path.relative_to(root).parts)


def discover_records(
    root: Path,
    excluded_directories: Iterable[str],
) -> tuple[list[DocumentRecord], list[Issue]]:
    """解析未排除的 Markdown 文件并同时返回解析问题。"""

    records: list[DocumentRecord] = []
    issues: list[Issue] = []
    for path in sorted(root.rglob("*.md")):
        if is_excluded(path, root, excluded_directories):
            continue
        if path.name.upper() == "TEMPLATE.MD":
            continue
        try:
            records.append(parse_document(path))
        except FrontMatterError as error:
            issues.append(Issue("KB_FRONTMATTER", path, str(error)))
    return records, issues
