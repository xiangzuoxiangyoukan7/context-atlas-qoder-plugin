"""定义检查器跨模块共享的不可变数据模型。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Issue:
    """表示具有代码、路径和可选位置的验证问题。"""

    code: str
    path: Path
    message: str
    location: str | None = None


@dataclass(frozen=True)
class DocumentRecord:
    """表示已解析的 Markdown 知识记录。"""

    path: Path
    metadata: dict[str, object]
    body: str


@dataclass(frozen=True)
class KnowledgeTarget:
    """表示可被关系链接精确定位的文档或聚合文档知识项。"""

    identifier: str
    path: Path
    anchor: str | None
    kind: str


@dataclass(frozen=True)
class RelationEdge:
    """表示从使用方知识指向基础知识的单条权威正向关系。"""

    field: str
    source: KnowledgeTarget
    target: KnowledgeTarget
