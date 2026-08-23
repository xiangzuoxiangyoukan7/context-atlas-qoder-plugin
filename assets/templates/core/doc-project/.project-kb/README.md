# 内部检查包

初始化时，Agent 从已安装 Skill 复制检查器运行时及 `schemas/` 到本目录，使知识库脱离模板仓库后仍可自检。该目录属于生成产物，不存放项目事实，也不生成或维护 `AGENTS.md`、`CLAUDE.md`。

检查前读取上级 `knowledge-base.yaml`。检查器只在知识库目录内读取文档，并输出稳定的文本或 JSON 报告。
