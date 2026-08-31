"""验证知识库固定入口、authority 和知识类型的唯一目录归属。"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

from .model import DocumentRecord, Issue


REQUIRED_ENTRIES = (
    "README.md", "knowledge-base.yaml", "00-项目总览/README.md",
    "00-项目总览/项目概述.md", "01-功能基线/README.md",
    "01-功能基线/能力地图.md", "02-架构与契约/README.md",
    "02-架构与契约/系统架构.md", "03-变更与证据/README.md",
    "03-变更与证据/验收矩阵.md", "04-决策记录/README.md",
    "05-知识治理/README.md", "05-知识治理/AI知识采集协议.md",
    "90-历史归档/README.md",
)
OPTIONAL_ENTRIES = {"00-项目总览/术语表.md", "05-知识治理/协作与责任.md"}
TYPE_DIRECTORIES = {
    "source": "05-知识治理",
    "requirement": "01-功能基线/需求",
    "feature": "01-功能基线/功能",
    "data_asset": "02-架构与契约",
    "data_source": "02-架构与契约",
    "database_unit": "02-架构与契约",
    "database_namespace": "02-架构与契约",
    "database_table": "02-架构与契约",
    "acceptance": "03-变更与证据",
    "knowledge_proposal": "03-变更与证据",
    "module": "02-架构与契约/模块",
    "interface": "02-架构与契约/接口",
}
LEGACY_FIXED = {
    "03-实施与验收",
    "03-变更与证据/任务包",
    "03-变更与证据/执行看板.md",
    "03-变更与证据/影响分析",
    "03-变更与证据/知识提案",
    "00-项目总览/项目目标与成功标准.md",
    "00-项目总览/项目边界.md",
    "00-项目总览/产品能力地图.md",
    "00-项目总览/技术栈与版本.md",
    "00-项目总览/知识来源.md",
    "00-项目总览/协作人员.md",
    "05-开发指南",
}


def _authorities(path: Path) -> list[str]:
    """读取受控 manifest 中 authority 映射的标量目标。"""

    if not path.is_file():
        return []
    result: list[str] = []
    in_authority = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == "authority:":
            in_authority = True
            continue
        if in_authority and line.startswith("  ") and ":" in line:
            result.append(line.split(":", 1)[1].strip().strip("'\""))
        elif in_authority and line.strip():
            break
    return result


def _format_version(path: Path) -> int:
    """读取清单格式版本；旧清单缺失时按格式一处理。"""

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("format_version:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return 0
    return 1


def validate_structure(root: Path, records: Iterable[DocumentRecord]) -> list[Issue]:
    """返回固定结构、权威路径及类型目录问题。"""

    issues: list[Issue] = []
    if not (root / "knowledge-base.yaml").is_file():
        return issues
    for relative in REQUIRED_ENTRIES:
        path = root / relative
        if not path.exists():
            issues.append(Issue("KB_STRUCTURE_REQUIRED", path, f"missing required entry: {relative}"))
    for relative in _authorities(root / "knowledge-base.yaml"):
        candidate = (root / relative).resolve()
        if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
            issues.append(Issue("KB_AUTHORITY_MISSING", root / "knowledge-base.yaml", f"authority target does not exist: {relative}"))
    for relative in LEGACY_FIXED:
        path = root / relative
        if path.exists():
            issues.append(Issue("KB_STRUCTURE_LEGACY", path, f"legacy fixed entry remains: {relative}"))
    format_version = _format_version(root / "knowledge-base.yaml")
    for record in records:
        kind = record.metadata.get("type")
        expected = TYPE_DIRECTORIES.get(str(kind))
        if expected is not None:
            relative = record.path.resolve().relative_to(root.resolve()).as_posix()
            identifier = record.metadata.get("id")
            legacy_feature = (
                kind == "feature"
                and format_version <= 5
                and relative.startswith("01-功能基线/")
                and isinstance(identifier, str)
                and re.fullmatch(r"F\d+", identifier) is not None
            )
            if not relative.startswith(expected + "/") and not legacy_feature:
                issues.append(Issue("KB_TYPE_DIRECTORY", record.path, f"{kind} must be stored under {expected}"))
        sources = record.metadata.get("sources")
        if format_version >= 4 and isinstance(sources, list) and any(not isinstance(item, dict) for item in sources):
            issues.append(Issue("KB_SOURCE_LEGACY", record.path, "format 4 requires embedded source objects"))
    return issues
