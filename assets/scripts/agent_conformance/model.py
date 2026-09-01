"""定义不同 Agent 运行器共用的场景结果模型。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class ScenarioResult:
    """保存一个验收场景可被机器复核的最小证据。"""

    workspace: Path
    before: set[str]
    after: set[str]
    messages: list[str]
    command_exit_codes: list[int]


@dataclass(frozen=True)
class AgentTurn:
    """保存一次 Agent 命令的运行结果，原始内容不得直接作为发布证据。"""

    session_id: str | None
    exit_code: int
    result_text: str
    structured_output: object | None
    stderr: str
    started_at: datetime
    finished_at: datetime
