"""定义核心知识库模板必须包含的稳定路径。"""

from pathlib import Path
from typing import Sequence

# context-atlas-rules: [[rules/知识治理规则#RULE-GOV-003|RULE-GOV-003]]


TEMPLATE_MARKERS = frozenset(
    {
        "{{PROJECT_ID}}",
        "{{PROJECT_NAME}}",
        "{{KNOWLEDGE_BASE_NAME}}",
        "{{WORKSPACE_PROFILE}}",
        "{{INITIALIZED_AT}}",
    }
)


def required_template_paths() -> Sequence[Path]:
    """返回初始化产物必须具备的文件路径集合。"""

    return tuple(
        Path(path)
        for path in (
            "README.md",
            "knowledge-base.yaml",
            ".project-kb/README.md",
            "Clippings/README.md",
            "00-项目总览/README.md",
            "00-项目总览/项目概述.md",
            "00-项目总览/术语表.md",
            "01-功能基线/README.md",
            "01-功能基线/需求/README.md",
            "01-功能基线/功能/README.md",
            "02-技术基线/README.md",
            "02-技术基线/系统架构.md",
            "02-技术基线/模块/README.md",
            "02-技术基线/接口/README.md",
            "02-技术基线/数据库/README.md",
            "02-技术基线/数据资产/README.md",
            "02-技术基线/原型/README.md",
            "02-技术基线/外部依赖/README.md",
            "03-变更与证据/README.md",
            "03-变更与证据/变更/README.md",
            "03-变更与证据/验收证据/README.md",
            "03-变更与证据/待确认知识/README.md",
            "04-决策记录/README.md",
            "05-知识治理/README.md",
            "05-知识治理/来源资料/README.md",
            "05-知识治理/AI知识采集协议.md",
            "05-知识治理/使用场景.md",
            "90-历史归档/README.md",
            ".project-kb/templates/knowledge/requirement.md",
            ".project-kb/templates/knowledge/feature.md",
            ".project-kb/templates/knowledge/module.md",
            ".project-kb/templates/knowledge/interface.md",
            ".project-kb/templates/knowledge/data-source.md",
            ".project-kb/templates/knowledge/database-table.md",
            ".project-kb/templates/knowledge/data-asset.md",
            ".project-kb/templates/knowledge/specification-change.md",
            ".project-kb/templates/knowledge/specification-delta.md",
            ".project-kb/templates/knowledge/acceptance-evidence.md",
            ".project-kb/templates/knowledge/knowledge-proposal.md",
            ".project-kb/templates/knowledge/adr.md",
        )
    )
