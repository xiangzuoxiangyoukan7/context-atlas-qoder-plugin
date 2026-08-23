"""校验 Obsidian 关系链接并构造可查询的正向与反向索引。"""

# context-atlas-rules: [[rules/知识治理规则#RULE-REL-002|RULE-REL-002]]

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

from .model import DocumentRecord, Issue, KnowledgeTarget, RelationEdge
from .relation_catalog import RelationCatalog, RelationDefinition


RELATION_LINK = re.compile(
    r"^\[\[(?P<path>[^\]#|]+)(?:#(?P<anchor>[^\]|]+))?\|(?P<identifier>[^\]|]+)\]\]$"
)
HEADING_TARGET = re.compile(r"^#{2,6}\s+(?P<identifier>[A-Z][A-Z0-9-]*-\d+)\s+(?P<title>.+?)\s*$")
BLOCK_TARGET = re.compile(
    r"(?:^|\s|\|)\^(?P<identifier>[A-Z][A-Z0-9-]*-\d+)\s*(?:\|\s*)?$"
)


def _identifier_family(identifier: str) -> str:
    """从稳定编号提取关系目录使用的端点族。"""

    acceptance = re.match(r"^(?P<family>F\d+|KB)-AC-\d+$", identifier)
    if acceptance:
        family = acceptance.group("family")
        return "F" if family.startswith("F") else family
    if re.fullmatch(r"F\d+", identifier):
        return "F"
    return identifier.split("-", 1)[0]


def _prefix_allowed(identifier: str, prefixes: frozenset[str]) -> bool:
    """判断稳定编号是否属于关系定义允许的端点族。"""

    return "*" in prefixes or _identifier_family(identifier) in prefixes


def _record_target(record: DocumentRecord) -> KnowledgeTarget | None:
    """把带稳定编号的独立文档转换为可链接目标。"""

    identifier = record.metadata.get("id")
    if not isinstance(identifier, str) or not identifier:
        return None
    kind_value = record.metadata.get("type")
    kind = kind_value if isinstance(kind_value, str) else _identifier_family(identifier)
    return KnowledgeTarget(identifier, record.path.resolve(), None, kind)


def _aggregate_targets(record: DocumentRecord) -> list[KnowledgeTarget]:
    """从聚合文档标题或块编号中发现可精确寻址的知识项。"""

    targets: list[KnowledgeTarget] = []
    for line in record.body.splitlines():
        heading = HEADING_TARGET.match(line)
        if heading:
            identifier = heading.group("identifier")
            anchor = f"{identifier} {heading.group('title')}"
            targets.append(
                KnowledgeTarget(
                    identifier, record.path.resolve(), anchor, _identifier_family(identifier)
                )
            )
            continue
        block = BLOCK_TARGET.search(line)
        if block:
            identifier = block.group("identifier")
            targets.append(
                KnowledgeTarget(
                    identifier,
                    record.path.resolve(),
                    f"^{identifier}",
                    _identifier_family(identifier),
                )
            )
    return targets


def _resolve_link_path(root: Path, raw_path: str) -> Path | None:
    """安全解析知识库相对路径，并拒绝绝对路径和越界路径。"""

    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    if relative.suffix == "":
        relative = relative.with_suffix(".md")
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError:
        return None
    return candidate


def _relation_values(value: object) -> list[str] | None:
    """仅接受由非空字符串组成的关系列表。"""

    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        return None
    return list(value)


def _direction_is_valid(
    definition: RelationDefinition,
    source_identifier: str,
    target_identifier: str,
) -> bool:
    """验证源和目标编号族，并限制替代关系只能连接同族知识。"""

    if not _prefix_allowed(source_identifier, definition.source_prefixes):
        return False
    if not _prefix_allowed(target_identifier, definition.target_prefixes):
        return False
    if definition.field == "rel_supersedes":
        return _identifier_family(source_identifier) == _identifier_family(
            target_identifier
        )
    return True


