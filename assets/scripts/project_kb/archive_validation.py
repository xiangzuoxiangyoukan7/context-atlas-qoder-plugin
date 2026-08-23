"""验证历史归档位置、状态和当前知识对归档的引用边界。"""

from __future__ import annotations

from pathlib import Path

from .discovery import discover_records
from .links import LINK_PATTERN
from .model import DocumentRecord, Issue

# context-atlas-rules: [[rules/知识治理规则#RULE-ARCHIVE-001|RULE-ARCHIVE-001]]


ARCHIVABLE_TYPES = frozenset(
    {
        "knowledge_item", "requirement", "feature", "module", "contract",
        "interface", "data_asset", "data_source", "database_unit",
        "database_namespace", "database_table",
    }
)


def discover_archive(root: Path) -> tuple[list[DocumentRecord], list[Issue]]:
    """发现归档中的正式知识；旧任务和原始材料不纳入生命周期校验。"""

    archive = root / "90-历史归档"
    if not archive.is_dir():
        return [], []
    records, issues = discover_records(archive, frozenset({".obsidian", "Excalidraw"}))
    formal = [record for record in records if record.metadata.get("type") in ARCHIVABLE_TYPES]
    for record in formal:
        if record.metadata.get("status") != "archived":
            issues.append(Issue("KB_ARCHIVE_STATUS", record.path, "归档中的正式知识必须使用 archived 状态"))
    return formal, issues


def validate_current_archive_links(root: Path, current: list[DocumentRecord]) -> list[Issue]:
    """逐项检查当前状态和 Markdown 链接，禁止把归档内容当作当前依据。"""

    issues: list[Issue] = []
    archive = (root / "90-历史归档").resolve()
    for record in current:
        if record.metadata.get("status") == "archived":
            issues.append(Issue("KB_ARCHIVE_LOCATION", record.path, "archived 状态的正式知识必须移入 90-历史归档"))
        for target in LINK_PATTERN.findall(record.path.read_text(encoding="utf-8")):
            relative = target.split("#", maxsplit=1)[0]
            if not relative or relative.startswith(("http://", "https://", "mailto:")):
                continue
            candidate = (record.path.parent / relative).resolve()
            try:
                candidate.relative_to(archive)
            except ValueError:
                continue
            if candidate == archive / "README.md":
                continue
            issues.append(Issue("KB_ARCHIVE_REFERENCE", record.path, f"当前知识不得引用归档文件：{target}"))
    return issues
