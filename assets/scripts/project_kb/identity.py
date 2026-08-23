"""发现 Git 候选身份并与项目内稳定人员编号进行隐私保护匹配。"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import subprocess

from .model import Issue


PERSON_COLUMNS = (
    "人员编号",
    "显示名称",
    "所属团队",
    "状态",
    "Git 用户名别名",
    "Git 邮箱摘要",
)
PERSON_ID_PATTERN = re.compile(r"PERSON-[A-Z0-9-]+$")
EMAIL_HASH_PATTERN = re.compile(r"[0-9a-f]{64}$")


@dataclass(frozen=True)
class Person:
    """表示项目确认过的稳定人员和 Git 身份别名。"""

    identifier: str
    display_name: str
    team: str
    status: str
    git_names: frozenset[str]
    email_hashes: frozenset[str]


@dataclass(frozen=True)
class GitIdentity:
    """保存 Git 候选名称和不可逆邮箱摘要，不保留明文邮箱。"""

    name: str
    email_hash: str


@dataclass(frozen=True)
class IdentityMatch:
    """描述 Git 候选与稳定人员编号的匹配或待确认状态。"""

    status: str
    person_id: str
    candidate_name: str
    email_hash: str
    requires_confirmation: bool


def email_digest(email: str) -> str:
    """对规范化邮箱生成不可逆 SHA-256 摘要。"""

    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _cells(line: str) -> list[str]:
    """把不含链接的协作人员 Markdown 表格行拆为单元格。"""

    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _aliases(value: str) -> frozenset[str]:
    """把分号分隔的别名转换为忽略空占位符的集合。"""

    if value in {"", "—", "-"}:
        return frozenset()
    return frozenset(item.strip() for item in value.split(";") if item.strip())


def load_people(path: Path) -> tuple[list[Person], list[Issue]]:
    """解析协作人员登记表并报告编号、状态和邮箱隐私问题。"""

    lines = path.read_text(encoding="utf-8").splitlines()
    header_index = next(
        (index for index, line in enumerate(lines) if tuple(_cells(line)) == PERSON_COLUMNS),
        None,
    )
    if header_index is None:
        return [], [Issue("KB_PERSON_COLUMNS", path, "协作人员表缺少统一列")]
    people: list[Person] = []
    issues: list[Issue] = []
    seen: set[str] = set()
    for row_number, line in enumerate(lines[header_index + 2 :], start=1):
        if not line.strip().startswith("|"):
            if people:
                break
            continue
        values = _cells(line)
        location = f"协作人员第 {row_number} 行"
        if len(values) != len(PERSON_COLUMNS):
            issues.append(Issue("KB_PERSON_COLUMNS", path, "人员行列数不正确", location))
            continue
        identifier, name, team, status, raw_names, raw_hashes = values
        if PERSON_ID_PATTERN.fullmatch(identifier) is None:
            issues.append(Issue("KB_PERSON_ID", path, f"人员编号不合法：{identifier}", location))
        if identifier in seen:
            issues.append(Issue("KB_PERSON_DUPLICATE", path, f"人员编号重复：{identifier}", location))
        seen.add(identifier)
        if status not in {"active", "inactive"}:
            issues.append(Issue("KB_PERSON_STATUS", path, f"人员状态不合法：{status}", location))
        hashes = _aliases(raw_hashes)
        if any(EMAIL_HASH_PATTERN.fullmatch(value) is None for value in hashes):
            issues.append(
                Issue("KB_PERSON_EMAIL_PRIVACY", path, "Git 邮箱只能保存 SHA-256 摘要", location)
            )
            hashes = frozenset(
                value for value in hashes if EMAIL_HASH_PATTERN.fullmatch(value)
            )
        people.append(
            Person(identifier, name, team, status, _aliases(raw_names), hashes)
        )
    return people, issues


def match_git_identity(path: Path, name: str, email: str) -> IdentityMatch:
    """优先按邮箱摘要、其次按名称别名匹配，歧义或新身份要求确认。"""

    people, issues = load_people(path)
    if issues:
        raise ValueError("协作人员登记表无效，不能安全匹配 Git 身份")
    digest = email_digest(email)
    hash_matches = [person for person in people if digest in person.email_hashes]
    name_matches = [
        person
        for person in people
        if name == person.display_name or name in person.git_names
    ]
    candidates = hash_matches if hash_matches else name_matches
    unique_ids = {person.identifier for person in candidates}
    if len(unique_ids) == 1:
        return IdentityMatch("matched", next(iter(unique_ids)), name, digest, False)
    if len(unique_ids) > 1:
        return IdentityMatch("ambiguous", "PERSON-UNKNOWN", name, digest, True)
    return IdentityMatch("candidate", "PERSON-UNKNOWN", name, digest, True)


def _git_config(root: Path, key: str) -> str:
    """读取当前仓库生效的 Git 配置值并拒绝缺失配置。"""

    result = subprocess.run(
        ["git", "config", "--get", key],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        raise ValueError(f"Git 配置缺失：{key}")
    return value


def discover_git_identity(root: Path) -> GitIdentity:
    """只读发现当前仓库 Git 名称和邮箱摘要，不修改任何 Git 配置。"""

    name = _git_config(root.resolve(), "user.name")
    email = _git_config(root.resolve(), "user.email")
    return GitIdentity(name=name, email_hash=email_digest(email))


def discover_identity_match(root: Path, people_path: Path) -> IdentityMatch:
    """读取仓库生效 Git 身份并直接匹配，返回值不保留明文邮箱。"""

    name = _git_config(root.resolve(), "user.name")
    email = _git_config(root.resolve(), "user.email")
    return match_git_identity(people_path.resolve(), name, email)


def validate_people(root: Path) -> list[Issue]:
    """当固定协作人员入口存在时验证其人员编号和隐私边界。"""

    path = root.resolve() / "05-知识治理" / "协作与责任.md"
    if not path.is_file():
        return []
    _, issues = load_people(path)
    return issues
