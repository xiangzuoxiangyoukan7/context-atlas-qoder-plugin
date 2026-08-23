"""解析并验证数据库表文档中的字段含义和值域定义。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from typing import Iterable

from .model import DocumentRecord, Issue
from .relations import RELATION_LINK, RelationIndex


FIELD_COLUMNS = (
    "字段编号",
    "字段名",
    "数据类型",
    "可空",
    "默认值",
    "中文含义",
    "值域类型",
    "允许值或最小值",
    "最大值或格式",
    "允许其他值",
    "约束执行位置",
    "来源",
    "锚点",
)
DOMAIN_TYPES = frozenset({"枚举", "范围", "格式", "任意", "未知"})
ENFORCEMENT_TYPES = frozenset({"数据库约束", "应用规则", "仅文档", "未知"})
FIELD_ID_PATTERN = re.compile(r"FIELD-[A-Z0-9-]+$")
SOURCE_LINK_PATTERN = re.compile(r"\[\[[^\]|#]+(?:#[^\]|]+)?\|SRC-[A-Z0-9-]+\]\]$")
RELATION_COLUMNS = ("关系编号", "子字段编号", "主表与字段", "物理约束", "约束名称")
FOREIGN_KEY_ID_PATTERN = re.compile(r"FK-[A-Z0-9-]+$")


@dataclass(frozen=True)
class DatabaseField:
    """表示表文档中一行具有业务含义和值域的数据库字段。"""

    identifier: str
    name: str
    data_type: str
    nullable: str
    default: str
    meaning_zh: str
    domain_type: str
    allowed_or_minimum: str
    maximum_or_format: str
    allow_other: str
    enforcement: str
    source: str
    anchor: str


@dataclass(frozen=True)
class ForeignKeyMapping:
    """表示子表字段到主表字段的逻辑关系和实际物理约束状态。"""

    identifier: str
    child_field_id: str
    parent_field_link: str
    physical_constraint: str
    constraint_name: str


def _cells(line: str) -> list[str]:
    """把 Markdown 表格行拆分为去除首尾空白的单元格。"""

    content = line.strip().strip("|")
    cells: list[str] = []
    current: list[str] = []
    in_wikilink = False
    index = 0
    while index < len(content):
        pair = content[index : index + 2]
        if pair == "[[":
            in_wikilink = True
            current.extend(pair)
            index += 2
            continue
        if pair == "]]":
            in_wikilink = False
            current.extend(pair)
            index += 2
            continue
        character = content[index]
        # Wikilink 的显示文本分隔符也是竖线，不能被误认为表格列边界。
        if character == "|" and not in_wikilink:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
        index += 1
    cells.append("".join(current).strip())
    return cells


def _named_section(body: str, title: str) -> list[str] | None:
    """返回指定二级标题下、下一个同级标题前的正文行。"""

    lines = body.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        if line.strip() == f"## {title}":
            start = index + 1
            break
    if start is None:
        return None
    section: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        section.append(line)
    return section


def _field_section(body: str) -> list[str] | None:
    """返回字段定义二级标题内的正文行。"""

    return _named_section(body, "字段定义")


def _table_lines(section: list[str]) -> list[str]:
    """提取字段定义区中的连续 Markdown 表格行。"""

    table: list[str] = []
    started = False
    for line in section:
        if line.strip().startswith("|"):
            started = True
            table.append(line)
        elif started and line.strip():
            break
    return table


def _field_from_cells(values: list[str]) -> DatabaseField:
    """把已经对齐列数的单元格转换为不可变字段模型。"""

    return DatabaseField(*values)


def _domain_is_valid(field: DatabaseField) -> bool:
    """按中文值域类型验证枚举、范围、格式、任意值或未知原因。"""

    if field.domain_type == "枚举":
        entries = [entry.strip() for entry in field.allowed_or_minimum.split(";")]
        return bool(entries) and all(
            "=" in entry
            and all(part.strip() for part in entry.split("=", maxsplit=1))
            for entry in entries
        )
    if field.domain_type == "范围":
        try:
            minimum = Decimal(field.allowed_or_minimum)
            maximum = Decimal(field.maximum_or_format)
        except InvalidOperation:
            return False
        return minimum <= maximum
    if field.domain_type in {"格式", "任意", "未知"}:
        return field.maximum_or_format not in {"", "—", "-"}
    return False


def parse_database_fields(
    record: DocumentRecord,
) -> tuple[list[DatabaseField], list[Issue]]:
    """解析一个数据表的字段定义，并返回结构和值域问题。"""

    section = _field_section(record.body)
    if section is None:
        return [], [
            Issue("KB_DB_FIELDS_REQUIRED", record.path, "数据表必须包含“字段定义”章节")
        ]
    table = _table_lines(section)
    if len(table) < 3:
        return [], [
            Issue("KB_DB_FIELDS_REQUIRED", record.path, "字段定义章节必须包含字段表和至少一行字段")
        ]
    if tuple(_cells(table[0])) != FIELD_COLUMNS:
        return [], [
            Issue("KB_DB_FIELD_COLUMNS", record.path, "字段表列必须与统一模板完全一致")
        ]

    fields: list[DatabaseField] = []
    issues: list[Issue] = []
    seen: set[str] = set()
    for row_number, line in enumerate(table[2:], start=1):
        values = _cells(line)
        location = f"字段定义第 {row_number} 行"
        if len(values) != len(FIELD_COLUMNS):
            issues.append(
                Issue("KB_DB_FIELD_COLUMNS", record.path, "字段行列数不正确", location)
            )
            continue
        field = _field_from_cells(values)
        required_values = (
            field.identifier,
            field.name,
            field.data_type,
            field.nullable,
            field.default,
            field.meaning_zh,
            field.domain_type,
            field.allow_other,
            field.enforcement,
            field.source,
            field.anchor,
        )
        if any(not value for value in required_values):
            issues.append(
                Issue("KB_DB_FIELD_REQUIRED", record.path, "字段必填单元格不能为空", location)
            )
        if FIELD_ID_PATTERN.fullmatch(field.identifier) is None:
            issues.append(
                Issue("KB_DB_FIELD_ID", record.path, f"字段编号不合法：{field.identifier}", location)
            )
        if field.identifier in seen:
            issues.append(
                Issue("KB_DB_FIELD_DUPLICATE", record.path, f"字段编号重复：{field.identifier}", location)
            )
        seen.add(field.identifier)
        if field.nullable not in {"是", "否"} or field.allow_other not in {"是", "否"}:
            issues.append(
                Issue("KB_DB_FIELD_ENUM", record.path, "可空和允许其他值只能填写“是”或“否”", location)
            )
        if field.domain_type not in DOMAIN_TYPES or not _domain_is_valid(field):
            issues.append(
                Issue("KB_DB_FIELD_DOMAIN", record.path, f"字段值域不完整：{field.identifier}", location)
            )
        if field.enforcement not in ENFORCEMENT_TYPES:
            issues.append(
                Issue("KB_DB_FIELD_ENUM", record.path, f"约束执行位置不合法：{field.enforcement}", location)
            )
        if SOURCE_LINK_PATTERN.fullmatch(field.source) is None:
            issues.append(
                Issue("KB_DB_FIELD_SOURCE", record.path, "字段来源必须链接到具体 SRC 文件", location)
            )
        if field.anchor != f"^{field.identifier}":
            issues.append(
                Issue("KB_DB_FIELD_ANCHOR", record.path, "字段锚点必须与字段编号一致", location)
            )
        fields.append(field)
    return fields, issues


def validate_database_fields(records: Iterable[DocumentRecord]) -> list[Issue]:
    """验证所有数据库表记录的字段定义并返回稳定问题列表。"""

    issues: list[Issue] = []
    for record in records:
        if record.metadata.get("type") != "database_table":
            continue
        _, field_issues = parse_database_fields(record)
        issues.extend(field_issues)
    return issues


def _parse_foreign_key_mappings(
    record: DocumentRecord,
) -> tuple[list[ForeignKeyMapping], list[Issue]]:
    """解析主子表关系表并验证列数、编号和物理约束填写方式。"""

    section = _named_section(record.body, "主子表关系")
    if section is None:
        return [], []
    table = _table_lines(section)
    if len(table) < 3 or tuple(_cells(table[0])) != RELATION_COLUMNS:
        return [], [
            Issue("KB_DB_PARENT_COLUMNS", record.path, "主子表关系表必须使用统一列")
        ]
    mappings: list[ForeignKeyMapping] = []
    issues: list[Issue] = []
    seen: set[str] = set()
    for row_number, line in enumerate(table[2:], start=1):
        values = _cells(line)
        location = f"主子表关系第 {row_number} 行"
        if len(values) != len(RELATION_COLUMNS):
            issues.append(
                Issue("KB_DB_PARENT_COLUMNS", record.path, "主子表关系行列数不正确", location)
            )
            continue
        mapping = ForeignKeyMapping(*values)
        if FOREIGN_KEY_ID_PATTERN.fullmatch(mapping.identifier) is None:
            issues.append(
                Issue("KB_DB_PARENT_ID", record.path, f"关系编号不合法：{mapping.identifier}", location)
            )
        if mapping.identifier in seen:
            issues.append(
                Issue("KB_DB_PARENT_DUPLICATE", record.path, f"关系编号重复：{mapping.identifier}", location)
            )
        seen.add(mapping.identifier)
        if mapping.physical_constraint not in {"是", "否"}:
            issues.append(
                Issue("KB_DB_PHYSICAL_FK", record.path, "物理约束只能填写“是”或“否”", location)
            )
        elif mapping.physical_constraint == "是" and mapping.constraint_name in {
            "",
            "—",
            "-",
        }:
            issues.append(
                Issue("KB_DB_PHYSICAL_FK", record.path, "已有物理外键必须记录真实约束名称", location)
            )
        elif mapping.physical_constraint == "否" and mapping.constraint_name not in {
            "—",
            "-",
        }:
            issues.append(
                Issue("KB_DB_PHYSICAL_FK", record.path, "无物理约束时约束名称应填写破折号", location)
            )
        mappings.append(mapping)
    return mappings, issues


def _linked_field_target(
    root: Path,
    link: str,
    index: RelationIndex,
) -> tuple[str, Path] | None:
    """解析主字段 Wikilink，并确认文件、块锚点和显示编号指向同一字段。"""

    match = RELATION_LINK.fullmatch(link)
    if match is None:
        return None
    relative = Path(match.group("path"))
    if relative.is_absolute() or ".." in relative.parts:
        return None
    if relative.suffix == "":
        relative = relative.with_suffix(".md")
    resolved_root = root.resolve()
    path = (resolved_root / relative).resolve()
    try:
        path.relative_to(resolved_root)
    except ValueError:
        return None
    identifier = match.group("identifier")
    anchor = match.group("anchor")
    candidates = index.targets.get(identifier, ())
    if not any(target.path == path and target.anchor == anchor for target in candidates):
        return None
    if not identifier.startswith("FIELD-"):
        return None
    return identifier, path


def validate_database_relations(
    root: Path,
    records: Iterable[DocumentRecord],
    index: RelationIndex,
) -> list[Issue]:
    """验证逻辑外键字段映射、统一父表关系和已有物理外键名称。"""

    record_list = list(records)
    table_records = [
        record for record in record_list if record.metadata.get("type") == "database_table"
    ]
    table_ids_by_path = {
        record.path.resolve(): str(record.metadata.get("id")) for record in table_records
    }
    issues: list[Issue] = []
    for record in table_records:
        table_id = record.metadata.get("id")
        if not isinstance(table_id, str):
            continue
        fields, _ = parse_database_fields(record)
        child_fields = {field.identifier for field in fields}
        mappings, mapping_issues = _parse_foreign_key_mappings(record)
        issues.extend(mapping_issues)
        parent_edges = {
            edge.target.identifier
            for edge in index.outgoing(table_id)
            if edge.field == "rel_logical_parent"
        }
        if parent_edges and _named_section(record.body, "主子表关系") is None:
            issues.append(
                Issue("KB_DB_PARENT_MAPPING_REQUIRED", record.path, "逻辑父表关系必须具有字段映射表")
            )
        mapped_parent_ids: set[str] = set()
        for mapping in mappings:
            if mapping.child_field_id not in child_fields:
                issues.append(
                    Issue("KB_DB_CHILD_FIELD", record.path, f"子字段不存在：{mapping.child_field_id}")
                )
            linked = _linked_field_target(root, mapping.parent_field_link, index)
            if linked is None:
                issues.append(
                    Issue("KB_DB_PARENT_FIELD", record.path, f"主字段链接无效：{mapping.parent_field_link}")
                )
                continue
            _, parent_path = linked
            parent_table_id = table_ids_by_path.get(parent_path)
            if parent_table_id is None:
                issues.append(
                    Issue("KB_DB_PARENT_FIELD", record.path, "主字段必须属于已登记的数据表")
                )
                continue
            mapped_parent_ids.add(parent_table_id)
            if parent_table_id not in parent_edges:
                issues.append(
                    Issue("KB_DB_PARENT_RELATION", record.path, f"缺少 rel_logical_parent：{parent_table_id}")
                )
        for parent_id in sorted(parent_edges - mapped_parent_ids):
            issues.append(
                Issue("KB_DB_PARENT_MAPPING_REQUIRED", record.path, f"父表缺少字段映射：{parent_id}")
            )
    return issues
