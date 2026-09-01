---
id: IDX-FEATURES
type: knowledge_index
title: 功能
rel_classified_under:
  - "[[01-功能基线/README|IDX-FUNCTIONAL-BASELINE]]"
---
# 功能

## 目录契约

本目录只保存功能规格，不保存需求、实现任务或实际证据。功能按下文规则命名，并以 `rel_classified_under` 指向本 README。使用 `children` 查看目录内容、`neighbors` 查询直接成员；普通 `graph` 到达本 README 后停止，只有显式分类成员查询才继续展开。

每项功能使用 `.project-kb/templates/knowledge/feature.md` 创建独立文件，文件名为 `F-<领域>-<三位序号>-<名称>.md`。功能描述系统可观察行为，通过 `rel_satisfies` 关联需求，通过模块和接口关系关联实现结构。

旧版直接位于 `01-功能基线/` 且使用 `F01` 编号的功能卡保留一个格式版本的读取兼容；新建功能必须使用本目录和新编号。
