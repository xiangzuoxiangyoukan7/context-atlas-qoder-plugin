---
id: IDX-FUNCTIONAL-BASELINE
type: knowledge_index
title: 功能基线
rel_classified_under:
  - "[[README|IDX-ROOT]]"
---
# 功能基线

产品能力直接从[功能](./功能/README.md)及其成员动态查询。具体知识分为[需求](./需求/README.md)和功能：需求说明为什么做，功能说明系统应表现出的行为。两者是多对多关系，由功能使用 `rel_satisfies` 指向需求。

新建功能必须使用 `.project-kb/templates/knowledge/feature.md` 和 `F-<领域>-<三位序号>` 编号。

候选内容先以 Proposal 呈现；确认前状态不得升级为现行基线。未知验收条件要标记待确认，不能编造。
