"""为 Context Atlas 操作提供统一的项目级临时工作区。"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import shutil
import uuid
from typing import Iterator


TEMPORARY_ROOT_NAME = ".context-atlas-temp"


def temporary_root(project_root: Path) -> Path:
    """返回并校验固定临时根，拒绝链接或非目录占位。"""

    root = project_root.resolve() / TEMPORARY_ROOT_NAME
    if root.exists() and (root.is_symlink() or not root.is_dir()):
        raise ValueError("Context Atlas temporary root must be a regular directory")
    root.mkdir(exist_ok=True)
    return root


@contextmanager
def operation_workspace(project_root: Path, operation: str) -> Iterator[Path]:
    """在固定临时根内创建并最终清理一个操作专属目录。"""

    if not operation or any(character in operation for character in "/\\"):
        raise ValueError("temporary operation name must be a safe path segment")
    workspace = temporary_root(project_root) / f"{operation}-{uuid.uuid4().hex[:8]}"
    workspace.mkdir()
    try:
        yield workspace
    finally:
        if workspace.exists():
            shutil.rmtree(workspace)
