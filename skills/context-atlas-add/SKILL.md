---
name: context-atlas-add
description: Add one or more new stable identities to an existing Context Atlas knowledge base. Use only when explicitly invoked for add-only formal project knowledge; route changes, withdrawals, format upgrades, and mixed maintenance elsewhere.
---

# Context Atlas Add

For a confirmed managed-source inbox Proposal, use the packaged `managed-source-apply` operation with the exact proposed and confirmed revision. It may write only under `05-知识治理/来源资料/` and remove an original from `Clippings/` only after digest verification and successful knowledge-base validation. Never recreate this move with ad-hoc file commands.

Add new formal project knowledge whose stable identities do not already exist. Formal writes require explicit invocation of this Skill, or explicit delegation from an invoked `$context-atlas-work`; natural-language requests may inspect but must not write.

Read `../../references/执行状态机.md`, `../../references/知识采集与确认.md`, `../../references/更新冲突与归档.md`, `../../references/验证与结果报告.md`, and `../../references/宿主执行与运行时探测.md`. Read the target knowledge base root `README.md` and `knowledge-base.yaml` before proposing changes.

Follow `inspect -> propose -> await_confirmation -> apply -> validate -> report`. Diagnose format compatibility first; direct the user to `$context-atlas-upgrade` when conversion is required, or to `$context-atlas-init` when no knowledge base exists. Present exact target paths, stable IDs, sources, relations, impact, validation, and the Proposal revision. Obtain 显式确认 of that exact revision before writing.

Reject duplicate identity and semantic overlap. If the request changes an existing item or replaces it with a successor, stop and direct it to `$context-atlas-revise`; if it withdraws authority without creating a successor, use `$context-atlas-retire`. Route any request spanning more than one maintenance kind to `$context-atlas-work`; this Skill must not own a mixed Proposal.

Before apply, follow runtime detection. Prefer the bundled Python executor under `../../assets/scripts/` and apply every confirmed file in one `update` command using paired `--file` and `--content-file` arguments plus matching proposal and confirmation revisions. The executor must run the complete structural validator and roll back the whole set on failure. Use `agent_host` only under the isolated staging and scope rules in the runtime contract; otherwise keep zero formal writes. Preserve source, approval, and validator evidence as distinct records. Never store secrets or unredacted personal data.
