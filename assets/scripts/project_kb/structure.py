"""验证知识库固定入口、authority 和知识类型的唯一目录归属。"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

from .frontmatter import FrontMatterError, parse_document
from .model import DocumentRecord, Issue


CLASSIFICATION_TARGET = re.compile(r"\|(?P<id>IDX-[A-Z0-9_-]+)\]\]$")
DATABASE_ROOT = "02-技术基线/数据库"


REQUIRED_ENTRIES = (
    "README.md", "knowledge-base.yaml", "00-项目总览/README.md",
    "00-项目总览/项目概述.md", "01-功能基线/README.md",
    "01-功能基线/需求/README.md", "01-功能基线/功能/README.md",
    "02-技术基线/README.md",
    "02-技术基线/系统架构.md", "03-变更与证据/README.md",
    "05-知识治理/README.md", "05-知识治理/AI知识采集协议.md",
    "90-历史归档/README.md",
)
OPTIONAL_ENTRIES = {"00-项目总览/术语表.md", "05-知识治理/协作与责任.md"}
TYPE_DIRECTORIES = {
    "source": "05-知识治理",
    "requirement": "01-功能基线/需求",
    "feature": "01-功能基线/功能",
    "data_asset": "02-技术基线",
    "data_source": "02-技术基线",
    "database_unit": "02-技术基线",
    "database_namespace": "02-技术基线",
    "database_table": "02-技术基线",
    "acceptance": "03-变更与证据",
    "knowledge_proposal": "03-变更与证据",
    "module": "02-技术基线/模块",
    "interface": "02-技术基线/接口",
    "knowledge_index": "",
}
CLASSIFICATION_INDEXES = {
    "00-项目总览": "IDX-OVERVIEW",
    "01-功能基线": "IDX-FUNCTIONAL-BASELINE",
    "01-功能基线/需求": "IDX-REQUIREMENTS",
    "01-功能基线/功能": "IDX-FEATURES",
    "02-技术基线/模块": "IDX-MODULES",
    "02-技术基线/接口": "IDX-INTERFACES",
    "02-技术基线/数据库": "IDX-DATABASE",
    "02-技术基线/数据库/数据源": "IDX-DATA-SOURCES",
    "02-技术基线/数据库/数据库单元": "IDX-DATABASE-UNITS",
    "02-技术基线/数据库/数据命名空间": "IDX-DATABASE-NAMESPACES",
    "02-技术基线/数据库/数据表": "IDX-DATABASE-TABLES",
    "02-技术基线/数据资产": "IDX-DATA-ASSETS",
    "02-技术基线/外部依赖": "IDX-DEPENDENCIES",
    "02-技术基线/原型": "IDX-PROTOTYPES",
    "02-技术基线": "IDX-TECHNICAL-BASELINE",
    "03-变更与证据/变更": "IDX-CHANGES",
    "03-变更与证据/验收证据": "IDX-EVIDENCE",
    "03-变更与证据/待确认知识": "IDX-PROPOSALS",
    "03-变更与证据": "IDX-CHANGES-EVIDENCE",
    "05-知识治理/来源资料": "IDX-SOURCES",
    "05-知识治理/公共来源": "IDX-COMMON-SOURCES",
    "05-知识治理": "IDX-GOVERNANCE",
    "90-历史归档": "IDX-ARCHIVE",
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
    "01-功能基线/能力地图.md",
    "02-架构与契约",
    "02-技术基线/关系目录.md",
    "03-变更与证据/当前变更.md",
    "03-变更与证据/验收矩阵.md",
    "90-历史归档/旧契约",
    "90-历史归档/旧验收契约",
    "04-决策记录",
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


def _authority_keys(path: Path) -> list[str]:
    """读取 authority 映射的键，用于拒绝最新格式的废弃入口。"""

    if not path.is_file():
        return []
    result: list[str] = []
    in_authority = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == "authority:":
            in_authority = True
            continue
        if in_authority and line.startswith("  ") and ":" in line:
            result.append(line.strip().split(":", 1)[0])
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


def _relative_path(root: Path, record: DocumentRecord) -> str:
    """返回知识库相对 POSIX 路径。"""

    return record.path.resolve().relative_to(root.resolve()).as_posix()


def _data_source_directory(relative: str) -> str | None:
    """识别由数据源 README 充当实体入口的一级数据库子目录。"""

    prefix = DATABASE_ROOT + "/"
    if not relative.startswith(prefix):
        return None
    remainder = relative[len(prefix) :]
    if "/" not in remainder:
        return None
    directory, _ = remainder.split("/", 1)
    return f"{DATABASE_ROOT}/{directory}"


def _relation_targets_identifier(value: object, identifier: str) -> bool:
    """判断单值关系列表是否指向给定稳定身份。"""

    return (
        isinstance(value, list)
        and len(value) == 1
        and f"|{identifier}]]" in str(value[0])
    )


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
        if path.exists() and (not path.is_dir() or any(path.iterdir())):
            issues.append(Issue("KB_STRUCTURE_LEGACY", path, f"legacy fixed entry remains: {relative}"))
    format_version = _format_version(root / "knowledge-base.yaml")
    if format_version >= 13 and "decisions" in _authority_keys(root / "knowledge-base.yaml"):
        issues.append(Issue("KB_AUTHORITY_LEGACY", root / "knowledge-base.yaml", "format 13 forbids authority.decisions"))
    record_list = list(records)
    if format_version >= 11:
        archive_readme = root / "90-历史归档/README.md"
        if archive_readme.is_file() and all(
            record.path.resolve() != archive_readme.resolve() for record in record_list
        ):
            try:
                record_list.append(parse_document(archive_readme))
            except FrontMatterError as error:
                issues.append(Issue("KB_FRONTMATTER", archive_readme, str(error)))
        for directory in CLASSIFICATION_INDEXES:
            if not (root / directory).is_dir():
                continue
            readme = root / directory / "README.md"
            if not readme.is_file():
                issues.append(
                    Issue(
                        "KB_CLASSIFICATION_README",
                        readme,
                        f"formal knowledge directory must contain README.md: {directory}",
                    )
                )

    classification_ids: dict[str, DocumentRecord] = {}
    indexes_by_directory: dict[str, str] = {}
    data_sources_by_directory: dict[str, str] = {}
    for record in record_list:
        identifier = record.metadata.get("id")
        relative = _relative_path(root, record)
        if (
            record.metadata.get("type") == "knowledge_index"
            and record.path.name == "README.md"
            and isinstance(identifier, str)
        ):
            directory = relative.rsplit("/", 1)[0] if "/" in relative else ""
            indexes_by_directory[directory] = identifier
        if (
            record.metadata.get("type") == "data_source"
            and record.path.name == "README.md"
            and isinstance(identifier, str)
        ):
            directory = _data_source_directory(relative)
            if directory is not None and relative == f"{directory}/README.md":
                data_sources_by_directory[directory] = identifier
    classification_parents: dict[str, str] = {}
    for record in record_list:
        kind = record.metadata.get("type")
        expected = TYPE_DIRECTORIES.get(str(kind))
        if expected:
            relative = _relative_path(root, record)
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
        if format_version >= 11:
            relative = _relative_path(root, record)
            if relative == "Clippings/README.md" or relative.startswith(
                (".project-kb/", "Clippings/", "05-知识治理/来源资料/files/")
            ):
                continue
            identifier = record.metadata.get("id")
            relations = record.metadata.get("rel_classified_under")
            if identifier == "IDX-ROOT":
                if relations != []:
                    issues.append(Issue("KB_CLASSIFICATION_ROOT", record.path, "IDX-ROOT must not have a parent classification"))
                continue
            data_source_directory = _data_source_directory(relative)
            is_data_source_readme = (
                kind == "data_source"
                and record.path.name == "README.md"
                and data_source_directory is not None
                and relative == f"{data_source_directory}/README.md"
            )
            if kind == "data_source" and not is_data_source_readme:
                issues.append(
                    Issue(
                        "KB_DATABASE_DATASOURCE_README",
                        record.path,
                        "data_source must be stored as DS-*/README.md",
                    )
                )
            if not isinstance(relations, list) or len(relations) != 1:
                issues.append(Issue("KB_CLASSIFICATION_REQUIRED", record.path, "format 11+ knowledge must have exactly one rel_classified_under"))
                continue
            if is_data_source_readme:
                assert data_source_directory is not None
                if data_source_directory.rsplit("/", 1)[-1] != identifier:
                    issues.append(
                        Issue(
                            "KB_DATABASE_DATASOURCE_DIRECTORY",
                            record.path,
                            f"data source directory must match its id: {identifier}",
                        )
                    )
                expected_index = indexes_by_directory.get(DATABASE_ROOT)
                if expected_index is None:
                    issues.append(
                        Issue(
                            "KB_CLASSIFICATION_README",
                            record.path,
                            "database directory must contain a README knowledge_index",
                        )
                    )
                elif not _relation_targets_identifier(relations, expected_index):
                    issues.append(
                        Issue(
                            "KB_CLASSIFICATION_DIRECTORY",
                            record.path,
                            f"data source README must be classified under {expected_index}",
                        )
                    )
                continue
            if record.metadata.get("type") == "knowledge_index":
                if record.path.name != "README.md":
                    issues.append(Issue("KB_CLASSIFICATION_FILENAME", record.path, "knowledge_index must be stored as README.md"))
                    continue
                if isinstance(identifier, str):
                    if identifier in classification_ids:
                        issues.append(Issue("KB_CLASSIFICATION_DUPLICATE", record.path, f"duplicate classification id: {identifier}"))
                    classification_ids[identifier] = record
                    match = CLASSIFICATION_TARGET.search(str(relations[0]))
                    if match is not None:
                        classification_parents[identifier] = match.group("id")
                directory = relative.rsplit("/", 1)[0] if "/" in relative else ""
                expected_identifier = "IDX-ROOT" if not directory else CLASSIFICATION_INDEXES.get(directory)
                if expected_identifier is not None and identifier != expected_identifier:
                    issues.append(Issue("KB_CLASSIFICATION_ID", record.path, f"directory index id must be {expected_identifier}"))
                if directory:
                    parent_directory = directory.rsplit("/", 1)[0] if "/" in directory else ""
                    expected_parent = indexes_by_directory.get(parent_directory)
                    if expected_parent is not None and f"|{expected_parent}]]" not in str(relations[0]):
                        issues.append(Issue("KB_CLASSIFICATION_PARENT", record.path, f"classification must point to direct parent {expected_parent}"))
                continue
            directory = relative.rsplit("/", 1)[0] if "/" in relative else ""
            container = data_sources_by_directory.get(directory)
            if container is not None:
                data_source_id = container
                expected_index = indexes_by_directory.get(DATABASE_ROOT)
                if expected_index is None:
                    issues.append(
                        Issue(
                            "KB_CLASSIFICATION_README",
                            record.path,
                            "database directory must contain a README knowledge_index",
                        )
                    )
                elif not _relation_targets_identifier(relations, expected_index):
                    issues.append(
                        Issue(
                            "KB_CLASSIFICATION_DIRECTORY",
                            record.path,
                            f"data source member must be classified under {expected_index}",
                        )
                    )
                if kind == "database_table" and not _relation_targets_identifier(
                    record.metadata.get("rel_belongs_to"), data_source_id
                ):
                    issues.append(
                        Issue(
                            "KB_DATABASE_TABLE_DATASOURCE",
                            record.path,
                            f"database table must belong to containing data source {data_source_id}",
                        )
                    )
                continue
            if data_source_directory is not None:
                issues.append(
                    Issue(
                        "KB_DATABASE_DATASOURCE_README",
                        record.path,
                        "database data-source directory must contain a data_source README.md",
                    )
                )
                continue
            expected_index = indexes_by_directory.get(directory)
            if expected_index is None:
                issues.append(Issue("KB_CLASSIFICATION_README", record.path, "knowledge directory must contain a README knowledge_index"))
            elif f"|{expected_index}]]" not in str(relations[0]):
                issues.append(Issue("KB_CLASSIFICATION_DIRECTORY", record.path, f"classification must match directory index {expected_index}"))
    for identifier in classification_parents:
        visited: set[str] = set()
        current = identifier
        while current in classification_parents:
            if current in visited:
                issues.append(Issue("KB_CLASSIFICATION_CYCLE", classification_ids[identifier].path, f"classification cycle contains {current}"))
                break
            visited.add(current)
            current = classification_parents[current]
    return issues
