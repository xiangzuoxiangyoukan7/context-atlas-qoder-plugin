"""把验证问题渲染为稳定的文本或 JSON 报告。"""

from __future__ import annotations

import json
from typing import Sequence

from .model import Issue


def _sorted(issues: Sequence[Issue]) -> list[Issue]:
    """按路径、代码和消息稳定排序验证问题。"""

    return sorted(issues, key=lambda issue: (str(issue.path), issue.code, issue.message))


def render_text(issues: Sequence[Issue]) -> str:
    """渲染适合人工阅读的逐行验证结果。"""

    if not issues:
        return "Knowledge base validation passed"
    lines: list[str] = []
    for issue in _sorted(issues):
        location = f" ({issue.location})" if issue.location else ""
        lines.append(f"{issue.code} {issue.path}{location}: {issue.message}")
    return "\n".join(lines)


def render_json(issues: Sequence[Issue]) -> str:
    """渲染适合 Agent 和持续集成消费的 JSON 结果。"""

    ordered = _sorted(issues)
    payload = {
        "ok": not ordered,
        "issue_count": len(ordered),
        "issues": [
            {
                "code": issue.code,
                "path": str(issue.path),
                "message": issue.message,
                "location": issue.location,
            }
            for issue in ordered
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
