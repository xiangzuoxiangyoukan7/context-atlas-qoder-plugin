---
name: context-atlas-add
description: Add new formal business knowledge to an existing self-contained Context Atlas project knowledge base. Use only when the user explicitly invokes context-atlas-add. Do not use it to revise, retire, or upgrade existing knowledge.
---

# Context Atlas Add

For a confirmed managed-source inbox Proposal, use the packaged `managed-source-apply` operation with the exact proposed and confirmed revision. It may write only under `05-知识治理/来源资料/` and remove an original from `Clippings/` only after digest verification and successful knowledge-base validation. Never recreate this move with ad-hoc file commands.

Add a new formal knowledge item to an existing project knowledge base. Formal writes require explicit invocation of this Skill; natural-language requests may inspect and propose but must not write.

Read `../../references/执行状态机.md`, `../../references/知识采集与确认.md`, `../../references/更新冲突与归档.md`, `../../references/验证与结果报告.md`, and `../../references/宿主执行与运行时探测.md`. Read the target knowledge base root `README.md` and `knowledge-base.yaml` before proposing changes.

Follow `inspect -> propose -> await_confirmation -> apply -> validate -> report`. Diagnose format compatibility first; direct the user to `$context-atlas-upgrade` when conversion is required, or to `$context-atlas-init` when no knowledge base exists. Present exact target paths, stable IDs, sources, relations, impact, validation, and the Proposal revision. Obtain 显式确认 of that exact revision before writing.

Reject duplicate identity and semantic overlap. If the request changes an existing item, stop and direct it to `$context-atlas-revise`; if it removes current authority, use `$context-atlas-retire`. A request spanning add, revise, and retire must be represented by one atomic Proposal and applied together through the shared executor.

Before apply, follow runtime detection. Prefer the bundled Python executor under `../../assets/scripts/`. Use `agent_host` only under the isolated staging and scope rules in the runtime contract; otherwise keep zero formal writes. Preserve source, approval, and validator evidence as distinct records. Never store secrets or unredacted personal data.
