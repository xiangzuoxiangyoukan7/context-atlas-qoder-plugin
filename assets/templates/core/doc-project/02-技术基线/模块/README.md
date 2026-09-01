---
id: IDX-MODULES
type: knowledge_index
title: 模块
rel_classified_under:
  - "[[02-技术基线/README|IDX-TECHNICAL-BASELINE]]"
---
# 模块

每个稳定模块使用一份 `MOD-<领域>-<名称>.md` 文件。模块契约描述职责、明确不负责内容、代码位置、允许依赖和禁止依赖；具体通信格式由接口契约定义。

功能通过 `rel_primary_module` 和 `rel_participating_modules` 关联模块。功能文件仍按产品知识组织，不随模块目录或代码重构移动。
