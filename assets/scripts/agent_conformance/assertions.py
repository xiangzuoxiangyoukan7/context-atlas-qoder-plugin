"""根据文件和命令证据断言跨 Agent 行为不变量。"""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath

from .model import ScenarioResult


SNAPSHOT_SEPARATOR = "\tsha256:"
SENTINEL_NAME = ".context-atlas-sentinel"


def _record_path(record: str) -> str:
    """从带摘要的快照记录中提取 POSIX 相对路径。"""

    return record.split(SNAPSHOT_SEPARATOR, maxsplit=1)[0]


def _is_formal_knowledge_path(relative_path: str) -> bool:
    """判断路径是否位于 Context Atlas 正式知识库目录。"""

    parts = PurePosixPath(relative_path).parts
    return bool(parts) and parts[0].startswith("doc-")


def _sha256(path: Path) -> str:
    """计算哨兵文件摘要，避免依赖 Agent 的文字声明。"""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _snapshot_paths(records: set[str]) -> set[str]:
    """将快照记录集合转换为相对路径集合。"""

    return {_record_path(record) for record in records}


def assert_no_formal_write_before_confirmation(result: ScenarioResult) -> list[str]:
    """报告未确认阶段新增、删除或修改的正式知识文件。"""

    # 使用对称差集同时捕获新增、删除和同路径内容摘要变化。
    changed_records = result.before.symmetric_difference(result.after)
    changed_paths = sorted(
        {
            _record_path(record)
            for record in changed_records
            if _is_formal_knowledge_path(_record_path(record))
        }
    )
    return [f"未确认阶段修改了正式知识文件：{path}" for path in changed_paths]


def assert_ingest_response(
    result_text: str,
    *,
    expected_status: str,
    expected_action: str | tuple[str, ...] | None = None,
    forbidden_values: tuple[str, ...] = (),
) -> list[str]:
    """验证 ingest 正文包含跨平台稳定字段，不比较自然语言逐字内容。"""

    issues: list[str] = []
    required = (
        "source_identity",
        "observed_at",
        "source_digest_or_version",
        "route_plan",
        "writes_performed",
        "false",
        "confirmation_state",
        "not_applicable",
        "next_action",
        expected_status,
    )
    for phrase in required:
        if phrase not in result_text:
            issues.append(f"ingest 报告缺少核心字段或值：{phrase}")
    expected_actions = (
        (expected_action,) if isinstance(expected_action, str) else expected_action or ()
    )
    for action in expected_actions:
        if action not in result_text:
            issues.append(f"ingest 报告缺少预期候选动作或路由：{action}")
    for value in forbidden_values:
        if value in result_text:
            issues.append("ingest 报告回显了禁止公开的测试敏感值")
    return issues


def assert_existing_target_preserved(
    result: ScenarioResult,
    sentinel_sha256: str,
) -> list[str]:
    """报告已有目标快照或固定哨兵内容发生的任何变化。"""

    issues: list[str] = []
    changed_records = result.before.symmetric_difference(result.after)
    changed_formal_paths = sorted(
        {
            _record_path(record)
            for record in changed_records
            if _is_formal_knowledge_path(_record_path(record))
        }
    )
    if changed_formal_paths:
        issues.append(
            "已有正式目标发生变化：" + "、".join(changed_formal_paths)
        )

    sentinels = sorted(result.workspace.rglob(SENTINEL_NAME))
    if len(sentinels) != 1:
        issues.append(f"应存在且仅存在一个哨兵文件，实际为 {len(sentinels)} 个")
        return issues
    if _sha256(sentinels[0]) != sentinel_sha256:
        issues.append("已有目标的哨兵文件摘要发生变化")
    return issues


def assert_valid_initialized_target(
    result: ScenarioResult,
    expected_name: str,
) -> list[str]:
    """报告确认后目标在结构、自包含性、名称或检查结果上的问题。"""

    issues: list[str] = []
    target_name = expected_name if expected_name.startswith("doc-") else f"doc-{expected_name}"
    target = result.workspace / target_name
    required_files = (
        target / "knowledge-base.yaml",
        target / ".project-kb" / "scripts" / "check_knowledge_base.py",
        target / ".project-kb" / "schemas" / "catalog.json",
    )
    after_paths = _snapshot_paths(result.after)
    before_paths = _snapshot_paths(result.before)

    for path in required_files:
        relative_path = path.relative_to(result.workspace).as_posix()
        if not path.is_file():
            issues.append(f"初始化目标缺少自包含文件：{relative_path}")
        if relative_path not in after_paths or relative_path in before_paths:
            issues.append(f"初始化场景未产生预期文件：{relative_path}")

    manifest = target / "knowledge-base.yaml"
    if manifest.is_file():
        expected_line = f"knowledge_base_name: {target_name}"
        if expected_line not in manifest.read_text(encoding="utf-8").splitlines():
            issues.append(f"知识库名称不是预期值：{target_name}")

    # 退出码是实际检查器结果；自然语言中的“成功”不能替代它。
    if not result.command_exit_codes or any(
        exit_code != 0 for exit_code in result.command_exit_codes
    ):
        issues.append(f"场景命令存在非零退出码：{result.command_exit_codes}")
    return issues


def _scenario_index(report: dict[str, object]) -> dict[str, dict[str, object]]:
    """按场景编号索引报告，并忽略无法用于机器判断的畸形条目。"""

    raw_scenarios = report.get("scenarios", [])
    if not isinstance(raw_scenarios, list):
        return {}
    indexed: dict[str, dict[str, object]] = {}
    for scenario in raw_scenarios:
        if not isinstance(scenario, dict):
            continue
        scenario_id = scenario.get("id")
        if isinstance(scenario_id, str):
            indexed[scenario_id] = scenario
    return indexed


def _formal_changed_records(scenario: dict[str, object]) -> list[str]:
    """提取正式知识文件变化路径，忽略平台无关正文和内容摘要。"""

    summary = scenario.get("file_summary")
    if not isinstance(summary, dict):
        return []
    records = summary.get("changed_records", [])
    if not isinstance(records, list):
        return []
    return sorted(
        _record_path(record)
        for record in records
        if isinstance(record, str) and _is_formal_knowledge_path(_record_path(record))
    )


def compare_invariants(
    claude_report: dict[str, object],
    codex_report: dict[str, object],
) -> list[str]:
    """比较两平台结构化行为，不比较可能随机变化的自然语言正文。"""

    issues: list[str] = []
    claude_scenarios = _scenario_index(claude_report)
    codex_scenarios = _scenario_index(codex_report)
    scenario_ids = sorted(set(claude_scenarios) | set(codex_scenarios))

    if claude_report.get("status") != "passed":
        issues.append("Claude 整体验收状态不是 passed")
    if codex_report.get("status") != "passed":
        issues.append("Codex 整体验收状态不是 passed")

    for scenario_id in scenario_ids:
        claude_scenario = claude_scenarios.get(scenario_id)
        codex_scenario = codex_scenarios.get(scenario_id)
        if claude_scenario is None or codex_scenario is None:
            issues.append(f"{scenario_id}：平台场景集合不一致")
            continue
        if claude_scenario.get("status") != codex_scenario.get("status"):
            issues.append(f"{scenario_id}：平台场景状态不一致")
        if claude_scenario.get("command_exit_codes") != codex_scenario.get(
            "command_exit_codes"
        ):
            issues.append(f"{scenario_id}：命令退出码不一致")
        if _formal_changed_records(claude_scenario) != _formal_changed_records(
            codex_scenario
        ):
            issues.append(f"{scenario_id}：正式知识文件变化不一致")
    return issues
