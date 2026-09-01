---
id: IDX-INTERFACES
type: knowledge_index
title: 接口
rel_classified_under:
  - "[[02-技术基线/README|IDX-TECHNICAL-BASELINE]]"
---
# 接口

HTTP、RPC、事件、Webhook、文件和稳定函数接口使用统一 `interface` 知识类型，一个具体端点、事件或交换入口一个文件并在本目录平铺。文件名必须为 `<接口ID>-<业务用途>.md`，标题必须包含可理解的业务名称；不得只用稳定 ID 命名，或把一个功能的多个端点聚合成单个接口文件。通过 `interface_kind` 区分通信方式，通过 `visibility` 区分内部与外部接口。总路由、Servlet 集合和集成概况应写入系统架构或外部依赖。

接口文件是输入、输出、错误、敏感字段、版本和兼容策略的唯一项目定义。提供方和调用方通过关系引用稳定 ID，不复制契约正文；反向消费者由检查器计算。
