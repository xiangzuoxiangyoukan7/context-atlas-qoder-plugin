---
id: IDX-CHANGES-EVIDENCE
type: knowledge_index
title: 变更与证据
rel_classified_under:
  - "[[README|IDX-ROOT]]"
---
# 变更与证据

本目录分离变更提案、规格增量、验收结果与实际证据。业务验收标准保留在需求文件，具体验收场景保留在所属功能文件；外部 OpenSpec、Spec Kit 或任务系统可以被引用，但其状态不等于正式知识批准。

- `变更/`：单次变化的 Proposal、Delta、Design 和外部任务引用。
- 验收结果从功能内场景与实际证据动态查询，不维护人工矩阵。

- [变更](./变更/README.md)：保存有稳定身份的规格变化
- [验收证据](./验收证据/README.md)：实际结果、证据与版本
- [验收证据](./验收证据/README.md)：实际执行过的验证记录
- 影响记录使用 `.project-kb/templates/knowledge/impact-record.md`，仅在需要审计或人工确认时按需保存。
- [待确认知识](./待确认知识/README.md)：仅在用户明确要求记录候选时按需保存

本目录不保存开发计划、任务拆分、修改许可或调度状态。外部 Issue、OpenSpec、Superpowers 或其他工具负责“怎么做”；知识库只记录发生了什么变化、关联哪些知识，以及如何证明。未知或未执行项保持 `not_started` 或 `partial`。
