---
name: context-atlas-retire
description: Retire formal business knowledge in a self-contained Context Atlas project knowledge base through supersession, archival, or explicitly confirmed deletion. Use only when the user explicitly invokes context-atlas-retire. Do not use it for ordinary revision or format upgrades.
---

# Context Atlas Retire

Remove knowledge from current authority without treating retirement as an ordinary file deletion. Formal writes require explicit invocation of this Skill; natural-language requests may inspect and propose but must not write.

Read `../../references/执行状态机.md`, `../../references/知识采集与确认.md`, `../../references/更新冲突与归档.md`, `../../references/关系与影响分析.md`, `../../references/验证与结果报告.md`, and `../../references/宿主执行与运行时探测.md`. Read the target root `README.md`, `knowledge-base.yaml`, current references, and archive index before proposing.

Follow `inspect -> propose -> await_confirmation -> apply -> validate -> report`. Diagnose compatibility first; use `$context-atlas-upgrade` for conversion and `$context-atlas-init` when no knowledge base exists. Obtain 显式确认 of the exact Proposal revision before any status change, move, or deletion.

Select the outcome by governance semantics: establish a confirmed successor and migrate references for supersession; use `archive-propose` then `archive-apply` for content with audit value; physically delete only content with no audit value after its exact path, digest, reason, relations, impact, and validation are confirmed. Never delete referenced current authority or collapse these outcomes into a generic delete.

Use the shared executor under `../../assets/scripts/`; archive operations must remain atomic and roll back on validation failure. Follow runtime detection and use `agent_host` only under the isolated staging and scope contract; otherwise keep zero formal writes. Report the chosen retirement outcome and unresolved owner decisions.