@dataclass(frozen=True)
class RelationIndex:
    """保存已验证关系以及按源编号、目标编号生成的双向查询索引。"""

    edges: tuple[RelationEdge, ...]
    by_source: dict[str, tuple[RelationEdge, ...]]
    by_target: dict[str, tuple[RelationEdge, ...]]
    targets: dict[str, tuple[KnowledgeTarget, ...]]

    @classmethod
    def build(
        cls,
        root: Path,
        records: Iterable[DocumentRecord],
        catalog: RelationCatalog,
    ) -> tuple[RelationIndex, list[Issue]]:
        """发现链接目标、校验全部正向关系并生成确定性索引。"""

        record_list = list(records)
        targets_by_file: dict[Path, dict[str, list[KnowledgeTarget]]] = {}
        sources_by_file: dict[Path, KnowledgeTarget] = {}
        for record in record_list:
            resolved_path = record.path.resolve()
            document_target = _record_target(record)
            discovered = ([] if document_target is None else [document_target]) + _aggregate_targets(record)
            file_targets = targets_by_file.setdefault(resolved_path, {})
            for target in discovered:
                file_targets.setdefault(target.identifier, []).append(target)
            if document_target is not None:
                sources_by_file[resolved_path] = document_target

        edges: list[RelationEdge] = []
        issues: list[Issue] = []
        for record in record_list:
            relation_fields = sorted(
                field for field in record.metadata if field.startswith("rel_")
            )
            if not relation_fields:
                continue
            source = sources_by_file.get(record.path.resolve())
            if source is None:
                issues.append(
                    Issue(
                        "KB_REL_SOURCE_ID",
                        record.path,
                        "包含关系的文档必须声明非空 id",
                    )
                )
                continue
            for field in relation_fields:
                definition = catalog.get(field)
                if definition is None:
                    issues.append(
                        Issue("KB_REL_FIELD_UNKNOWN", record.path, f"未登记的关系字段：{field}", field)
                    )
                    continue
                values = _relation_values(record.metadata[field])
                if values is None:
                    issues.append(
                        Issue("KB_REL_LINK_FORMAT", record.path, f"{field} 必须是 Obsidian 链接列表", field)
                    )
                    continue
                seen: set[tuple[str, str]] = set()
                for value in values:
                    edge = cls._validate_value(
                        root, record, source, field, definition, value, targets_by_file, issues
                    )
                    if edge is None:
                        continue
                    duplicate_key = (field, edge.target.identifier)
                    if duplicate_key in seen:
                        issues.append(
                            Issue("KB_REL_DUPLICATE", record.path, f"重复关系：{field} -> {edge.target.identifier}", field)
                        )
                        continue
                    seen.add(duplicate_key)
                    edges.append(edge)

        ordered = tuple(
            sorted(edges, key=lambda edge: (edge.source.identifier, edge.field, edge.target.identifier))
        )
        targets_by_identifier: dict[str, list[KnowledgeTarget]] = {}
        for file_targets in targets_by_file.values():
            for identifier, targets in file_targets.items():
                targets_by_identifier.setdefault(identifier, []).extend(targets)
        return cls(
            edges=ordered,
            by_source=cls._group(ordered, source=True),
            by_target=cls._group(ordered, source=False),
            targets={
                identifier: tuple(
                    sorted(targets, key=lambda target: (str(target.path), target.anchor or ""))
                )
                for identifier, targets in targets_by_identifier.items()
            },
        ), issues

    @staticmethod
    def _validate_value(
        root: Path,
        record: DocumentRecord,
        source: KnowledgeTarget,
        field: str,
        definition: RelationDefinition,
        value: str,
        targets_by_file: dict[Path, dict[str, list[KnowledgeTarget]]],
        issues: list[Issue],
    ) -> RelationEdge | None:
        """校验单个关系值并在成功时返回关系边。"""

        match = RELATION_LINK.fullmatch(value)
        if match is None:
            issues.append(Issue("KB_REL_LINK_FORMAT", record.path, f"关系不是统一链接格式：{value}", field))
            return None
        target_path = _resolve_link_path(root, match.group("path"))
        if target_path is None or target_path not in targets_by_file:
            issues.append(Issue("KB_REL_TARGET_FILE", record.path, f"关系目标文件不存在：{match.group('path')}", field))
            return None
        identifier = match.group("identifier")
        candidates = targets_by_file[target_path].get(identifier, [])
        if not candidates:
            issues.append(Issue("KB_REL_TARGET_ID", record.path, f"目标文件中不存在编号：{identifier}", field))
            return None
        anchor = match.group("anchor")
        matched_targets = [target for target in candidates if target.anchor == anchor]
        if not matched_targets:
            issues.append(Issue("KB_REL_TARGET_ANCHOR", record.path, f"目标锚点与编号不匹配：{identifier}", field))
            return None
        target = matched_targets[0]
        if not _direction_is_valid(definition, source.identifier, target.identifier):
            issues.append(Issue("KB_REL_DIRECTION", record.path, f"关系端点类型不合法：{source.identifier} -> {target.identifier}", field))
            return None
        return RelationEdge(field, source, target)

    @staticmethod
    def _group(
        edges: tuple[RelationEdge, ...],
        *,
        source: bool,
    ) -> dict[str, tuple[RelationEdge, ...]]:
        """按源或目标稳定编号分组，供正向和反向查询复用。"""

        grouped: dict[str, list[RelationEdge]] = {}
        for edge in edges:
            key = edge.source.identifier if source else edge.target.identifier
            grouped.setdefault(key, []).append(edge)
        return {key: tuple(value) for key, value in grouped.items()}

    def outgoing(self, identifier: str) -> tuple[RelationEdge, ...]:
        """返回指定知识项写出的全部权威正向关系。"""

        return self.by_source.get(identifier, ())

    def incoming(self, identifier: str) -> tuple[RelationEdge, ...]:
        """返回由正向关系计算得到的全部反向使用方。"""

        return self.by_target.get(identifier, ())

    def contains(self, identifier: str) -> bool:
        """判断稳定编号是否存在于独立文档或聚合文档知识项中。"""

        return identifier in self.targets

    def target(self, identifier: str) -> KnowledgeTarget | None:
        """返回稳定编号的首个确定性目标；不存在时返回空值。"""

        targets = self.targets.get(identifier, ())
        return targets[0] if targets else None
