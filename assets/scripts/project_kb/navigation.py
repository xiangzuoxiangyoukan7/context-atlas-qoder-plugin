"""提供知识库目录树与关系图的渐进式只读导航。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .discovery import discover_records
from .frontmatter import FrontMatterError, parse_document
from .model import DocumentRecord, KnowledgeTarget, RelationEdge
from .relation_catalog import RelationCatalog
from .relations import RelationIndex


EXCLUDED_DIRECTORIES = frozenset({".obsidian", "Excalidraw", "Clippings", ".project-kb"})
GRAPH_EXCLUDED_DIRECTORIES = EXCLUDED_DIRECTORIES | frozenset({"90-历史归档"})
ALLOWED_DIRECTIONS = frozenset({"outgoing", "incoming", "both"})


@dataclass(frozen=True)
class NeighborNode:
    """表示无需加载正文即可判断相关性的知识节点摘要。"""

    id: str
    type: str
    title: str
    status: str | None
    path: str
    anchor: str | None


@dataclass(frozen=True)
class NeighborEdge:
    """表示相对于查询节点的一条相邻关系。"""

    direction: str
    relation: str
    relation_name: str
    node: NeighborNode


@dataclass(frozen=True)
class NeighborReport:
    """表示确定性的一跳邻接查询结果。"""

    operation: str
    knowledge_base: str
    node: NeighborNode
    outgoing: tuple[NeighborEdge, ...]
    incoming: tuple[NeighborEdge, ...]
    depth: int = 1


@dataclass(frozen=True)
class TreeNode:
    """表示目录树中无需加载完整正文的目录或文件摘要。"""

    kind: str
    path: str
    title: str
    description: str | None
    id: str | None
    type: str | None
    status: str | None
    child_count: int | None


@dataclass(frozen=True)
class ChildrenReport:
    """表示一个目录节点及其直接子节点。"""

    operation: str
    knowledge_base: str
    node: TreeNode
    children: tuple[TreeNode, ...]
    depth: int = 1


@dataclass(frozen=True)
class GraphEdge:
    """表示关系图中的一条有向边。"""

    relation: str
    relation_name: str
    source: str
    target: str


@dataclass(frozen=True)
class GraphReport:
    """表示从起点展开的子图或显式请求的完整关系图。"""

    operation: str
    knowledge_base: str
    mode: str
    start: str | None
    depth: int | None
    max_nodes: int
    truncated: bool
    nodes: tuple[NeighborNode, ...]
    edges: tuple[GraphEdge, ...]


def _issue_message(issues: Iterable[object]) -> str:
    """把发现或关系问题整理为稳定的失败消息。"""

    return "; ".join(
        f"{getattr(issue, 'code')}: {getattr(issue, 'message')}" for issue in issues
    )


def _resolve_query_path(root: Path, raw_path: str) -> Path:
    """解析知识库内相对 Markdown 路径并拒绝越界。"""

    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("knowledge path must be relative to the knowledge-base root")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("knowledge path resolves outside the knowledge-base root") from error
    if not candidate.is_file():
        raise FileNotFoundError(f"knowledge file was not found: {raw_path}")
    return candidate


def _record_map(records: Iterable[DocumentRecord]) -> dict[Path, DocumentRecord]:
    """按绝对路径索引已解析文档。"""

    return {record.path.resolve(): record for record in records}


def _discover_graph_records(root: Path) -> tuple[list[DocumentRecord], list[object]]:
    """发现现行知识及具备格式 11 分类关系的归档知识。"""

    records, issues = discover_records(root, GRAPH_EXCLUDED_DIRECTORIES)
    archive = root / "90-历史归档"
    if archive.is_dir():
        archived, archive_issues = discover_records(
            archive, frozenset({".obsidian", "Excalidraw"})
        )
        issues.extend(archive_issues)
        records.extend(
            record
            for record in archived
            if record.path.name == "README.md"
            or isinstance(record.metadata.get("rel_classified_under"), list)
        )
    return records, issues


def _summary(body: str) -> str | None:
    """提取正文中第一个非标题、非列表的短段落作为导航说明。"""

    paragraph: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            if paragraph:
                break
            continue
        if line.startswith(("#", "- ", "* ", ">", "```", "|")):
            if paragraph:
                break
            continue
        paragraph.append(line)
    return " ".join(paragraph) if paragraph else None


def _visible_child(path: Path) -> bool:
    """判断目录项是否属于默认的当前知识树。"""

    if path.name in EXCLUDED_DIRECTORIES or path.name.startswith("."):
        return False
    if path.is_symlink():
        return False
    return not (path.is_file() and path.name.upper() in {"README.MD", "TEMPLATE.MD"})


def _tree_path(root: Path, raw_path: str) -> Path:
    """安全解析知识库内的相对目录路径。"""

    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("tree path must be relative to the knowledge-base root")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("tree path resolves outside the knowledge-base root") from error
    if not candidate.is_dir():
        raise FileNotFoundError(f"knowledge directory was not found: {raw_path}")
    return candidate


def _tree_node(root: Path, path: Path) -> TreeNode:
    """从目录 README 或文件 Front Matter 生成树节点摘要。"""

    if path.is_dir():
        index = path / "README.md"
        record = parse_document(index) if index.is_file() else None
        metadata = {} if record is None else record.metadata
        title = metadata.get("title")
        if not isinstance(title, str) or not title:
            title = root.name if path == root else path.name
        children = tuple(
            child
            for child in path.iterdir()
            if _visible_child(child) and (child.is_dir() or child.suffix.lower() == ".md")
        )
        return TreeNode(
            kind="directory",
            path="." if path == root else path.relative_to(root).as_posix(),
            title=title,
            description=None if record is None else _summary(record.body),
            id=None,
            type=None,
            status=None,
            child_count=len(children),
        )
    record = parse_document(path)
    metadata = record.metadata
    identifier = metadata.get("id")
    item_type = metadata.get("type")
    status = metadata.get("status")
    title = metadata.get("title")
    return TreeNode(
        kind="file",
        path=path.relative_to(root).as_posix(),
        title=title if isinstance(title, str) and title else path.stem,
        description=_summary(record.body),
        id=identifier if isinstance(identifier, str) else None,
        type=item_type if isinstance(item_type, str) else None,
        status=status if isinstance(status, str) else None,
        child_count=None,
    )


def query_children(knowledge_base_root: Path, *, path: str = ".") -> ChildrenReport:
    """返回指定目录及其直接子目录、Markdown 文件摘要。"""

    root = knowledge_base_root.resolve()
    if not root.is_dir():
        raise ValueError("knowledge-base root must be an existing directory")
    directory = _tree_path(root, path)
    try:
        children = tuple(
            _tree_node(root, child)
            for child in sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name))
            if _visible_child(child) and (child.is_dir() or child.suffix.lower() == ".md")
        )
        node = _tree_node(root, directory)
    except FrontMatterError as error:
        raise ValueError(f"knowledge tree metadata is invalid: {error}") from error
    return ChildrenReport("children", root.name, node, children)


def _node(root: Path, target: KnowledgeTarget, records: dict[Path, DocumentRecord]) -> NeighborNode:
    """把关系目标转换为轻量节点摘要。"""

    record = records.get(target.path.resolve())
    metadata = {} if record is None else record.metadata
    title_value = metadata.get("title")
    title = str(title_value) if isinstance(title_value, str) and title_value else target.identifier
    status_value = metadata.get("status")
    status = str(status_value) if isinstance(status_value, str) else None
    return NeighborNode(
        id=target.identifier,
        type=target.kind,
        title=title,
        status=status,
        path=target.path.resolve().relative_to(root).as_posix(),
        anchor=target.anchor,
    )


def _edge(
    root: Path,
    edge: RelationEdge,
    direction: str,
    records: dict[Path, DocumentRecord],
    catalog: RelationCatalog,
) -> NeighborEdge:
    """把权威关系边转换为相对于查询节点的结果。"""

    definition = catalog.get(edge.field)
    assert definition is not None
    target = edge.target if direction == "outgoing" else edge.source
    return NeighborEdge(direction, edge.field, definition.name_zh, _node(root, target, records))


def query_neighbors(
    knowledge_base_root: Path,
    *,
    identifier: str | None = None,
    path: str | None = None,
    direction: str = "both",
    relation: str | None = None,
) -> NeighborReport:
    """按稳定编号或文件路径返回当前节点的一跳双向邻接清单。"""

    root = knowledge_base_root.resolve()
    if not root.is_dir():
        raise ValueError("knowledge-base root must be an existing directory")
    if (identifier is None) == (path is None):
        raise ValueError("supply exactly one of identifier or path")
    if direction not in ALLOWED_DIRECTIONS:
        raise ValueError(f"unsupported direction: {direction}")

    schema_root = root / ".project-kb" / "schemas"
    catalog = RelationCatalog.load(schema_root / "relation-catalog.json")
    if relation is not None and catalog.get(relation) is None:
        raise ValueError(f"unknown relation: {relation}")

    records, discovery_issues = _discover_graph_records(root)
    if discovery_issues:
        raise ValueError(f"knowledge discovery failed: {_issue_message(discovery_issues)}")
    index, relation_issues = RelationIndex.build(root, records, catalog)
    if relation_issues:
        raise ValueError(f"knowledge relations are invalid: {_issue_message(relation_issues)}")

    records_by_path = _record_map(records)
    if path is not None:
        query_path = _resolve_query_path(root, path)
        record = records_by_path.get(query_path)
        raw_identifier = None if record is None else record.metadata.get("id")
        if not isinstance(raw_identifier, str) or not raw_identifier:
            raise ValueError("knowledge file does not declare a stable id; query it by a contained id")
        identifier = raw_identifier
    assert identifier is not None
    current = index.target(identifier)
    if current is None:
        raise ValueError(f"knowledge node was not found: {identifier}")

    outgoing_edges = index.outgoing(identifier) if direction in {"outgoing", "both"} else ()
    incoming_edges = index.incoming(identifier) if direction in {"incoming", "both"} else ()
    if relation is not None:
        outgoing_edges = tuple(edge for edge in outgoing_edges if edge.field == relation)
        incoming_edges = tuple(edge for edge in incoming_edges if edge.field == relation)
    outgoing = tuple(_edge(root, edge, "outgoing", records_by_path, catalog) for edge in outgoing_edges)
    incoming = tuple(_edge(root, edge, "incoming", records_by_path, catalog) for edge in incoming_edges)
    return NeighborReport(
        operation="neighbors",
        knowledge_base=root.name,
        node=_node(root, current, records_by_path),
        outgoing=outgoing,
        incoming=incoming,
    )


def query_graph(
    knowledge_base_root: Path,
    *,
    start: str | None = None,
    all_nodes: bool = False,
    depth: int = 1,
    max_nodes: int = 200,
    relation: str | None = None,
    node_type: str | None = None,
    status: str | None = None,
    expand_classification_members: bool = False,
) -> GraphReport:
    """返回受限多跳子图，或在显式请求时返回受数量限制的完整图。"""

    root = knowledge_base_root.resolve()
    if not root.is_dir():
        raise ValueError("knowledge-base root must be an existing directory")
    if (start is None) == (not all_nodes):
        raise ValueError("supply exactly one of start or all_nodes")
    if depth < 0:
        raise ValueError("graph depth must be zero or greater")
    if max_nodes < 1:
        raise ValueError("max_nodes must be greater than zero")

    catalog = RelationCatalog.load(root / ".project-kb" / "schemas" / "relation-catalog.json")
    if relation is not None and catalog.get(relation) is None:
        raise ValueError(f"unknown relation: {relation}")
    records, discovery_issues = _discover_graph_records(root)
    if discovery_issues:
        raise ValueError(f"knowledge discovery failed: {_issue_message(discovery_issues)}")
    index, relation_issues = RelationIndex.build(root, records, catalog)
    if relation_issues:
        raise ValueError(f"knowledge relations are invalid: {_issue_message(relation_issues)}")
    records_by_path = _record_map(records)

    def allowed(identifier: str) -> bool:
        """判断节点是否满足可选的类型和状态过滤条件。"""

        target = index.target(identifier)
        if target is None:
            return False
        node = _node(root, target, records_by_path)
        return (node_type is None or node.type == node_type) and (
            status is None or node.status == status
        )

    candidate_edges = tuple(
        edge for edge in index.edges if relation is None or edge.field == relation
    )
    truncated = False
    if all_nodes:
        identifiers = sorted(identifier for identifier in index.targets if allowed(identifier))
        truncated = len(identifiers) > max_nodes
        selected = set(identifiers[:max_nodes])
        report_depth: int | None = None
        mode = "all"
    else:
        assert start is not None
        if index.target(start) is None:
            raise ValueError(f"knowledge node was not found: {start}")
        selected = {start}
        frontier = {start}
        for _ in range(depth):
            adjacent: set[str] = set()
            for edge in candidate_edges:
                source_is_boundary = (
                    index.target(edge.source.identifier) is not None
                    and index.target(edge.source.identifier).kind == "knowledge_index"  # type: ignore[union-attr]
                    and not expand_classification_members
                )
                target_is_boundary = (
                    index.target(edge.target.identifier) is not None
                    and index.target(edge.target.identifier).kind == "knowledge_index"  # type: ignore[union-attr]
                    and not expand_classification_members
                )
                if edge.source.identifier in frontier and not source_is_boundary:
                    adjacent.add(edge.target.identifier)
                if edge.target.identifier in frontier and not target_is_boundary:
                    adjacent.add(edge.source.identifier)
            adjacent = {identifier for identifier in adjacent if allowed(identifier)} - selected
            remaining = max_nodes - len(selected)
            if len(adjacent) > remaining:
                truncated = True
                adjacent = set(sorted(adjacent)[: max(remaining, 0)])
            selected.update(adjacent)
            frontier = adjacent
            if not frontier or len(selected) >= max_nodes:
                if frontier and any(
                    edge.source.identifier in frontier or edge.target.identifier in frontier
                    for edge in candidate_edges
                ):
                    truncated = True
                break
        report_depth = depth
        mode = "subgraph"

    nodes = tuple(
        _node(root, index.target(identifier), records_by_path)  # type: ignore[arg-type]
        for identifier in sorted(selected)
    )
    edges = tuple(
        GraphEdge(
            edge.field,
            catalog.get(edge.field).name_zh,  # type: ignore[union-attr]
            edge.source.identifier,
            edge.target.identifier,
        )
        for edge in candidate_edges
        if edge.source.identifier in selected and edge.target.identifier in selected
    )
    return GraphReport(
        "graph",
        root.name,
        mode,
        start,
        report_depth,
        max_nodes,
        truncated,
        nodes,
        edges,
    )
