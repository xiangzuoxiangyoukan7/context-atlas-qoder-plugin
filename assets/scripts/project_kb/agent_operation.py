"""实现带提案修订门禁的确定性 Agent 操作。"""

from __future__ import annotations

# context-atlas-rules: [[rules/知识治理规则#RULE-AGENT-001|RULE-AGENT-001]]

from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from .initialization_contract import validate_initialization_proposal
from .initializer import initialize_from_assets
from .validator import ValidationConfig, validate


@dataclass(frozen=True)
class OperationIssue:
    """保存操作后验证发现的单个结构问题。"""

    code: str
    path: str
    message: str


@dataclass(frozen=True)
class OperationReport:
    """保存 Agent 可安全返回的固定字段操作报告。"""

    operation: str
    target: Path
    changed_files: tuple[str, ...]
    validator_exit_code: int
    issues: tuple[OperationIssue, ...]


@dataclass(frozen=True)
class ConfirmationReport:
    """记录执行器实际验证的确认修订。"""

    state: str
    confirmed_revision: str


@dataclass(frozen=True)
class RuntimeAttemptReport:
    """记录一个不泄露环境变量的解释器探测结果。"""

    command: str
    result: str
    exit_code: int | None
    python_major: int | None


@dataclass(frozen=True)
class RuntimeDetectionReport:
    """记录执行模式选择所依据的最小运行时证据。"""

    performed_by: str
    platform: str
    attempts: tuple[RuntimeAttemptReport, ...]
    selected_command: str | None
    capability_checks: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class ExecutionReport:
    """记录正式写入实际采用的执行模式。"""

    mode: str
    runtime_detection: RuntimeDetectionReport


@dataclass(frozen=True)
class ValidationReport:
    """记录实际执行的知识库验证结果。"""

    result: str
    authority: str
    deterministic_validation: str
    command: str
    exit_code: int
    issue_count: int
    checks: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class InitializationReport:
    """返回初始化结果 Schema 要求的全部字段。"""

    operation: str
    project_root: Path
    knowledge_base: Path
    proposal_revision: str
    confirmation: ConfirmationReport
    execution: ExecutionReport
    written_files: tuple[str, ...]
    technology_stacks: tuple[dict[str, object], ...]
    validation: ValidationReport
    unknowns: tuple[str, ...]
    conflicts: tuple[str, ...]
    next_action: str


def _navigation_smoke(target: Path) -> tuple[tuple[dict[str, str], ...], list[str]]:
    """使用生成目标自己的脚本验证最小渐进导航链路。"""

    operation = target / ".project-kb/scripts/agent_kb_operation.py"
    commands: list[tuple[str, list[str]]] = [
        ("self_contained_children", ["children", str(target), "--path", "."]),
    ]
    stable_ids = re.findall(
        r"(?m)^id:\s*([^\s]+)",
        "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in target.rglob("*.md")
            if path.name != "TEMPLATE.md" and ".project-kb" not in path.parts
        ),
    )
    if stable_ids:
        identifier = stable_ids[0]
        commands.extend(
            (
                ("self_contained_neighbors", ["neighbors", str(target), "--id", identifier]),
                (
                    "self_contained_bounded_graph",
                    ["graph", str(target), "--start", identifier, "--depth", "1", "--max-nodes", "20"],
                ),
            )
        )
    checks: list[dict[str, str]] = []
    failures: list[str] = []
    for name, arguments in commands:
        completed = subprocess.run(
            [sys.executable, str(operation), *arguments],
            cwd=target.parent,
            capture_output=True,
            timeout=120,
        )
        valid_json = False
        try:
            json.loads(completed.stdout.decode("utf-8"))
            valid_json = True
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        passed = completed.returncode == 0 and valid_json
        checks.append({"name": name, "result": "passed" if passed else "failed"})
        if not passed:
            failures.append(name)
    return tuple(checks), failures


