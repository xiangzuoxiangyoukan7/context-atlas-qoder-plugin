"""验证 Codex 与 Claude Code 插件清单的一致性。"""

from __future__ import annotations

import json
import re
from pathlib import Path


SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
CLAUDE_FIELDS = frozenset(
    {
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "skills",
    }
)
QODER_FIELDS = frozenset(
    {
        "name",
        "version",
        "displayName",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "skills",
    }
)
COMMON_FIELDS = ("name", "version", "description")
CODEX_MARKETPLACE = Path(".agents") / "plugins" / "marketplace.json"
CLAUDE_MARKETPLACE = Path(".claude-plugin") / "marketplace.json"


def _load_object(path: Path) -> dict[str, object]:
    """读取并确认插件清单根节点是 JSON 对象。"""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON 无法解析：{path}: {error.msg}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"JSON 根节点必须是对象：{path}")
    return payload


def load_plugin_manifests(root: Path) -> tuple[dict[str, object], dict[str, object]]:
    """读取仓库中的 Claude 与 Codex 插件清单。"""

    root = root.resolve()
    claude = _load_object(root / ".claude-plugin" / "plugin.json")
    codex = _load_object(root / ".codex-plugin" / "plugin.json")
    return claude, codex


def load_qoder_manifest(root: Path) -> dict[str, object]:
    """读取可选的 Qoder 插件清单；源码仓库缺少时由调用方决定是否报错。"""

    return _load_object(root.resolve() / ".qoder-plugin" / "plugin.json")


def load_marketplace_manifests(root: Path) -> tuple[dict[str, object], dict[str, object]]:
    """读取 Codex 与 Claude Marketplace 索引。"""

    root = root.resolve()
    codex = _load_object(root / CODEX_MARKETPLACE)
    claude = _load_object(root / CLAUDE_MARKETPLACE)
    return codex, claude


def _validate_marketplace(label: str, marketplace: dict[str, object], plugin: dict[str, object], platform: str) -> list[str]:
    """验证单个平台 Marketplace 根对象及插件条目。"""

    errors: list[str] = []
    required_fields = (
        {"name", "interface", "plugins"}
        if platform == "codex"
        else {"name", "description", "owner", "plugins"}
    )
    required_entry_fields = (
        {"name", "source", "policy", "category"}
        if platform == "codex"
        else {"name", "description", "version", "source", "author"}
    )
    for field in ("name", "interface", "plugins") if platform == "codex" else ("name", "description", "owner", "plugins"):
        if field not in marketplace:
            errors.append(f"{label} Marketplace 缺少字段：{field}")
    unexpected_fields = sorted(set(marketplace) - required_fields)
    if unexpected_fields:
        errors.append(f"{label} Marketplace 含非标准字段：{unexpected_fields}")
    if not isinstance(marketplace.get("name"), str) or not marketplace.get("name"):
        errors.append(f"{label} Marketplace 的 name 必须是非空字符串")
    if platform == "codex":
        if not isinstance(marketplace.get("interface"), dict):
            errors.append(f"{label} Marketplace 的 interface 必须是对象")
        elif not marketplace["interface"].get("displayName"):
            errors.append(f"{label} Marketplace 的 interface.displayName 必须是非空字符串")
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        errors.append(f"{label} Marketplace 的 plugins 必须是数组")
        return errors
    if not plugins:
        errors.append(f"{label} Marketplace 的 plugins 不能为空")
        return errors
    entry = plugins[0]
    if not isinstance(entry, dict):
        errors.append(f"{label} Marketplace 的第一条插件必须是对象")
        return errors
    for field in required_entry_fields:
        if field not in entry:
            errors.append(f"{label} Marketplace 插件条目缺少字段：{field}")
    unexpected_entry_fields = sorted(set(entry) - required_entry_fields)
    if unexpected_entry_fields:
        errors.append(f"{label} Marketplace 插件条目含非标准字段：{unexpected_entry_fields}")
    if entry.get("name") != "context-atlas":
        errors.append(f"{label} Marketplace 第一条插件名称必须是 context-atlas")
    if entry.get("name") != plugin.get("name"):
        errors.append(f"{label} Marketplace 插件 name 必须与插件清单一致")
    source = entry.get("source")
    if platform == "codex":
        if not isinstance(source, dict) or source.get("source") != "url" or source.get("url") != "./":
            errors.append(f"{label} Marketplace 插件 source 必须是 url ./")
        policy = entry.get("policy")
        if not isinstance(policy, dict):
            errors.append(f"{label} Marketplace 插件 policy 必须是对象")
        else:
            for field in ("installation", "authentication"):
                if field not in policy:
                    errors.append(f"{label} Marketplace policy 缺少字段：{field}")
            if policy.get("installation") not in {"NOT_AVAILABLE", "AVAILABLE", "INSTALLED_BY_DEFAULT"}:
                errors.append(f"{label} Marketplace installation 策略值无效")
            if policy.get("authentication") not in {"ON_INSTALL", "ON_USE"}:
                errors.append(f"{label} Marketplace authentication 策略值无效")
        if entry.get("category") != "Productivity":
            errors.append(f"{label} Marketplace 插件 category 必须是 Productivity")
    elif source != "./":
        errors.append(f"{label} Marketplace 插件来源必须是 ./")
    if platform == "claude" and entry.get("version") != plugin.get("version"):
        errors.append(f"{label} Marketplace 插件 version 必须与插件清单一致")
    return errors


