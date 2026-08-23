"""验证知识库 Markdown 相对链接的安全性与完整性。"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable
from urllib.parse import unquote

from .discovery import is_excluded
from .model import Issue


LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")


def validate_links(
    root: Path,
    excluded_directories: Iterable[str],
) -> list[Issue]:
    """检查链接目标存在并忽略允许的外部协议。"""

    issues: list[Issue] = []
    for path in sorted(root.rglob("*.md")):
        if is_excluded(path, root, excluded_directories):
            continue
        content = path.read_text(encoding="utf-8")
        for target in LINK_PATTERN.findall(content):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            relative = unquote(target.split("#", maxsplit=1)[0])
            if not relative:
                continue
            candidate = (path.parent / relative).resolve()
            if not candidate.exists():
                issues.append(Issue("KB_LINK_BROKEN", path, f"broken relative link: {target}"))
    return issues
