"""解析知识文档使用的受限 YAML 文档头。"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .model import DocumentRecord


class FrontMatterError(ValueError):
    """表示文档头缺失、截断或字段格式不受支持。"""


MAPPING_ITEM_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*\s*:")


def _unquote_scalar(value: str) -> str:
    """去除简单标量两端成对的单引号或双引号。"""

    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parse_scalar(value: str) -> str | list[str]:
    """把受支持的标量或行内列表转换为 Python 值。"""

    if value.startswith("[") and value.endswith("]"):
        body = value[1:-1].strip()
        return (
            []
            if not body
            else [_unquote_scalar(item.strip()) for item in body.split(",")]
        )
    return _unquote_scalar(value)


def parse_document(path: Path) -> DocumentRecord:
    """读取 Markdown 文件并分离元数据和正文。"""

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return DocumentRecord(path=path, metadata={}, body="".join(lines))

    metadata: dict[str, object] = {}
    closing_index: int | None = None
    pending_list_key: str | None = None
    pending_mapping: dict[str, object] | None = None
    for index, raw_line in enumerate(lines[1:], start=1):
        line = raw_line.rstrip("\r\n")
        if line == "---":
            if pending_list_key and not metadata[pending_list_key]:
                raise FrontMatterError(
                    f"{path}:{index + 1}: empty block list is unsupported"
                )
            closing_index = index
            break
        if line.startswith("    "):
            if pending_mapping is None or ":" not in line:
                raise FrontMatterError(f"{path}:{index + 1}: unsupported nested metadata")
            key, value = (part.strip() for part in line.split(":", maxsplit=1))
            if not key or not value or key in pending_mapping:
                raise FrontMatterError(f"{path}:{index + 1}: invalid nested mapping field")
            pending_mapping[key] = _parse_scalar(value)
            continue
        if line.startswith("  - "):
            if pending_list_key is None:
                raise FrontMatterError(
                    f"{path}:{index + 1}: nested metadata is unsupported"
                )
            item = line[4:].strip()
            if not item:
                raise FrontMatterError(
                    f"{path}:{index + 1}: nested metadata is unsupported"
                )
            pending_values = metadata[pending_list_key]
            if not isinstance(pending_values, list):
                raise FrontMatterError(
                    f"{path}:{index + 1}: mixed scalar and list metadata"
                )
            if MAPPING_ITEM_PATTERN.match(item):
                if pending_list_key != "sources":
                    raise FrontMatterError(
                        f"{path}:{index + 1}: nested metadata is unsupported"
                    )
                key, nested_value = (part.strip() for part in item.split(":", maxsplit=1))
                if not nested_value:
                    raise FrontMatterError(f"{path}:{index + 1}: empty nested mapping value")
                pending_mapping = {key: _parse_scalar(nested_value)}
                pending_values.append(pending_mapping)
            else:
                pending_mapping = None
                pending_values.append(_unquote_scalar(item))
            continue
        if line.startswith((" ", "\t", "- ")):
            raise FrontMatterError(f"{path}:{index + 1}: nested metadata is unsupported")
        if pending_list_key is not None:
            if not metadata[pending_list_key]:
                raise FrontMatterError(
                    f"{path}:{index + 1}: empty block list is unsupported"
                )
            pending_list_key = None
            pending_mapping = None
        if ":" not in line:
            raise FrontMatterError(f"{path}:{index + 1}: expected key: value")
        key, value = (part.strip() for part in line.split(":", maxsplit=1))
        if not key:
            raise FrontMatterError(f"{path}:{index + 1}: empty metadata key")
        if key in metadata:
            raise FrontMatterError(f"{path}:{index + 1}: duplicate metadata key: {key}")
        if not value:
            metadata[key] = []
            pending_list_key = key
        else:
            metadata[key] = _parse_scalar(value)

    if closing_index is None:
        raise FrontMatterError(f"{path}: missing closing front matter delimiter")

    return DocumentRecord(
        path=path,
        metadata=metadata,
        body="".join(lines[closing_index + 1 :]),
    )
