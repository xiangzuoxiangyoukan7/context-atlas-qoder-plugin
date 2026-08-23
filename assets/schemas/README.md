# 核心 Schema

Schema 可以理解为“机器可执行的表格填写规则”：它不保存项目知识，而是规定某类文件必须有哪些字段、字段允许填什么、格式必须怎样。

本目录有两类 Schema：

1. `catalog.json` 登记的轻量 Schema，约束知识库 Markdown 顶部的 YAML Front Matter。
2. `initialization-*.schema.json`、`ingest-report.schema.json` 和 `batch-ingest-report.schema.json` 使用标准 JSON Schema 约束会话 Proposal 或报告；`embedded-source.schema.json` 定义格式 4 及后续格式中知识项就地携带的来源对象。这些都不登记进知识类型 `catalog.json`。

完整的逐文件、逐字段中文解释见[字段说明](./字段说明.md)。

- [目录](./catalog.json)
- [项目清单](./project-manifest.schema.json)
- [通用知识项](./knowledge-item.schema.json)
- [数据资产](./data-asset.schema.json)
- [需求](./requirement.schema.json)
- [功能](./feature.schema.json)
- [模块](./module.schema.json)
- [接口](./interface.schema.json)
- [独立契约](./contract.schema.json)
- [产品任务](./task.schema.json)
- [治理任务](./governance-task.schema.json)
- [验收](./acceptance.schema.json)
- [验收契约](./acceptance-contract.schema.json)
- [规格变更](./specification-change.schema.json)
- [规格增量](./specification-delta.schema.json)
- [知识来源](./source.schema.json)
- [内嵌来源](./embedded-source.schema.json)
- [初始化 Proposal](./initialization-proposal.schema.json)
- [初始化报告](./initialization-report.schema.json)
- [单来源摄取报告](./ingest-report.schema.json)
- [批量摄取报告](./batch-ingest-report.schema.json)

技术栈记录只增加项目事实，不能改变核心状态、权威来源、确认规则或验收结果。

除 `required`、`enums`、`patterns`、`non_empty_lists`、`unique_lists` 外，Schema 还支持 `list_enums`，用于约束字符串列表中的每个成员必须来自预定义枚举。

