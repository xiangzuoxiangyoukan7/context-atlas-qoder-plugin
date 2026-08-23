"""提供增强摄取的批次边界、网页安全读取和脱敏历史保存。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import socket
import tempfile
from typing import Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen


MAX_BATCH_SOURCES = 20
MAX_WEB_BYTES = 1_048_576
MAX_HISTORY_RECORDS = 100
MAX_HISTORY_DAYS = 30
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(token|password|secret|private[_ -]?key)\s*[:=]\s*[^\s,;]+"
)


@dataclass(frozen=True)
class WebSnapshot:
    """描述一个受限网页来源的可追溯快照。"""

    original_url: str
    final_url: str
    observed_at: str
    content_sha256: str
    content_type: str
    text: str


@dataclass(frozen=True)
class HistoryReport:
    """描述一次非正式摄取历史保存和清理结果。"""

    path: str
    removed: tuple[str, ...]
    formal_knowledge_written: bool = False


def validate_batch_sources(sources: list[dict[str, object]]) -> tuple[dict[str, object], ...]:
    """先校验 1～20 个来源的字段和身份唯一性，再返回规范化副本。"""

    if not 1 <= len(sources) <= MAX_BATCH_SOURCES:
        raise ValueError("batch ingest requires between 1 and 20 sources")
    normalized: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for index, source in enumerate(sources, start=1):
        source_type = source.get("type")
        reference = source.get("reference")
        if not isinstance(source_type, str) or not source_type:
            raise ValueError(f"source {index} requires a non-empty type")
        if not isinstance(reference, str) or not reference:
            raise ValueError(f"source {index} requires a non-empty reference")
        identity = (source_type, reference)
        if identity in seen:
            raise ValueError(f"duplicate source identity: {source_type}:{reference}")
        seen.add(identity)
        normalized.append(dict(source))
    return tuple(normalized)


def aggregate_batch_reports(reports: list[dict[str, object]]) -> dict[str, object]:
    """汇总逐来源报告，并保留每项状态和去重后的维护路由。"""

    routes: list[str] = []
    for report in reports:
        raw_routes = report.get("route_plan", [])
        if not isinstance(raw_routes, list):
            raise ValueError("each ingest report route_plan must be a list")
        for route in raw_routes:
            if isinstance(route, str) and route not in routes:
                routes.append(route)
    return {
        "operation": "batch_ingest",
        "status": "blocked"
        if reports and all(item.get("status") == "blocked" for item in reports)
        else "analyzed",
        "source_count": len(reports),
        "reports": reports,
        "route_plan": routes,
        "writes_performed": False,
        "confirmation_state": "not_applicable",
    }


def _validate_public_web_url(url: str) -> None:
    """拒绝非网页协议、本机名和解析到私有网络的地址。"""

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("web source must use an absolute HTTP or HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("web source URL must not contain credentials")
    if parsed.hostname.lower() in {"localhost", "localhost.localdomain"}:
        raise ValueError("local web sources are not allowed")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, None)}
    except socket.gaierror as error:
        raise ValueError("web source host could not be resolved") from error
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValueError("private or local web source addresses are not allowed")


def fetch_web_snapshot(
    url: str,
    *,
    observed_at: datetime | None = None,
    opener: Callable[..., object] = urlopen,
) -> WebSnapshot:
    """读取单个受限网页并返回包含最终定位与摘要的文本快照。"""

    _validate_public_web_url(url)
    request = Request(url, headers={"User-Agent": "Context-Atlas/0.8"})
    with opener(request, timeout=20) as response:  # type: ignore[attr-defined]
        final_url = response.geturl()
        _validate_public_web_url(final_url)
        content_type = response.headers.get_content_type()
        if content_type not in {"text/plain", "text/html", "application/json"}:
            raise ValueError(f"unsupported web content type: {content_type}")
        body = response.read(MAX_WEB_BYTES + 1)
        if len(body) > MAX_WEB_BYTES:
            raise ValueError("web source exceeds the 1 MiB limit")
        charset = response.headers.get_content_charset() or "utf-8"
    text = body.decode(charset, errors="replace")
    return WebSnapshot(
        original_url=url,
        final_url=final_url,
        observed_at=(observed_at or datetime.now(UTC)).isoformat(),
        content_sha256=hashlib.sha256(body).hexdigest(),
        content_type=content_type,
        text=text,
    )


def _sanitize(value: object) -> object:
    """递归脱敏字符串值，并拒绝把网页全文或原始对话写入历史。"""

    if isinstance(value, str):
        return SENSITIVE_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _sanitize(item)
            for key, item in value.items()
            if key not in {"raw_content", "web_text", "conversation", "prompt"}
        }
    return value


def save_ingest_history(
    project_root: Path,
    report: dict[str, object],
    *,
    recorded_at: datetime | None = None,
) -> HistoryReport:
    """显式保存脱敏的非正式报告，并确定性执行条数和时间保留策略。"""

    root = project_root.resolve()
    if not root.is_dir():
        raise ValueError("project root does not exist")
    now = recorded_at or datetime.now(UTC)
    history = root / ".context-atlas" / "ingest-history"
    history.mkdir(parents=True, exist_ok=True)
    safe_report = _sanitize(report)
    payload = {
        "schema_version": "1.0",
        "recorded_at": now.isoformat(),
        "report": safe_report,
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    target = history / f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-{digest[:12]}.json"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=history, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(target)

    entries = sorted(history.glob("*.json"), key=lambda path: path.name)
    cutoff = now - timedelta(days=MAX_HISTORY_DAYS)
    removed: list[str] = []
    for path in list(entries):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            timestamp = datetime.fromisoformat(str(record["recorded_at"]))
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            timestamp = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        if timestamp < cutoff:
            path.unlink()
            removed.append(path.name)
            entries.remove(path)
    for path in entries[:-MAX_HISTORY_RECORDS]:
        path.unlink()
        removed.append(path.name)
    return HistoryReport(
        path=target.relative_to(root).as_posix(),
        removed=tuple(sorted(removed)),
    )