def _safe_skill_path(value: object) -> bool:
    """判断清单是否指向共享 Skill 根目录。"""

    return value == "./skills/"


def _author_name(manifest: dict[str, object]) -> object:
    """安全提取清单中的作者名称。"""

    author = manifest.get("author")
    return author.get("name") if isinstance(author, dict) else None


def _validate_release_boundary(root: Path) -> list[str]:
    """拒绝仅允许出现在开发工作区中的发布包内容。"""

    if (root / ".git").exists():
        return []
    errors: list[str] = []
    for filename in ("AGENTS.md", "CLAUDE.md"):
        if (root / filename).exists():
            errors.append(f"发布包不得包含开发入口：{filename}")
    tests = root / "tests"
    if tests.exists():
        errors.append("发布包不得包含测试夹具：tests/fixtures")
    worktrees = root / ".worktrees"
    if worktrees.exists():
        errors.append("发布包不得包含开发工作区：.worktrees")
    return errors


def validate_plugin_contract(root: Path) -> list[str]:
    """返回双平台身份、字段和 Skill 唯一性错误。"""

    root = root.resolve()
    errors: list[str] = []
    try:
        claude, codex = load_plugin_manifests(root)
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        return [str(error)]

    try:
        codex_marketplace, claude_marketplace = load_marketplace_manifests(root)
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        return [str(error)]

    errors: list[str] = []
    errors.extend(_validate_marketplace("Codex", codex_marketplace, codex, "codex"))
    errors.extend(_validate_marketplace("Claude", claude_marketplace, claude, "claude"))
    errors.extend(_validate_release_boundary(root))

    qoder_path = root / ".qoder-plugin" / "plugin.json"
    if qoder_path.is_file():
        try:
            qoder = load_qoder_manifest(root)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
            errors.append(str(error))
            qoder = None
        if qoder is not None:
            unexpected_qoder = sorted(set(qoder) - QODER_FIELDS)
            if unexpected_qoder:
                errors.append(f"Qoder 清单含不支持字段：{unexpected_qoder}")
            for field in COMMON_FIELDS:
                if qoder.get(field) != claude.get(field):
                    errors.append(f"Qoder 的 {field} 必须与其他平台一致")
            if qoder.get("name") != "context-atlas":
                errors.append("Qoder 插件名称必须是 context-atlas")
            if qoder.get("displayName") != "Context Atlas":
                errors.append("Qoder displayName 必须是 Context Atlas")
            if not _safe_skill_path(qoder.get("skills")):
                errors.append("Qoder 的 skills 必须指向 ./skills/")
            if _author_name(qoder) != _author_name(claude):
                errors.append("Qoder 的 author.name 必须与其他平台一致")
            qoder_marketplace_path = root / ".qoder-plugin" / "marketplace.json"
            if not qoder_marketplace_path.is_file():
                errors.append("Qoder 清单存在时必须提供 .qoder-plugin/marketplace.json")
            else:
                try:
                    qoder_marketplace = _load_object(qoder_marketplace_path)
                    plugins = qoder_marketplace.get("plugins")
                    if not isinstance(plugins, list) or not plugins:
                        errors.append("Qoder Marketplace 的 plugins 必须是非空数组")
                    else:
                        entry = plugins[0]
                        if not isinstance(entry, dict) or entry.get("name") != "context-atlas":
                            errors.append("Qoder Marketplace 第一条插件必须是 context-atlas")
                        elif entry.get("source") != "./":
                            errors.append("Qoder Marketplace 插件 source 必须是 ./")
                except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
                    errors.append(str(error))

    if claude.get("name") != "context-atlas":
        errors.append("Claude 插件名称必须是 context-atlas")
    for field in COMMON_FIELDS:
        if claude.get(field) != codex.get(field):
            errors.append(f"两个平台的 {field} 必须一致")
    if _author_name(claude) != _author_name(codex) or not _author_name(claude):
        errors.append("两个平台的 author.name 必须一致且非空")
    version = claude.get("version")
    if not isinstance(version, str) or not SEMVER_RE.fullmatch(version):
        errors.append("插件版本必须使用严格三段语义版本")
    if set(claude) - CLAUDE_FIELDS:
        errors.append(f"Claude 清单含不支持字段：{sorted(set(claude) - CLAUDE_FIELDS)}")
    for platform, manifest in (("Claude", claude), ("Codex", codex)):
        if not _safe_skill_path(manifest.get("skills")):
            errors.append(f"{platform} 的 skills 必须指向 ./skills/")
    if "hooks" in codex:
        errors.append("Codex 清单不得声明未提供的 hooks")
    interface = codex.get("interface")
    required_interface = {
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "capabilities",
        "defaultPrompt",
    }
    if not isinstance(interface, dict):
        errors.append("Codex 清单缺少 interface")
    else:
        missing = sorted(field for field in required_interface if not interface.get(field))
        if missing:
            errors.append(f"Codex interface 缺少字段：{missing}")
        if interface.get("displayName") != codex.get("name"):
            errors.append("Codex interface.displayName 必须与插件 name 一致")

    expected_skills = {
        (root / "skills" / "context-atlas-work" / "SKILL.md").resolve(),
        (root / "skills" / "context-atlas-init" / "SKILL.md").resolve(),
        (root / "skills" / "context-atlas-navigate" / "SKILL.md").resolve(),
        (root / "skills" / "context-atlas-review" / "SKILL.md").resolve(),
        (root / "skills" / "context-atlas-ingest" / "SKILL.md").resolve(),
        (root / "skills" / "context-atlas-add" / "SKILL.md").resolve(),
        (root / "skills" / "context-atlas-revise" / "SKILL.md").resolve(),
        (root / "skills" / "context-atlas-retire" / "SKILL.md").resolve(),
        (root / "skills" / "context-atlas-upgrade" / "SKILL.md").resolve(),
    }
    named_skills: set[Path] = set()
    for path in root.rglob("SKILL.md"):
        if (root / ".git").exists() and ({".worktrees", ".codex", "build"} & set(path.relative_to(root).parts)):
            continue
        try:
            text = path.read_text(encoding="utf-8")
            if "name: context-atlas-" in text:
                named_skills.add(path.resolve())
        except (OSError, UnicodeDecodeError):
            continue
    if named_skills != expected_skills:
        errors.append("仓库必须且只能存在 context-atlas-work、context-atlas-init、context-atlas-navigate、context-atlas-review、context-atlas-ingest、context-atlas-add、context-atlas-revise、context-atlas-retire 和 context-atlas-upgrade 九个 Skills")
    if (root / "commands").is_dir() and any((root / "commands").iterdir()):
        errors.append("插件不得包含 commands；Codex 与 Claude Code 必须共用 Skills")
    for directory in (root / ".claude-plugin" / "skills", root / ".codex-plugin" / "skills"):
        if directory.exists():
            errors.append(f"平台目录不得复制 Skill：{directory.relative_to(root)}")
    return errors
