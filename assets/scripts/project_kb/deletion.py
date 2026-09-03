"""为无审计价值知识提供可确认、可预演且失败回滚的物理删除操作。"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile

from .discovery import discover_records
from .frontmatter import parse_document
from .relations import RELATION_LINK
from .traceability import REFERENCE_FIELDS, as_list
from .validator import ValidationConfig, validate


@dataclass(frozen=True)
class DeleteTarget:
    """记录单个删除文件的相对路径、并发摘要和责任人确认原因。"""
    path: str
    digest: str
    reason: str


@dataclass(frozen=True)
class DeleteReplacement:
    """记录为清理关联关系而整体替换的文件及其前后摘要。"""
    path: str
    digest: str
    new_digest: str


@dataclass(frozen=True)
class DeleteProposal:
    """保存删除范围、关系影响、隔离预演结果和不可变确认修订。"""
    operation: str
    deletions: tuple[DeleteTarget, ...]
    replacements: tuple[DeleteReplacement, ...]
    affected_relations: tuple[str, ...]
    source_reference: str
    preflight_status: str
    preflight_issue_count: int
    proposal_revision: str


@dataclass(frozen=True)
class DeleteReport:
    """报告确认后实际删除、同步改写以及最终结构验证结果。"""
    operation: str
    proposal_revision: str
    deleted_files: tuple[str, ...]
    changed_files: tuple[str, ...]
    validator_exit_code: int


def _digest(content: bytes) -> str:
    """计算稳定 SHA-256 摘要以检测确认前后的文件并发变化。"""
    return sha256(content).hexdigest()


def _safe(root: Path, relative: str) -> Path:
    """解析知识库内相对路径，并拒绝越界路径和受管结构资产。"""
    if not relative or Path(relative).is_absolute():
        raise ValueError(f"删除计划路径必须是知识库内相对路径：{relative}")
    path = (root / relative).resolve()
    try:
        parts = path.relative_to(root).parts
    except ValueError as error:
        raise ValueError(f"删除计划路径超出知识库：{relative}") from error
    if not parts or parts[0] in {".project-kb", ".obsidian", "Clippings"} or relative == "knowledge-base.yaml":
        raise ValueError(f"删除操作不支持受管资产或清单路径：{relative}")
    return path


def _load_plan(plan_path: Path) -> dict[str, object]:
    """读取候选删除计划并验证顶层字段和最小非空约束。"""
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("删除计划必须是 JSON 对象")
    if not isinstance(payload.get("source_reference"), str) or not payload["source_reference"]:
        raise ValueError("删除计划必须提供非空 source_reference")
    if not isinstance(payload.get("deletions"), list) or not payload["deletions"]:
        raise ValueError("删除计划必须提供至少一个 deletions 条目")
    if not isinstance(payload.get("replacements", []), list):
        raise ValueError("删除计划 replacements 必须是数组")
    return payload


def _normalize(root: Path, plan: dict[str, object]) -> tuple[tuple[DeleteTarget, ...], tuple[DeleteReplacement, ...], dict[str, str]]:
    """规范化删除和替换项，绑定现存文件摘要并拒绝重复目标。"""
    deletions: list[DeleteTarget] = []
    replacements: list[DeleteReplacement] = []
    contents: dict[str, str] = {}
    seen: set[str] = set()
    for raw in plan["deletions"]:
        if not isinstance(raw, dict) or not isinstance(raw.get("path"), str) or not isinstance(raw.get("reason"), str) or not raw["reason"]:
            raise ValueError("每个删除条目必须提供 path 和非空 reason")
        relative = Path(raw["path"]).as_posix()
        target = _safe(root, relative)
        if relative in seen or not target.is_file() or target.name.casefold() == "readme.md":
            raise ValueError(f"删除目标重复或不存在：{relative}")
        record = parse_document(target)
        if not isinstance(record.metadata.get("id"), str):
            raise ValueError(f"删除目标必须是带稳定 ID 的正式叶子知识：{relative}")
        seen.add(relative)
        deletions.append(DeleteTarget(relative, _digest(target.read_bytes()), raw["reason"]))
    for raw in plan.get("replacements", []):
        if not isinstance(raw, dict) or not isinstance(raw.get("path"), str) or not isinstance(raw.get("content"), str):
            raise ValueError("每个替换条目必须提供 path 和完整 content")
        relative = Path(raw["path"]).as_posix()
        target = _safe(root, relative)
        if relative in seen or not target.is_file():
            raise ValueError(f"替换目标重复、与删除冲突或不存在：{relative}")
        seen.add(relative)
        content = raw["content"]
        replacements.append(DeleteReplacement(relative, _digest(target.read_bytes()), _digest(content.encode("utf-8"))))
        contents[relative] = content
    return tuple(deletions), tuple(replacements), contents


def _relation_targets(metadata: dict[str, object]) -> list[tuple[str, str]]:
    """从新式 rel_ 字段和仍受控的旧式引用字段提取目标编号。"""
    targets: list[tuple[str, str]] = []
    for field, value in metadata.items():
        if field.startswith("rel_"):
            for raw in as_list(value):
                match = RELATION_LINK.fullmatch(raw)
                if match:
                    targets.append((field, match.group("identifier")))
        elif field in REFERENCE_FIELDS:
            targets.extend((field, identifier) for identifier in as_list(value))
    return targets


def _validate_leaf_and_cleanup(
    root: Path,
    deletions: tuple[DeleteTarget, ...],
    replacements: tuple[DeleteReplacement, ...],
    contents: dict[str, str],
) -> tuple[str, ...]:
    """拒绝分类父节点，并证明所有存活入向关系都由计划改写清理。"""

    records, issues = discover_records(
        root, frozenset({".project-kb", ".obsidian", "Excalidraw", "Clippings", "90-历史归档"})
    )
    if issues:
        raise ValueError("当前知识发现失败，不能证明删除目标为叶子节点")
    deleted_paths = {item.path for item in deletions}
    replacement_paths = {item.path for item in replacements}
    deleted_ids = {
        str(parse_document(_safe(root, item.path)).metadata["id"]): item.path for item in deletions
    }
    affected: list[str] = []
    for record in records:
        relative = record.path.relative_to(root).as_posix()
        source_id = str(record.metadata.get("id", relative))
        for field, target_id in _relation_targets(record.metadata):
            if target_id not in deleted_ids or relative in deleted_paths:
                continue
            if field == "rel_classified_under":
                raise ValueError(
                    f"删除目标不是分类树叶子：{deleted_ids[target_id]} 被 {relative} 分类引用"
                )
            affected.append(f"{source_id}:{field}->{target_id}")
            if relative not in replacement_paths:
                raise ValueError(f"删除计划未改写入向关系：{relative} ({field} -> {target_id})")
    for relative, content in contents.items():
        with tempfile.TemporaryDirectory(prefix="context-atlas-relation-check-") as directory:
            candidate = Path(directory) / "candidate.md"
            candidate.write_text(content, encoding="utf-8")
            metadata = parse_document(candidate).metadata
        remaining = [f"{field}->{target}" for field, target in _relation_targets(metadata) if target in deleted_ids]
        if remaining:
            raise ValueError(f"替换内容仍引用删除目标：{relative} ({', '.join(remaining)})")
    return tuple(sorted(affected))


def _mutate(root: Path, deletions: tuple[DeleteTarget, ...], replacements: tuple[DeleteReplacement, ...], contents: dict[str, str]) -> None:
    """先写入完整关系清理内容，再删除已确认的叶子知识文件。"""
    for item in replacements:
        _safe(root, item.path).write_text(contents[item.path], encoding="utf-8")
    for item in deletions:
        _safe(root, item.path).unlink()


def build_delete_proposal(root: Path, plan_path: Path) -> DeleteProposal:
    """构造可确认且经过隔离预演的删除提案。

    读取 Agent 计划并绑定当前文件摘要，证明目标都是分类树叶子且全部存活入向关系由同一计划清理；
    随后复制完整知识库，在隔离副本应用计划并运行结构验证，最终由规范化内容生成稳定修订号。
    """

    root = root.resolve()
    if not (root / "knowledge-base.yaml").is_file():
        raise ValueError("知识库根目录必须包含 knowledge-base.yaml")
    plan = _load_plan(plan_path)
    deletions, replacements, contents = _normalize(root, plan)
    affected_relations = _validate_leaf_and_cleanup(root, deletions, replacements, contents)
    values = {
        "deletions": [item.__dict__ for item in deletions],
        "replacements": [item.__dict__ for item in replacements],
        "source_reference": plan["source_reference"],
        "affected_relations": affected_relations,
    }
    revision = _digest(json.dumps(values, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    with tempfile.TemporaryDirectory(prefix="context-atlas-delete-") as directory:
        staging = Path(directory) / root.name
        shutil.copytree(root, staging)
        _mutate(staging, deletions, replacements, contents)
        issues = validate(staging, ValidationConfig(schema_root=staging / ".project-kb" / "schemas"))
    return DeleteProposal("delete", deletions, replacements, affected_relations, str(plan["source_reference"]), "passed" if not issues else "failed", len(issues), revision)


def apply_delete(root: Path, plan_path: Path, proposal_revision: str, confirmed_revision: str) -> DeleteReport:
    """重算提案后原子应用删除与引用改写，结构验证失败时恢复全部文件。"""

    if not proposal_revision or proposal_revision != confirmed_revision:
        raise PermissionError("confirmed revision does not match current delete proposal")
    root = root.resolve()
    proposal = build_delete_proposal(root, plan_path)
    if proposal.proposal_revision != proposal_revision:
        raise PermissionError("delete proposal no longer matches current files or plan")
    if proposal.preflight_status != "passed":
        raise ValueError("delete preflight validation did not pass")
    plan = _load_plan(plan_path)
    deletions, replacements, contents = _normalize(root, plan)
    snapshots = {item.path: _safe(root, item.path).read_bytes() for item in (*deletions, *replacements)}
    try:
        _mutate(root, deletions, replacements, contents)
        issues = validate(root, ValidationConfig(schema_root=root / ".project-kb" / "schemas"))
        if issues:
            raise ValueError("删除后校验失败：" + "; ".join(f"{issue.code}: {issue.message}" for issue in issues))
    except Exception:
        for relative, content in snapshots.items():
            target = _safe(root, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        raise
    return DeleteReport("deleted", proposal_revision, tuple(item.path for item in deletions), tuple(item.path for item in replacements), 0)
