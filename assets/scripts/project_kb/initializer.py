"""以暂存目录和原子替换方式安全初始化知识库。"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import re
import json
import shutil
import uuid
from .validator import ValidationConfig, validate
from .agent_entry import apply_entry


MARKER_PATTERN = re.compile(r"{{[A-Z][A-Z0-9_]*}}")

OBSIDIAN_COLOR_GROUPS = (
    ("[type:requirement]", 14701138),
    ("[type:feature]", 4360181),
    ("[type:module]", 39423),
    ("[type:interface]", 16753920),
    ("[type:contract OR independent_contract]", 10181046),
    ("[type:database_table OR database_unit OR database_namespace OR data_source]", 3447003),
    ("[type:data_asset]", 16766720),
    ("[type:adr]", 16744448),
    ("[type:acceptance_contract]", 6737151),
    ("[type:specification_change OR specification_delta]", 10040012),
)


def _materialize_obsidian_profile(root: Path) -> None:
    """创建不含个人状态、插件和工作区布局的最小 Obsidian 配置。"""

    settings = root / ".obsidian"
    settings.mkdir()
    (settings / "app.json").write_text("{}\n", encoding="utf-8", newline="\n")
    graph = {
        "collapse-filter": False,
        "search": '-path:"90-历史归档"',
        "showTags": False,
        "showAttachments": False,
        "hideUnresolved": False,
        "showOrphans": True,
        "collapse-color-groups": False,
        "colorGroups": [
            {"query": query, "color": {"a": 1, "rgb": rgb}}
            for query, rgb in OBSIDIAN_COLOR_GROUPS
        ],
        "collapse-display": True,
        "showArrow": True,
        "textFadeMultiplier": 0,
        "nodeSizeMultiplier": 1,
        "lineSizeMultiplier": 1,
        "collapse-forces": True,
        "centerStrength": 0.5,
        "repelStrength": 10,
        "linkStrength": 1,
        "linkDistance": 250,
        "scale": 1,
        "close": False,
    }
    (settings / "graph.json").write_text(
        json.dumps(graph, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _cell(value: object) -> str:
    """将已校验文本安全放入 Markdown 表格单元格。"""

    return str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def _source(fact: dict[str, object]) -> str:
    """把事实来源格式化为可回查的表格文本。"""

    source = fact["source"]
    assert isinstance(source, dict)
    confirmation = source.get("confirmed_at", "未确认")
    return (
        f"{_cell(source['type'])}: {_cell(source['reference'])}; "
        f"observed_at={_cell(source['observed_at'])}; "
        f"confirmation={_cell(source['confirmation_status'])}@{_cell(confirmation)}"
    )


def _embedded_source_lines(fact: dict[str, object]) -> list[str]:
    """把已校验来源渲染为受限 Front Matter 支持的内嵌对象。"""

    source = fact["source"]
    assert isinstance(source, dict)
    lines = [
        f"  - type: {source['type']}",
        f"    reference: {source['reference']}",
        f"    observed_at: {source['observed_at']}",
        f"    confirmation_status: {source['confirmation_status']}",
    ]
    if "confirmed_at" in source:
        lines.append(f"    confirmed_at: {source['confirmed_at']}")
    return lines


def _knowledge_status(fact: dict[str, object]) -> str:
    """将初始化事实状态映射为通用知识状态。"""

    return "approved" if fact.get("status") == "confirmed" else "proposed"


def _render_module(root: Path, item: dict[str, object]) -> None:
    """把模块观察写成可独立引用的模块契约。"""

    identifier = _cell(item["id"])
    source = item["source"]
    assert isinstance(source, dict)
    lines = [
        "---", f"id: {identifier}", "type: module", f"title: {identifier}",
        f"status: {_knowledge_status(item)}", f"paths: [{_cell(source['reference'])}]", "sources:",
        *_embedded_source_lines(item), "rel_provides: []", "rel_calls: []", "rel_depends_on: []",
        f"last_updated: {str(source['observed_at'])[:10]}", "---", f"# {identifier}", "",
        "## 职责", "", _cell(item["value"]), "", "## 明确不负责", "", "待确认。", "",
        "## 允许依赖与禁止依赖", "", "待确认。", "",
    ]
    (root / "02-架构与契约" / "模块" / f"{identifier}.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _render_interface(root: Path, item: dict[str, object]) -> None:
    """把接口观察写成统一接口契约并按编号确定通信类型。"""

    identifier = _cell(item["id"])
    source = item["source"]
    assert isinstance(source, dict)
    prefix = identifier.split("-", 1)[0]
    kinds = {"API": "http", "RPC": "rpc", "EVENT": "event", "WEBHOOK": "webhook", "FILE": "file"}
    lines = [
        "---", f"id: {identifier}", "type: interface", f"title: {identifier}",
        f"status: {_knowledge_status(item)}", f"interface_kind: {kinds.get(prefix, 'function')}",
        "visibility: internal", "version: v1", "sources:", *_embedded_source_lines(item),
        "rel_reads: []", "rel_writes: []", "rel_depends_on: []", "rel_verified_by: []",
        f"last_updated: {str(source['observed_at'])[:10]}", "---", f"# {identifier}", "",
        "## 入口、输入与输出", "", _cell(item["value"]), "", "## 错误语义", "", "待确认。", "",
        "## 版本、兼容与敏感字段", "", "待确认。", "",
    ]
    (root / "02-架构与契约" / "接口" / f"{identifier}.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _render_confirmed_content(root: Path, proposal: dict[str, object]) -> None:
    """把 Proposal 的受控字段渲染到预定义文档，禁止任意目标路径。"""

    facts = proposal["facts"]
    assert isinstance(facts, dict)

    overview = [f"# {_cell(proposal['project']['name'])} 项目概述", "", "## 项目定位", ""]
    goal_items = facts["goals"]
    assert isinstance(goal_items, list)
    if goal_items:
        overview.extend(f"- **{_cell(item['id'])}** {_cell(item['value'])}（{_cell(item['status'])}）" for item in goal_items)
    else:
        overview.append("待确认。")

    overview.extend(["", "## 长期职责", ""])
    inside = facts["boundaries_in"]
    outside = facts["boundaries_out"]
    assert isinstance(inside, list) and isinstance(outside, list)
    overview.extend(f"- **{_cell(item['id'])}** {_cell(item['value'])}（{_cell(item['status'])}）" for item in inside)
    if not inside:
        overview.append("待确认。")
    overview.extend(["", "## 明确不负责", ""])
    overview.extend(f"- **{_cell(item['id'])}** {_cell(item['value'])}（{_cell(item['status'])}）" for item in outside)
    if not outside:
        overview.append("待确认。")
    overview.extend(["", "## 来源", ""])
    source_items = [*goal_items, *inside, *outside]
    overview.extend(f"- **{_cell(item['id'])}** {_source(item)}" for item in source_items)
    if not source_items:
        overview.append("待确认。")
    overview.append("")
    (root / "00-项目总览" / "项目概述.md").write_text("\n".join(overview), encoding="utf-8", newline="\n")

    technologies = ["# 系统架构", "", "## 技术基线", "", "| 技术 | 版本 | 使用目录或模块 | 项目用途 | 构建、测试与运行命令 | 配置位置 | 来源 | 状态 |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    stacks = facts["technology_stacks"]
    assert isinstance(stacks, list)
    technologies.extend(
        f"| {_cell(item['name'])} | {_cell(item['version'])} | {_cell(item['location'])} | {_cell(item['purpose'])} | {_cell('; '.join(item['commands']))} | {_cell(item['configuration'])} | {_source(item)} | {_cell(item['status'])} |"
        for item in stacks
    )
    technologies.append("")
    technologies.extend(["", "## 上下文与组件", "", "待确认。", ""])
    (root / "02-架构与契约" / "系统架构.md").write_text("\n".join(technologies), encoding="utf-8", newline="\n")

    def render_table(relative: str, title: str, group: str, headers: tuple[str, ...]) -> None:
        """将一类仓库观察写入其唯一固定文档。"""

        items = facts[group]
        assert isinstance(items, list)
        lines = [f"# {title}", "", "| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
        for item in items:
            lines.append(
                f"| {_cell(item['id'])} | {_cell(item['value'])} | {_source(item)} | {_cell(item['status'])} |"
            )
        lines.extend(["", "仓库观察只证明可定位的实现事实；产品含义、设计原因和批准状态仍需责任人确认。", ""])
        (root / relative).write_text("\n".join(lines), encoding="utf-8", newline="\n")

    render_table("00-项目总览/术语表.md", "术语表", "terms", ("术语编号", "名称与含义", "来源", "状态"))
    capability_items = [*facts["capabilities"], *facts["features"]]
    facts["_routed_features"] = capability_items
    render_table("01-功能基线/能力地图.md", "产品能力地图", "_routed_features", ("编号", "能力或功能", "来源", "状态"))
    for module in facts["modules"]:
        _render_module(root, module)
    for interface in facts["interfaces"]:
        _render_interface(root, interface)
    render_table("02-架构与契约/数据库/README.md", "数据库知识", "databases", ("数据库编号", "观察事实", "来源", "状态"))
    render_table("02-架构与契约/外部依赖/README.md", "外部依赖", "external_dependencies", ("依赖编号", "依赖与用途", "来源", "状态"))
    render_table("04-决策记录/README.md", "决策记录", "adrs", ("ADR 编号", "已有决策摘要", "来源", "状态"))

    test_items = facts["tests"]
    assert isinstance(test_items, list)
    if test_items:
        technologies.extend(["## 已观察的验证入口", "", "| 编号 | 命令或测试位置 | 来源 | 状态 |", "| --- | --- | --- | --- |"])
        technologies.extend(
            f"| {_cell(item['id'])} | {_cell(item['value'])} | {_source(item)} | {_cell(item['status'])} |"
            for item in test_items
        )
        technologies.append("")
        (root / "02-架构与契约" / "系统架构.md").write_text("\n".join(technologies), encoding="utf-8", newline="\n")


def _safe_project_name(name: str) -> str:
    """验证项目名只能形成一个安全目录段。"""

    normalized = name.strip()
    if not normalized or normalized in {".", ".."} or "/" in normalized or "\\" in normalized:
        raise ValueError("project name must be one safe directory segment")
    return normalized


def _replace_markers(root: Path, values: dict[str, str]) -> None:
    """替换模板变量并拒绝任何未解析标记。"""

    unresolved: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for marker, value in values.items():
            content = content.replace(marker, value)
        unresolved.extend(f"{path}: {marker}" for marker in MARKER_PATTERN.findall(content))
        path.write_text(content, encoding="utf-8", newline="\n")
    if unresolved:
        raise ValueError("unresolved template markers: " + ", ".join(unresolved))


def initialize_from_assets(
    project_root: Path,
    project_name: str | None = None,
    assets_root: Path = Path("assets"),
    initialized_at: str | None = None,
    proposal: dict[str, object] | None = None,
    project_display_name: str | None = None,
    workspace_profile: str = "standard",
    agent_entry: dict[str, str] | None = None,
) -> Path:
    """从 Skill 资产创建自包含且已验证的新知识库。"""

    project_root = project_root.resolve()
    if not project_root.is_dir():
        raise ValueError("project root must be an existing directory")
    name = _safe_project_name(project_name or project_root.name)
    if workspace_profile not in {"standard", "obsidian"}:
        raise ValueError("workspace profile must be standard or obsidian")
    target = project_root / f"doc-{name}"
    if target.exists():
        raise FileExistsError(f"knowledge-base target already exists: {target}")

    assets_root = assets_root.resolve()
    template = assets_root / "templates" / "core" / "doc-project"
    schema_root = assets_root / "schemas"
    if not template.is_dir() or not schema_root.is_dir():
        raise ValueError("Skill assets are incomplete")

    # 先在同一文件系统完成复制和验证，最后原子改名，避免暴露半成品目标。
    staging = project_root / f".{target.name}.initializing-{uuid.uuid4().hex[:8]}"
    staging.mkdir()
    try:
        shutil.copytree(template, staging, dirs_exist_ok=True)
        _replace_markers(
            staging,
            {
                "{{PROJECT_ID}}": name,
                "{{PROJECT_NAME}}": project_display_name or name,
                "{{KNOWLEDGE_BASE_NAME}}": target.name,
                "{{WORKSPACE_PROFILE}}": workspace_profile,
                "{{INITIALIZED_AT}}": initialized_at or date.today().isoformat(),
            },
        )
        if proposal is not None:
            _render_confirmed_content(staging, proposal)
        if workspace_profile == "obsidian":
            _materialize_obsidian_profile(staging)
        shutil.copytree(assets_root / "scripts", staging / ".project-kb" / "scripts")
        shutil.copytree(schema_root, staging / ".project-kb" / "schemas")
        shutil.copy2(
            assets_root / "compatibility.json",
            staging / ".project-kb" / "compatibility.json",
        )
        issues = validate(staging, ValidationConfig(schema_root=staging / ".project-kb" / "schemas"))
        if issues:
            codes = ", ".join(issue.code for issue in issues)
            raise ValueError(f"materialized knowledge base is invalid: {codes}")
        if target.exists():
            raise FileExistsError(f"knowledge-base target appeared during initialization: {target}")
        staging.replace(target)
        if agent_entry is not None:
            entry_path = project_root / agent_entry["filename"]
            original_entry = entry_path.read_bytes() if entry_path.exists() else None
            try:
                apply_entry(project_root, agent_entry["host"], agent_entry["filename"], target.name)
            except Exception:
                if original_entry is None:
                    if entry_path.exists():
                        entry_path.unlink()
                else:
                    entry_path.write_bytes(original_entry)
                shutil.rmtree(target)
                raise
        return target
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
