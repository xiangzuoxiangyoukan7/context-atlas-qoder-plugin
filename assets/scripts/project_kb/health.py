"""生成只读知识库健康报告，不替代结构验证或人工批准。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import re
from typing import Iterable

from .discovery import discover_records
from .obsidian import TYPE_COLORS, read_graph, type_query


def _has_body_sources(body: str) -> bool:
    """识别格式十二以后正文来源表中的至少一条实际来源记录。"""

    match = re.search(r"(?ms)^## 来源与确认\s*$\n(.*?)(?=^## |\Z)", body)
    if match is None:
        return False
    rows = [line.strip() for line in match.group(1).splitlines() if line.strip().startswith("|")]
    return len(rows) >= 3


@dataclass(frozen=True)
class HealthFinding:
    """描述一个可定位的健康问题或人工复核项。"""

    code: str
    severity: str
    path: str
    identifier: str | None
    message: str


@dataclass(frozen=True)
class HealthReport:
    """汇总健康检查结果并声明只读边界。"""

    status: str
    findings: tuple[HealthFinding, ...]
    files_scanned: int
    writes_performed: bool = False


def inspect_health(
    knowledge_base_root: Path,
    *,
    today: date | None = None,
    stale_days: int = 180,
    excluded: Iterable[str] = (".project-kb", ".obsidian", "Excalidraw", "Clippings", "90-历史归档"),
) -> HealthReport:
    """检查重复、孤立、陈旧、冲突、来源和权威入口缺口。"""

    root = knowledge_base_root.resolve()
    records, parse_issues = discover_records(root, excluded)
    findings = [
        HealthFinding(issue.code, "error", issue.path.relative_to(root).as_posix(), None, issue.message)
        for issue in parse_issues
    ]
    identifiers: dict[str, list[Path]] = {}
    referenced: set[str] = set()
    relation_references: list[tuple[Path, str, str]] = []
    for record in records:
        identifier = record.metadata.get("id")
        if isinstance(identifier, str):
            identifiers.setdefault(identifier, []).append(record.path)
        for field, value in record.metadata.items():
            if not field.startswith("rel_") or not isinstance(value, list):
                continue
            for item in value:
                if isinstance(item, str) and "|" in item:
                    target_id = item.rsplit("|", 1)[-1].rstrip("]")
                    referenced.add(target_id)
                    relation_references.append((record.path, field, target_id))
    for identifier, paths in sorted(identifiers.items()):
        if len(paths) > 1:
            for path in paths:
                findings.append(HealthFinding("KB_HEALTH_DUPLICATE_ID", "error", path.relative_to(root).as_posix(), identifier, "duplicate stable identity"))
    for path, field, target_id in relation_references:
        if target_id not in identifiers:
            findings.append(HealthFinding("KB_HEALTH_DANGLING_RELATION", "error", path.relative_to(root).as_posix(), target_id, f"{field} references a missing identity"))
    threshold = (today or date.today()) - timedelta(days=stale_days)
    for record in records:
        path = record.path.relative_to(root).as_posix()
        identifier = record.metadata.get("id")
        stable_id = identifier if isinstance(identifier, str) else None
        status = record.metadata.get("status")
        if status == "conflicted":
            findings.append(HealthFinding("KB_HEALTH_UNRESOLVED_CONFLICT", "review_required", path, stable_id, "conflicted knowledge requires owner review"))
        if status == "approved" and not record.metadata.get("sources") and not _has_body_sources(record.body):
            findings.append(HealthFinding("KB_HEALTH_UNVERIFIED_SOURCE", "error", path, stable_id, "approved knowledge has no sources"))
        updated = record.metadata.get("last_updated")
        if isinstance(updated, str):
            try:
                if date.fromisoformat(updated) < threshold:
                    findings.append(HealthFinding("KB_HEALTH_STALE", "warning", path, stable_id, f"last_updated is older than {stale_days} days"))
            except ValueError:
                pass
        if stable_id and stable_id not in referenced and not any(
            field.startswith("rel_") for field in record.metadata
        ):
            findings.append(HealthFinding("KB_HEALTH_ORPHAN", "warning", path, stable_id, "knowledge item has no declared relationships"))
    graph_path = root / ".obsidian" / "graph.json"
    if graph_path.is_file():
        try:
            graph = read_graph(graph_path)
            groups = graph.get("colorGroups", [])
            queries = [
                group.get("query") for group in groups
                if isinstance(group, dict) and isinstance(group.get("query"), str)
            ] if isinstance(groups, list) else []
            for document_type in sorted({str(record.metadata.get("type")) for record in records}):
                expected = type_query(document_type)
                if document_type not in TYPE_COLORS:
                    findings.append(HealthFinding("KB_OBSIDIAN_COLOR_TYPE_UNKNOWN", "error", ".obsidian/graph.json", None, f"no managed color for type: {document_type}"))
                elif queries.count(expected) != 1:
                    findings.append(HealthFinding("KB_OBSIDIAN_COLOR_COVERAGE", "error", ".obsidian/graph.json", None, f"type must have exactly one managed color group: {document_type}"))
        except (OSError, ValueError) as error:
            findings.append(HealthFinding("KB_OBSIDIAN_GRAPH_INVALID", "error", ".obsidian/graph.json", None, str(error)))
    manifest = root / "knowledge-base.yaml"
    if manifest.is_file():
        text = manifest.read_text(encoding="utf-8")
        for authority in ("overview", "features", "technical_baseline", "evidence", "collaboration"):
            if f"  {authority}:" not in text:
                findings.append(HealthFinding("KB_HEALTH_AUTHORITY_GAP", "error", "knowledge-base.yaml", None, f"missing authority entry: {authority}"))
    ordered = tuple(sorted(findings, key=lambda item: (item.severity, item.code, item.path, item.identifier or "")))
    return HealthReport("healthy" if not ordered else "findings", ordered, len(records))
