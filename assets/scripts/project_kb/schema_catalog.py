"""加载简化 JSON Schema 目录并验证知识元数据。"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import json
from typing import Mapping

from .model import Issue


@dataclass(frozen=True)
class SchemaCatalog:
    """保存按知识类型索引的受控 Schema 定义。"""

    root: Path
    schemas: dict[str, dict[str, object]]

    @classmethod
    def load(cls, root: Path) -> SchemaCatalog:
        """从目录文件加载所有已登记 Schema。"""

        resolved_root = root.resolve()
        catalog_path = resolved_root / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        if not isinstance(catalog, dict):
            raise ValueError(f"schema catalog must be an object: {catalog_path}")

        schemas: dict[str, dict[str, object]] = {}
        for kind, relative in catalog.items():
            candidate = (resolved_root / str(relative)).resolve()
            if resolved_root not in candidate.parents:
                raise ValueError(f"schema escapes root: {relative}")
            schema = json.loads(candidate.read_text(encoding="utf-8"))
            if not isinstance(schema, dict):
                raise ValueError(f"schema must be an object: {candidate}")
            schemas[str(kind)] = schema
        return cls(root=resolved_root, schemas=schemas)

    def validate(
        self,
        kind: str,
        metadata: Mapping[str, object],
        path: Path,
    ) -> list[Issue]:
        """按必填、枚举、模式和列表约束验证元数据。"""

        schema = self.schemas.get(kind)
        if schema is None:
            return [Issue("KB_SCHEMA_KIND", path, f"unknown schema kind: {kind}")]

        issues: list[Issue] = []
        for field in schema.get("forbidden", []):
            if field in metadata:
                issues.append(
                    Issue("KB_SCHEMA_FORBIDDEN", path, f"forbidden field: {field}")
                )
        for field in schema.get("required", []):
            if field not in metadata:
                issues.append(
                    Issue("KB_SCHEMA_REQUIRED", path, f"missing required field: {field}")
                )
        for field, allowed in schema.get("enums", {}).items():
            if field in metadata and metadata[field] not in allowed:
                issues.append(
                    Issue("KB_SCHEMA_ENUM", path, f"invalid {field}: {metadata[field]!r}")
                )
        for field, allowed in schema.get("list_enums", {}).items():
            value = metadata.get(field)
            if field not in metadata:
                continue
            if not isinstance(value, list):
                issues.append(Issue("KB_SCHEMA_LIST", path, f"{field} must be a list"))
                continue
            invalid = [item for item in value if item not in allowed]
            if invalid:
                issues.append(
                    Issue(
                        "KB_SCHEMA_ENUM",
                        path,
                        f"invalid {field} values: {invalid!r}",
                    )
                )
        for field, pattern in schema.get("patterns", {}).items():
            value = metadata.get(field)
            if isinstance(value, str) and re.fullmatch(str(pattern), value) is None:
                issues.append(
                    Issue("KB_SCHEMA_PATTERN", path, f"invalid {field}: {value!r}")
                )
        for field in schema.get("non_empty_lists", []):
            value = metadata.get(field)
            if not isinstance(value, list) or not value:
                issues.append(
                    Issue("KB_SCHEMA_LIST", path, f"{field} must be a non-empty list")
                )
        for field in schema.get("unique_lists", []):
            value = metadata.get(field)
            if isinstance(value, list) and len(value) != len({json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value}):
                issues.append(
                    Issue("KB_SCHEMA_LIST", path, f"{field} must contain unique values")
                )
        return issues
