"""验证规格就绪度、内嵌验收场景、接口粒度和变更增量。"""

from __future__ import annotations

from collections.abc import Iterable
import re

from .model import DocumentRecord, Issue
from .relations import RelationIndex


def _as_list(value: object) -> list[str]:
    """把可选标量或列表规范化为字符串列表。"""

    if isinstance(value, list):
        return [str(item) for item in value]
    if value in {None, ""}:
        return []
    return [str(value)]


def _registered(value: object) -> bool:
    """判断元数据值是否已填写且不是约定占位符。"""

    return isinstance(value, str) and bool(value.strip()) and value.strip() not in {
        "待确认",
        "—",
        "-",
    }


def validate_specifications(
    records: Iterable[DocumentRecord],
    relation_index: RelationIndex | None = None,
) -> list[Issue]:
    """执行只依赖结构化知识和稳定 Markdown 标题的规格检查。"""

    materialized = [record for record in records if record.metadata]
    ids = {
        str(record.metadata["id"]): record
        for record in materialized
        if isinstance(record.metadata.get("id"), str)
    }
    issues: list[Issue] = []
    acceptance_ids: set[str] = set()
    for record in materialized:
        if record.metadata.get("type") == "feature":
            acceptance_ids.update(_as_list(record.metadata.get("acceptance")))
    features_by_requirement: dict[str, set[str]] = {}
    if relation_index is not None:
        for edge in relation_index.edges:
            if edge.field == "rel_satisfies":
                features_by_requirement.setdefault(edge.target.identifier, set()).add(
                    edge.source.identifier
                )

    for record in materialized:
        metadata = record.metadata
        readiness = metadata.get("spec_readiness")
        questions = _as_list(metadata.get("blocking_questions"))
        if readiness == "blocked" and not questions:
            issues.append(
                Issue("KB_SPEC_BLOCKER_REQUIRED", record.path, "blocked specification requires blocking_questions")
            )
        if readiness == "ready" and questions:
            issues.append(
                Issue("KB_SPEC_READY_BLOCKED", record.path, "ready specification cannot retain blocking_questions")
            )

        kind = metadata.get("type")
        if readiness == "ready" and kind == "feature":
            if " MUST " not in record.body and " SHALL " not in record.body:
                issues.append(
                    Issue("KB_SPEC_NORMATIVE", record.path, "ready feature lacks MUST or SHALL behavior")
                )
            if "#### 场景" not in record.body and "#### Scenario" not in record.body:
                issues.append(
                    Issue("KB_SPEC_SCENARIO", record.path, "ready feature lacks a level-four acceptance scenario")
                )
            required_design_sections = ("## 功能设计", "### 设计概述", "### 异常、边界与降级", "### 技术对象与影响")
            for heading in required_design_sections:
                if heading not in record.body:
                    issues.append(
                        Issue("KB_SPEC_FEATURE_DESIGN", record.path, f"ready feature lacks design section: {heading}")
                    )
            if "### 处理流程" not in record.body and "### 输入、输出与状态变化" not in record.body:
                issues.append(
                    Issue("KB_SPEC_FEATURE_DESIGN", record.path, "ready feature requires process flow or state transition design")
                )
            declared = set(_as_list(metadata.get("acceptance")))
            headings = set(re.findall(r"^#### (?:场景|Scenario)\s+((?:AC-[A-Z0-9]+-[0-9]{3}|(?:F\d{2}|KB)-AC-\d{2}))[：:]", record.body, re.MULTILINE))
            if not declared:
                issues.append(
                    Issue("KB_SPEC_COVERAGE", record.path, "ready feature requires declared embedded acceptance scenarios")
                )
            if declared != headings:
                issues.append(
                    Issue("KB_SPEC_SCENARIO_COVERAGE", record.path, "feature acceptance ids must exactly match embedded scenario headings")
                )
            sections = re.split(r"(?=^#### (?:场景|Scenario)\s+(?:AC-[A-Z0-9]+-[0-9]{3}|(?:F\d{2}|KB)-AC-\d{2})[：:])", record.body, flags=re.MULTILINE)[1:]
            for section in sections:
                if not all(marker in section for marker in ("GIVEN", "WHEN", "THEN")) or not re.search(r"验证方式|Verification", section):
                    issues.append(
                        Issue("KB_SPEC_SCENARIO_SECTION", record.path, "embedded scenario requires GIVEN, WHEN, THEN, and verification method")
                    )
                    break
        if readiness == "ready" and kind == "requirement":
            for field in ("stakeholders", "business_rules", "success_criteria"):
                if not _as_list(metadata.get(field)):
                    issues.append(
                        Issue("KB_SPEC_REQUIREMENT", record.path, f"ready requirement lacks {field}")
                    )
            identifier = metadata.get("id")
            if relation_index is not None and identifier not in features_by_requirement:
                issues.append(
                    Issue("KB_COVERAGE_REQUIREMENT", record.path, "ready requirement is not satisfied by a feature")
                )
        if readiness == "ready" and kind == "feature" and relation_index is not None:
            identifier = metadata.get("id")
            implementation_relations = {
                "rel_primary_module", "rel_participating_modules", "rel_exposes",
                "rel_calls", "rel_reads", "rel_writes", "rel_depends_on",
            }
            if not any(
                edge.field in implementation_relations
                for edge in relation_index.outgoing(str(identifier))
            ):
                issues.append(
                    Issue("KB_COVERAGE_IMPLEMENTATION", record.path, "ready feature lacks module or technical-object coverage")
                )
        if kind == "task":
            identifier = str(metadata.get("id", ""))
            feature = metadata.get("feature")
            executes_change = bool(
                relation_index
                and any(
                    edge.field == "rel_executes"
                    for edge in relation_index.outgoing(identifier)
                )
            )
            if not (isinstance(feature, str) and feature in ids) and not executes_change:
                issues.append(
                    Issue(
                        "KB_COVERAGE_TASK_ORIGIN",
                        record.path,
                        "external task must trace to a feature or specification change",
                    )
                )
            if "## 验证" not in record.body and "## Verification" not in record.body:
                issues.append(
                    Issue(
                        "KB_COVERAGE_TASK_VERIFICATION",
                        record.path,
                        "external task must describe its verification method",
                    )
                )
            declared_acceptance = set(_as_list(metadata.get("acceptance")))
            if acceptance_ids and not declared_acceptance.intersection(acceptance_ids):
                issues.append(
                    Issue(
                        "KB_COVERAGE_TASK_ACCEPTANCE",
                        record.path,
                        "external task is not linked to an embedded acceptance scenario",
                    )
                )
        if kind == "interface":
            identifier = str(metadata.get("id", ""))
            title = str(metadata.get("title", ""))
            if title == identifier or record.path.stem == identifier or not record.path.stem.startswith(identifier + "-"):
                issues.append(
                    Issue("KB_INTERFACE_NAME", record.path, "interface filename and title require a human-readable business name")
                )
            endpoint_rows = re.findall(r"^\|\s*(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s*\|", record.body, re.MULTILINE | re.IGNORECASE)
            if len(endpoint_rows) > 1:
                issues.append(
                    Issue("KB_INTERFACE_AGGREGATE", record.path, "one interface file cannot aggregate multiple HTTP endpoints")
                )

        if kind != "specification_delta":
            continue

        change_id = metadata.get("change_id")
        if not isinstance(change_id, str) or ids.get(change_id, DocumentRecord(record.path, {}, "")).metadata.get("type") != "specification_change":
            issues.append(Issue("KB_DELTA_CHANGE", record.path, f"unknown specification change: {change_id}"))

        target_id = metadata.get("target_id")
        operation = metadata.get("operation")
        if operation == "added":
            if isinstance(target_id, str) and target_id in ids:
                issues.append(Issue("KB_DELTA_TARGET_EXISTS", record.path, f"ADDED target already exists: {target_id}"))
        elif not isinstance(target_id, str) or target_id not in ids:
            issues.append(Issue("KB_DELTA_TARGET_MISSING", record.path, f"delta target does not exist: {target_id}"))

        expected_heading = {
            "added": "## ADDED Requirements",
            "modified": "## MODIFIED Requirements",
            "removed": "## REMOVED Requirements",
            "renamed": "## RENAMED Requirements",
            "superseded": "## SUPERSEDED Requirements",
        }.get(str(operation))
        if expected_heading and expected_heading not in record.body:
            issues.append(Issue("KB_DELTA_SECTION", record.path, f"missing delta section: {expected_heading}"))

        if operation == "removed":
            for field in ("reason", "migration", "rollback"):
                if not _registered(metadata.get(field)):
                    issues.append(Issue("KB_DELTA_MIGRATION", record.path, f"REMOVED delta lacks {field}"))
        if operation in {"renamed", "superseded"} and not _registered(metadata.get("replacement_id")):
            issues.append(Issue("KB_DELTA_REPLACEMENT", record.path, f"{operation} delta lacks replacement_id"))

    return issues
