---
name: context-atlas-retire
description: Withdraw formal project knowledge without creating a successor, or archive an item already superseded by revise. Use only when explicitly invoked for retire-only work; do not use it to create replacements, perform ordinary revisions, or upgrade formats.
---

# Context Atlas Retire

Remove formal project knowledge from current authority without treating retirement as an ordinary file deletion. Formal writes require explicit invocation of this Skill, or explicit delegation from an invoked `$context-atlas-work`; natural-language requests may inspect but must not write.

Read `../../references/执行状态机.md`, `../../references/知识采集与确认.md`, `../../references/更新冲突与归档.md`, `../../references/关系与影响分析.md`, `../../references/验证与结果报告.md`, and `../../references/宿主执行与运行时探测.md`. Read the target root `README.md`, `knowledge-base.yaml`, current references, and archive index before proposing.

Follow `inspect -> propose -> await_confirmation -> apply -> validate -> report`. Diagnose compatibility first; use `$context-atlas-upgrade` for conversion and `$context-atlas-init` when no knowledge base exists. Obtain 显式确认 of the exact Proposal revision before any status change, move, or deletion.

Select the outcome by governance semantics. If the request creates a successor, route it to `$context-atlas-revise`; this Skill does not establish supersession. For an item already superseded with references migrated, use `archive-propose` then `archive-apply` when it has audit value. A withdrawal without a successor must first remove or migrate every current reference through a confirmed retire-only Proposal. Physical deletion is allowed only for content with no audit value after its exact path, digest, reason, relations, impact, and validation are confirmed; if no deterministic delete operation is available, stop with zero writes instead of deleting ad hoc. Never delete referenced current authority.

Route mixed add, revise, and retire requests to `$context-atlas-work`; this Skill must not own a mixed Proposal. Use the shared executor under `../../assets/scripts/`; retire-only file changes use one atomic `update`, while archive operations use `archive-propose` and `archive-apply`. Every path must run the complete structural validator and roll back on failure. Follow runtime detection and use `agent_host` only under the isolated staging and scope contract; otherwise keep zero formal writes. Report the chosen retirement outcome and unresolved owner decisions.
