"""解析、校验并规范化初始化 Proposal。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any


REVISION_RE = re.compile(r"^sha256:[a-f0-9]{64}$")
SAFE_ID_RE = re.compile(r"^[A-Z]+-[0-9]{3}$")
OPEN_ID_RE = re.compile(r"^(?:UNKNOWN|CONFLICT)-[0-9]{3}$")
SOURCE_TYPES = {
    "repository_file",
    "user_statement",
    "existing_document",
    "command_output",
    "ai_inference",
}
FACT_GROUPS = {
    "goals",
    "boundaries_in",
    "boundaries_out",
    "technology_stacks",
    "terms",
    "capabilities",
    "features",
    "modules",
    "interfaces",
    "databases",
    "external_dependencies",
    "tests",
    "adrs",
}


def canonical_revision(proposal: dict[str, Any]) -> str:
    """根据不含 revision 字段的规范 JSON 计算稳定摘要。"""

    payload = dict(proposal)
    payload.pop("proposal_revision", None)
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _object(value: object, label: str, allowed: set[str], required: set[str]) -> dict[str, Any]:
    """要求对象仅包含允许字段并具备全部必填字段。"""

    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - allowed)
    if missing:
        raise ValueError(f"{label} missing fields: {missing}")
    if unknown:
        raise ValueError(f"{label} has unknown fields: {unknown}")
    return value


def _text(value: object, label: str) -> str:
    """要求值为不含空字节的非空文本。"""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    if "\x00" in value:
        raise ValueError(f"{label} contains a null byte")
    return value.strip()


def _source(value: object, label: str) -> dict[str, str]:
    """校验事实来源类型和可回查引用。"""

    source = _object(
        value, label,
        {"type", "reference", "observed_at", "confirmation_status", "confirmed_at"},
        {"type", "reference", "observed_at", "confirmation_status"},
    )
    source_type = _text(source["type"], f"{label}.type")
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"{label}.type is unsupported")
    confirmation_status = _text(source["confirmation_status"], f"{label}.confirmation_status")
    if confirmation_status not in {"observed", "confirmed"}:
        raise ValueError(f"{label}.confirmation_status is unsupported")
    normalized = {
        "type": source_type,
        "reference": _text(source["reference"], f"{label}.reference"),
        "observed_at": _text(source["observed_at"], f"{label}.observed_at"),
        "confirmation_status": confirmation_status,
    }
    if "confirmed_at" in source:
        normalized["confirmed_at"] = _text(source["confirmed_at"], f"{label}.confirmed_at")
    if confirmation_status == "confirmed" and "confirmed_at" not in normalized:
        raise ValueError(f"{label}.confirmed_at is required when confirmed")
    return normalized


def _fact(value: object, label: str, extra: set[str] | None = None) -> dict[str, Any]:
    """校验公共事实字段并阻止确认 AI 推测。"""

    extras = extra or set()
    fact = _object(
        value,
        label,
        {"id", "value", "status", "source"} | extras,
        {"id", "value", "status", "source"} | extras,
    )
    fact_id = _text(fact["id"], f"{label}.id")
    if not SAFE_ID_RE.fullmatch(fact_id):
        raise ValueError(f"{label}.id has an invalid format")
    status = _text(fact["status"], f"{label}.status")
    if status not in {"confirmed", "proposed"}:
        raise ValueError(f"{label}.status is unsupported")
    source = _source(fact["source"], f"{label}.source")
    if status == "confirmed" and source["type"] == "ai_inference":
        raise ValueError(f"{label} cannot confirm an AI inference")
    normalized: dict[str, Any] = {
        "id": fact_id,
        "value": _text(fact["value"], f"{label}.value"),
        "status": status,
        "source": source,
    }
    return normalized


def _list(value: object, label: str) -> list[object]:
    """要求值为数组并返回数组成员。"""

    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def validate_initialization_proposal(proposal: object) -> dict[str, Any]:
    """校验初始化 Proposal，并返回可供渲染的规范化对象。"""

    root = _object(
        proposal,
        "proposal",
        {"operation", "proposal_revision", "project", "facts", "unknowns", "conflicts"},
        {"operation", "proposal_revision", "project", "facts", "unknowns", "conflicts"},
    )
    if root["operation"] != "initialize":
        raise ValueError("proposal.operation must be initialize")
    revision = _text(root["proposal_revision"], "proposal.proposal_revision")
    if not REVISION_RE.fullmatch(revision) or revision != canonical_revision(root):
        raise ValueError("proposal revision does not match canonical content")

    project = _object(
        root["project"],
        "proposal.project",
        {"root", "id", "name", "knowledge_base_name", "workspace_profile"},
        {"root", "id", "name", "knowledge_base_name"},
    )
    project_id = _text(project["id"], "proposal.project.id")
    if project_id in {".", ".."} or "/" in project_id or "\\" in project_id:
        raise ValueError("proposal.project.id must be one safe directory segment")
    knowledge_base_name = _text(project["knowledge_base_name"], "proposal.project.knowledge_base_name")
    if knowledge_base_name != f"doc-{project_id}":
        raise ValueError("knowledge_base_name must equal doc-<project.id>")
    workspace_profile = _text(
        project.get("workspace_profile", "standard"),
        "proposal.project.workspace_profile",
    )
    if workspace_profile not in {"standard", "obsidian"}:
        raise ValueError("proposal.project.workspace_profile is unsupported")

    facts = _object(root["facts"], "proposal.facts", FACT_GROUPS, FACT_GROUPS)
    normalized_facts: dict[str, list[dict[str, Any]]] = {}
    for group in (
        "goals", "boundaries_in", "boundaries_out", "terms", "capabilities",
        "features", "modules", "interfaces", "databases",
        "external_dependencies", "tests", "adrs",
    ):
        normalized_facts[group] = [
            _fact(item, f"proposal.facts.{group}[{index}]")
            for index, item in enumerate(_list(facts[group], f"proposal.facts.{group}"))
        ]

    technology_fields = {"name", "version", "location", "purpose", "commands", "configuration"}
    normalized_facts["technology_stacks"] = []
    for index, item in enumerate(_list(facts["technology_stacks"], "proposal.facts.technology_stacks")):
        label = f"proposal.facts.technology_stacks[{index}]"
        normalized = _fact(item, label, technology_fields)
        assert isinstance(item, dict)
        for field in technology_fields - {"commands"}:
            normalized[field] = _text(item[field], f"{label}.{field}")
        normalized["commands"] = [
            _text(command, f"{label}.commands") for command in _list(item["commands"], f"{label}.commands")
        ]
        normalized_facts["technology_stacks"].append(normalized)

    def open_items(key: str) -> list[dict[str, str]]:
        """校验未知项或冲突项的固定字段。"""

        result: list[dict[str, str]] = []
        for index, item in enumerate(_list(root[key], f"proposal.{key}")):
            label = f"proposal.{key}[{index}]"
            value = _object(item, label, {"id", "question", "owner_action"}, {"id", "question", "owner_action"})
            item_id = _text(value["id"], f"{label}.id")
            if not OPEN_ID_RE.fullmatch(item_id):
                raise ValueError(f"{label}.id has an invalid format")
            result.append({
                "id": item_id,
                "question": _text(value["question"], f"{label}.question"),
                "owner_action": _text(value["owner_action"], f"{label}.owner_action"),
            })
        return result

    return {
        "operation": "initialize",
        "proposal_revision": revision,
        "project": {
            "root": str(Path(_text(project["root"], "proposal.project.root")).resolve()),
            "id": project_id,
            "name": _text(project["name"], "proposal.project.name"),
            "knowledge_base_name": knowledge_base_name,
            "workspace_profile": workspace_profile,
        },
        "facts": normalized_facts,
        "unknowns": open_items("unknowns"),
        "conflicts": open_items("conflicts"),
    }
