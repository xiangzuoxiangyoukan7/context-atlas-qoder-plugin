"""以安全、可测试的命令边界运行 Claude Code 单轮对话。"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .model import AgentTurn


class ProcessRunner(Protocol):
    """描述可替换的子进程调用接口，便于离线验证命令契约。"""

    def __call__(
        self,
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        """执行命令并返回包含文本输出的完成结果。"""


class Clock(Protocol):
    """描述返回带时区时间的可替换时钟接口。"""

    def __call__(self) -> datetime:
        """返回当前时间。"""


def _utc_now() -> datetime:
    """返回当前 UTC 时间作为可序列化的运行时间。"""

    return datetime.now(timezone.utc)


def resolve_claude_executable() -> str:
    """解析可由无 Shell 子进程直接启动的 Claude 平台入口。"""

    resolved = shutil.which("claude")
    if not resolved:
        return "claude"
    launcher = Path(resolved)
    if launcher.suffix.lower() in {".cmd", ".ps1"}:
        native_binary = (
            launcher.parent
            / "node_modules"
            / "@anthropic-ai"
            / "claude-code"
            / "bin"
            / "claude.exe"
        )
        # npm 的 Windows 启动脚本只是转发到同包原生程序，直接调用可保持 shell=False。
        if native_binary.is_file():
            return str(native_binary)
    return resolved


def _parse_payload(stdout: str) -> tuple[str | None, str, object | None]:
    """从 Claude 单结果 JSON 中提取允许在内存中使用的字段。"""

    payload = json.loads(stdout)
    if not isinstance(payload, dict):
        raise ValueError("Claude JSON 顶层必须是对象")
    session_id = payload.get("session_id")
    result_text = payload.get("result", "")
    if session_id is not None and not isinstance(session_id, str):
        raise ValueError("Claude session_id 必须是字符串")
    if not isinstance(result_text, str):
        raise ValueError("Claude result 必须是字符串")
    return session_id, result_text, payload.get("structured_output")


def build_turn_evidence(turn: AgentTurn, scenario_id: str) -> dict[str, object]:
    """构造不含会话、提示词、正文和认证信息的白名单证据。"""

    return {
        "scenario_id": scenario_id,
        "exit_code": turn.exit_code,
        "started_at": turn.started_at.isoformat(),
        "finished_at": turn.finished_at.isoformat(),
        "has_session": bool(turn.session_id),
        "has_result": bool(turn.result_text),
        "has_structured_output": turn.structured_output is not None,
    }


class ClaudeRunner:
    """使用仓库插件在指定临时工作区执行 Claude Code。"""

    plugin_root: Path
    persist_sessions: bool
    process_runner: ProcessRunner
    now: Clock
    executable: str

    def __init__(
        self,
        plugin_root: Path,
        persist_sessions: bool = False,
        process_runner: ProcessRunner = subprocess.run,
        now: Clock = _utc_now,
        executable: str | None = None,
    ) -> None:
        """保存绝对插件路径、会话策略和可替换系统边界。"""

        resolved_plugin_root = plugin_root.resolve()
        marketplace_index = resolved_plugin_root / ".claude-plugin" / "marketplace.json"
        candidate_source_root = resolved_plugin_root.parent.parent
        if (
            marketplace_index.is_file()
            and not (resolved_plugin_root / "skills").is_dir()
            and (candidate_source_root / "skills").is_dir()
        ):
            resolved_plugin_root = candidate_source_root
        self.plugin_root = resolved_plugin_root
        self.persist_sessions = persist_sessions
        self.process_runner = process_runner
        self.now = now
        self.executable = executable or resolve_claude_executable()

    def _prepare_plugin_release(self, release_root: Path) -> Path:
        """从 Marketplace 发布边界组装 Claude 的临时插件目录。"""

        marketplace = self.plugin_root / ".claude-plugin" / "marketplace.json"
        manifest = self.plugin_root / ".claude-plugin" / "plugin.json"
        skills = self.plugin_root / "skills"
        if not marketplace.is_file() or not manifest.is_file() or not skills.is_dir():
            raise RuntimeError("Claude Marketplace 发布边界不完整")
        claude_plugin = release_root / ".claude-plugin"
        claude_plugin.mkdir(parents=True)
        shutil.copy2(marketplace, claude_plugin / "marketplace.json")
        shutil.copy2(manifest, claude_plugin / "plugin.json")
        shutil.copytree(skills, release_root / "skills")
        shutil.copytree(self.plugin_root / "assets", release_root / "assets")
        shutil.copytree(self.plugin_root / "references", release_root / "references")
        return release_root

    def _build_command(
        self,
        prompt: str,
        resume_session_id: str | None,
        plugin_directory: Path,
    ) -> list[str]:
        """构造不包含危险权限绕过参数的 Claude 命令。"""

        command = [
            self.executable,
            "--bare",
            "-p",
            "--plugin-dir",
            str(plugin_directory),
            "--permission-mode",
            "acceptEdits",
            "--output-format",
            "json",
        ]
        if not self.persist_sessions:
            command.append("--no-session-persistence")
        if resume_session_id:
            command.extend(["--resume", resume_session_id])
        command.append(prompt)
        return command

    def run_turn(
        self,
        workspace: Path,
        prompt: str,
        resume_session_id: str | None,
    ) -> AgentTurn:
        """运行一次 Claude 对话并返回解析后的内存结果。"""

        started_at = self.now()
        with tempfile.TemporaryDirectory(prefix="context-atlas-claude-") as directory:
            plugin_directory = self._prepare_plugin_release(Path(directory))
            command = self._build_command(prompt, resume_session_id, plugin_directory)
            attempts = 2 if resume_session_id is None else 1
            for attempt in range(attempts):
                try:
                    completed = self.process_runner(
                        command,
                        cwd=workspace,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=600,
                    )
                    break
                except subprocess.TimeoutExpired:
                    # 未续接轮按契约不得正式写入，可重试一次；确认后的写入轮必须立即上抛。
                    if attempt + 1 >= attempts:
                        raise
        finished_at = self.now()
        try:
            session_id, result_text, structured_output = _parse_payload(completed.stdout)
            exit_code = completed.returncode
            stderr = "Claude Code 产生标准错误输出" if completed.stderr else ""
        except (json.JSONDecodeError, ValueError, TypeError):
            # 原始无效输出可能含会话、路径或令牌，因此只保留固定诊断信息。
            session_id = None
            result_text = ""
            structured_output = None
            exit_code = completed.returncode or 2
            stderr = "Claude Code 输出不是有效的单结果 JSON"
        return AgentTurn(
            session_id=session_id,
            exit_code=exit_code,
            result_text=result_text,
            structured_output=structured_output,
            stderr=stderr,
            started_at=started_at,
            finished_at=finished_at,
        )
