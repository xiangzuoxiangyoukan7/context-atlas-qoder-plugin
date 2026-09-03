"""生成并执行旧知识来源关系到当前格式的轻量等价转换。"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Iterable

from .compatibility import CompatibilityPolicy
from .model import DocumentRecord
from .obsidian import graph_text, read_graph


@dataclass(frozen=True)
class MigrationChange:
    """描述一个文件需要内嵌的来源对象及原内容摘要。"""

    path: Path
    links: tuple[str, ...]
    original_digest: str


@dataclass(frozen=True)
class MigrationMove:
    """描述知识治理文件的安全路径迁移。"""

    source: Path
    target: Path
    original_digest: str


@dataclass(frozen=True)
class MigrationRemoval:
    """描述可证明为旧模板占位内容的删除项。"""

    path: Path
    original_digest: str


@dataclass(frozen=True)
class MigrationRewrite:
    """描述旧治理路径引用的可审计文本替换。"""

    path: Path
    original_digest: str
    content: str | None = None


@dataclass(frozen=True)
class MigrationCreation:
    """描述格式升级需要创建且提案时不存在的标准文件。"""

    path: Path
    content: str
    content_digest: str


@dataclass(frozen=True)
class MigrationAsset:
    """描述格式升级需要创建或替换的自包含运行资产。"""

    path: Path
    content: bytes
    original_digest: str | None
    content_digest: str


@dataclass(frozen=True)
class MigrationUnresolved:
    """描述无法唯一定位、必须由用户确认的旧来源编号。"""

    path: Path
    source_id: str
    reason: str


@dataclass(frozen=True)
class AgentMigrationDecision:
    """记录 Agent 基于旧知识语义提出的一项可审计迁移判断。"""

    action: str
    path: str
    target: str | None
    reason: str
    source_paths: tuple[str, ...]
    source_digests: tuple[str, ...]


@dataclass(frozen=True)
class MigrationProposal:
    """保存只读分析产生的不可变转换范围和确认修订号。"""

    proposal_revision: str
    source_version: int
    target_version: int
    changes: tuple[MigrationChange, ...]
    moves: tuple[MigrationMove, ...]
    removals: tuple[MigrationRemoval, ...]
    rewrites: tuple[MigrationRewrite, ...]
    creations: tuple[MigrationCreation, ...]
    assets: tuple[MigrationAsset, ...]
    unresolved: tuple[MigrationUnresolved, ...]
    agent_decisions: tuple[AgentMigrationDecision, ...] = ()
    preflight_status: str = "not_run"
    preflight_validation_issues: tuple[str, ...] = ()
    preflight_health_findings: tuple[str, ...] = ()


@dataclass(frozen=True)
class MigrationReport:
    """保存已确认迁移实际修改的文件和最终格式版本。"""

    status: str
    changed_files: tuple[str, ...]
    format_version: int
    validation_issue_count: int = 0
    health_finding_count: int = 0
    blocking_health_finding_count: int = 0


def _digest(data: bytes) -> str:
    """返回文件内容摘要，用于拒绝提案生成后的并发变化。"""

    return hashlib.sha256(data).hexdigest()


def _source_paths(records: Iterable[DocumentRecord]) -> dict[str, list[Path]]:
    """按来源稳定编号建立可能包含重复项的文件索引。"""

    index: dict[str, list[Path]] = {}
    for record in records:
        if record.metadata.get("type") != "source":
            continue
        identifier = record.metadata.get("id")
        if isinstance(identifier, str):
            index.setdefault(identifier, []).append(record.path.resolve())
    return index


def _revision(
    source_version: int,
    target_version: int,
    changes: Iterable[MigrationChange],
    moves: Iterable[MigrationMove],
    removals: Iterable[MigrationRemoval],
    rewrites: Iterable[MigrationRewrite],
    creations: Iterable[MigrationCreation],
    assets: Iterable[MigrationAsset],
    unresolved: Iterable[MigrationUnresolved],
    agent_decisions: Iterable[AgentMigrationDecision] = (),
) -> str:
    """根据完整提案内容生成稳定且不可猜测的短修订号。"""

    parts = [f"{source_version}->{target_version}"]
    # 每个类别都按规范化字符串排序。调用方即使传入由 set 或文件系统
    # 遍历产生的非确定性顺序，也必须得到同一个提案修订号。
    parts.extend(sorted(
        f"change:{change.path}:{change.original_digest}:{','.join(change.links)}"
        for change in changes
    ))
    parts.extend(sorted(
        f"move:{move.source}:{move.target}:{move.original_digest}" for move in moves
    ))
    parts.extend(sorted(
        f"remove:{removal.path}:{removal.original_digest}" for removal in removals
    ))
    parts.extend(sorted(
        f"rewrite:{rewrite.path}:{rewrite.original_digest}:"
        f"{_digest(rewrite.content.encode('utf-8')) if rewrite.content is not None else 'dynamic'}"
        for rewrite in rewrites
    ))
    parts.extend(sorted(
        f"create:{creation.path}:{creation.content_digest}" for creation in creations
    ))
    parts.extend(sorted(
        f"asset:{asset.path}:{asset.original_digest or 'missing'}:{asset.content_digest}"
        for asset in assets
    ))
    parts.extend(sorted(
        f"unresolved:{item.path}:{item.source_id}:{item.reason}"
        for item in unresolved
    ))
    parts.extend(sorted(
        f"agent:{item.action}:{item.path}:{item.target or ''}:{item.reason}:"
        f"{','.join(item.source_paths)}:{','.join(item.source_digests)}"
        for item in agent_decisions
    ))
    return "migration-" + hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:12]


def _inside_knowledge_root(root: Path, relative: str) -> Path:
    """解析 Agent 路径并拒绝绝对路径、目录逃逸和运行资产覆盖。"""

    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"agent migration path escapes knowledge base: {relative}")
    normalized = (root / candidate).resolve()
    normalized.relative_to(root.resolve())
    if candidate.parts and candidate.parts[0] in {".project-kb", ".obsidian"}:
        raise ValueError(f"agent migration cannot modify runtime assets: {relative}")
    if candidate.as_posix() == "knowledge-base.yaml":
        raise ValueError("agent migration cannot modify knowledge-base.yaml")
    return normalized


def merge_agent_migration_plan(
    root: Path,
    proposal: MigrationProposal,
    plan_path: Path | None,
) -> MigrationProposal:
    """把 Agent 的语义迁移决策合入确定性提案并重新计算确认修订号。

    Agent 只提供知识文件的精确创建、改写、移动或删除判断；执行器负责路径边界、
    原文件摘要、冲突检测与最终预演，避免 Agent 绕过运行资产和确认门禁。
    """

    if plan_path is None:
        return proposal
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    raw_decisions = payload.get("decisions") if isinstance(payload, dict) else None
    if not isinstance(raw_decisions, list) or not raw_decisions:
        raise ValueError("agent migration plan must contain non-empty decisions")
    changes = {item.path.resolve(): item for item in proposal.changes}
    rewrites = {item.path.resolve(): item for item in proposal.rewrites}
    creations = {item.path.resolve(): item for item in proposal.creations}
    moves = {(item.source.resolve(), item.target.resolve()): item for item in proposal.moves}
    removals = {item.path.resolve(): item for item in proposal.removals}
    decisions: list[AgentMigrationDecision] = []
    for raw in raw_decisions:
        if not isinstance(raw, dict):
            raise ValueError("agent migration decision must be an object")
        action = raw.get("action")
        relative = raw.get("path")
        reason = raw.get("reason")
        source_paths = raw.get("source_paths")
        if action not in {"rewrite", "create", "move", "remove"}:
            raise ValueError("agent migration action must be rewrite, create, move, or remove")
        if not isinstance(relative, str) or not isinstance(reason, str) or not reason.strip():
            raise ValueError("agent migration decision requires path and reason")
        if not isinstance(source_paths, list) or not source_paths or not all(isinstance(item, str) for item in source_paths):
            raise ValueError("agent migration decision requires source_paths")
        path = _inside_knowledge_root(root, relative)
        source_digests: list[str] = []
        for source_path in source_paths:
            source = _inside_knowledge_root(root, source_path)
            if not source.is_file():
                raise ValueError(f"agent migration source does not exist: {source_path}")
            source_digests.append(_digest(source.read_bytes()))
        target_relative = raw.get("target")
        target = None
        if action == "rewrite":
            content = raw.get("content")
            if not path.is_file() or not isinstance(content, str):
                raise ValueError("agent rewrite requires an existing file and string content")
            removals.pop(path, None)
            rewrites[path] = MigrationRewrite(path, _digest(path.read_bytes()), content)
        elif action == "create":
            content = raw.get("content")
            if path.exists() or not isinstance(content, str):
                raise ValueError("agent create requires a missing path and string content")
            creations[path] = MigrationCreation(path, content, _digest(content.encode("utf-8")))
        elif action == "move":
            if not isinstance(target_relative, str) or not path.is_file():
                raise ValueError("agent move requires an existing source and target")
            target = _inside_knowledge_root(root, target_relative)
            if target.exists() and (path.resolve(), target.resolve()) not in moves:
                raise ValueError("agent move target already exists")
            moves[(path, target)] = MigrationMove(path, target, _digest(path.read_bytes()))
        else:
            if not path.is_file():
                raise ValueError("agent remove requires an existing file")
            rewrites.pop(path, None)
            creations.pop(path, None)
            changes.pop(path, None)
            moves = {
                key: value for key, value in moves.items()
                if value.source.resolve() != path and value.target.resolve() != path
            }
            removals[path] = MigrationRemoval(path, _digest(path.read_bytes()))
        decisions.append(AgentMigrationDecision(
            action, relative, target_relative if isinstance(target_relative, str) else None,
            reason.strip(), tuple(source_paths), tuple(source_digests),
        ))
    merged = replace(
        proposal,
        changes=tuple(sorted(changes.values(), key=lambda item: str(item.path))),
        rewrites=tuple(sorted(rewrites.values(), key=lambda item: str(item.path))),
        creations=tuple(sorted(creations.values(), key=lambda item: str(item.path))),
        moves=tuple(sorted(moves.values(), key=lambda item: (str(item.source), str(item.target)))),
        removals=tuple(sorted(removals.values(), key=lambda item: str(item.path))),
        agent_decisions=tuple(decisions),
    )
    revision = _revision(
        merged.source_version, merged.target_version, merged.changes, merged.moves,
        merged.removals, merged.rewrites, merged.creations, merged.assets,
        merged.unresolved, merged.agent_decisions,
    )
    return replace(merged, proposal_revision=revision)


def _remap_proposal(proposal: MigrationProposal, source: Path, target: Path) -> MigrationProposal:
    """把正式知识库路径映射到隔离预演副本。"""

    def mapped(path: Path) -> Path:
        """映射一个位于正式知识库内的路径。"""

        return target / path.resolve().relative_to(source.resolve())

    return replace(
        proposal,
        changes=tuple(replace(item, path=mapped(item.path)) for item in proposal.changes),
        moves=tuple(replace(item, source=mapped(item.source), target=mapped(item.target)) for item in proposal.moves),
        removals=tuple(replace(item, path=mapped(item.path)) for item in proposal.removals),
        rewrites=tuple(replace(item, path=mapped(item.path)) for item in proposal.rewrites),
        creations=tuple(replace(item, path=mapped(item.path)) for item in proposal.creations),
        assets=tuple(replace(item, path=mapped(item.path)) for item in proposal.assets),
    )


def preflight_migration(
    root: Path,
    proposal: MigrationProposal,
    schema_root: Path,
) -> MigrationProposal:
    """在隔离副本完整应用并验证 Proposal，正式知识库保持零写入。"""

    from .health import inspect_health
    from .validator import ValidationConfig, validate

    if proposal.unresolved:
        return replace(proposal, preflight_status="blocked")
    with tempfile.TemporaryDirectory(prefix="context-atlas-upgrade-") as directory:
        staging = Path(directory) / root.resolve().name
        shutil.copytree(root.resolve(), staging)
        staged = _remap_proposal(proposal, root.resolve(), staging)
        apply_migration(staging, staged, staged.proposal_revision)
        issues = validate(staging, ValidationConfig(schema_root=schema_root))
        health = inspect_health(staging)
        blocking = tuple(item for item in health.findings if item.severity != "warning")
        return replace(
            proposal,
            preflight_status="passed" if not issues and not blocking else "failed",
            preflight_validation_issues=tuple(
                f"{item.code} {item.path.relative_to(staging).as_posix()}: {item.message}"
                for item in issues
            ),
            preflight_health_findings=tuple(
                f"{item.code} {item.path}: {item.message}" for item in blocking
            ),
        )


def _current_format_creations(root: Path) -> tuple[MigrationCreation, ...]:
    """从随插件发布的核心模板补齐当前格式所需目录及其可达模板。"""

    template_root = Path(__file__).resolve().parents[2] / "templates" / "core" / "doc-project"
    relatives = (
        Path("01-功能基线/需求/README.md"),
        Path("01-功能基线/功能/README.md"),
        Path("02-技术基线/README.md"),
        Path("02-技术基线/模块/README.md"),
        Path("02-技术基线/接口/README.md"),
        Path("02-技术基线/数据库/README.md"),
        Path("02-技术基线/数据资产/README.md"),
        Path("02-技术基线/原型/README.md"),
        Path("02-技术基线/外部依赖/README.md"),
        Path("03-变更与证据/变更/README.md"),
        Path("03-变更与证据/验收证据/README.md"),
        Path("03-变更与证据/待确认知识/README.md"),
    )
    creations: list[MigrationCreation] = []
    for relative in relatives:
        target = root / relative
        if target.exists():
            continue
        content = (template_root / relative).read_text(encoding="utf-8")
        creations.append(MigrationCreation(target.resolve(), content, _digest(content.encode("utf-8"))))
    return tuple(creations)


def _readme_contract_section(content: str) -> str:
    """提取模板 README 的受管目录契约章节。"""

    match = re.search(r"(?ms)^## 目录契约\s*\n.*?(?=^## |\Z)", content)
    if match is None:
        raise ValueError("README template has no 目录契约 section")
    return match.group(0).rstrip() + "\n"


def _merge_readme_contract(content: str, contract: str) -> str:
    """替换或插入目录契约，同时保留未受管的项目补充章节。"""

    current = re.search(r"(?ms)^## 目录契约\s*\n.*?(?=^## |\Z)", content)
    if current is not None:
        return content[: current.start()] + contract + content[current.end() :]
    heading = re.search(r"(?m)^# .+$", content)
    if heading is None:
        return content
    insertion = heading.end()
    return content[:insertion] + "\n\n" + contract.rstrip() + "\n" + content[insertion:].lstrip("\r\n")


def _current_format_readme_rewrites(
    root: Path, records: Iterable[DocumentRecord]
) -> tuple[MigrationRewrite, ...]:
    """把现有正式 README 归一到当前模板契约。"""

    template_root = Path(__file__).resolve().parents[2] / "templates" / "core" / "doc-project"
    rewrites: dict[Path, MigrationRewrite] = {}
    managed_paths: set[Path] = set()
    for source in sorted(template_root.rglob("README.md")):
        relative = source.relative_to(template_root)
        if (
            relative.as_posix() in {"README.md", "Clippings/README.md", "90-历史归档/README.md"}
            or ".project-kb" in relative.parts
        ):
            continue
        target = (root / relative).resolve()
        if not target.is_file():
            continue
        managed_paths.add(target)
        expected = source.read_text(encoding="utf-8")
        if target.read_text(encoding="utf-8") != expected:
            rewrites[target] = MigrationRewrite(
                target, _digest(target.read_bytes()), expected
            )

    data_source_template = (
        template_root / ".project-kb/templates/knowledge/data-source.md"
    ).read_text(encoding="utf-8")
    data_source_contract = _readme_contract_section(data_source_template)
    archive_contract = _readme_contract_section(
        (template_root / "90-历史归档/README.md").read_text(encoding="utf-8")
    )
    for record in records:
        target = record.path.resolve()
        if record.path.name != "README.md" or target in managed_paths:
            continue
        relative = target.relative_to(root.resolve()).as_posix()
        if relative in {"README.md", "Clippings/README.md"}:
            continue
        kind = record.metadata.get("type")
        if kind == "data_source":
            contract = data_source_contract
        elif relative == "90-历史归档/README.md":
            contract = archive_contract
        else:
            continue
        original = target.read_text(encoding="utf-8")
        normalized = _merge_readme_contract(original, contract)
        if normalized != original:
            rewrites[target] = MigrationRewrite(
                target, _digest(target.read_bytes()), normalized
            )
    return tuple(sorted(rewrites.values(), key=lambda item: str(item.path)))


def _asset_source_root() -> Path:
    """定位源码仓库或已安装插件中的运行资产根。"""

    module_root = Path(__file__).resolve().parents[2]
    if (module_root / "assets" / "manifest.json").is_file():
        return module_root
    if (module_root / "manifest.json").is_file():
        return module_root
    raise FileNotFoundError("cannot locate plugin asset manifest")


def _current_format_assets(root: Path) -> tuple[MigrationAsset, ...]:
    """为当前格式提案枚举需要写入 `.project-kb` 的全部运行资产。"""

    source_root = _asset_source_root()
    manifest_path = (
        source_root / "assets" / "manifest.json"
        if (source_root / "assets" / "manifest.json").is_file()
        else source_root / "manifest.json"
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    relative_paths = payload.get("files")
    if not isinstance(relative_paths, list):
        raise ValueError("plugin asset manifest has no files list")
    selected = [
        relative
        for relative in relative_paths
        if isinstance(relative, str)
        and (
            relative == "compatibility.json"
            or relative.startswith(("schemas/", "scripts/", "rules/", "operations/"))
        )
    ]
    selected = sorted([*selected, "manifest.json"])
    assets: list[MigrationAsset] = []
    for relative_text in selected:
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe plugin asset path: {relative_text}")
        source = manifest_path if relative_text == "manifest.json" else source_root / relative
        content = source.read_bytes()
        target = (root / ".project-kb" / relative).resolve()
        original_digest = _digest(target.read_bytes()) if target.is_file() else None
        if original_digest == _digest(content):
            continue
        assets.append(
            MigrationAsset(target, content, original_digest, _digest(content))
        )
    knowledge_templates = source_root / "templates" / "core" / "doc-project" / ".project-kb" / "templates" / "knowledge"
    for source in sorted(knowledge_templates.glob("*.md")):
        target = (root / ".project-kb" / "templates" / "knowledge" / source.name).resolve()
        content = source.read_bytes()
        original_digest = _digest(target.read_bytes()) if target.is_file() else None
        if original_digest != _digest(content):
            assets.append(MigrationAsset(target, content, original_digest, _digest(content)))
    return tuple(assets)


LEGACY_PLACEHOLDERS = {
    "本地开发.md": """# 本地开发

