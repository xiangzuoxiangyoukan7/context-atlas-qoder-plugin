"""验证知识生命周期、跨记录引用和验收追溯关系。"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable, Mapping

from .model import DocumentRecord, Issue

# context-atlas-rules: [[rules/知识治理规则#RULE-SRC-001|RULE-SRC-001]]


ACCEPTANCE_PATTERN = re.compile(r"(?:(?:F\d{2}|KB)-AC-\d{2}|AC-[A-Z0-9]+-[0-9]{3})\Z")
ACCEPTANCE_RESULTS = {"not_started", "partial", "passed", "not_applicable"}
SOURCE_TYPES = {"user_statement", "repository_file", "command_output", "existing_document", "external_document", "ai_inference"}
REFERENCE_FIELDS = (
    "depends_on",
    "adr",
    "database",
    "prototypes",
    "external_dependencies",
    "supersedes",
    "superseded_by",
)
LIFECYCLE_TYPES = frozenset(
    {
        "knowledge_item",
        "data_asset",
        "data_source",
        "database_unit",
        "database_namespace",
        "database_table",
    }
)


def as_list(value: object) -> list[str]:
    """把空值、标量或列表统一转换为字符串列表。"""

    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


def _records_with_metadata(records: Iterable[DocumentRecord]) -> list[DocumentRecord]:
    """过滤出具有正式元数据的知识记录。"""

    return [record for record in records if record.metadata]


def _id_index(records: Iterable[DocumentRecord], issues: list[Issue]) -> dict[str, DocumentRecord]:
    """建立稳定编号索引并报告重复编号。"""

    index: dict[str, DocumentRecord] = {}
    for record in _records_with_metadata(records):
        identifier = record.metadata.get("id")
        if not isinstance(identifier, str):
            continue
        if identifier in index:
            issues.append(
                Issue(
                    "KB_ID_DUPLICATE",
                    record.path,
                    f"duplicate id {identifier}; first declared by {index[identifier].path}",
                )
            )
        else:
            index[identifier] = record
    return index


def _validate_lifecycle(
    records: Iterable[DocumentRecord],
    ids: Mapping[str, DocumentRecord],
) -> list[Issue]:
    """验证来源、确认、冲突和替代状态的一致性。"""

    issues: list[Issue] = []
    for record in _records_with_metadata(records):
        metadata = record.metadata
        if metadata.get("type") not in LIFECYCLE_TYPES:
            continue
        status = metadata.get("status")
        raw_sources = metadata.get("sources")
        embedded_sources = raw_sources if isinstance(raw_sources, list) and all(isinstance(item, dict) for item in raw_sources) else None
        sources = as_list(raw_sources) if embedded_sources is None else []
        for source in sources:
            if source not in ids:
                issues.append(
                    Issue("KB_SOURCE_UNKNOWN", record.path, f"unknown source reference: {source}")
                )
            elif ids[source].metadata.get("type") != "source":
                issues.append(
                    Issue("KB_SOURCE_TYPE", record.path, f"source reference is not a source: {source}")
                )
        if status == "approved":
            body_authoritative_requirement = (
                metadata.get("type") == "requirement" and "readiness" in metadata
            )
            missing = (
                []
                if body_authoritative_requirement
                else [field for field in ("approved_by", "approved_at") if not metadata.get(field)]
            )
            if missing:
                issues.append(
                    Issue(
                        "KB_APPROVAL_REQUIRED",
                        record.path,
                        f"approved item lacks: {', '.join(missing)}",
                    )
                )
            if body_authoritative_requirement:
                source_section = re.search(
                    r"(?ms)^## 来源与确认\s*\n(.*?)(?=^## |\Z)", record.body
                )
                if source_section is None or not re.search(
                    r"(?mi)^\|.*\|\s*confirmed\s*\|.*\|\s*$",
                    source_section.group(1),
                ):
                    issues.append(
                        Issue(
                            "KB_APPROVAL_REQUIRED",
                            record.path,
                            "approved requirement requires a confirmed source row in 来源与确认",
                        )
                    )
            proposal_revision = metadata.get("proposal_revision")
            confirmed_revision = metadata.get("confirmed_revision")
            if (
                proposal_revision is not None
                and confirmed_revision is not None
                and proposal_revision != confirmed_revision
            ):
                issues.append(
                    Issue(
                        "KB_PROPOSAL_STALE",
                        record.path,
                        "confirmed revision does not match the written Proposal revision",
                    )
                )
            registered_sources = [ids[source] for source in sources if source in ids]
            only_ai_inference = bool(registered_sources) and all(
                source.metadata.get("type") == "source" and source.metadata.get("source_type") == "ai_inference"
                for source in registered_sources
            )
            if embedded_sources is not None:
                for index, source in enumerate(embedded_sources):
                    required = {"type", "reference", "observed_at", "confirmation_status"}
                    missing = required - set(source)
                    if missing:
                        issues.append(Issue("KB_SOURCE_EMBEDDED", record.path, f"embedded source {index} lacks: {', '.join(sorted(missing))}"))
                    if source.get("type") not in SOURCE_TYPES:
                        issues.append(Issue("KB_SOURCE_EMBEDDED", record.path, f"embedded source {index} has invalid type"))
                    if source.get("confirmation_status") not in {"observed", "confirmed"}:
                        issues.append(Issue("KB_SOURCE_EMBEDDED", record.path, f"embedded source {index} has invalid confirmation_status"))
                    if source.get("confirmation_status") == "confirmed" and not source.get("confirmed_at"):
                        issues.append(Issue("KB_SOURCE_EMBEDDED", record.path, f"embedded source {index} lacks confirmed_at"))
                only_ai_inference = bool(embedded_sources) and all(source.get("type") == "ai_inference" for source in embedded_sources)
            if only_ai_inference:
                issues.append(
                    Issue(
                        "KB_APPROVAL_AI_INFERENCE",
                        record.path,
                        "approved item cannot rely only on ai_inference sources",
                    )
                )
        if status == "conflicted":
            source_count = len({str(source) for source in (embedded_sources or sources)})
            if source_count < 2:
                issues.append(
                    Issue(
                        "KB_CONFLICT_SOURCES",
                        record.path,
                        "conflicted item requires at least two distinct sources",
                    )
                )
            if not metadata.get("resolution_required_from"):
                issues.append(
                    Issue(
                        "KB_CONFLICT_RESOLVER",
                        record.path,
                        "conflicted item requires resolution_required_from",
                    )
                )
        if status == "superseded":
            successor = metadata.get("superseded_by")
            if not isinstance(successor, str) or successor not in ids:
                issues.append(
                    Issue(
                        "KB_SUPERSESSION_LINK",
                        record.path,
                        "superseded item requires a valid superseded_by reference",
                    )
                )
            elif metadata.get("id") not in as_list(ids[successor].metadata.get("supersedes")):
                issues.append(
                    Issue(
                        "KB_SUPERSESSION_LINK",
                        record.path,
                        f"successor does not supersede this item: {successor}",
                    )
                )
        identifier = metadata.get("id")
        if isinstance(identifier, str):
            for predecessor_id in as_list(metadata.get("supersedes")):
                predecessor = ids.get(predecessor_id)
                if predecessor is None:
                    continue
                if (
                    predecessor.metadata.get("status") != "superseded"
                    or predecessor.metadata.get("superseded_by") != identifier
                ):
                    issues.append(
                        Issue(
                            "KB_SUPERSESSION_LINK",
                            record.path,
                            f"supersession is not bidirectional: {predecessor_id}",
                        )
                    )
    return issues


def _validate_references(
    records: Iterable[DocumentRecord],
    ids: Mapping[str, DocumentRecord],
    archived_ids: frozenset[str] = frozenset(),
) -> list[Issue]:
    """验证受控引用字段均指向已登记知识编号。"""

    issues: list[Issue] = []
    for record in _records_with_metadata(records):
        for field in REFERENCE_FIELDS:
            for reference in as_list(record.metadata.get(field)):
                if reference and reference not in ids and not (field == "supersedes" and reference in archived_ids):
                    issues.append(
                        Issue(
                            "KB_TRACE_REFERENCE",
                            record.path,
                            f"unknown {field} reference: {reference}",
                        )
                    )
        if record.metadata.get("type") == "task":
            feature = record.metadata.get("feature")
            if isinstance(feature, str) and feature not in ids:
                issues.append(
                    Issue("KB_TRACE_REFERENCE", record.path, f"unknown feature reference: {feature}")
                )
    return issues


def _matrix_rows(path: Path, issues: list[Issue]) -> list[tuple[str, str, str, str]]:
    """解析验收矩阵中的编号、结果、证据和版本列。"""

    if not path.exists():
        return []
    rows: list[tuple[str, str, str, str]] = []
    header: list[str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and cells[0] == "验收编号":
            header = cells
            continue
        if not cells or not ACCEPTANCE_PATTERN.fullmatch(cells[0]) or header is None:
            continue
        required = {"结果", "证据位置", "对应版本"}
        if not required.issubset(header):
            issues.append(
                Issue(
                    "KB_MATRIX_HEADER",
                    path,
                    f"matrix header lacks {sorted(required - set(header))}",
                )
            )
            continue
        indexes = {name: header.index(name) for name in required}
        if len(cells) <= max(indexes.values()):
            issues.append(Issue("KB_MATRIX_ROW", path, f"matrix row is short: {cells[0]}"))
            continue
        rows.append(
            (
                cells[0],
                cells[indexes["结果"]],
                cells[indexes["证据位置"]],
                cells[indexes["对应版本"]],
            )
        )
    return rows


def _registered(value: str) -> bool:
    """判断矩阵单元格是否登记了非占位内容。"""

    return bool(value.strip() and value.strip() not in {"—", "-"})


def _evidence_path(root: Path, value: str) -> Path | None:
    """把矩阵证据单元格解析为当前证据目录中的实际文件。"""

    link = re.search(r"\[[^\]]+\]\((?P<path>[^)]+)\)", value)
    if link:
        candidate = (root / "03-变更与证据" / link.group("path")).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            return None
        return candidate if candidate.is_file() else None
    evidence_root = root / "03-变更与证据" / "验收证据"
    normalized = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", value)
    matches = [
        path
        for path in evidence_root.glob("*.md")
        if re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", path.stem) == normalized
    ]
    return matches[0] if len(matches) == 1 else None


def _validate_acceptance_views(root: Path, records: Iterable[DocumentRecord]) -> list[Issue]:
    """从功能内场景和实际证据动态核对验收追溯，不依赖人工矩阵。"""

    issues: list[Issue] = []
    declarations: dict[str, list[Path]] = {}
    completed: list[tuple[Path, list[str]]] = []
    record_list = list(_records_with_metadata(records))
    for record in record_list:
        if record.metadata.get("type") not in {"feature", "task", "governance_task"}:
            continue
        acceptance = as_list(record.metadata.get("acceptance"))
        for identifier in acceptance:
            declarations.setdefault(identifier, []).append(record.path)
            if record.metadata.get("type") == "feature" and identifier not in record.body:
                issues.append(Issue("KB_ACCEPTANCE_SCENARIO", record.path, f"declared acceptance scenario is missing from feature body: {identifier}"))
        if record.metadata.get("status") == "completed":
            completed.append((record.path, acceptance))

    for identifier, paths in declarations.items():
        if len(paths) > 1:
            issues.append(Issue("KB_ACCEPTANCE_DUPLICATE", paths[0], f"acceptance ID is declared by multiple records: {identifier}"))

    evidence_root = root / "03-变更与证据" / "验收证据"
    evidence_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in evidence_root.glob("*.md")
        if path.name != "README.md"
    ) if evidence_root.is_dir() else ""
    for path, acceptance in completed:
        for identifier in acceptance:
            if identifier not in evidence_text:
                issues.append(Issue("KB_COMPLETION_EVIDENCE", path, f"completed record lacks locatable evidence: {identifier}"))
    return issues


def validate_traceability(
    root: Path,
    records: Iterable[DocumentRecord],
    archived_ids: frozenset[str] = frozenset(),
) -> list[Issue]:
    """汇总生命周期、引用和验收矩阵的追溯问题。"""

    materialized = list(records)
    issues: list[Issue] = []
    ids = _id_index(materialized, issues)
    issues.extend(_validate_lifecycle(materialized, ids))
    issues.extend(_validate_references(materialized, ids, archived_ids))
    issues.extend(_validate_acceptance_views(root, materialized))
    return issues
