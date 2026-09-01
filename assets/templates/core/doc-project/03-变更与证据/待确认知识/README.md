---
id: IDX-PROPOSALS
type: knowledge_index
title: 待确认知识
rel_classified_under:
  - "[[03-变更与证据/README|IDX-CHANGES-EVIDENCE]]"
---
# 待确认知识

## 目录契约

本目录只保存用户明确要求持久化的候选，不保存临时推测或分析。候选使用稳定身份命名，并以 `rel_classified_under` 指向本 README。使用 `children` 查看目录内容、`neighbors` 查询直接成员；普通 `graph` 到达本 README 后停止，只有显式分类成员查询才继续展开。

本目录按需保存用户明确要求记录的 `PROP-*` 待确认候选。候选不是正式知识，不控制开发任务执行，也不能因自动检查通过而变成 `approved`。普通开发不得自动创建本目录或候选文件。

同一会话或任务中的相关候选按“目标知识项 + 内容摘要”合并去重。用户确认后，Agent 按正式更新流程修改需求、功能、接口、数据库或规则；拒绝项可标记为 `rejected`，已应用项标记为 `applied`。
