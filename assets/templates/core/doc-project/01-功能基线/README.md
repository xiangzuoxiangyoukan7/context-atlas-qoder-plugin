---
id: IDX-FUNCTIONAL-BASELINE
type: knowledge_index
title: 功能基线
rel_classified_under:
  - "[[README|IDX-ROOT]]"
---
# 功能基线

## 目录契约

本目录只保存下文定义的需求与功能分类，不保存实现任务或运行资产。知识项按直接子目录规则命名，并指向自己的直接分类 README。使用 `children` 查看目录内容、`neighbors` 查询直接成员；普通 `graph` 到达本 README 后停止，只有显式分类成员查询才继续展开。

产品能力直接从[功能](./功能/README.md)及其成员动态查询。具体知识分为[需求](./需求/README.md)和功能：需求说明为什么做，功能说明系统应表现出的行为。两者是多对多关系，由功能使用 `rel_satisfies` 指向需求。

新建功能必须使用 `.project-kb/templates/knowledge/feature.md` 和 `F-<领域>-<三位序号>` 编号。

候选内容先以 Proposal 呈现；确认前状态不得升级为现行基线。未知验收条件要标记待确认，不能编造。
