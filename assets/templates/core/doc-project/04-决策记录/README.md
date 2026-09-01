---
id: IDX-DECISIONS
type: knowledge_index
title: 决策记录
rel_classified_under:
  - "[[README|IDX-ROOT]]"
---
# 决策记录

## 目录契约

本目录只保存稳定架构或治理决策，不保存临时讨论或未确认偏好。决策使用稳定身份命名，并以 `rel_classified_under` 指向本 README。使用 `children` 查看目录内容、`neighbors` 查询直接成员；普通 `graph` 到达本 README 后停止，只有显式分类成员查询才继续展开。

从 `.project-kb/templates/knowledge/adr.md` 创建 `ADR-001-简短标题.md`。ADR 记录背景、候选方案、决策、影响、来源、批准人和版本。

新决策替代旧决策时必须保留旧文件，将其标为 `superseded` 并建立双向链接；未知权衡不得由 Agent 自行裁决。
