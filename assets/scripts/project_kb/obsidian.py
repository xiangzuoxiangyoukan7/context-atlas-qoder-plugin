"""集中生成并质检 Context Atlas 管理的 Obsidian 类型颜色组。"""

from __future__ import annotations

import json
from pathlib import Path


TYPE_COLORS: dict[str, int] = {
    "knowledge_index": 10027212,
    "overview_document": 14069084,
    "requirement": 14701138,
    "feature": 4360181,
    "architecture": 14048348,
    "module": 39423,
    "interface": 16753920,
    "database_namespace": 3447003,
    "database_unit": 3447003,
    "database_table": 3447003,
    "data_source": 3447003,
    "data_asset": 16766720,
    "specification_change": 10040012,
    "specification_delta": 10040012,
    "acceptance": 6084269,
    "acceptance_evidence": 6084269,
    "knowledge_proposal": 10040012,
    "knowledge_item": 10027212,
    "managed_source": 11392604,
    "source": 11392604,
    "governance_document": 6073814,
    "governance_task": 6073814,
    "task": 6073814,
}


def type_query(document_type: str) -> str:
    """返回一个知识类型的稳定 Obsidian 属性查询。"""

    return f"[type:{document_type}]"


def managed_color_groups() -> list[dict[str, object]]:
    """按稳定类型顺序返回 Context Atlas 管理的颜色组。"""

    return [
        {"query": type_query(document_type), "color": {"a": 1, "rgb": rgb}}
        for document_type, rgb in TYPE_COLORS.items()
    ]


def default_graph_settings() -> dict[str, object]:
    """返回不含个人工作区状态的最小图谱配置。"""

    return {
        "collapse-filter": False,
        "search": '-path:"90-历史归档"',
        "showTags": False,
        "showAttachments": False,
        "hideUnresolved": False,
        "showOrphans": True,
        "collapse-color-groups": False,
        "colorGroups": managed_color_groups(),
        "collapse-display": True,
        "showArrow": True,
        "textFadeMultiplier": 0,
        "nodeSizeMultiplier": 1,
        "lineSizeMultiplier": 1,
        "collapse-forces": True,
        "centerStrength": 0.5,
        "repelStrength": 10,
        "linkStrength": 1,
        "linkDistance": 250,
        "scale": 1,
        "close": False,
    }


def merge_graph_settings(current: dict[str, object]) -> dict[str, object]:
    """更新受管类型颜色，保留用户颜色组和其他 Obsidian 设置。"""

    managed_queries = {type_query(document_type) for document_type in TYPE_COLORS}
    raw_groups = current.get("colorGroups", [])
    custom_groups = [
        group for group in raw_groups
        if isinstance(group, dict) and group.get("query") not in managed_queries
    ] if isinstance(raw_groups, list) else []
    merged = dict(current)
    merged["colorGroups"] = [*managed_color_groups(), *custom_groups]
    return merged


def graph_text(current: dict[str, object] | None = None) -> str:
    """序列化新建或合并后的图谱配置。"""

    payload = default_graph_settings() if current is None else merge_graph_settings(current)
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def read_graph(path: Path) -> dict[str, object]:
    """读取并要求 graph.json 的根节点为对象。"""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Obsidian graph.json root must be an object")
    return payload
