"""在自然检查点把结构化知识候选保存为待确认提案队列。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
import tempfile

from .frontmatter import FrontMatterError, parse_document


CHECKPOINTS = {
    "user_decision",
    "requirement_change",
    "contract_change",
    "before_plan",
    "before_delivery",
    "after_acceptance",
    "before_release",
    "session_end",
}
SOURCE_TYPES = {
    "user_statement",
    "repository_file",
    "command_output",
    "existing_document",
    "external_document",
    "ai_inference",
}


@dataclass(frozen=True)
class CaptureCandidate:
    """表示 Agent 在检查点发现但尚未进入正式基线的知识候选。"""

    checkpoint: str
    summary: str
    target_ids: tuple[str, ...]
    source_type: str
    source_reference: str
    differences: tuple[str, ...]
    impact_ids: tuple[str, ...]
    unknowns: tuple[str, ...]
    conflicts: tuple[str, ...]
    proposed_by: str
    operated_by: str
    project_version: str


@dataclass(frozen=True)
class CaptureReport:
    """描述本次捕获是创建新提案还是命中已有重复提案。"""

    status: str
    proposal_id: str
    path: Path
    content_digest: str


def _one_line(value: str, field: str) -> str:
    """规范用户文本为单行并拒绝会破坏元数据边界的空内容。"""

    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{field} must not be empty")
    return normalized


def _content_digest(candidate: CaptureCandidate) -> str:
    """按目标编号和候选摘要生成用于同任务去重的稳定摘要。"""

    targets = ",".join(sorted(set(candidate.target_ids)))
    summary = _one_line(candidate.summary, "summary")
    return hashlib.sha256(f"{targets}\n{summary}".encode("utf-8")).hexdigest()


def _list_text(values: tuple[str, ...]) -> str:
    """把稳定编号列表渲染为受限 Front Matter 行内列表。"""

    return "[" + ", ".join(sorted(set(values))) + "]"


def _bullets(values: tuple[str, ...], empty_text: str) -> str:
    """把说明列表渲染为 Markdown 项，空列表使用明确占位说明。"""

    if not values:
        return f"- {empty_text}"
    return "\n".join(f"- {_one_line(value, 'item')}" for value in values)


def _render(
    proposal_id: str,
    digest: str,
    candidate: CaptureCandidate,
    captured_at: str,
) -> str:
    """渲染不含其他插件全文和正式批准结论的提案文档。"""

    summary = _one_line(candidate.summary, "summary")
    source_reference = _one_line(candidate.source_reference, "source_reference")
    return (
        "---\n"
        f"id: {proposal_id}\n"
        "type: knowledge_proposal\n"
        f"title: {summary}\n"
        "status: proposed\n"
        f"checkpoint: {candidate.checkpoint}\n"
        f"content_digest: {digest}\n"
        f"target_ids: {_list_text(candidate.target_ids)}\n"
        f"source_type: {candidate.source_type}\n"
        f"source_reference: {source_reference}\n"
        f"proposed_by: {candidate.proposed_by}\n"
        f"operated_by: {candidate.operated_by}\n"
        "confirmed_by: pending\n"
        "git_commit: pending\n"
        f"project_version: {candidate.project_version}\n"
        f"captured_at: {captured_at}\n"
        "---\n"
        f"# {proposal_id} {summary}\n\n"
        "> 本文件是自动捕获的待确认候选，不是正式知识，也不构成任务执行许可。\n\n"
        "## 建议更新目标\n\n"
        f"{_bullets(candidate.target_ids, '尚未确定目标知识项')}\n\n"
        "## 与现有知识的差异\n\n"
        f"{_bullets(candidate.differences, '尚未确认差异')}\n\n"
        "## 可能影响\n\n"
        f"{_bullets(candidate.impact_ids, '尚未发现关联影响')}\n\n"
        "## 未决问题\n\n"
        f"{_bullets(candidate.unknowns, '无')}\n\n"
        "## 冲突\n\n"
        f"{_bullets(candidate.conflicts, '无')}\n\n"
        "## 来源\n\n"
        f"- 类型：`{candidate.source_type}`\n"
        f"- 引用：`{source_reference}`\n"
        "- 只保存来源位置或摘要，不复制会话及其他插件过程文件全文。\n"
    )


def _existing_by_digest(queue: Path, digest: str) -> tuple[str, Path] | None:
    """查找同目标和同摘要的已有提案，解析失败文件留给总检查器报告。"""

    if not queue.is_dir():
        return None
    for path in sorted(queue.glob("PROP-*.md")):
        try:
            record = parse_document(path)
        except FrontMatterError:
            continue
        if record.metadata.get("content_digest") == digest:
            identifier = record.metadata.get("id")
            if isinstance(identifier, str):
                return identifier, path
    return None


def _atomic_write(path: Path, content: str) -> None:
    """在队列目录原子创建单个提案文件。"""

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".capturing",
        delete=False,
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def capture_candidate(
    root: Path,
    candidate: CaptureCandidate,
    captured_at: str,
    *,
    user_requested: bool = False,
) -> CaptureReport:
    """在用户明确要求记录时，验证、去重并创建待确认知识。"""

    if not user_requested:
        raise ValueError("recording pending knowledge requires an explicit user request")

    if candidate.checkpoint not in CHECKPOINTS:
        raise ValueError(f"unsupported capture checkpoint: {candidate.checkpoint}")
    if candidate.source_type not in SOURCE_TYPES:
        raise ValueError(f"unsupported source type: {candidate.source_type}")
    if not candidate.target_ids:
        raise ValueError("capture candidate requires target_ids")
    if not candidate.proposed_by.startswith(("PERSON-", "AGENT-")):
        raise ValueError("proposed_by must be PERSON-* or AGENT-*")
    if not candidate.operated_by.startswith("AGENT-"):
        raise ValueError("operated_by must be AGENT-*")
    try:
        timestamp = datetime.fromisoformat(captured_at)
    except ValueError as error:
        raise ValueError("captured_at must be ISO-8601") from error
    digest = _content_digest(candidate)
    queue = root.resolve() / "03-变更与证据" / "待确认知识"
    existing = _existing_by_digest(queue, digest)
    if existing is not None:
        return CaptureReport("duplicate", existing[0], existing[1], digest)
    date_text = timestamp.strftime("%Y%m%d")
    proposal_id = f"PROP-{date_text}-{digest[:8].upper()}"
    queue.mkdir(parents=True, exist_ok=True)
    path = queue / f"{proposal_id}.md"
    content = _render(proposal_id, digest, candidate, captured_at)
    _atomic_write(path, content)
    return CaptureReport("created", proposal_id, path, digest)
