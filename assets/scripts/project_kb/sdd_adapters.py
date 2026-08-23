"""只读发现 OpenSpec 与 Spec Kit 工作区并映射其规格工件。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class SddArtifact:
    """描述一个外部 SDD 工件及其 Context Atlas 候选角色。"""

    source_system: str
    source_path: str
    artifact_kind: str
    atlas_role: str


@dataclass(frozen=True)
class SddInspection:
    """保存只读工作区检查结果。"""

    source_system: str
    root: str
    artifacts: tuple[SddArtifact, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """返回适合 JSON 输出的映射，并显式声明没有写入。"""

        return {
            "source_system": self.source_system,
            "root": self.root,
            "artifacts": [asdict(item) for item in self.artifacts],
            "warnings": list(self.warnings),
            "writes_performed": False,
        }


def _relative_files(root: Path, pattern: str) -> list[Path]:
    """按稳定顺序返回匹配且确实存在的文件。"""

    return sorted(path for path in root.glob(pattern) if path.is_file())


def inspect_openspec(root: Path) -> SddInspection:
    """读取 OpenSpec 工件路径，不修改工作区或 Context Atlas。"""

    resolved = root.resolve()
    planning = resolved / "openspec"
    artifacts: list[SddArtifact] = []
    mapping = {
        "proposal.md": ("proposal", "change_proposal"),
        "design.md": ("design", "change_design"),
        "tasks.md": ("tasks", "external_tasks"),
    }
    for path in _relative_files(planning, "changes/**/*"):
        if path.name in mapping:
            kind, role = mapping[path.name]
        elif "specs" in path.parts and path.name == "spec.md":
            kind, role = "spec_delta", "specification_delta"
        else:
            continue
        artifacts.append(SddArtifact("openspec", path.relative_to(resolved).as_posix(), kind, role))
    warnings = () if planning.exists() else ("openspec directory not found",)
    return SddInspection("openspec", str(resolved), tuple(artifacts), warnings)


def inspect_spec_kit(root: Path) -> SddInspection:
    """读取 Spec Kit feature 工件路径，不修改分支或生成任务。"""

    resolved = root.resolve()
    specs = resolved / "specs"
    artifacts: list[SddArtifact] = []
    mapping = {
        "spec.md": ("spec", "feature_candidate"),
        "plan.md": ("plan", "change_design"),
        "research.md": ("research", "external_evidence"),
        "data-model.md": ("data_model", "data_contract_candidate"),
        "quickstart.md": ("quickstart", "acceptance_candidate"),
        "tasks.md": ("tasks", "external_tasks"),
    }
    for path in _relative_files(specs, "**/*.md"):
        if "contracts" in path.parts:
            kind, role = "contract", "interface_candidate"
        elif "checklists" in path.parts:
            kind, role = "checklist", "spec_review_evidence"
        elif path.name in mapping:
            kind, role = mapping[path.name]
        else:
            continue
        artifacts.append(SddArtifact("spec_kit", path.relative_to(resolved).as_posix(), kind, role))
    warnings = () if specs.exists() else ("specs directory not found",)
    return SddInspection("spec_kit", str(resolved), tuple(artifacts), warnings)


def inspect_sdd_workspace(root: Path, source_system: str) -> SddInspection:
    """按显式来源类型分派只读检查。"""

    if source_system == "openspec":
        return inspect_openspec(root)
    if source_system == "spec-kit":
        return inspect_spec_kit(root)
    raise ValueError(f"unsupported SDD source system: {source_system}")
