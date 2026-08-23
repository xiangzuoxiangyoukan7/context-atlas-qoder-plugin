"""加载权威规则与标准操作，并计算规则消费者覆盖。"""

from __future__ import annotations

# context-atlas-rules: [[rules/知识治理规则#RULE-GOV-001|RULE-GOV-001]] [[rules/知识治理规则#RULE-GOV-002|RULE-GOV-002]]

import json
import re
from dataclasses import dataclass
from pathlib import Path


EXPECTED_OPERATION_IDS = frozenset(
    {
        "initialize",
        "read",
        "capture",
        "create",
        "update",
        "archive",
        "impact-analysis",
        "migrate",
        "validate",
        "release-archive",
    }
)
RULE_LINK_RE = re.compile(
    r"\[\[(?P<path>rules/[^#\]|]+)(?:\.md)?#(?P<id>RULE-[A-Z0-9-]+)\|(?P=id)\]\]"
)


@dataclass(frozen=True)
class Rule:
    """表示规则目录中的权威规则索引。"""

    id: str
    name_zh: str
    authority: str
    authority_path: Path
    enforced_by: frozenset[str]


@dataclass(frozen=True)
class Operation:
    """表示一个平台无关的标准知识库操作。"""

    id: str
    name_zh: str
    rules: frozenset[str]
    path: Path


@dataclass(frozen=True)
class RuleConsumer:
    """表示主动引用权威规则的实现文件。"""

    path: Path
    kind: str


@dataclass(frozen=True)
class RuleIssue:
    """表示规则目录或执行覆盖问题。"""

    code: str
    path: Path
    message: str


@dataclass(frozen=True)
class RuleImpact:
    """表示规则变化对单个消费者的处理要求。"""

    rule_id: str
    consumer: RuleConsumer
    action: str


