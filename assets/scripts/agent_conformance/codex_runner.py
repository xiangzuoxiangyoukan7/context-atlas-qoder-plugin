"""以临时插件安装和安全沙箱运行 Codex 单轮对话。"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .claude_runner import Clock, ProcessRunner
from .model import AgentTurn


def _utc_now() -> datetime:
    """返回当前 UTC 时间作为运行证据时间。"""

    return datetime.now(timezone.utc)


def resolve_codex_executable() -> str:
    """解析不经过 Shell 即可启动的 Codex 可执行文件。"""

    return shutil.which("codex") or "codex"


def _adapt_prompt(prompt: str) -> str:
    """将 Claude 显式技能命令转换为 Codex 的技能调用语法。"""

    mappings = {
        "/context-atlas:context-atlas-work": "$context-atlas-work",
        "/context-atlas:context-atlas-init": "$context-atlas-init",
        "/context-atlas:context-atlas-navigate": "$context-atlas-navigate",
        "/context-atlas:context-atlas-review": "$context-atlas-review",
        "/context-atlas:context-atlas-ingest": "$context-atlas-ingest",
        "/context-atlas:context-atlas-add": "$context-atlas-add",
        "/context-atlas:context-atlas-revise": "$context-atlas-revise",
        "/context-atlas:context-atlas-retire": "$context-atlas-retire",
        "/context-atlas:context-atlas-upgrade": "$context-atlas-upgrade",
        "/context-atlas-work": "$context-atlas-work",
        "/context-atlas-init": "$context-atlas-init",
        "/context-atlas-navigate": "$context-atlas-navigate",
        "/context-atlas-review": "$context-atlas-review",
        "/context-atlas-ingest": "$context-atlas-ingest",
        "/context-atlas-add": "$context-atlas-add",
        "/context-atlas-revise": "$context-atlas-revise",
        "/context-atlas-retire": "$context-atlas-retire",
        "/context-atlas-upgrade": "$context-atlas-upgrade",
    }
    adapted = prompt
    for claude_command, codex_command in mappings.items():
        adapted = adapted.replace(claude_command, codex_command)
    return adapted


def _parse_json_lines(stdout: str) -> tuple[str | None, str, object]:
    """从 Codex JSONL 事件流提取线程编号与最后一条 Agent 正文。"""

    session_id: str | None = None
    result_text = ""
    event_types: list[str] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError("Codex JSONL 事件必须是对象")
        event_type = event.get("type")
        if isinstance(event_type, str):
            event_types.append(event_type)
        if event_type == "thread.started":
            thread_id = event.get("thread_id")
            if isinstance(thread_id, str):
                session_id = thread_id
        if event_type == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str):
                    result_text = text
    return session_id, result_text, {"event_types": event_types}


class CodexRunner:
    """在独立 CODEX_HOME 中安装仓库插件并运行 Codex。"""

    plugin_root: Path
    codex_home: Path
    persist_sessions: bool
    process_runner: ProcessRunner
    now: Clock
    executable: str
    auth_source: Path | None
    continuation_contexts: dict[str, tuple[str, str]]

    def __init__(
        self,
        plugin_root: Path,
        codex_home: Path,
        persist_sessions: bool = False,
        process_runner: ProcessRunner = subprocess.run,
        now: Clock = _utc_now,
        executable: str | None = None,
        auth_source: Path | None = None,
    ) -> None:
        """保存插件源、临时主目录、会话策略和可替换系统边界。"""

        resolved_plugin_root = plugin_root.resolve()
        marketplace_index = resolved_plugin_root / ".agents" / "plugins" / "marketplace.json"
        candidate_source_root = resolved_plugin_root.parent.parent
        if marketplace_index.is_file() and (candidate_source_root / ".codex-plugin").is_dir():
            resolved_plugin_root = candidate_source_root
        self.plugin_root = resolved_plugin_root
        self.codex_home = codex_home.resolve()
        self.persist_sessions = persist_sessions
        self.process_runner = process_runner
        self.now = now
        self.executable = executable or resolve_codex_executable()
        self.auth_source = auth_source
        self.continuation_contexts = {}

    def _environment(self) -> dict[str, str]:
        """构造只重定向 CODEX_HOME 的子进程环境。"""

        environment = dict(os.environ)
        environment["CODEX_HOME"] = str(self.codex_home)
        return environment

    def _prepare_marketplace(self) -> None:
        """在临时主目录创建本地 marketplace 并安装一次仓库插件。"""

        marker = self.codex_home / ".context-atlas-plugin-installed"
        if marker.is_file():
            return
        self.codex_home.mkdir(parents=True, exist_ok=True)
        # Windows Codex 的临时主目录没有沙箱后端默认值；仅声明后端，避免复制用户配置。
        (self.codex_home / "config.toml").write_text(
            '[windows]\nsandbox = "unelevated"\n',
            encoding="utf-8",
        )
        if self.auth_source and self.auth_source.is_file():
            shutil.copy2(self.auth_source, self.codex_home / "auth.json")

        release_root = self.plugin_root
        marketplace = self.codex_home / "context-atlas-marketplace"
        if marketplace.exists():
            shutil.rmtree(marketplace)
        marketplace.mkdir(parents=True, exist_ok=True)
        packaged_plugin = marketplace
        marketplace_name = "context-atlas"
        for relative_path in (Path(".codex-plugin"), Path("skills"), Path("assets"), Path("references")):
            source = self.plugin_root / relative_path
            destination = packaged_plugin / relative_path
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(source, destination)
        marketplace_manifest = marketplace / ".agents" / "plugins" / "marketplace.json"
        marketplace_manifest.parent.mkdir(parents=True, exist_ok=True)
        marketplace_manifest.write_text(
            json.dumps(
                {
                    "name": marketplace_name,
                    "interface": {"displayName": "Context Atlas"},
                    "plugins": [
                        {
                            "name": "context-atlas",
                            "source": {"source": "local", "path": "./"},
                            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                            "category": "Productivity",
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        environment = self._environment()
        commands = (
            [
                self.executable,
                "plugin",
                "marketplace",
                "add",
                str(marketplace),
                "--json",
            ],
            [
                self.executable,
                "plugin",
                "add",
                f"context-atlas@{marketplace_name}",
                "--json",
            ],
        )
        for command in commands:
            completed = self.process_runner(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                env=environment,
            )
            if completed.returncode != 0:
                raise RuntimeError("Codex 临时插件安装失败")
        marker.write_text("installed\n", encoding="utf-8")

    def _build_command(
        self,
        workspace: Path,
        prompt: str,
        resume_session_id: str | None,
    ) -> list[str]:
        """构造启用工作区沙箱且不含危险权限绕过参数的命令。"""

        command = [
            self.executable,
            "exec",
            "-s",
            "workspace-write",
            "--json",
            "--skip-git-repo-check",
            "-C",
            str(workspace),
        ]
        command.append("--ephemeral")
        adapted_prompt = _adapt_prompt(prompt)
        if resume_session_id:
            previous_context = self.continuation_contexts.get(resume_session_id)
            if previous_context is None:
                raise RuntimeError("Codex 续接上下文不存在")
            initial_prompt, proposal_revision = previous_context
            # Codex 0.147.0 原生 resume 会恢复为只读沙箱；内存重放保持工作流语义与写权限。
            adapted_prompt = (
                "$context-atlas-init\n"
                "继续同一知识治理流程。首轮用户请求如下：\n"
                f"{initial_prompt}\n\n"
                "首轮已完成只读检查、展示 Proposal，且没有正式写入。\n"
                f"首轮 Proposal 修订号：{proposal_revision}\n\n"
                "用户后续消息：\n"
                f"{adapted_prompt}"
            )
        command.append(adapted_prompt)
        return command

    def run_turn(
        self,
        workspace: Path,
        prompt: str,
        resume_session_id: str | None,
    ) -> AgentTurn:
        """安装临时插件、运行一轮 Codex 并返回脱敏前的内存结果。"""

        self._prepare_marketplace()
        started_at = self.now()
        completed = self.process_runner(
            self._build_command(workspace, prompt, resume_session_id),
            cwd=workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            env=self._environment(),
        )
        finished_at = self.now()
        try:
            session_id, result_text, structured_output = _parse_json_lines(
                completed.stdout
            )
            exit_code = completed.returncode
            stderr = "Codex 产生标准错误输出" if completed.stderr else ""
        except (json.JSONDecodeError, ValueError, TypeError):
            # 原始异常流可能包含提示词、路径或凭据，因此报告只保留固定诊断。
            session_id = None
            result_text = ""
            structured_output = None
            exit_code = completed.returncode or 2
            stderr = "Codex 输出不是有效的 JSONL 事件流"
        if (
            self.persist_sessions
            and session_id
            and exit_code == 0
            and result_text
        ):
            revision_match = re.search(r"sha256:[a-f0-9]{64}", result_text, re.IGNORECASE)
            proposal_revision = (
                revision_match.group(0).lower() if revision_match else "未解析"
            )
            # 只保留用户首轮请求和机器提取的修订号，不重放模型长正文或敏感信息。
            self.continuation_contexts[session_id] = (
                _adapt_prompt(prompt),
                proposal_revision,
            )
        return AgentTurn(
            session_id=session_id,
            exit_code=exit_code,
            result_text=result_text,
            structured_output=structured_output,
            stderr=stderr,
            started_at=started_at,
            finished_at=finished_at,
        )
