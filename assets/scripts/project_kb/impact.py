"""沿关系反向索引生成只读的三级知识变化影响清单。"""

# context-atlas-rules: [[rules/知识治理规则#RULE-IMPACT-002|RULE-IMPACT-002]]

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path

from .relation_catalog import RelationCatalog
from .relations import RelationIndex


LEVEL_ORDER = {"required": 0, "review_required": 1, "informational": 2}


@dataclass(frozen=True)
class ImpactItem:
    """描述一个受变化波及的知识项及其关系、等级和传播深度。"""

    changed_id: str
    affected_id: str
    relation: str
    level: str
    depth: int
    source_path: Path
    affected_path: Path


def _indirect_level(level: str, depth: int) -> str:
    """限制间接影响的自动结论，避免把不确定传播升级为必改。"""

    if depth > 1 and level == "required":
        return "review_required"
    return level


def analyze_impact(
    index: RelationIndex,
    catalog: RelationCatalog,
    changed_id: str,
    change_type: str,
    max_depth: int = 2,
) -> list[ImpactItem]:
    """从变化知识项反向遍历消费者并返回稳定排序的影响项。"""

    if max_depth < 1:
        return []
    changed_target = index.target(changed_id)
    if changed_target is None:
        return []

    impacts: list[ImpactItem] = []
    shortest_depth: dict[str, int] = {changed_id: 0}
    pending: deque[tuple[str, int]] = deque([(changed_id, 0)])
    while pending:
        current_id, current_depth = pending.popleft()
        next_depth = current_depth + 1
        if next_depth > max_depth:
            continue
        for edge in index.incoming(current_id):
            affected_id = edge.source.identifier
            if affected_id == changed_id:
                continue
            previous_depth = shortest_depth.get(affected_id)
            if previous_depth is not None and previous_depth < next_depth:
                continue
            level = _indirect_level(
                catalog.impact_level(edge.field, change_type), next_depth
            )
            impacts.append(
                ImpactItem(
                    changed_id=changed_id,
                    affected_id=affected_id,
                    relation=edge.field,
                    level=level,
                    depth=next_depth,
                    source_path=changed_target.path,
                    affected_path=edge.source.path,
                )
            )
            if previous_depth is None or next_depth < previous_depth:
                shortest_depth[affected_id] = next_depth
                pending.append((affected_id, next_depth))

    return sorted(
        impacts,
        key=lambda item: (
            LEVEL_ORDER[item.level],
            item.depth,
            item.affected_id,
            item.relation,
        ),
    )
