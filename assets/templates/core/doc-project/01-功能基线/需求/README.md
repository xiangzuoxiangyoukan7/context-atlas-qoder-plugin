---
id: IDX-REQUIREMENTS
type: knowledge_index
title: 需求
rel_classified_under:
  - "[[01-功能基线/README|IDX-FUNCTIONAL-BASELINE]]"
---
# 需求

每项需求使用 `.project-kb/templates/knowledge/requirement.md` 创建独立文件，文件名为 `REQ-<领域>-<三位序号>-<名称>.md`。需求描述为什么做、解决什么问题、范围和约束，不描述具体代码实现。

需求与功能是多对多关系。功能使用 `rel_satisfies` 指向需求；需求文件不手工维护反向功能列表。候选需求在责任人确认前保持 `proposed`。
