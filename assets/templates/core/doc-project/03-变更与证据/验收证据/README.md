---
id: IDX-EVIDENCE
type: knowledge_index
title: 验收证据
rel_classified_under:
  - "[[03-变更与证据/README|IDX-CHANGES-EVIDENCE]]"
---
# 验收证据

## 目录契约

本目录只保存实际执行结果与可定位证据，不保存未执行计划或业务批准推测。证据使用稳定身份命名，并以 `rel_classified_under` 指向本 README。使用 `children` 查看目录内容、`neighbors` 查询直接成员；普通 `graph` 到达本 README 后停止，只有显式分类成员查询才继续展开。

从 `.project-kb/templates/knowledge/acceptance-evidence.md` 创建报告。证据应记录命令、环境、时间、输出摘要、失败项和对应版本；大文件可保存外部引用，但必须可追溯。

不得伪造第二个 Agent、人工确认或未运行的测试。无法取得的证据将结果保持为 `partial` 或 `not_started`。
