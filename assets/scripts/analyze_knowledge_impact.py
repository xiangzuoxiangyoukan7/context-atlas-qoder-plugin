"""提供知识变化三级影响分析的只读命令行入口。"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.project_kb.discovery import discover_records
from scripts.project_kb.impact import ImpactItem, analyze_impact
from scripts.project_kb.relation_catalog import RelationCatalog
from scripts.project_kb.relations import RelationIndex


def _parser() -> argparse.ArgumentParser:
    """创建影响分析参数解析器。"""

    parser = argparse.ArgumentParser(description="分析知识变化可能影响的业务知识")
    parser.add_argument("root", type=Path)
    parser.add_argument("--schema-root", type=Path, default=Path("schemas"))
    parser.add_argument("--changed-id", required=True)
    parser.add_argument("--change-type", required=True)
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def _relative(path: Path, root: Path) -> str:
    """优先输出知识库内相对路径，避免报告泄露无关绝对目录。"""

    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _json_payload(
    impacts: list[ImpactItem],
    root: Path,
    changed_id: str,
    change_type: str,
) -> str:
    """把影响项渲染为稳定、可供工具读取的 JSON。"""

    rendered: list[dict[str, object]] = []
    for item in impacts:
        payload = asdict(item)
        payload["source_path"] = _relative(item.source_path, root)
        payload["affected_path"] = _relative(item.affected_path, root)
        rendered.append(payload)
    return json.dumps(
        {
            "changed_id": changed_id,
            "change_type": change_type,
            "impacts": rendered,
        },
        ensure_ascii=False,
        indent=2,
    )


def _text_payload(impacts: list[ImpactItem], root: Path) -> str:
    """把影响项渲染为便于人工确认的中文文本。"""

    if not impacts:
        return "未发现关系图中的受影响知识项。"
    return "\n".join(
        f"[{item.level}] 深度 {item.depth}：{item.affected_id} "
        f"经 {item.relation}（{_relative(item.affected_path, root)}）"
        for item in impacts
    )


def main(argv: Sequence[str] | None = None) -> int:
    """加载关系图、分析影响并按输入有效性返回稳定退出码。"""

    parser = _parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    root = args.root.resolve()
    try:
        catalog = RelationCatalog.load(args.schema_root / "relation-catalog.json")
        records, discovery_issues = discover_records(
            root, frozenset({".project-kb", ".obsidian", "Excalidraw", "Clippings", "90-历史归档"})
        )
        index, relation_issues = RelationIndex.build(root, records, catalog)
    except (OSError, ValueError) as error:
        parser.exit(2, f"配置错误：{error}\n")
    issues = discovery_issues + relation_issues
    if issues:
        parser.exit(2, f"知识关系无效：{issues[0].code} {issues[0].message}\n")
    if not index.contains(args.changed_id):
        parser.exit(2, f"知识编号不存在：{args.changed_id}\n")
    if args.max_depth < 1:
        parser.exit(2, "分析深度必须大于零\n")

    impacts = analyze_impact(
        index,
        catalog,
        args.changed_id,
        args.change_type,
        max_depth=args.max_depth,
    )
    if args.format == "json":
        print(_json_payload(impacts, root, args.changed_id, args.change_type))
    else:
        print(_text_payload(impacts, root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
