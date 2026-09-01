---
id: IDX-DATABASE
type: knowledge_index
title: 数据库
rel_classified_under:
  - "[[02-技术基线/README|IDX-TECHNICAL-BASELINE]]"
---
# 数据库知识

## 目录契约

本目录只保存数据库层级和表结构知识，不保存连接密钥或执行日志。新增正式子目录时必须创建稳定 `IDX-*` README，目录内知识项指向该直接分类。使用 `children` 查看目录内容、`neighbors` 查询直接成员；普通 `graph` 到达 README 后停止，只有显式分类成员查询才继续展开。

<!-- context-atlas-rules: [[rules/知识治理规则#RULE-DB-001|RULE-DB-001]] -->

默认按数据源隔离：每个数据源创建 `DS-<领域>-<名称>/` 目录，公共连接、产品、版本、安全和治理信息写入该目录的 `README.md`，项目依赖的每张表在同一目录下一表一文件。创建时使用`.project-kb/templates/knowledge/data-source.md`和`.project-kb/templates/knowledge/database-table.md`。

Database、Oracle PDB、Schema 或 Namespace 默认作为数据源元数据中的可选字段，不创建空壳层级。只有复杂拓扑需要被独立引用和分析影响时，才升级为独立知识项。

功能、接口和任务使用 `rel_reads`、`rel_writes` 或 `rel_depends_on` 引用数据表；表不反向维护业务消费者。表使用 `rel_belongs_to` 指向所在数据源。子表使用 `rel_logical_parent` 引用主表，并在正文精确链接主字段块锚点。
