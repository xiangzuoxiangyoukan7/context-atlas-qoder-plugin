"""读取插件兼容声明并对目标知识库执行只读格式诊断。"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class FormatConversion:
    """描述一个已实现的旧格式到新格式等价转换。"""

    source_version: int
    target_version: int
    identifier: str


@dataclass(frozen=True)
class CompatibilityResult:
    """描述知识库格式是否可读、可写以及是否存在转换器。"""

    format_version: int
    status: str
    write_blocked: bool
    conversion_available: bool
    creates_format_version: int


@dataclass(frozen=True)
class CompatibilityPolicy:
    """保存插件版本、可读格式、新建格式和单向转换声明。"""

    plugin_version: str
    reads_format_versions: frozenset[int]
    creates_format_version: int
    conversions: tuple[FormatConversion, ...]

    @classmethod
    def load(cls, path: Path) -> CompatibilityPolicy:
        """加载兼容声明并拒绝无法执行或相互矛盾的转换范围。"""

        payload = json.loads(path.resolve().read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ValueError("compatibility version must be 1")
        plugin_version = payload.get("plugin_version")
        raw_reads = payload.get("reads_format_versions")
        creates = payload.get("creates_format_version")
        raw_conversions = payload.get("conversions")
        if not isinstance(plugin_version, str) or not plugin_version:
            raise ValueError("plugin_version is required")
        if (
            not isinstance(raw_reads, list)
            or not raw_reads
            or any(not isinstance(item, int) or item < 1 for item in raw_reads)
            or len(raw_reads) != len(set(raw_reads))
        ):
            raise ValueError("reads_format_versions must contain unique positive integers")
        if not isinstance(creates, int) or creates < 1 or creates not in raw_reads:
            raise ValueError("creates_format_version must be readable")
        if not isinstance(raw_conversions, list):
            raise ValueError("conversions must be a list")
        conversions: list[FormatConversion] = []
        for raw in raw_conversions:
            if not isinstance(raw, dict):
                raise ValueError("conversion must be an object")
            source = raw.get("from")
            target = raw.get("to")
            identifier = raw.get("id")
            if (
                not isinstance(source, int)
                or source not in raw_reads
                or not isinstance(target, int)
                or target != creates
                or source >= target
                or not isinstance(identifier, str)
                or not identifier
            ):
                raise ValueError("invalid conversion declaration")
            conversions.append(FormatConversion(source, target, identifier))
        return cls(
            plugin_version=plugin_version,
            reads_format_versions=frozenset(raw_reads),
            creates_format_version=creates,
            conversions=tuple(conversions),
        )

    def diagnose(self, root: Path) -> CompatibilityResult:
        """只读解析目标清单，并返回兼容、可转换或不支持状态。"""

        manifest = root.resolve() / "knowledge-base.yaml"
        lines = manifest.read_text(encoding="utf-8").splitlines()
        format_version = 1
        for line in lines:
            if line.startswith("format_version:"):
                raw_value = line.split(":", maxsplit=1)[1].strip()
                try:
                    format_version = int(raw_value)
                except ValueError as error:
                    raise ValueError("format_version must be an integer") from error
                break
        conversion = next(
            (
                item
                for item in self.conversions
                if item.source_version == format_version
                and item.target_version == self.creates_format_version
            ),
            None,
        )
        if format_version not in self.reads_format_versions:
            return CompatibilityResult(
                format_version,
                "unsupported",
                True,
                conversion is not None,
                self.creates_format_version,
            )
        if format_version == self.creates_format_version:
            return CompatibilityResult(
                format_version,
                "compatible",
                False,
                False,
                self.creates_format_version,
            )
        return CompatibilityResult(
            format_version,
            "conversion_available" if conversion is not None else "compatible",
            False,
            conversion is not None,
            self.creates_format_version,
        )
