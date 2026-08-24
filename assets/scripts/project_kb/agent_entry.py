"""按当前宿主 Agent 创建或补充项目入口文件。"""

from __future__ import annotations

from pathlib import Path
import re


BEGIN = "<!-- context-atlas:begin -->"
END = "<!-- context-atlas:end -->"
HOST_FILES = {"codex": "AGENTS.md", "qoder": "AGENTS.md", "trae": "AGENTS.md", "claude": "CLAUDE.md"}
BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)


def validate_entry(host: str, filename: str) -> None:
    """校验宿主与入口文件映射，防止 Proposal 写出任意路径。"""

    if host not in HOST_FILES:
        raise ValueError("agent_entry.host is unsupported")
    if filename != HOST_FILES[host]:
        raise ValueError("agent_entry.filename does not match host")


def render_entry_block(knowledge_base_name: str) -> str:
    """渲染可重复更新的 Agent 受管说明区块。"""

    skills = ", ".join(
        f"`context-atlas-{name}`"
        for name in ("init", "navigate", "review", "ingest", "add", "revise", "retire", "upgrade")
    )
    return "\n".join(
        [
            BEGIN,
            "## Context Atlas 项目知识库",
            "",
            f"本项目使用 Context Atlas 管理项目事实，知识库位于 `{knowledge_base_name}/`。",
            "当任务涉及项目架构、约束、功能、接口、数据库、变更、验收证据或来源时，先读取相关知识库内容。",
            "",
            f"可用 Skill：{skills}。",
            "初始化、维护、退役或格式升级前，必须遵循：",
            "`inspect → propose → await_confirmation → apply → validate → report`。",
            "没有用户明确确认时，只能读取、分析和展示 Proposal，不得写入正式知识库。",
            "Context Atlas 只负责项目知识治理，不替代开发决策，也不调用或托管大模型。",
            END,
        ]
    )


def apply_entry(project_root: Path, host: str, filename: str, knowledge_base_name: str) -> Path:
    """根据宿主映射创建或更新受管区块，并保留入口文件其他内容。"""

    validate_entry(host, filename)
    path = project_root / filename
    block = render_entry_block(knowledge_base_name)
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    if BEGIN in original and END in original:
        content = BLOCK_RE.sub(block, original, count=1)
    elif original:
        content = original.rstrip() + "\n\n" + block + "\n"
    else:
        content = "# Agent 项目协作入口\n\n" + block + "\n"
    path.write_text(content, encoding="utf-8", newline="\n")
    return path
