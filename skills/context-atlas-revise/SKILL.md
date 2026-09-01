---
name: context-atlas-revise
description: Revise existing formal project knowledge or replace it with an explicit successor. Use only when explicitly invoked for revise-only work; route unrelated additions, withdrawal without a successor, format upgrades, and mixed maintenance elsewhere.
---

# Context Atlas Revise

Revise existing formal project knowledge without silently overwriting approved history. Formal writes require explicit invocation of this Skill, or explicit delegation from an invoked `$context-atlas-work`; natural-language requests may inspect but must not write.

Read `../../references/执行状态机.md`, `../../references/知识采集与确认.md`, `../../references/更新冲突与归档.md`, `../../references/关系与影响分析.md`, `../../references/验证与结果报告.md`, and `../../references/宿主执行与运行时探测.md`. Read the target root `README.md` and `knowledge-base.yaml` before proposing.

Follow `inspect -> propose -> await_confirmation -> apply -> validate -> report`. Diagnose compatibility first; use `$context-atlas-upgrade` for format conversion and `$context-atlas-init` when no knowledge base exists. Obtain 显式确认 of the exact Proposal revision before writing.

Choose `patch` only when stable identity and meaning remain the same. Choose `supersede` when authority or semantics change and a successor will become current: create the successor, establish `supersedes` and `superseded_by`, migrate current references, then validate. Preserve competing evidence as `conflicted`; never pick a winner without the required resolver. Unrelated new identities belong to `$context-atlas-add`; withdrawal without creating a successor belongs to `$context-atlas-retire`.

Route a request spanning multiple maintenance kinds to `$context-atlas-work`; this Skill must not own a mixed Proposal. For revise-only work, use one `update` command with paired `--file` and `--content-file` arguments and matching revisions. The executor must validate the complete knowledge base and roll back the full replacement set on failure. Follow runtime detection; use `agent_host` only under its isolated staging contract and otherwise keep zero formal writes. Report exact paths, confirmation, impact, validation, unknowns, and conflicts.
