"""加载受控关系定义和确定性变化影响规则。"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


ALLOWED_DIRECTIONS = frozenset({"forward_only"})
ALLOWED_STATUSES = frozenset({"active", "reserved", "deprecated"})
ALLOWED_IMPACT_LEVELS = frozenset(
    {"required", "review_required", "informational"}
)


def _string_set(value: object, field: str) -> frozenset[str]:
    """把非空字符串列表转换为不可变集合，否则拒绝目录。"""

    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty list")
    items = frozenset(item for item in value if isinstance(item, str) and item)
    if len(items) != len(value):
        raise ValueError(f"{field} must contain unique non-empty strings")
    return items


@dataclass(frozen=True)
class RelationDefinition:
    """描述一种关系的名称、合法端点、方向和影响规则。"""

    field: str
    name_zh: str
    source_prefixes: frozenset[str]
    target_prefixes: frozenset[str]
    direction: str
    status: str
    default_impact: str
    impact_rules: dict[str, str]


@dataclass(frozen=True)
class RelationCatalog:
    """保存按 `rel_*` 字段索引的唯一受控关系目录。"""

    path: Path
    relations: dict[str, RelationDefinition]

    @classmethod
    def load(cls, path: Path) -> RelationCatalog:
        """从 JSON 文件加载目录并拒绝缺字段、重复项和非法枚举。"""

        resolved = path.resolve()
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ValueError("relation catalog version must be 1")
        raw_relations = payload.get("relations")
        if not isinstance(raw_relations, list) or not raw_relations:
            raise ValueError("relation catalog must contain relations")

        relations: dict[str, RelationDefinition] = {}
        for raw in raw_relations:
            if not isinstance(raw, dict):
                raise ValueError("relation definition must be an object")
            field = raw.get("field")
            name_zh = raw.get("name_zh")
            direction = raw.get("direction")
            status = raw.get("status")
            default_impact = raw.get("default_impact")
            impact_rules = raw.get("impact_rules")
            if not isinstance(field, str) or not field.startswith("rel_"):
                raise ValueError("relation field must start with rel_")
            if field in relations:
                raise ValueError(f"duplicate relation field: {field}")
            if not isinstance(name_zh, str) or not name_zh.strip():
                raise ValueError(f"relation name_zh is required: {field}")
            if direction not in ALLOWED_DIRECTIONS:
                raise ValueError(f"invalid relation direction: {field}")
            if status not in ALLOWED_STATUSES:
                raise ValueError(f"invalid relation status: {field}")
            if default_impact not in ALLOWED_IMPACT_LEVELS:
                raise ValueError(f"invalid default impact: {field}")
            if not isinstance(impact_rules, dict) or any(
                not isinstance(change_type, str)
                or not change_type
                or level not in ALLOWED_IMPACT_LEVELS
                for change_type, level in impact_rules.items()
            ):
                raise ValueError(f"invalid impact rules: {field}")
            relations[field] = RelationDefinition(
                field=field,
                name_zh=name_zh,
                source_prefixes=_string_set(
                    raw.get("source_prefixes"), "source_prefixes"
                ),
                target_prefixes=_string_set(
                    raw.get("target_prefixes"), "target_prefixes"
                ),
                direction=direction,
                status=status,
                default_impact=default_impact,
                impact_rules={str(key): str(value) for key, value in impact_rules.items()},
            )
        return cls(path=resolved, relations=relations)

    def get(self, field: str) -> RelationDefinition | None:
        """返回字段定义；未登记字段返回空值供验证器生成定位问题。"""

        return self.relations.get(field)

    def impact_level(self, field: str, change_type: str) -> str:
        """返回关系与变化类型组合的等级，未知变化安全降级为人工复核。"""

        definition = self.get(field)
        if definition is None:
            raise KeyError(field)
        return definition.impact_rules.get(change_type, definition.default_impact)