| 目的 | 前置条件 | 命令 | 预期结果 | 来源 | 状态 |
| --- | --- | --- | --- | --- | --- |
| 安装依赖 | 待确认 | 待确认 | 依赖可复现 | SRC-001 | missing |
| 启动项目 | 待确认 | 待确认 | 服务健康 | SRC-001 | missing |
| 构建产物 | 待确认 | 待确认 | 构建成功 | SRC-001 | missing |

Agent 从构建文件、脚本和 CI 验证命令，不凭语言猜测。环境差异、必要服务和非敏感配置应逐项说明。""",
    "测试规则.md": """# 测试规则

| 层级 | 工具/位置 | 命名 | 运行命令 | 覆盖要求 | 来源 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 单元测试 | 待确认 | 待确认 | 待确认 | 关键分支 | SRC-001 | missing |

记录项目实际使用的测试框架、夹具、覆盖门槛和失败排查入口。功能完成前必须运行适用验证并保存证据；未运行测试不得声称通过。""",
}


def _evidence_layout(root: Path) -> tuple[MigrationMove, ...]:
    """把旧实施目录安全映射为变更、证据和历史任务目录。"""

    legacy = root / "03-实施与验收"
    if not legacy.is_dir():
        return ()
    moves: list[MigrationMove] = []
    for source in sorted(path for path in legacy.rglob("*") if path.is_file()):
        relative = source.relative_to(legacy)
        if relative.parts[0] == "任务包" or relative.name == "执行看板.md":
            suffix = relative.relative_to("任务包") if relative.parts[0] == "任务包" else relative
            target = root / "90-历史归档" / "实施任务包" / suffix
        elif relative.parts[0] == "影响分析":
            target = root / "03-变更与证据" / "影响记录" / relative.relative_to("影响分析")
        elif relative.parts[0] == "知识提案":
            target = root / "03-变更与证据" / "待确认知识" / relative.relative_to("知识提案")
        else:
            target = root / "03-变更与证据" / relative
        moves.append(MigrationMove(source, target, _digest(source.read_bytes())))
    return tuple(moves)


def _governance_layout(root: Path) -> tuple[tuple[MigrationMove, ...], tuple[MigrationRemoval, ...], tuple[MigrationRewrite, ...], tuple[MigrationUnresolved, ...]]:
    """计算格式 3 的目录迁移，不删除有实质内容的旧文件。"""

    legacy = root / "05-开发指南"
    target = root / "05-知识治理"
    moves: list[MigrationMove] = []
    removals: list[MigrationRemoval] = []
    rewrites: list[MigrationRewrite] = []
    unresolved: list[MigrationUnresolved] = []
    for name in ("README.md", "AI知识采集协议.md"):
        source = legacy / name
        destination = target / name
        if source.is_file():
            if destination.exists():
                unresolved.append(MigrationUnresolved(source, name, "新旧治理路径同时存在"))
            else:
                moves.append(MigrationMove(source, destination, _digest(source.read_bytes())))
    for name, placeholder in LEGACY_PLACEHOLDERS.items():
        path = legacy / name
        if not path.is_file():
            continue
        normalized = path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
        if normalized == placeholder.strip():
            removals.append(MigrationRemoval(path, _digest(path.read_bytes())))
        else:
            unresolved.append(
                MigrationUnresolved(path, name, "包含项目内容，需确认迁入技术栈或技术契约")
            )
    readme = root / "README.md"
    if readme.is_file() and "05-开发指南" in readme.read_text(encoding="utf-8"):
        rewrites.append(MigrationRewrite(readme, _digest(readme.read_bytes())))
    return tuple(moves), tuple(removals), tuple(rewrites), tuple(unresolved)


def _rewrite_governance_paths(content: str, governance_readme: bool = False) -> str:
    """将旧开发指南语义收敛为知识治理，保留其他项目内容。"""

    result = (
        content.replace("05-开发指南", "05-知识治理")
        .replace("开发指南", "知识治理")
        .replace("00-项目总览/SRC-", "05-知识治理/公共来源/SRC-")
        .replace("rel_implements:", "rel_satisfies:")
        .replace("03-实施与验收/任务包", "90-历史归档/实施任务包")
        .replace("03-实施与验收/影响分析", "03-变更与证据/影响记录")
        .replace("03-实施与验收/知识提案", "03-变更与证据/待确认知识")
        .replace("03-实施与验收", "03-变更与证据")
        .replace("02-架构与契约", "02-技术基线")
    )
    if governance_readme:
        lines = [
            line for line in result.splitlines()
            if "./本地开发.md" not in line and "./测试规则.md" not in line
        ]
        result = "\n".join(lines).rstrip() + "\n"
    return result


FORMAT11_REMOVALS = {
    "01-功能基线/能力地图.md",
    "02-技术基线/关系目录.md",
    "03-变更与证据/当前变更.md",
    "03-变更与证据/验收矩阵.md",
}

FORMAT11_LEGACY_DIRECTORIES = (
    "02-技术基线/独立契约",
    "03-变更与证据/验收契约",
)


def _format13_decision_item(content: str) -> str:
    """把无法安全并入业务文档的旧 ADR 无损转为待确认通用知识。"""

    content = re.sub(r"(?m)^type:\s*adr\s*$", "type: knowledge_item", content)
    content = re.sub(r"(?m)^status:\s*accepted\s*$", "status: missing", content)
    content = re.sub(
        r'(?ms)^rel_classified_under:\s*\n(?:\s+-.*\n)+',
        'rel_classified_under:\n  - "[[03-变更与证据/待确认知识/README|IDX-PROPOSALS]]"\n',
        content,
    )
    return content


def _format13_document(content: str) -> str:
    """移除格式 13 已废弃的功能 ADR 引用字段。"""

    return re.sub(r"(?ms)^adr:\s*.*?(?=^[A-Za-z_][A-Za-z0-9_-]*:|^---\s*$)", "", content)


def _format13_layout(root: Path) -> tuple[tuple[MigrationMove, ...], tuple[MigrationRemoval, ...], tuple[MigrationUnresolved, ...]]:
    """移除独立决策目录，并把尚未人工归属的真实内容移入待确认知识。"""

    decision_root = root / "04-决策记录"
    moves: list[MigrationMove] = []
    removals: list[MigrationRemoval] = []
    unresolved: list[MigrationUnresolved] = []
    if decision_root.is_dir():
        for source in sorted(path for path in decision_root.rglob("*") if path.is_file()):
            if source.name == "README.md":
                removals.append(MigrationRemoval(source, _digest(source.read_bytes())))
                continue
            target = root / "03-变更与证据" / "待确认知识" / source.name
            if target.exists():
                unresolved.append(MigrationUnresolved(source, source.stem, "待确认知识目标文件已存在"))
            else:
                moves.append(MigrationMove(source, target, _digest(source.read_bytes())))
    legacy_template = root / ".project-kb" / "templates" / "knowledge" / "adr.md"
    if legacy_template.is_file():
        removals.append(MigrationRemoval(legacy_template, _digest(legacy_template.read_bytes())))
    return tuple(moves), tuple(removals), tuple(unresolved)

FORMAT11_CLASSIFICATION_INDEXES = {
    "00-项目总览": "IDX-OVERVIEW",
    "01-功能基线": "IDX-FUNCTIONAL-BASELINE",
    "01-功能基线/需求": "IDX-REQUIREMENTS",
    "01-功能基线/功能": "IDX-FEATURES",
    "02-技术基线/模块": "IDX-MODULES",
    "02-技术基线/接口": "IDX-INTERFACES",
    "02-技术基线/数据库": "IDX-DATABASE",
    "02-技术基线/数据库/数据源": "IDX-DATA-SOURCES",
    "02-技术基线/数据库/数据库单元": "IDX-DATABASE-UNITS",
    "02-技术基线/数据库/数据命名空间": "IDX-DATABASE-NAMESPACES",
    "02-技术基线/数据库/数据表": "IDX-DATABASE-TABLES",
    "02-技术基线/数据资产": "IDX-DATA-ASSETS",
    "02-技术基线/外部依赖": "IDX-DEPENDENCIES",
    "02-技术基线/原型": "IDX-PROTOTYPES",
    "02-技术基线": "IDX-TECHNICAL-BASELINE",
    "03-变更与证据/变更": "IDX-CHANGES",
    "03-变更与证据/验收证据": "IDX-EVIDENCE",
    "03-变更与证据/待确认知识": "IDX-PROPOSALS",
    "03-变更与证据": "IDX-CHANGES-EVIDENCE",
    "04-决策记录": "IDX-DECISIONS",
    "05-知识治理/来源资料": "IDX-SOURCES",
    "05-知识治理/公共来源": "IDX-COMMON-SOURCES",
    "05-知识治理": "IDX-GOVERNANCE",
    "Clippings": "IDX-CLIPPINGS",
}


def _format11_layout(root: Path) -> tuple[tuple[MigrationMove, ...], tuple[MigrationRemoval, ...], tuple[MigrationUnresolved, ...]]:
    """把旧技术目录迁入格式 11，并删除可再生或已退役的物理文件。"""

    moves: list[MigrationMove] = []
    removals: list[MigrationRemoval] = []
    unresolved: list[MigrationUnresolved] = []
    legacy_technical = root / "02-架构与契约"
    if legacy_technical.is_dir():
        for source in sorted(path for path in legacy_technical.rglob("*") if path.is_file()):
            # TEMPLATE.md 是旧模板占位文件，由下面的删除计划处理，不能同时迁移。
            if source.name == "TEMPLATE.md":
                continue
            if source.relative_to(legacy_technical).parts[0] == "独立契约":
                # 独立契约目录已从当前格式移除；真实契约改放入通用知识目录，
                # README/模板由删除计划处理。
                if source.name == "README.md":
                    removals.append(MigrationRemoval(source, _digest(source.read_bytes())))
                    continue
                target = root / "03-变更与证据" / "待确认知识" / source.name
                if target.exists():
                    unresolved.append(MigrationUnresolved(source, source.stem, "通用知识目标文件已存在"))
                else:
                    moves.append(MigrationMove(source, target, _digest(source.read_bytes())))
                continue
            if source.relative_to(legacy_technical).as_posix() == "关系目录.md":
                removals.append(MigrationRemoval(source, _digest(source.read_bytes())))
                continue
            target = root / "02-技术基线" / source.relative_to(legacy_technical)
            if target.exists():
                unresolved.append(MigrationUnresolved(source, source.stem, "新旧技术基线路径同时存在"))
            else:
                moves.append(MigrationMove(source, target, _digest(source.read_bytes())))
    for relative in sorted(FORMAT11_REMOVALS):
        path = root / relative
        if path.is_file():
            removals.append(MigrationRemoval(path, _digest(path.read_bytes())))
    for directory in (root / "90-历史归档" / "旧契约", root / "90-历史归档" / "旧验收契约"):
        if directory.is_dir():
            for path in sorted(item for item in directory.rglob("*") if item.is_file()):
                removals.append(MigrationRemoval(path, _digest(path.read_bytes())))
    for path in sorted(root.rglob("TEMPLATE.md")):
        if ".project-kb" not in path.parts:
            removals.append(MigrationRemoval(path, _digest(path.read_bytes())))
    for relative in FORMAT11_LEGACY_DIRECTORIES:
        directory = root / relative
        if not directory.is_dir():
            continue
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            if path.name == "README.md" or path.name == "TEMPLATE.md":
                removals.append(MigrationRemoval(path, _digest(path.read_bytes())))
            else:
                target = root / "03-变更与证据" / "待确认知识" / path.name
                if target.exists():
                    unresolved.append(MigrationUnresolved(path, path.stem, "待确认知识目标文件已存在"))
                else:
                    moves.append(MigrationMove(path, target, _digest(path.read_bytes())))
    move_sources = {move.source.resolve() for move in moves}
    removal_paths = {removal.path.resolve() for removal in removals}
    conflicts = move_sources & removal_paths
    if conflicts:
        for path in sorted(conflicts):
            unresolved.append(
                MigrationUnresolved(
                    path,
                    path.name,
                    "同一路径同时出现在移动和删除计划中",
                )
            )
        moves = [move for move in moves if move.source.resolve() not in conflicts]
    unique_removals = {removal.path.resolve(): removal for removal in removals}
    return (
        tuple(moves),
        tuple(sorted(unique_removals.values(), key=lambda item: str(item.path))),
        tuple(unresolved),
    )


def _format11_classification(relative: str, identifier: str | None) -> str | None:
    """根据最终路径生成格式 11 的唯一分类关系。"""

    if identifier == "IDX-ROOT":
        return "rel_classified_under: []"
    directory = relative.rsplit("/", 1)[0] if "/" in relative else ""
    if relative.endswith("/README.md") and identifier and identifier.startswith("IDX-"):
        if "/" not in directory:
            return 'rel_classified_under:\n  - "[[README|IDX-ROOT]]"'
        directory = directory.rsplit("/", 1)[0]
    matches = [
        (prefix, value) for prefix, value in FORMAT11_CLASSIFICATION_INDEXES.items()
        if directory == prefix or directory.startswith(prefix + "/")
    ]
    match = max(matches, key=lambda item: len(item[0]), default=None)
    index = match[1] if match else None
    if index is None:
        return None
    prefix = match[0]
    return f'rel_classified_under:\n  - "[[{prefix}/README|{index}]]"'


def _format11_document(content: str, relative: str, initialized_at: str | None) -> str:
    """将旧文档的路径、分类和已知旧契约类型转换为格式 11 表达。"""

    result = _rewrite_governance_paths(content)
    lines = result.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return result
    closing = next((i for i, line in enumerate(lines[1:], 1) if line.rstrip("\r\n") == "---"), None)
    if closing is None:
        return result
    metadata = "".join(lines[1:closing])
    identifier_match = re.search(r"(?m)^id:\s*(\S+)", metadata)
    identifier = identifier_match.group(1) if identifier_match else None
    type_match = re.search(
        r"(?m)^type:\s*(contract|independent_contract|acceptance_contract)\s*$",
        metadata,
    )
    if type_match:
        metadata = re.sub(
            r"(?m)^type:\s*(?:contract|independent_contract|acceptance_contract)\s*$",
            "type: knowledge_item",
            metadata,
        )
        if not re.search(r"(?m)^status:", metadata):
            metadata += "status: missing\n"
        if not re.search(r"(?m)^sources:", metadata):
            reference = relative.replace("\\", "/")
            metadata += "sources:\n  - type: repository_file\n"
            metadata += f"    reference: {json.dumps(reference, ensure_ascii=False)}\n"
            metadata += "    confirmation_status: observed\n"
        if not re.search(r"(?m)^last_updated:", metadata) and initialized_at:
            metadata += f"last_updated: {initialized_at}\n"
    classification = _format11_classification(relative, identifier)
    if classification:
        metadata = re.sub(r"(?ms)^rel_classified_under:.*?(?=^[A-Za-z_][A-Za-z0-9_]*:|\Z)", "", metadata)
        metadata = re.sub(r"(?m)^type:.*$", lambda match: match.group(0) + "\n" + classification, metadata, count=1)
    return "".join([lines[0], metadata, lines[closing], *lines[closing + 1:]])


def _metadata_block(metadata: str, key: str) -> str:
    """读取一个顶层 Front Matter 字段及其缩进内容。"""

    match = re.search(
        rf"(?ms)^{re.escape(key)}:\s*(.*?)(?=^[A-Za-z_][A-Za-z0-9_-]*:|\Z)",
        metadata,
    )
    return match.group(1).strip() if match else ""


def _simple_metadata_values(metadata: str, key: str) -> list[str]:
    """读取旧需求中使用的行内列表或简单块列表。"""

    raw = _metadata_block(metadata, key)
    if not raw:
        return []
    if raw.startswith("[") and raw.endswith("]"):
        return [item.strip().strip("\"'") for item in raw[1:-1].split(",") if item.strip()]
    return [match.strip().strip("\"'") for match in re.findall(r"(?m)^\s*-\s+(.+)$", raw)]


def _append_requirement_section(body: str, title: str, content: str) -> str:
    """只在旧需求缺少目标章节时追加格式 12 的稳定章节。"""

    if re.search(rf"(?m)^## {re.escape(title)}\s*$", body):
        return body
    return body.rstrip() + f"\n\n## {title}\n\n{content.strip()}\n"


def _embedded_source_rows(metadata: str) -> list[str]:
    """把格式 11 的内嵌来源对象转换为正文来源表格行。"""

    raw = _metadata_block(metadata, "sources")
    if not raw:
        return []
    rows: list[str] = []
    for chunk in re.split(r"(?m)^\s*-\s+", raw):
        chunk = chunk.strip()
        if not chunk:
            continue
        values = {
            key: value.strip().strip("\"'")
            for key, value in re.findall(r"(?m)^\s*([A-Za-z_][A-Za-z0-9_-]*):\s*(.+)$", chunk)
        }
        rows.append(
            "| {type} | {reference} | {observed_at} | {confirmation_status} | {confirmed_at} |".format(
                type=values.get("type", "unknown"),
                reference=values.get("reference", "待确认").replace("|", "\\|"),
                observed_at=values.get("observed_at", "待确认"),
                confirmation_status=values.get("confirmation_status", "observed"),
                confirmed_at=values.get("confirmed_at", "—"),
            )
        )
    return rows


def _format12_requirement(content: str) -> str:
    """把格式 11 需求的重复元数据等价收敛到正文。"""

    lines = content.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return content
    closing = next((i for i, line in enumerate(lines[1:], 1) if line.rstrip("\r\n") == "---"), None)
    if closing is None:
        return content
    metadata = "".join(lines[1:closing])
    if not re.search(r"(?m)^type:\s*requirement\s*$", metadata):
        return content
    body = "".join(lines[closing + 1:])
    mapped_sections = {
        "business_rules": "业务规则",
        "success_criteria": "成功标准",
        "assumptions": "假设",
        "blocking_questions": "待澄清问题",
    }
    for key, title in mapped_sections.items():
        values = _simple_metadata_values(metadata, key)
        if values and re.search(rf"(?m)^## {re.escape(title)}\s*$", body):
            section = re.search(
                rf"(?ms)^## {re.escape(title)}\s*\n(.*?)(?=^## |\Z)", body
            )
            if section and any(value not in section.group(1) for value in values):
                raise ValueError(f"requirement metadata conflicts with body section: {title}")
    rules = _simple_metadata_values(metadata, "business_rules")
    criteria = _simple_metadata_values(metadata, "success_criteria")
    assumptions = _simple_metadata_values(metadata, "assumptions")
    questions = _simple_metadata_values(metadata, "blocking_questions")
    if rules:
        rows = "\n".join(f"| BR-MIGRATED-{index:03d} | {value} | 格式 11 元数据 |" for index, value in enumerate(rules, 1))
        body = _append_requirement_section(body, "业务规则", f"| ID | 规则 | 来源 |\n| --- | --- | --- |\n{rows}")
    if criteria:
        rows = "\n".join(f"| SC-MIGRATED-{index:03d} | {value} | 待确认 | 格式 11 元数据 |" for index, value in enumerate(criteria, 1))
        body = _append_requirement_section(body, "成功标准", f"| ID | 可观察结果 | 验证方式 | 来源 |\n| --- | --- | --- | --- |\n{rows}")
    body = _append_requirement_section(body, "约束与依赖", "无已登记外部依赖。")
    body = _append_requirement_section(body, "假设", "\n".join(f"- {value}" for value in assumptions) if assumptions else "当前没有已登记假设。")
    question_rows = "\n".join(f"| BQ-MIGRATED-{index:03d} | {value} | 待确认 | open |" for index, value in enumerate(questions, 1))
    body = _append_requirement_section(body, "待澄清问题", f"| ID | 问题 | 影响范围 | 状态 |\n| --- | --- | --- | --- |\n{question_rows}")
    source_rows = _embedded_source_rows(metadata)
    source_table = "| 类型 | 精确定位 | 观察时间 | 确认状态 | 确认时间 |\n| --- | --- | --- | --- | --- |"
    source_table += "\n" + ("\n".join(source_rows) if source_rows else "| existing_document | 格式 11 原需求元数据 | 待确认 | observed | — |")
    body = _append_requirement_section(body, "来源与确认", source_table)
    readiness_match = re.search(r"(?m)^(?:spec_readiness|readiness):\s*(\S+)\s*$", metadata)
    readiness = readiness_match.group(1) if readiness_match else "draft"
    removed = (
        "approval_status", "lifecycle_status", "spec_readiness", "readiness", "stakeholders",
        "business_rules", "success_criteria", "assumptions", "blocking_questions", "sources",
    )
    for key in removed:
        metadata = re.sub(
            rf"(?ms)^{re.escape(key)}:.*?(?=^[A-Za-z_][A-Za-z0-9_-]*:|\Z)",
            "",
            metadata,
        )
    status_match = re.search(r"(?m)^status:.*$", metadata)
    insertion = f"readiness: {readiness}"
    if status_match:
        metadata = metadata[:status_match.end()] + "\n" + insertion + metadata[status_match.end():]
    else:
        metadata += insertion + "\n"
    return "".join([lines[0], metadata, lines[closing], body])


def _initialized_at(root: Path) -> str | None:
    """读取清单初始化日期，供遗留文档补齐最新元数据。"""

    manifest = root / "knowledge-base.yaml"
    if not manifest.is_file():
        return None
    match = re.search(
        r"(?m)^initialized_at:\s*(\d{4}-\d{2}-\d{2})\s*$",
        manifest.read_text(encoding="utf-8"),
    )
    return match.group(1) if match else None


def _format14_document(content: str) -> str:
    """为旧数据资产补齐待确认的独立性依据，不猜测业务归属。"""

    if not re.search(r"(?m)^type:\s*data_asset\s*$", content):
        return content
    if re.search(r"(?m)^independence_basis:", content):
        return content
    match = re.search(r"(?m)^sensitivity:.*$", content)
    if not match:
        return content
    return content[:match.start()] + "independence_basis: [missing]\n" + content[match.start():]


def build_migration_proposal(
    root: Path,
    records: Iterable[DocumentRecord],
    policy: CompatibilityPolicy,
) -> MigrationProposal:
    """只读分析旧裸来源编号并生成可确认的一对一转换提案。

    先诊断格式兼容性并建立来源编号索引，再逐份扫描旧记录，把可唯一解析的来源构造成
    正式关系；歧义项保留为 unresolved，最后根据文件摘要构造稳定提案修订号。
    """

    resolved_root = root.resolve()
    result = policy.diagnose(resolved_root)
    if not result.conversion_available and result.format_version != result.creates_format_version:
        raise ValueError("current format has no applicable conversion")
    record_list = list(records)
    sources = _source_paths(record_list)
    source_records = {
        str(record.metadata.get("id")): record
        for record in record_list
        if record.metadata.get("type") == "source" and isinstance(record.metadata.get("id"), str)
    }
    changes: list[MigrationChange] = []
    unresolved: list[MigrationUnresolved] = []
    referenced_source_ids: set[str] = set()
    for record in record_list if result.format_version <= 3 else ():
        if record.metadata.get("type") == "source":
            continue
        raw_sources = record.metadata.get("sources")
        if not isinstance(raw_sources, list) or not raw_sources or all(isinstance(item, dict) for item in raw_sources):
            continue
        links: list[str] = []
        record_unresolved: list[MigrationUnresolved] = []
        for raw_source in raw_sources:
            source_id = str(raw_source)
            referenced_source_ids.add(source_id)
            candidates = sources.get(source_id, [])
            if len(candidates) != 1:
                reason = "来源不存在" if not candidates else "来源编号不唯一"
                record_unresolved.append(
                    MigrationUnresolved(record.path.resolve(), source_id, reason)
                )
                continue
            source_record = source_records[source_id]
            confirmation_status = "confirmed" if record.metadata.get("status") == "approved" else "observed"
            embedded = {
                "type": source_record.metadata.get("source_type"),
                "reference": source_record.metadata.get("reference"),
                "observed_at": f"{source_record.metadata.get('last_updated')}T00:00:00Z",
                "confirmation_status": confirmation_status,
            }
            if confirmation_status == "confirmed":
                approved_at = record.metadata.get("approved_at")
                embedded["confirmed_at"] = f"{approved_at}T00:00:00Z" if approved_at else embedded["observed_at"]
            links.append(json.dumps(embedded, ensure_ascii=False, sort_keys=True))
        if record_unresolved:
            unresolved.extend(record_unresolved)
            continue
        if links:
            data = record.path.read_bytes()
            changes.append(
                MigrationChange(
                    record.path.resolve(), tuple(sorted(set(links))), _digest(data)
                )
            )
    ordered_changes = tuple(sorted(changes, key=lambda item: str(item.path)))
    moves, removals, rewrites, layout_unresolved = _governance_layout(resolved_root)
    if result.creates_format_version >= 11:
        format_moves, format_removals, format_unresolved = _format11_layout(resolved_root)
        moves += format_moves
        removals += format_removals
        layout_unresolved += format_unresolved
    if result.creates_format_version >= 13:
        format_moves, format_removals, format_unresolved = _format13_layout(resolved_root)
        moves += format_moves
        removals += format_removals
        layout_unresolved += format_unresolved
    destinations = {move.target for move in moves}
    for move in _evidence_layout(resolved_root):
        if move.target.exists() or move.target in destinations:
            layout_unresolved += (
                MigrationUnresolved(move.source, move.source.name, "新旧变更证据路径同时存在"),
            )
        else:
            moves += (move,)
            destinations.add(move.target)
    for source_id, record in source_records.items():
        try:
            relative = record.path.resolve().relative_to(resolved_root)
        except ValueError:
            unresolved.append(MigrationUnresolved(record.path.resolve(), source_id, "公共来源路径逃逸知识库"))
            continue
        already_common = relative.as_posix().startswith("05-知识治理/公共来源/")
        if source_id not in referenced_source_ids and not already_common:
            unresolved.append(MigrationUnresolved(record.path.resolve(), source_id, "来源未被任何知识项引用，不能安全删除"))
        if relative.parts and relative.parts[0] == "00-项目总览":
            destination = resolved_root / "05-知识治理" / "公共来源" / record.path.name
            if destination.exists():
                unresolved.append(MigrationUnresolved(record.path.resolve(), source_id, "公共来源新旧位置同时存在"))
            else:
                moves += (MigrationMove(record.path.resolve(), destination, _digest(record.path.read_bytes())),)
    initialized_at = _initialized_at(resolved_root)
    moved_sources = {move.source.resolve() for move in moves}
    if result.creates_format_version >= 11:
        for path in sorted(resolved_root.rglob("*.md")):
            if path.resolve() in moved_sources:
                continue
            original = path.read_text(encoding="utf-8")
            normalized = _format11_document(
                original,
                path.resolve().relative_to(resolved_root).as_posix(),
                initialized_at,
            )
            if result.creates_format_version >= 12:
                try:
                    normalized = _format12_requirement(normalized)
                except ValueError as error:
                    layout_unresolved += (
                        MigrationUnresolved(path.resolve(), path.name, str(error)),
                    )
                    continue
            if result.creates_format_version >= 13:
                normalized = _format13_document(normalized)
            if result.creates_format_version >= 14:
                normalized = _format14_document(normalized)
            if normalized == original:
                continue
            rewrites = tuple(
                item for item in rewrites if item.path.resolve() != path.resolve()
            ) + (MigrationRewrite(path.resolve(), _digest(path.read_bytes()), normalized),)
    readme_rewrites = _current_format_readme_rewrites(resolved_root, record_list)
    readme_paths = {item.path.resolve() for item in readme_rewrites}
    rewrites = tuple(
        item for item in rewrites if item.path.resolve() not in readme_paths
    ) + readme_rewrites
    unresolved.extend(layout_unresolved)
    ordered_unresolved = tuple(
        sorted(unresolved, key=lambda item: (str(item.path), item.source_id))
    )
    creations = _current_format_creations(resolved_root)
    graph_path = resolved_root / ".obsidian" / "graph.json"
    if (resolved_root / ".obsidian").is_dir():
        if graph_path.is_file():
            normalized_graph = graph_text(read_graph(graph_path))
            if normalized_graph != graph_path.read_text(encoding="utf-8"):
                rewrites += (MigrationRewrite(graph_path.resolve(), _digest(graph_path.read_bytes()), normalized_graph),)
        else:
            content = graph_text()
            creations += (MigrationCreation(graph_path.resolve(), content, _digest(content.encode("utf-8"))),)
    common_sources = resolved_root / "05-知识治理" / "公共来源"
    common_readme = common_sources / "README.md"
    if common_sources.is_dir() and not common_readme.exists():
        content = (
            "---\nid: IDX-COMMON-SOURCES\ntype: knowledge_index\ntitle: 公共来源\n"
            "rel_classified_under:\n  - \"[[05-知识治理/README|IDX-GOVERNANCE]]\"\n---\n"
            "# 公共来源\n\n本目录只保存多个知识项共同引用的去重来源；单项知识仍须自带可定位来源。\n"
        )
        creations += (MigrationCreation(common_readme.resolve(), content, _digest(content.encode("utf-8"))),)
    nested_indexes = {
        "02-技术基线/数据库/数据源": ("IDX-DATA-SOURCES", "数据源"),
        "02-技术基线/数据库/数据库单元": ("IDX-DATABASE-UNITS", "数据库单元"),
        "02-技术基线/数据库/数据命名空间": ("IDX-DATABASE-NAMESPACES", "数据命名空间"),
        "02-技术基线/数据库/数据表": ("IDX-DATABASE-TABLES", "数据表"),
    }
    for relative, (identifier, title) in nested_indexes.items():
        directory = resolved_root / relative
        readme = directory / "README.md"
        if not directory.is_dir() or readme.exists():
            continue
        content = (
            f"---\nid: {identifier}\ntype: knowledge_index\ntitle: {title}\n"
            "rel_classified_under:\n  - \"[[02-技术基线/数据库/README|IDX-DATABASE]]\"\n---\n"
            f"# {title}\n\n本目录按稳定身份保存{title}知识。\n"
        )
        creations += (MigrationCreation(readme.resolve(), content, _digest(content.encode("utf-8"))),)
    assets = _current_format_assets(resolved_root)
    return MigrationProposal(
        proposal_revision=_revision(
            result.format_version,
            result.creates_format_version,
            ordered_changes,
            moves,
            removals,
            rewrites,
            creations,
            assets,
            ordered_unresolved,
        ),
        source_version=result.format_version,
        target_version=result.creates_format_version,
        changes=ordered_changes,
        moves=moves,
        removals=removals,
        rewrites=rewrites,
        creations=creations,
        assets=assets,
        unresolved=ordered_unresolved,
    )


def _add_supported_by(content: str, links: tuple[str, ...]) -> str:
    """把旧来源编号替换为 Front Matter 内嵌来源对象。"""

    lines = content.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise ValueError("migration target lacks front matter")
    closing: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.rstrip("\r\n") == "---":
            closing = index
            break
    if closing is None:
        raise ValueError("migration target has incomplete front matter")
    retained: list[str] = []
    skipping = False
    for line in lines[1:closing]:
        if line.startswith(("sources:", "rel_supported_by:")):
            skipping = True
            continue
        if skipping and line.startswith(("  ", "\t")):
            continue
        skipping = False
        retained.append(line)
    addition = ["sources:\n"]
    for encoded in links:
        source = json.loads(encoded)
        first = True
        for key in ("type", "reference", "observed_at", "confirmation_status", "confirmed_at"):
            if key not in source:
                continue
            prefix = "  - " if first else "    "
            addition.append(f'{prefix}{key}: {json.dumps(source[key], ensure_ascii=False)}\n')
            first = False
    return "".join([lines[0], *retained, *addition, lines[closing]]) + "".join(lines[closing + 1:])


def _set_format_version(content: str, target_version: int) -> str:
    """升级根清单版本模型，同时保持项目业务版本原值。"""

    lines = content.splitlines(keepends=True)
    normalized: list[str] = []
    has_format = False
    has_revision = False
    has_created_by = any(line.startswith("created_by:") for line in lines)
    for line in lines:
        if line.startswith(("protocol_version:", "schema_version:")):
            continue
        if line.startswith("format_version:"):
            normalized.append(f"format_version: {target_version}\n")
            has_format = True
            continue
        if line.startswith("revision:"):
            normalized.append("knowledge_revision:" + line.split(":", maxsplit=1)[1])
            has_revision = True
            continue
        if line.startswith("knowledge_revision:"):
            normalized.append(line)
            has_revision = True
            continue
        normalized.append(line)
    lines = normalized
    insertion = next(
        (index + 1 for index, line in enumerate(lines) if line.startswith("project_version:")),
        len(lines),
    )
    if not has_format:
        lines.insert(insertion, f"format_version: {target_version}\n")
        insertion += 1
    if not has_revision:
        lines.insert(insertion, "knowledge_revision: 1\n")
    if not has_created_by:
        authority_index = next(
            (index for index, line in enumerate(lines) if line.startswith("authority:")),
            len(lines),
        )
        lines[authority_index:authority_index] = [
            "created_by:\n",
            "  product: context-atlas\n",
        ]
    return "".join(lines)


def _format13_manifest(content: str) -> str:
    """移除格式 13 已废弃的独立决策 authority。"""

    return re.sub(r"(?m)^\s{2}decisions:\s*.*(?:\r?\n)?", "", content)


def _atomic_write(path: Path, content: str) -> None:
    """在目标目录写入临时文件并原子替换单个知识文件。"""

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".migrating",
        delete=False,
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    """在目标目录写入二进制临时文件并原子替换运行资产。"""

    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".migrating",
        delete=False,
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def apply_migration(
    root: Path,
    proposal: MigrationProposal,
    confirmed_revision: str,
) -> MigrationReport:
    """在修订一致且无歧义时执行转换，并拒绝提案后的文件变化。

    先校验确认修订、未决项、目标边界和原文件摘要，再准备全部新内容；所有目标均未漂移后
    才逐项原子替换，并返回实际迁移文件及原格式版本。
    """

    if not confirmed_revision or confirmed_revision != proposal.proposal_revision:
        raise PermissionError("confirmed revision does not match migration proposal")
    if proposal.unresolved:
        raise ValueError("migration proposal contains unresolved source references")
    resolved_root = root.resolve()
    prepared: list[tuple[Path, str]] = []
    rewrite_by_path = {rewrite.path.resolve(): rewrite for rewrite in proposal.rewrites}
    for change in proposal.changes:
        try:
            change.path.relative_to(resolved_root)
        except ValueError as error:
            raise ValueError("migration target escapes knowledge-base root") from error
        data = change.path.read_bytes()
        if _digest(data) != change.original_digest:
            raise ValueError(f"migration target changed after proposal: {change.path.name}")
        rewrite = rewrite_by_path.get(change.path.resolve())
        base_content = rewrite.content if rewrite is not None and rewrite.content is not None else data.decode("utf-8")
        prepared.append((change.path, _add_supported_by(base_content, change.links)))
    for move in proposal.moves:
        if _digest(move.source.read_bytes()) != move.original_digest:
            raise ValueError(f"migration target changed after proposal: {move.source.name}")
        if move.target.exists():
            raise ValueError(f"migration target already exists: {move.target}")
    for removal in proposal.removals:
        if _digest(removal.path.read_bytes()) != removal.original_digest:
            raise ValueError(f"migration target changed after proposal: {removal.path.name}")
    for rewrite in proposal.rewrites:
        if _digest(rewrite.path.read_bytes()) != rewrite.original_digest:
            raise ValueError(f"migration target changed after proposal: {rewrite.path.name}")
    for creation in proposal.creations:
        if creation.path.exists():
            raise ValueError(f"migration creation target already exists: {creation.path}")
        if _digest(creation.content.encode("utf-8")) != creation.content_digest:
            raise ValueError(f"migration creation content changed: {creation.path.name}")
    for asset in proposal.assets:
        try:
            asset.path.relative_to(resolved_root / ".project-kb")
        except ValueError as error:
            raise ValueError("migration asset escapes runtime root") from error
        current_digest = _digest(asset.path.read_bytes()) if asset.path.is_file() else None
        if current_digest != asset.original_digest:
            raise ValueError(f"migration asset changed after proposal: {asset.path}")
        if _digest(asset.content) != asset.content_digest:
            raise ValueError(f"migration asset content changed: {asset.path}")
    manifest = resolved_root / "knowledge-base.yaml"
    manifest_content = _set_format_version(
        manifest.read_text(encoding="utf-8"), proposal.target_version
    )
    manifest_content = _rewrite_governance_paths(manifest_content)
    if proposal.target_version >= 13:
        manifest_content = _format13_manifest(manifest_content)
    manifest_content = (
        manifest_content
        .replace("03-变更与证据/验收矩阵.md", "03-变更与证据/验收证据/README.md")
        .replace("03-变更与证据/当前变更.md", "03-变更与证据/README.md")
    )
    affected = {path for path, _ in prepared} | {item.source for item in proposal.moves} | {item.target for item in proposal.moves} | {item.path for item in proposal.removals} | {item.path for item in proposal.rewrites} | {item.path for item in proposal.creations} | {item.path for item in proposal.assets} | {manifest}
    backups = {path: path.read_bytes() if path.is_file() else None for path in affected}
    existing_directories = {
        directory.resolve()
        for directory in resolved_root.rglob("*")
        if directory.is_dir()
    }
    try:
        # 先更新隔离副本或已确认目标中的运行资产，使后续知识转换始终配套当前工具。
        # 全部受 affected/backups 事务保护，任一后续步骤失败仍恢复原状态。
        for asset in proposal.assets:
            asset.path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write_bytes(asset.path, asset.content)
        for path, content in prepared:
            _atomic_write(path, content)
        for move in proposal.moves:
            move.target.parent.mkdir(parents=True, exist_ok=True)
            move.source.replace(move.target)
            if move.target.suffix.lower() == ".md":
                normalized = _format11_document(
                    move.target.read_text(encoding="utf-8"),
                    move.target.resolve().relative_to(resolved_root).as_posix(),
                    _initialized_at(resolved_root),
                )
                if proposal.target_version >= 12:
                    normalized = _format12_requirement(normalized)
                if proposal.target_version >= 13 and move.source.parent.name == "04-决策记录":
                    normalized = _format13_decision_item(normalized)
                if proposal.target_version >= 13:
                    normalized = _format13_document(normalized)
                if proposal.target_version >= 14:
                    normalized = _format14_document(normalized)
                if move.target.name == "README.md":
                    normalized = _rewrite_governance_paths(normalized, governance_readme=True)
                _atomic_write(move.target, normalized)
        for removal in proposal.removals:
            removal.path.unlink()
        for rewrite in proposal.rewrites:
            if rewrite.path.resolve() in {path.resolve() for path, _ in prepared}:
                continue
            _atomic_write(
                rewrite.path,
                rewrite.content
                if rewrite.content is not None
                else _rewrite_governance_paths(rewrite.path.read_text(encoding="utf-8")),
            )
        for creation in proposal.creations:
            creation.path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(creation.path, creation.content)
        _atomic_write(manifest, manifest_content)
        for directory in sorted(
            (path for path in resolved_root.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            try:
                directory.rmdir()
            except OSError:
                pass
    except Exception:
        for path, content in backups.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        created_directories = sorted(
            (
                directory
                for directory in resolved_root.rglob("*")
                if directory.is_dir() and directory.resolve() not in existing_directories
            ),
            key=lambda directory: len(directory.parts),
            reverse=True,
        )
        for directory in created_directories:
            try:
                directory.rmdir()
            except OSError:
                pass
        raise
    changed = tuple(
        [path.relative_to(resolved_root).as_posix() for path, _ in prepared]
        + [move.target.relative_to(resolved_root).as_posix() for move in proposal.moves]
        + [removal.path.relative_to(resolved_root).as_posix() for removal in proposal.removals]
        + [rewrite.path.relative_to(resolved_root).as_posix() for rewrite in proposal.rewrites]
        + [creation.path.relative_to(resolved_root).as_posix() for creation in proposal.creations]
        + [asset.path.relative_to(resolved_root).as_posix() for asset in proposal.assets]
        + ["knowledge-base.yaml"]
    )
    return MigrationReport("migrated", changed, proposal.target_version)
