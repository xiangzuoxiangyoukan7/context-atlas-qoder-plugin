---
id: IDX-MODULES
type: knowledge_index
title: 模块
rel_classified_under:
  - "[[02-技术基线/README|IDX-TECHNICAL-BASELINE]]"
---
# 模块

## 目录契约

本目录只保存稳定模块职责，不保存接口字段、临时任务或运行日志。模块按下文规则命名，并以 `rel_classified_under` 指向本 README。使用 `children` 查看目录内容、`neighbors` 查询直接成员；普通 `graph` 到达本 README 后停止，只有显式分类成员查询才继续展开。

每个稳定模块使用一份 `MOD-<领域>-<名称>.md` 文件。模块契约描述职责、明确不负责内容、代码位置、允许依赖和禁止依赖；具体通信格式由接口契约定义。

功能通过 `rel_primary_module` 和 `rel_participating_modules` 关联模块。功能文件仍按产品知识组织，不随模块目录或代码重构移动。
