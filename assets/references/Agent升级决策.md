# Agent 升级决策

当确定性 `upgrade-propose` 的隔离预演仍有问题时，Agent 读取对应旧文档、新 Schema、目录契约和关系目标，生成临时 JSON 决策文件，再以 `--agent-plan` 重新生成 Proposal。决策文件不是正式知识，不得放入目标知识库。

```json
{
  "decisions": [
    {
      "action": "rewrite",
      "path": "02-技术基线/数据库/DS-NKGIS/README.md",
      "content": "完整的新 Markdown 内容",
      "reason": "合并旧数据源实体与目录入口并保留双方内容",
      "source_paths": [
        "02-技术基线/数据库/DS-NKGIS/DS-NKGIS.md",
        "02-技术基线/数据库/DS-NKGIS/README.md"
      ]
    },
    {
      "action": "remove",
      "path": "02-技术基线/数据库/DS-NKGIS/DS-NKGIS.md",
      "reason": "全部内容已可追溯地合并到数据源 README",
      "source_paths": [
        "02-技术基线/数据库/DS-NKGIS/DS-NKGIS.md",
        "02-技术基线/数据库/DS-NKGIS/README.md"
      ]
    }
  ]
}
```

支持 `rewrite`、`create`、`move`、`remove`。`rewrite` 和 `create` 必须提供完整 `content`；`move` 必须提供 `target`。每项必须给出非空 `reason` 和实际参与判断的 `source_paths`。执行器记录来源摘要，将决策、内容、目标和来源摘要共同纳入 `proposal_revision`。

Agent 不得通过决策文件修改 `.project-kb/`、`.obsidian/` 或 `knowledge-base.yaml`；这些资产由确定性执行器管理。不得根据文件名补写业务事实，不得改变批准状态、来源事实或 `project_version`。能够证明等价时才合并、改写或删除；存在信息损失、竞争值或业务含义不确定时，将问题保留为 unresolved 并请求用户裁决。

数据库结构归一化时，旧 `database_unit`、`database_namespace` 不是当前目标实体。Agent 必须读取旧文件和所在 `DS-*/README.md`，把数据库名、命名空间、正文事实和来源等价合并进数据源 README，再删除已完整吸收的旧文件；不能证明无信息损失时保留 unresolved。具体表删除指向 `IDX-DATABASE` 的 `rel_classified_under`，并保留或修正指向所在数据源 README 的 `rel_belongs_to`。不得用表到数据源的分类边替代归属边。

每次生成决策后运行：

```text
upgrade-propose <知识库> --compatibility <当前插件兼容清单> --agent-plan <临时决策文件>
```

只有 `preflight_status: passed`、`preflight_validation_issues` 为空、`preflight_health_findings` 为空且 `unresolved` 为空时，才能向用户展示最终 Proposal 并请求确认。`upgrade-apply` 必须使用同一 `--agent-plan`、`proposal_revision` 和 `confirmed_revision`；执行器会重新读取全部来源并拒绝陈旧确认。
