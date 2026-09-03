---
name: context-atlas-delete
description: Permanently delete formal Context Atlas knowledge that has no audit value, together with required reference cleanup. Use only when explicitly invoked for delete-only work; do not use for retirement, archival, replacement, ordinary revision, or format upgrades.
---

# Context Atlas Delete

Permanently remove formal knowledge only when the project owner has determined that it has no audit value. Formal deletion requires explicit invocation of this Skill, or explicit delegation from an invoked `$context-atlas-work`; a natural-language observation or cleanup suggestion may inspect but must not delete.

Read `../../references/执行状态机.md`, `../../references/知识采集与确认.md`, `../../references/更新冲突与归档.md`, `../../references/关系与影响分析.md`, `../../references/验证与结果报告.md`, and `../../references/宿主执行与运行时探测.md`. Read the target root `README.md`, `knowledge-base.yaml`, every deletion target, and all incoming and outgoing relations before proposing.

Follow `inspect -> propose -> await_confirmation -> apply -> validate -> report`. Prefer `$context-atlas-retire` when current authority should merely be withdrawn or history has audit value; use `$context-atlas-revise` when a successor is created. Route any request mixed with add, revise, or retire to `$context-atlas-work`.

Create one reviewable JSON plan containing a non-empty `source_reference`, exact `deletions` entries with `path` and `reason`, and complete `replacements` entries with `path` and final `content` for every reference cleanup. Run `delete-propose --plan <plan.json>` and display every target, current digest, reason, reference change, impact, preflight result, validation plan, and `proposal_revision`. The plan is a candidate artifact, not formal knowledge.

Only after the user confirms that exact revision, run `delete-apply` with the same plan, `--proposal-revision`, and matching `--confirmed-revision`. The executor recomputes file and plan digests, rejects protected paths, preflights an isolated copy, applies reference rewrites and deletions as one transaction, runs the complete validator, and restores every affected file on failure. Never use ad-hoc filesystem deletion for formal knowledge, never delete an index merely because it becomes empty, and never claim that structural validation proves the content lacked audit value.
