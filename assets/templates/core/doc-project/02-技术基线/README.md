---
id: IDX-TECHNICAL-BASELINE
type: knowledge_index
title: 技术基线
rel_classified_under:
  - "[[README|IDX-ROOT]]"
---
# 架构与契约

## 目录契约

本目录只保存下文定义的技术分类，不保存业务需求、临时任务或运行资产。知识项按直接子目录规则命名，并指向自己的直接分类 README。使用 `children` 查看目录内容、`neighbors` 查询直接成员；普通 `graph` 到达本 README 后停止，只有显式分类成员查询才继续展开。

- [系统架构](./系统架构.md)
- [模块](./模块/README.md)
- [接口](./接口/README.md)
- [数据库](./数据库/README.md)
- [数据资产](./数据资产/README.md)
- [原型](./原型/README.md)
- [外部依赖](./外部依赖/README.md)

本目录保存系统架构以及模块、具体接口、数据库、数据资产、原型和外部依赖等可复用技术对象。功能自身的完整设计与局部约束写入对应功能文档，并通过 `rel_*` 链接这里的详细定义。未确认的信息标记为 `missing` 或 `proposed`。
