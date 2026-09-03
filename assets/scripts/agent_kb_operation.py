"""为 Agent 提供非交互式知识库结构化操作命令。"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from dataclasses import replace
import json
from pathlib import Path
import sys
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.project_kb.agent_operation import execute_initialization_proposal
from scripts.project_kb.capture import CaptureCandidate, capture_candidate
from scripts.project_kb.compatibility import CompatibilityPolicy
from scripts.project_kb.discovery import discover_records
from scripts.project_kb.identity import discover_identity_match
from scripts.project_kb.migration import apply_migration, build_migration_proposal
from scripts.project_kb.navigation import query_children, query_graph, query_neighbors
from scripts.project_kb.updater import UpdateChange, execute_update
from scripts.project_kb.archive import apply_archive, build_archive_proposal
from scripts.project_kb.health import inspect_health
from scripts.project_kb.ingest_enhancements import save_ingest_history
from scripts.project_kb.managed_sources import apply_source_import, build_source_import_proposal
from scripts.project_kb.validator import ValidationConfig, validate


def _default_assets_root() -> Path:
    """根据脚本位于源码仓库还是发布资产中推导默认资源根目录。"""

    scripts_parent = Path(__file__).resolve().parents[1]
    if (scripts_parent / "templates" / "core" / "doc-project").is_dir():
        return scripts_parent
    source_assets = scripts_parent / "assets"
    if (source_assets / "templates" / "core" / "doc-project").is_dir():
        return source_assets
    raise FileNotFoundError("Context Atlas assets root was not found")


def _configure_utf8_stdio() -> None:
    """在 Windows 等非 UTF-8 终端中稳定接收和输出结构化中文。"""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="strict")


def _default_compatibility() -> Path:
    """返回源码仓库或知识库内置工具中的默认兼容声明。"""

    return _default_assets_root() / "compatibility.json"


def _parser() -> argparse.ArgumentParser:
    """创建只接受已确认结构化参数的命令行解析器。"""

    parser = argparse.ArgumentParser(description="执行已确认的 Context Atlas 结构化操作")
    subparsers = parser.add_subparsers(dest="operation", required=True)
    initialize = subparsers.add_parser("initialize", aliases=["init"])
    initialize.add_argument("--proposal", required=True, help="Proposal JSON path, or - for stdin")
    initialize.add_argument("--confirmed-revision", required=True)
    initialize.add_argument("--assets-root", type=Path)

    update = subparsers.add_parser("update")
    update.add_argument("knowledge_base_root", type=Path)
    update.add_argument("--proposal-revision", required=True)
    update.add_argument("--confirmed-revision", required=True)
    update.add_argument("--file", action="append", required=True)
    update.add_argument("--content-file", action="append", required=True)

    diagnose = subparsers.add_parser("upgrade-diagnose", aliases=["diagnose-format"])
    diagnose.add_argument("knowledge_base_root", type=Path)
    diagnose.add_argument(
        "--compatibility", type=Path
    )

    capture = subparsers.add_parser("capture")
    capture.add_argument("knowledge_base_root", type=Path)
    capture.add_argument("--checkpoint", required=True)
    capture.add_argument("--summary", required=True)
    capture.add_argument("--target-id", action="append", required=True)
    capture.add_argument("--source-type", required=True)
    capture.add_argument("--source-reference", required=True)
    capture.add_argument("--difference", action="append", default=[])
    capture.add_argument("--impact-id", action="append", default=[])
    capture.add_argument("--unknown", action="append", default=[])
    capture.add_argument("--conflict", action="append", default=[])
    capture.add_argument("--proposed-by", required=True)
    capture.add_argument("--operated-by", required=True)
    capture.add_argument("--project-version", required=True)
    capture.add_argument("--captured-at", required=True)
    capture.add_argument("--user-requested", action="store_true", required=True)

    identify = subparsers.add_parser("identify-contributor")
    identify.add_argument("repository_root", type=Path)
    identify.add_argument("knowledge_base_root", type=Path)

    neighbors = subparsers.add_parser("neighbors")
    neighbors.add_argument("knowledge_base_root", type=Path)
    query = neighbors.add_mutually_exclusive_group(required=True)
    query.add_argument("--id", dest="identifier")
    query.add_argument("--path")
    neighbors.add_argument(
        "--direction", choices=("outgoing", "incoming", "both"), default="both"
    )
    neighbors.add_argument("--relation")

    children = subparsers.add_parser("children")
    children.add_argument("knowledge_base_root", type=Path)
    children.add_argument("--path", default=".")

    graph = subparsers.add_parser("graph")
    graph.add_argument("knowledge_base_root", type=Path)
    graph_scope = graph.add_mutually_exclusive_group(required=True)
    graph_scope.add_argument("--start")
    graph_scope.add_argument("--all", dest="all_nodes", action="store_true")
    graph.add_argument("--depth", type=int, default=1)
    graph.add_argument("--max-nodes", type=int, default=200)
    graph.add_argument("--relation")
    graph.add_argument("--type", dest="node_type")
    graph.add_argument("--status")
    graph.add_argument(
        "--expand-classification-members",
        action="store_true",
        help="显式允许图查询从 README 分类节点继续展开成员",
    )

    health = subparsers.add_parser("health")
    health.add_argument("knowledge_base_root", type=Path)
    health.add_argument("--stale-days", type=int, default=180)

    history = subparsers.add_parser("ingest-history-save")
    history.add_argument("project_root", type=Path)
    history.add_argument("--report", required=True, type=Path)
    history.add_argument("--recorded-at")

    source_propose = subparsers.add_parser("managed-source-propose")
    source_propose.add_argument("knowledge_base_root", type=Path)

    source_apply = subparsers.add_parser("managed-source-apply")
    source_apply.add_argument("knowledge_base_root", type=Path)
    source_apply.add_argument("--proposal-revision", required=True)
    source_apply.add_argument("--confirmed-revision", required=True)

    for operation, alias in (("upgrade-propose", "migrate-propose"), ("upgrade-apply", "migrate-apply")):
        migration = subparsers.add_parser(operation, aliases=[alias])
        migration.add_argument("knowledge_base_root", type=Path)
        migration.add_argument(
            "--compatibility", type=Path
        )
        if operation == "upgrade-apply":
            migration.add_argument("--proposal-revision", required=True)
            migration.add_argument("--confirmed-revision", required=True)
    for operation in ("archive-propose", "archive-apply"):
        archive = subparsers.add_parser(operation)
        archive.add_argument("knowledge_base_root", type=Path)
        archive.add_argument("--source", required=True)
        archive.add_argument("--target", required=True)
        archive.add_argument("--successor-id", required=True)
        archive.add_argument("--archived-at", required=True)
        archive.add_argument("--reason", required=True)
        archive.add_argument("--source-reference", required=True)
        if operation == "archive-apply":
            archive.add_argument("--proposal-revision", required=True)
            archive.add_argument("--confirmed-revision", required=True)
    return parser


def _migration_proposal(root: Path, compatibility: Path) -> object:
    """发现知识记录并建立当前文件状态对应的只读迁移提案。"""

    records, issues = discover_records(
        root.resolve(), frozenset({".project-kb", ".obsidian", "Excalidraw", "Clippings", "90-历史归档"})
    )
    if issues:
        messages = "; ".join(f"{issue.code}: {issue.message}" for issue in issues)
        raise ValueError(f"knowledge discovery failed: {messages}")
    policy = CompatibilityPolicy.load(compatibility)
    return build_migration_proposal(root, records, policy)


def _execute(args: argparse.Namespace) -> tuple[object, int]:
    """按已解析操作执行并返回报告及进程退出码。"""

    if args.operation in {"initialize", "init"}:
        proposal_text = (
            sys.stdin.buffer.read().decode("utf-8")
            if args.proposal == "-" and hasattr(sys.stdin, "buffer")
            else sys.stdin.read()
            if args.proposal == "-"
            else Path(args.proposal).read_text(encoding="utf-8")
        )
        proposal = json.loads(proposal_text)
        report = execute_initialization_proposal(
            proposal=proposal,
            confirmed_revision=args.confirmed_revision,
            assets_root=args.assets_root or _default_assets_root(),
        )
        return report, report.validation.exit_code
    if args.operation == "update":
        if len(args.file) != len(args.content_file):
            raise ValueError("--file and --content-file must be supplied the same number of times")
        report = execute_update(
            knowledge_base_root=args.knowledge_base_root,
            proposal_revision=args.proposal_revision,
            confirmed_revision=args.confirmed_revision,
            changes=tuple(
                UpdateChange(path, Path(content_file))
                for path, content_file in zip(args.file, args.content_file)
            ),
        )
        return report, report.validator_exit_code
    if args.operation in {"upgrade-diagnose", "diagnose-format"}:
        policy = CompatibilityPolicy.load(
            args.compatibility or _default_compatibility()
        )
        result = policy.diagnose(args.knowledge_base_root)
        issues = validate(
            args.knowledge_base_root,
            ValidationConfig(schema_root=_default_assets_root() / "schemas"),
        )
        health = inspect_health(args.knowledge_base_root)
        blocking_health = tuple(
            finding for finding in health.findings if finding.severity != "warning"
        )
        result = replace(
            result,
            validation_issue_count=len(issues),
            health_finding_count=len(health.findings),
            blocking_health_finding_count=len(blocking_health),
        )
        if (
            result.status != "unsupported"
            and (issues or blocking_health)
            and result.format_version == result.created_format_version
        ):
            result = replace(
                result,
                status="needs_normalization",
                conversion_available=True,
            )
        return result, 2 if result.write_blocked else 0
    if args.operation == "capture":
        candidate = CaptureCandidate(
            checkpoint=args.checkpoint,
            summary=args.summary,
            target_ids=tuple(args.target_id),
            source_type=args.source_type,
            source_reference=args.source_reference,
            differences=tuple(args.difference),
            impact_ids=tuple(args.impact_id),
            unknowns=tuple(args.unknown),
            conflicts=tuple(args.conflict),
            proposed_by=args.proposed_by,
            operated_by=args.operated_by,
            project_version=args.project_version,
        )
        return (
            capture_candidate(
                args.knowledge_base_root,
                candidate,
                captured_at=args.captured_at,
                user_requested=args.user_requested,
            ),
            0,
        )
    if args.operation == "identify-contributor":
        people_path = (
            args.knowledge_base_root.resolve() / "05-知识治理" / "协作与责任.md"
        )
        return discover_identity_match(args.repository_root, people_path), 0
    if args.operation == "neighbors":
        return query_neighbors(
            args.knowledge_base_root,
            identifier=args.identifier,
            path=args.path,
            direction=args.direction,
            relation=args.relation,
        ), 0
    if args.operation == "children":
        return query_children(args.knowledge_base_root, path=args.path), 0
    if args.operation == "graph":
        return query_graph(
            args.knowledge_base_root,
            start=args.start,
            all_nodes=args.all_nodes,
            depth=args.depth,
            max_nodes=args.max_nodes,
            relation=args.relation,
            node_type=args.node_type,
            status=args.status,
            expand_classification_members=args.expand_classification_members,
        ), 0
    if args.operation == "health":
        return inspect_health(
            args.knowledge_base_root,
            stale_days=args.stale_days,
        ), 0
    if args.operation == "ingest-history-save":
        from datetime import datetime

        payload = json.loads(args.report.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("ingest history report must be a JSON object")
        recorded_at = datetime.fromisoformat(args.recorded_at) if args.recorded_at else None
        return save_ingest_history(
            args.project_root,
            payload,
            recorded_at=recorded_at,
        ), 0
    if args.operation == "managed-source-propose":
        return build_source_import_proposal(args.knowledge_base_root), 0
    if args.operation == "managed-source-apply":
        return apply_source_import(
            args.knowledge_base_root,
            args.proposal_revision,
            args.confirmed_revision,
        ), 0
    if args.operation in {"archive-propose", "archive-apply"}:
        proposal = build_archive_proposal(
            args.knowledge_base_root, args.source, args.target, args.successor_id,
            args.archived_at, args.reason, args.source_reference,
        )
        if args.operation == "archive-propose":
            return proposal, 0
        if args.proposal_revision != proposal.proposal_revision:
            raise PermissionError("proposal revision no longer matches current files")
        return apply_archive(args.knowledge_base_root, proposal, args.confirmed_revision), 0
    proposal = _migration_proposal(
        args.knowledge_base_root, args.compatibility or _default_compatibility()
    )
    if args.operation in {"upgrade-propose", "migrate-propose"}:
        # 未解析关系属于需要人工处理的有效分析结果，而不是程序崩溃。
        return proposal, 3 if proposal.unresolved else 0
    if args.proposal_revision != proposal.proposal_revision:
        raise PermissionError("proposal revision no longer matches current files")
    report = apply_migration(
        args.knowledge_base_root, proposal, args.confirmed_revision
    )
    issues = validate(
        args.knowledge_base_root,
        ValidationConfig(schema_root=_default_assets_root() / "schemas"),
    )
    health = inspect_health(args.knowledge_base_root)
    blocking_health = tuple(
        finding for finding in health.findings if finding.severity != "warning"
    )
    report = replace(
        report,
        status="migrated" if not issues and not blocking_health else "validation_failed",
        validation_issue_count=len(issues),
        health_finding_count=len(health.findings),
        blocking_health_finding_count=len(blocking_health),
    )
    return report, 0 if not issues and not blocking_health else 1


def main(argv: Sequence[str] | None = None) -> int:
    """执行结构化知识操作并输出不含会话全文的 JSON 报告。"""

    _configure_utf8_stdio()
    parser = _parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
        report, exit_code = _execute(args)
    except (json.JSONDecodeError, OSError, ValueError, PermissionError) as error:
        print(
            json.dumps(
                {"ok": False, "error_type": type(error).__name__, "message": str(error)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    payload = asdict(report)
    if args.operation in {
        "upgrade-diagnose", "diagnose-format", "upgrade-propose",
        "migrate-propose", "upgrade-apply", "migrate-apply",
    }:
        compatibility = args.compatibility or _default_compatibility()
        payload["runtime_assets_root"] = str(_default_assets_root().resolve())
        payload["compatibility_path"] = str(compatibility.resolve())
    payload["ok"] = exit_code == 0
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
