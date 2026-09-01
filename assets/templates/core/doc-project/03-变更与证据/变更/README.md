---
id: IDX-CHANGES
type: knowledge_index
title: 变更
rel_classified_under:
  - "[[03-变更与证据/README|IDX-CHANGES-EVIDENCE]]"
---
# 规格变更

## 目录契约

本目录只保存有稳定身份的规格变化，不保存实现任务或一次性日志。变更使用稳定身份命名，并以 `rel_classified_under` 指向本 README。使用 `children` 查看目录内容、`neighbors` 查询直接成员；普通 `graph` 到达本 README 后停止，只有显式分类成员查询才继续展开。

每个 `CHG-*` 使用独立目录保存单一变更意图、规格 Delta、可选设计和外部任务引用。变更接受或外部归档后只能生成基线合并 Proposal，不能直接批准当前事实。

- `.project-kb/templates/knowledge/specification-change.md`
- Delta 模板位于 `.project-kb/templates/knowledge/specification-delta.md`。
