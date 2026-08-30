"""清点并原子保存 Clippings 暂存箱中的外部来源文件。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
from pathlib import Path
import re
import shutil
import uuid

from .ingest_enhancements import SENSITIVE_ASSIGNMENT
from .validator import ValidationConfig, validate


MAX_MANAGED_SOURCE_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = frozenset({
    ".md", ".txt", ".pdf", ".docx", ".xlsx", ".csv", ".json", ".yaml",
    ".yml", ".png", ".jpg", ".jpeg", ".webp",
})
TEXT_EXTENSIONS = frozenset({".md", ".txt", ".csv", ".json", ".yaml", ".yml"})
MARKER_NAME = "README.md"


@dataclass(frozen=True)
class SourceImportItem:
    """描述一个暂存文件的当前身份、安全状态和固定目标。"""

    source_path: str
    source_id: str
    sha256: str
    size_bytes: int
    mime_type: str
    status: str
    blocked_reason: str | None
    managed_path: str
    card_path: str


@dataclass(frozen=True)
class SourceImportProposal:
    """描述当前暂存箱的不可变保存提案。"""

    operation: str
    proposal_revision: str
    items: tuple[SourceImportItem, ...]
    writes_performed: bool = False


@dataclass(frozen=True)
class SourceImportResult:
    """报告确认后逐文件保存、重复或阻塞结果。"""

    operation: str
    proposal_revision: str
    results: tuple[dict[str, str], ...]
    validator_exit_code: int


def _digest(path: Path) -> str:
    """流式计算文件摘要。"""

    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            value.update(block)
    return value.hexdigest()


def _safe_name(name: str) -> str:
    """把外部文件名收敛为单个可移植路径段。"""

    normalized = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "-", name, flags=re.UNICODE).strip(".-")
    return normalized[:120] or "source"


def _canonical_revision(items: tuple[SourceImportItem, ...]) -> str:
    """根据逐项清单生成与顺序和内容绑定的 Proposal 修订号。"""

    payload = [item.__dict__ for item in items]
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def build_source_import_proposal(knowledge_base_root: Path) -> SourceImportProposal:
    """逐项清点暂存箱，阻塞危险输入并确定唯一受管目标。"""

    root = knowledge_base_root.resolve()
    inbox = root / "Clippings"
    if not inbox.is_dir():
        raise ValueError("managed source inbox does not exist")
    managed_root = root / "05-知识治理" / "来源资料" / "files"
    existing_digests = {
        _digest(path)
        for path in managed_root.rglob("*")
        if path.is_file() and not path.is_symlink()
    } if managed_root.is_dir() else set()
    items: list[SourceImportItem] = []
    for path in sorted(inbox.rglob("*"), key=lambda value: value.as_posix()):
        if not path.is_file() or path.name == MARKER_NAME:
            continue
        relative = path.relative_to(root).as_posix()
        suffix = path.suffix.lower()
        blocked: str | None = None
        if path.is_symlink():
            blocked = "symbolic links are not allowed"
            # 不跟随暂存箱中的链接读取工作区外内容；仍生成稳定身份供 Proposal 复核。
            size = 0
            digest = hashlib.sha256(f"symlink:{relative}".encode("utf-8")).hexdigest()
        else:
            size = path.stat().st_size
            digest = _digest(path)
        if blocked is None and suffix not in ALLOWED_EXTENSIONS:
            blocked = "unsupported file type"
        if blocked is None and size > MAX_MANAGED_SOURCE_BYTES:
            blocked = "file exceeds the 20 MiB limit"
        if blocked is None and suffix in TEXT_EXTENSIONS:
            text = path.read_text(encoding="utf-8", errors="replace")
            if SENSITIVE_ASSIGNMENT.search(text):
                blocked = "text contains a possible secret assignment"
        status = "blocked" if blocked else "duplicate" if digest in existing_digests else "eligible"
        source_id = "SRC-EXT-" + digest[:12].upper()
        filename = f"{digest[:12]}-{_safe_name(path.name)}"
        items.append(SourceImportItem(
            source_path=relative,
            source_id=source_id,
            sha256=digest,
            size_bytes=size,
            mime_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            status=status,
            blocked_reason=blocked,
            managed_path=f"05-知识治理/来源资料/files/{source_id}/{filename}",
            card_path=f"05-知识治理/来源资料/{source_id}.md",
        ))
    if not items:
        raise ValueError("managed source inbox contains no files")
    normalized = tuple(items)
    return SourceImportProposal("managed_source_import", _canonical_revision(normalized), normalized)


def _card(item: SourceImportItem, imported_at: datetime) -> str:
    """生成可校验且不批准文件正文的来源登记卡。"""

    date_text = imported_at.date().isoformat()
    timestamp = imported_at.isoformat()
    return (
        "---\n"
        f"id: {item.source_id}\n"
        "type: managed_source\n"
        f"title: {_safe_name(Path(item.source_path).name)}\n"
        "status: approved\n"
        "content_revision: 1\n"
        f"original_reference: {item.source_path}\n"
        f"managed_path: {item.managed_path}\n"
        f"sha256: {item.sha256}\n"
        f"mime_type: {item.mime_type}\n"
        f"size_bytes: {item.size_bytes}\n"
        "sensitivity: internal\n"
        "sources:\n"
        "  - type: external_document\n"
        f"    reference: {item.source_path}\n"
        f"    observed_at: {timestamp}\n"
        "    confirmation_status: confirmed\n"
        f"    confirmed_at: {timestamp}\n"
        f"last_updated: {date_text}\n"
        "---\n"
        f"# {item.source_id}\n\n此文件是受管来源证据；保存不表示批准其中的业务内容。\n"
    )


def apply_source_import(
    knowledge_base_root: Path,
    proposal_revision: str,
    confirmed_revision: str,
    *,
    imported_at: datetime | None = None,
) -> SourceImportResult:
    """核对当前提案后保存合格文件，验证成功才删除暂存原件。"""

    root = knowledge_base_root.resolve()
    proposal = build_source_import_proposal(root)
    if proposal_revision != proposal.proposal_revision or confirmed_revision != proposal.proposal_revision:
        raise PermissionError("confirmed revision does not match current source import proposal")
    now = imported_at or datetime.now(timezone.utc)
    source_root = root / "05-知识治理" / "来源资料"
    source_root.mkdir(parents=True, exist_ok=True)
    staging = source_root / f".importing-{uuid.uuid4().hex[:8]}"
    staging.mkdir()
    installed: list[Path] = []
    originals_to_delete: list[Path] = []
    results: list[dict[str, str]] = []
    try:
        for item in proposal.items:
            original = root / item.source_path
            if item.status == "blocked":
                results.append({"source_path": item.source_path, "status": "blocked", "reason": item.blocked_reason or "blocked"})
                continue
            if item.status == "duplicate":
                results.append({"source_path": item.source_path, "status": "duplicate", "source_id": item.source_id})
                originals_to_delete.append(original)
                continue
            staged_file = staging / item.managed_path
            staged_card = staging / item.card_path
            staged_file.parent.mkdir(parents=True, exist_ok=True)
            staged_card.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, staged_file)
            if _digest(staged_file) != item.sha256:
                raise ValueError("staged source digest mismatch")
            staged_card.write_text(_card(item, now), encoding="utf-8", newline="\n")
            final_file = root / item.managed_path
            final_card = root / item.card_path
            if final_file.exists() or final_card.exists():
                raise FileExistsError("managed source target already exists")
            final_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staged_file), str(final_file))
            shutil.move(str(staged_card), str(final_card))
            installed.extend((final_file, final_card))
            originals_to_delete.append(original)
            results.append({"source_path": item.source_path, "status": "saved", "source_id": item.source_id, "managed_path": item.managed_path})
        issues = validate(root, ValidationConfig(schema_root=root / ".project-kb" / "schemas"))
        if issues:
            raise ValueError("managed source target validation failed: " + ", ".join(issue.code for issue in issues))
        for original in originals_to_delete:
            original.unlink()
        return SourceImportResult("managed_source_imported", proposal.proposal_revision, tuple(results), 0)
    except Exception:
        for path in reversed(installed):
            if path.is_file():
                path.unlink()
        for parent in sorted({path.parent for path in installed}, key=lambda value: len(value.parts), reverse=True):
            if parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
