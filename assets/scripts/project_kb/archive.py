"""为历史知识提供可确认、可重放且失败回滚的归档操作。"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re

from .discovery import discover_records
from .frontmatter import parse_document
from .traceability import REFERENCE_FIELDS, as_list
from .validator import ValidationConfig, validate


@dataclass(frozen=True)
class ArchiveProposal:
    """保存归档范围、并发摘要和需要用户确认的稳定修订号。"""

    source_path: str
    target_path: str
    identifier: str
    successor_id: str
    archived_at: str
    reason: str
    source_reference: str
    source_digest: str
    index_digest: str
    proposal_revision: str


@dataclass(frozen=True)
class ArchiveReport:
    """保存成功归档后移动位置、改动清单和最终校验状态。"""

    operation: str
    proposal_revision: str
    moved_from: str
    moved_to: str
    changed_files: tuple[str, ...]
    validator_exit_code: int


def _safe(root: Path, relative: str) -> Path:
    """解析知识库相对路径并拒绝任何越界结果。"""

    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"路径超出知识库：{relative}") from error
    return path


def _digest(content: bytes) -> str:
    """返回内容摘要，用于检测提案生成后的并发变化。"""

    return sha256(content).hexdigest()


def _replace_status(content: str) -> str:
    """精确替换旧知识状态，并拒绝缺失或含混的状态行。"""

    updated, count = re.subn(
        r"(?m)^status:[ \t]*superseded[ \t]*(?=\r?$)", "status: archived", content, count=1
    )
    if count != 1:
        raise ValueError("源文件必须且只能有一个 superseded 状态")
    return updated


def build_archive_proposal(
    root: Path, source_path: str, target_path: str, successor_id: str,
    archived_at: str, reason: str, source_reference: str,
) -> ArchiveProposal:
    """先验证路径、替代链和残留引用，再构造带文件摘要的只读归档提案。"""

    root = root.resolve()
    source = _safe(root, source_path)
    target = _safe(root, target_path)
    archive = (root / "90-历史归档").resolve()
    if not source.is_file() or source.suffix.lower() != ".md":
        raise ValueError("归档源必须是现存 Markdown 文件")
    try:
        source.relative_to(archive)
        raise ValueError("归档源已经位于历史归档")
    except ValueError as error:
        if str(error) == "归档源已经位于历史归档":
            raise
    try:
        target.relative_to(archive)
    except ValueError as error:
        raise ValueError("归档目标必须位于 90-历史归档") from error
    if target.exists():
        raise FileExistsError(f"归档目标已存在：{target_path}")
    record = parse_document(source)
    identifier = record.metadata.get("id")
    if not isinstance(identifier, str) or record.metadata.get("status") != "superseded":
        raise ValueError("归档源必须有 id 且状态为 superseded")
    if record.metadata.get("superseded_by") != successor_id:
        raise ValueError("归档源的 superseded_by 与后继编号不一致")
    records, issues = discover_records(root, frozenset({".project-kb", ".obsidian", "Excalidraw", "Clippings", "90-历史归档"}))
    if issues:
        raise ValueError("当前知识发现失败")
    ids = {item.metadata.get("id"): item for item in records}
    successor = ids.get(successor_id)
    if successor is None or identifier not in as_list(successor.metadata.get("supersedes")):
        raise ValueError("后继知识不存在或未建立反向 supersedes")
    for item in records:
        for field in REFERENCE_FIELDS:
            if identifier not in as_list(item.metadata.get(field)):
                continue
            if item.path == successor.path and field == "supersedes":
                continue
            raise ValueError(f"当前知识仍引用待归档项：{item.path.relative_to(root)} ({field})")
    index = archive / "README.md"
    if not index.is_file():
        raise ValueError("历史归档缺少 README.md 索引")
    if "<!-- archive-index-end -->" not in index.read_text(encoding="utf-8"):
        raise ValueError("历史归档索引缺少 archive-index-end 标记")
    values = {
        "source_path": source_path, "target_path": target_path, "identifier": identifier,
        "successor_id": successor_id, "archived_at": archived_at, "reason": reason,
        "source_reference": source_reference, "source_digest": _digest(source.read_bytes()),
        "index_digest": _digest(index.read_bytes()),
    }
    revision = _digest(json.dumps(values, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    return ArchiveProposal(**values, proposal_revision=revision)


def apply_archive(root: Path, proposal: ArchiveProposal, confirmed_revision: str) -> ArchiveReport:
    """先核对确认与摘要，再移动、改状态、更新索引并验证；失败时恢复全部写入。"""

    if confirmed_revision != proposal.proposal_revision:
        raise PermissionError("确认修订号与归档提案不一致")
    root = root.resolve()
    current = build_archive_proposal(
        root, proposal.source_path, proposal.target_path, proposal.successor_id,
        proposal.archived_at, proposal.reason, proposal.source_reference,
    )
    if current != proposal:
        raise PermissionError("归档提案生成后文件状态已变化")
    source, target = _safe(root, proposal.source_path), _safe(root, proposal.target_path)
    index = root / "90-历史归档" / "README.md"
    source_bytes, index_bytes = source.read_bytes(), index.read_bytes()
    relative = target.relative_to(index.parent).as_posix()
    row = f"| [{proposal.identifier}](./{relative}) | {proposal.successor_id} | {proposal.archived_at} | {proposal.reason} | {proposal.source_reference} |\n"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_replace_status(source_bytes.decode("utf-8")).encode("utf-8"))
        source.unlink()
        index_text = index_bytes.decode("utf-8")
        updated_index = index_text.replace(
            "<!-- archive-index-end -->", row + "<!-- archive-index-end -->", 1
        )
        index.write_bytes(updated_index.encode("utf-8"))
        issues = validate(root, ValidationConfig(schema_root=root / ".project-kb" / "schemas"))
        if issues:
            raise ValueError("归档后校验失败：" + "; ".join(f"{i.code}: {i.message}" for i in issues))
    except Exception:
        target.unlink(missing_ok=True)
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(source_bytes)
        index.write_bytes(index_bytes)
        raise
    return ArchiveReport("archived", proposal.proposal_revision, proposal.source_path, proposal.target_path, (proposal.target_path, "90-历史归档/README.md"), 0)