def _read_json(path: Path) -> object:
    """读取 UTF-8 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))


def _authority_parts(root: Path, authority: str) -> tuple[str, Path]:
    """解析权威 Obsidian 链接中的规则编号和文件路径。"""

    match = RULE_LINK_RE.fullmatch(authority)
    if not match:
        raise ValueError(f"invalid rule authority link: {authority}")
    relative = Path(match.group("path") + ".md")
    return match.group("id"), (root / relative).resolve()


def load_rule_catalog(root: Path) -> dict[str, Rule]:
    """加载并验证编号唯一的权威规则目录。"""

    root = root.resolve()
    payload = _read_json(root / "rules" / "catalog.json")
    if not isinstance(payload, dict) or payload.get("format_version") != 1:
        raise ValueError("rules/catalog.json format_version must be 1")
    entries = payload.get("rules")
    if not isinstance(entries, list):
        raise ValueError("rules/catalog.json rules must be a list")

    result: dict[str, Rule] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("rule entry must be an object")
        rule_id = entry.get("id")
        name_zh = entry.get("name_zh")
        authority = entry.get("authority")
        enforced_by = entry.get("enforced_by")
        if not isinstance(rule_id, str) or not isinstance(name_zh, str):
            raise ValueError("rule id and name_zh must be strings")
        if not isinstance(authority, str) or not isinstance(enforced_by, list):
            raise ValueError(f"invalid rule mapping: {rule_id}")
        linked_id, authority_path = _authority_parts(root, authority)
        if linked_id != rule_id:
            raise ValueError(f"authority id mismatch: {rule_id}")
        if rule_id in result:
            raise ValueError(f"duplicate rule id: {rule_id}")
        result[rule_id] = Rule(
            id=rule_id,
            name_zh=name_zh,
            authority=authority,
            authority_path=authority_path,
            enforced_by=frozenset(str(item) for item in enforced_by),
        )
    return result


def load_operations(root: Path) -> dict[str, Operation]:
    """加载标准操作并验证基础字段结构。"""

    result: dict[str, Operation] = {}
    for path in sorted((root / "operations").glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            raise ValueError(f"operation must be an object: {path}")
        operation_id = payload.get("id")
        name_zh = payload.get("name_zh")
        rules = payload.get("rules")
        if not isinstance(operation_id, str) or not isinstance(name_zh, str):
            raise ValueError(f"invalid operation identity: {path}")
        if not isinstance(rules, list) or not all(isinstance(item, str) for item in rules):
            raise ValueError(f"invalid operation rules: {path}")
        if operation_id in result:
            raise ValueError(f"duplicate operation id: {operation_id}")
        result[operation_id] = Operation(
            id=operation_id,
            name_zh=name_zh,
            rules=frozenset(rules),
            path=path.resolve(),
        )
    return result


def _consumer_kind(root: Path, path: Path) -> str:
    """根据仓库相对位置判定规则消费者类型。"""

    relative = path.resolve().relative_to(root.resolve())
    first = relative.parts[0]
    if first == "skills":
        return "skill"
    if first == "schemas":
        return "schema"
    if first == "templates":
        return "template"
    if first == "scripts":
        return "validator"
    if first == "tests":
        return "acceptance"
    if first == "operations":
        return "operation"
    return "other"


def _consumer_files(root: Path) -> list[Path]:
    """返回可能主动声明规则引用的权威源文件。"""

    paths: list[Path] = []
    scan_roots = (
        root / "skills",
        root / "schemas",
        root / "templates",
        root / "scripts",
        root / "tests",
        root / "operations",
    )
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for path in scan_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".md", ".json", ".py", ".yaml", ".yml"}:
                continue
            if "assets" in path.relative_to(root).parts:
                continue
            paths.append(path)
    return sorted(paths)


def build_reverse_index(root: Path) -> dict[str, tuple[RuleConsumer, ...]]:
    """扫描正向规则引用并生成不落盘的反向索引。"""

    root = root.resolve()
    catalog = load_rule_catalog(root)
    found: dict[str, set[RuleConsumer]] = {rule_id: set() for rule_id in catalog}
    for path in _consumer_files(root):
        text = path.read_text(encoding="utf-8")
        for match in RULE_LINK_RE.finditer(text):
            rule_id = match.group("id")
            if rule_id in found:
                found[rule_id].add(RuleConsumer(path.resolve(), _consumer_kind(root, path)))
    for operation in load_operations(root).values():
        for rule_id in operation.rules:
            if rule_id in found:
                found[rule_id].add(RuleConsumer(operation.path, "operation"))
    return {
        rule_id: tuple(sorted(consumers, key=lambda item: (item.kind, str(item.path))))
        for rule_id, consumers in found.items()
    }


def validate_rule_coverage(root: Path) -> list[RuleIssue]:
    """验证规则权威链接、引用编号和最低消费者覆盖。"""

    root = root.resolve()
    catalog = load_rule_catalog(root)
    operations = load_operations(root)
    reverse_index = build_reverse_index(root)
    issues: list[RuleIssue] = []

    for path in _consumer_files(root):
        text = path.read_text(encoding="utf-8")
        for match in RULE_LINK_RE.finditer(text):
            rule_id = match.group("id")
            if rule_id not in catalog:
                issues.append(RuleIssue("RULE_REFERENCE_UNKNOWN", path, rule_id))
            elif match.group(0) != catalog[rule_id].authority:
                issues.append(RuleIssue("RULE_AUTHORITY_MISMATCH", path, rule_id))

    missing_operations = EXPECTED_OPERATION_IDS - set(operations)
    extra_operations = set(operations) - EXPECTED_OPERATION_IDS
    for operation_id in sorted(missing_operations):
        issues.append(RuleIssue("RULE_OPERATION_MISSING", root / "operations", operation_id))
    for operation_id in sorted(extra_operations):
        issues.append(RuleIssue("RULE_OPERATION_UNKNOWN", operations[operation_id].path, operation_id))
    for operation in operations.values():
        for rule_id in sorted(operation.rules - set(catalog)):
            issues.append(RuleIssue("RULE_REFERENCE_UNKNOWN", operation.path, rule_id))

    for rule in catalog.values():
        if not rule.authority_path.is_file():
            issues.append(RuleIssue("RULE_AUTHORITY_MISSING", rule.authority_path, rule.id))
        else:
            anchor = f'<a id="{rule.id}"></a>'
            if anchor not in rule.authority_path.read_text(encoding="utf-8"):
                issues.append(RuleIssue("RULE_ANCHOR_MISSING", rule.authority_path, rule.id))
        actual_kinds = {consumer.kind for consumer in reverse_index[rule.id]}
        for kind in sorted(rule.enforced_by - actual_kinds):
            issues.append(
                RuleIssue("RULE_COVERAGE_MISSING", root / "rules" / "catalog.json", f"{rule.id}: {kind}")
            )
    return sorted(issues, key=lambda item: (str(item.path), item.code, item.message))


def build_rule_change_impact(root: Path, changed_rule_ids: set[str]) -> list[RuleImpact]:
    """把变化规则的消费者分类为必须处理或人工复核。

    先校验变化编号并构造规则消费者反向索引，再根据消费者类型逐项判断必须处理或人工复核，
    最后返回稳定排序的影响清单。
    """

    catalog = load_rule_catalog(root)
    unknown = changed_rule_ids - set(catalog)
    if unknown:
        raise ValueError(f"unknown changed rules: {sorted(unknown)}")
    reverse_index = build_reverse_index(root)
    must_handle = {"schema", "validator", "template", "operation", "acceptance"}
    impacts: list[RuleImpact] = []
    for rule_id in sorted(changed_rule_ids):
        for consumer in reverse_index[rule_id]:
            action = "must_handle" if consumer.kind in must_handle else "manual_review"
            impacts.append(RuleImpact(rule_id, consumer, action))
    return impacts
