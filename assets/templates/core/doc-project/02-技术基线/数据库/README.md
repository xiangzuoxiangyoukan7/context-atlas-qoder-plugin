---
id: IDX-DATABASE
type: knowledge_index
title: 数据库
rel_classified_under:
  - "[[02-技术基线/README|IDX-TECHNICAL-BASELINE]]"
---
# 数据库知识

## 目录契约

本目录只保存数据库层级和表结构知识，不保存连接密钥或执行日志。数据库根 README 是 `IDX-DATABASE` 分类索引；每个 `DS-*` 子目录的 README 则是该数据源唯一的 `data_source` 实体和目录入口，不再额外创建同名数据源卡。使用 `children` 查看目录内容、`neighbors` 查询直接关系、`graph` 分析有界影响。

<!-- context-atlas-rules: [[rules/知识治理规则#RULE-DB-001|RULE-DB-001]] -->

默认按数据源隔离：每个数据源创建 `DS-<领域>-<名称>/` 目录，并用 `.project-kb/templates/knowledge/data-source.md` 直接生成该目录的 `README.md`。这个 README 使用 `DS-*` 稳定身份并保存连接位置、产品、版本、Database、Schema/Namespace、安全和治理信息。项目依赖的每张表在同一目录下一表一文件，不创建重复的 `DS-*.md`。

Database、Oracle PDB、Schema 或 Namespace 默认作为数据源元数据中的可选字段，不创建空壳层级。只有复杂拓扑需要被独立引用和分析影响时，才升级为独立知识项。

功能、接口和任务使用 `rel_reads`、`rel_writes` 或 `rel_depends_on` 引用数据表；表不反向维护业务消费者。表通过 `rel_belongs_to` 直接指向所在 `DS-*/README.md`，并统一通过数据库根索引分类，不再向数据源 README 增加重复的分类关系。子表使用 `rel_logical_parent` 引用主表，并在正文精确链接主字段块锚点。
