"""发现知识记录中疑似未脱敏的敏感值。"""

from __future__ import annotations

import re
from typing import Iterable

from .model import DocumentRecord, Issue


ASSIGNMENT_PATTERN = re.compile(
    r"(?im)\b([A-Z0-9_]*(?:TOKEN|PASSWORD|SECRET|PRIVATE_KEY))\s*[:=]\s*([^\s#]+)"
)
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
SENSITIVE_KEY_PATTERN = re.compile(r"(?:TOKEN|PASSWORD|SECRET|PRIVATE_KEY)\Z", re.IGNORECASE)
SAFE_VALUES = {"example", "redacted", "placeholder", "changeme"}


def _is_safe_placeholder(value: str) -> bool:
    """判断命中值是否只是允许保存的占位符。"""

    normalized = value.strip().strip("'\"")
    if normalized.lower() in SAFE_VALUES:
        return True
    return normalized.startswith("${") and normalized.endswith("}")


def validate_security(records: Iterable[DocumentRecord]) -> list[Issue]:
    """扫描正文并报告疑似令牌、密码或私钥内容。"""

    issues: list[Issue] = []
    for record in records:
        if PRIVATE_KEY_PATTERN.search(record.body):
            issues.append(
                Issue(
                    "KB_SENSITIVE_VALUE",
                    record.path,
                    "possible private key material must not be stored in the knowledge base",
                )
            )
        for match in ASSIGNMENT_PATTERN.finditer(record.body):
            key, value = match.groups()
            if _is_safe_placeholder(value):
                continue
            issues.append(
                Issue(
                    "KB_SENSITIVE_VALUE",
                    record.path,
                    f"possible sensitive assignment for {key}; value omitted",
                )
            )
        for key, raw_value in record.metadata.items():
            if not SENSITIVE_KEY_PATTERN.search(key):
                continue
            values = raw_value if isinstance(raw_value, list) else [raw_value]
            if all(_is_safe_placeholder(str(value)) for value in values):
                continue
            issues.append(
                Issue(
                    "KB_SENSITIVE_VALUE",
                    record.path,
                    f"possible sensitive metadata field {key}; value omitted",
                )
            )
    return issues