def _relative_text(path: Path, root: Path) -> str:
    """将问题路径限制为知识库内相对路径或安全文件名。"""

    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def execute_initialize(
    project_root: Path,
    project_name: str | None,
    proposal_revision: str,
    confirmed_revision: str,
    assets_root: Path,
) -> OperationReport:
    """在确认修订一致后初始化知识库并执行二次验证。"""

    # 修订门禁必须早于路径解析和目录创建，才能保证拒绝时真正零写入。
    if not proposal_revision or proposal_revision != confirmed_revision:
        raise PermissionError("confirmed revision does not match current proposal")

    target = initialize_from_assets(
        project_root=project_root,
        project_name=project_name,
        assets_root=assets_root,
    )
    schema_root = target / ".project-kb" / "schemas"
    validation_issues = validate(target, ValidationConfig(schema_root=schema_root))
    issues = tuple(
        OperationIssue(
            code=issue.code,
            path=_relative_text(issue.path, target),
            message=issue.message,
        )
        for issue in validation_issues
    )
    changed_files = tuple(
        path.relative_to(target).as_posix()
        for path in sorted(target.rglob("*"))
        if path.is_file()
    )
    return OperationReport(
        operation="initialized",
        target=target,
        changed_files=changed_files,
        validator_exit_code=0 if not issues else 1,
        issues=issues,
    )


def execute_initialization_proposal(
    proposal: object,
    confirmed_revision: str,
    assets_root: Path,
) -> InitializationReport:
    """校验完整 Proposal、执行确定性初始化并返回规范报告。"""

    normalized = validate_initialization_proposal(proposal)
    revision = str(normalized["proposal_revision"])
    if revision != confirmed_revision:
        raise PermissionError("confirmed revision does not match current proposal")
    project = normalized["project"]
    assert isinstance(project, dict)
    project_root = Path(str(project["root"])).resolve()
    target = initialize_from_assets(
        project_root=project_root,
        project_name=str(project["id"]),
        assets_root=assets_root,
        proposal=normalized,
        project_display_name=str(project["name"]),
        workspace_profile=str(project["workspace_profile"]),
    )
    schema_root = target / ".project-kb" / "schemas"
    validation_issues = validate(target, ValidationConfig(schema_root=schema_root))
    smoke_checks, smoke_failures = _navigation_smoke(target)
    written_files = tuple(
        path.relative_to(target).as_posix()
        for path in sorted(target.rglob("*"))
        if path.is_file()
    )
    facts = normalized["facts"]
    assert isinstance(facts, dict)
    unknowns = tuple(str(item["id"]) for item in normalized["unknowns"])
    conflicts = tuple(str(item["id"]) for item in normalized["conflicts"])
    next_action = (
        f"处理 {conflicts[0]}" if conflicts else f"确认 {unknowns[0]}" if unknowns else "none"
    )
    command = (
        f"py {target.name}/.project-kb/scripts/check_knowledge_base.py "
        f"{target.name} --schema-root {target.name}/.project-kb/schemas"
    )
    exit_code = 0 if not validation_issues and not smoke_failures else 1
    return InitializationReport(
        operation="initialized" if exit_code == 0 else "failed",
        project_root=project_root,
        knowledge_base=target,
        proposal_revision=revision,
        confirmation=ConfirmationReport("confirmed", confirmed_revision),
        execution=ExecutionReport(
            mode="python_executor",
            runtime_detection=RuntimeDetectionReport(
                performed_by="python_executor",
                platform=sys.platform,
                attempts=(
                    RuntimeAttemptReport(
                        command=sys.executable,
                        result="available",
                        exit_code=0,
                        python_major=sys.version_info.major,
                    ),
                ),
                selected_command=sys.executable,
                capability_checks=(),
            ),
        ),
        written_files=written_files,
        technology_stacks=tuple(facts["technology_stacks"]),
        validation=ValidationReport(
            "passed" if exit_code == 0 else "failed",
            "deterministic_executor",
            "passed" if exit_code == 0 else "failed",
            command,
            exit_code,
            len(validation_issues),
            (
                {
                    "name": "full_schema_and_reference_validation",
                    "result": "passed" if not validation_issues else "failed",
                },
                *smoke_checks,
            ),
        ),
        unknowns=unknowns,
        conflicts=conflicts,
        next_action=next_action,
    )
