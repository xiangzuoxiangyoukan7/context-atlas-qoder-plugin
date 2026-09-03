"""验证正式 README 的目录职责与渐进导航契约。"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .model import DocumentRecord, Issue


README_TYPES = frozenset({"knowledge_index", "data_source"})
QUERY_TERMS = ("children", "neighbors", "graph")


def validate_readme_contracts(
    root: Path, records: Iterable[DocumentRecord]
) -> list[Issue]:
    """逐项检查正式目录入口，并汇总职责、范围与查询契约缺口。"""

    issues: list[Issue] = []
    resolved_root = root.resolve()
    for record in records:
        if record.path.name != "README.md":
            continue
        relative = record.path.resolve().relative_to(resolved_root).as_posix()
        if relative in {"README.md", "Clippings/README.md"}:
            continue
        kind = record.metadata.get("type")
        if kind not in README_TYPES:
            continue
        body = record.body
        if "## 目录契约" not in body:
            issues.append(
                Issue(
                    "KB_README_CONTRACT_REQUIRED",
                    record.path,
                    "formal README must contain a 目录契约 section",
                )
            )
        missing_terms = [term for term in QUERY_TERMS if term not in body]
        if missing_terms:
            issues.append(
                Issue(
                    "KB_README_QUERY_CONTRACT",
                    record.path,
                    f"formal README lacks query contract: {', '.join(missing_terms)}",
                )
            )
        if kind == "knowledge_index" and "只保存" not in body:
            issues.append(
                Issue(
                    "KB_README_SCOPE_REQUIRED",
                    record.path,
                    "knowledge index README must declare what the directory only stores",
                )
            )
    return issues
