# 规格审查与 SDD 适配

## 审查边界

规格审查是只读能力。它可以报告确定性错误、需要人工判断的缺口和阻塞问题，但不能批准事实、修改就绪度或替用户验收。`approved`、`active` 和 `ready` 是独立维度。

## 审查模式

- `requirement`：利益相关方、问题价值、范围、业务规则、成功指标、依赖、假设和未知项。
- `feature`：参与者、前置条件、规范性行为、输入输出、状态、失败边界、安全、非功能约束和验收场景。
- `design`：上下文、目标与非目标、关键决策、替代方案、风险、迁移、回滚和仍可延后的未知项。
- `change`：单一意图、Delta 类型、目标基线、影响、迁移和验收计划。
- `implementation_readiness`：规格已就绪、设计约束已解决、外部任务可追溯并包含验证方式。
- `acceptance_readiness`：验收契约已覆盖规范行为，环境、版本和证据位置可登记。

若未知项会改变规范行为、设计选择或任务拆分，结果必须为 `blocked`。措辞风格或非阻塞改进记录为人工复核项，不伪装成确定性错误。

## 外部 SDD 映射

OpenSpec 的 Proposal、Spec Delta、Design 和 Tasks 分别映射为变更候选、规格增量、变更设计和外部任务引用。Spec Kit 的 spec、plan、contracts、data-model、quickstart、tasks 和 checklists 分别映射为功能候选、设计、接口或数据候选、验收候选、外部任务和审查证据。

```powershell
py .project-kb/scripts/inspect_sdd_workspace.py openspec <工作区根>
py .project-kb/scripts/inspect_sdd_workspace.py spec-kit <工作区根>
```

输出只提供候选映射与原始路径，`writes_performed` 必须为 `false`。外部任务完成、归档、分支合并或测试通过不得自动改变 Context Atlas 当前基线。
