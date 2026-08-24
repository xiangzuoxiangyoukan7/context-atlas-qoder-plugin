# Context Atlas for Qoder

这是由 Context Atlas 唯一源码仓库构建的 Qoder `0.11.0` 插件包。不要在发布包中直接修改 Skill 或运行资产。

## 项目级安装

必须在目标项目范围安装，不要安装到用户级 `~/.qoder/skills/`。将 Qoder 发布仓库登记到 Marketplace，然后选择 Project 安装：

```powershell
qoder plugins marketplace add https://github.com/xiangzuoxiangyoukan7/context-atlas-qoder-plugin.git
qoder plugins install context-atlas@context-atlas
```

本地验收或开发时才在源码仓库构建 Qoder 包：

```powershell
py scripts/build_plugin.py qoder --output build/qoder/context-atlas
```

安装后重启 Qoder，在输入框中输入 `/` 检查九个 Context Atlas Skill 是否出现。

## 使用

```text
/context-atlas-work
/context-atlas-init
/context-atlas-navigate
/context-atlas-review
/context-atlas-ingest
/context-atlas-add
/context-atlas-revise
/context-atlas-retire
/context-atlas-upgrade
```

初始化和维护只生成 Proposal；必须明确回复“确认”后才会写入正式知识库。

## 升级插件

确认 Qoder Marketplace 当前选择的是目标项目的 **Project** 范围，然后执行：

```powershell
qoder plugins marketplace update context-atlas
qoder plugins update context-atlas@context-atlas
```

升级后重启 Qoder，在插件管理界面确认实际版本，并再次检查九个 Skill 是否完整加载。
