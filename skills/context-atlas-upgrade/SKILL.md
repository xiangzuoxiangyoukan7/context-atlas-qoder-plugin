---
name: context-atlas-upgrade
description: Upgrade one existing Context Atlas knowledge base to a supported representation and format. Use for compatibility migration only; never add, revise, retire, approve, or reinterpret project knowledge.
---

# Context Atlas Upgrade

Upgrade only the knowledge representation format and physical structure of an existing Context Atlas knowledge base. Never create, revise, approve, supersede, or archive business facts as part of this workflow.

Read `../../references/兼容与迁移.md`, `../../references/Agent升级决策.md`, `../../references/执行状态机.md`, `../../references/验证与结果报告.md`, and `../../references/宿主执行与运行时探测.md` before applying an upgrade. Read the target knowledge base's root `README.md`, `knowledge-base.yaml`, and `.project-kb/compatibility.json` when available.

Follow `upgrade-diagnose -> upgrade-propose -> await_confirmation -> upgrade-apply -> validate -> report`:

1. Run `upgrade-diagnose` without writing. Distinguish the installed plugin version, `format_version`, and business `project_version`.
2. Treat `compatible` as readable-format compatibility only. It is not proof that the knowledge base already has the latest layout, metadata, links, or health.
3. If status is `needs_normalization` or `conversion_available`, run `upgrade-propose`. The executor upgrades runtime assets and applies deterministic transformations only in an isolated copy, then returns preflight validation and health findings without formal writes.
4. If deterministic preflight does not pass, inspect each reported document and use Agent reasoning to create a temporary semantic migration plan following `Agent升级决策.md`. Preserve old meaning and source traceability; do not infer business facts. Rerun `upgrade-propose --agent-plan <plan>` until it passes or an actual ambiguity must be reported to the user.
5. Show the source and target formats, every deterministic operation, every Agent decision with rationale and source paths, unresolved items, preflight results, and `proposal_revision`.
6. A latest-format knowledge base with structural, metadata, link, authority, or health findings must enter `needs_normalization`; normalization must be idempotent and need not change the format number.
7. If status is `unsupported`, an Agent decision cannot preserve meaning, or preflight cannot converge, stop with zero formal writes and report what requires human resolution.
8. Apply only after the user explicitly confirms an exact Proposal whose `preflight_status` is `passed`. Recompute with the same Agent plan immediately before apply; reject stale confirmation.
9. Run the complete deterministic validator and health checker after apply and report the result. Report `migrated` only with zero validation issues and no non-warning health findings.

Installing or updating the Context Atlas plugin never upgrades a project knowledge base automatically. Upgrade may change only representation, layout, internal metadata, and `format_version`; preserve business meaning, approval state, source traceability, history, and `project_version`.

The upgrade checker must cover every installed-plugin upgrade, regardless of the starting format: format readability, latest directory layout, retired directories/files/templates, legacy relation paths, every formal document's front matter shape and field content, classification relations, authority targets, links, Schema compatibility, every managed README's directory contract and navigation-query contract, health findings, and generated navigation smoke tests. A format that is numerically current but fails any deterministic check is not “no action”; it requires a normalization Proposal and post-apply validation. Deterministic validation verifies representation contracts, not whether business statements are true or complete; unresolved business semantics remain explicit for human review.

Resolve the current installed Skill root first, then use only its `../../assets/scripts/agent_kb_operation.py` executor together with its `../../assets/compatibility.json` as the upgrade-version authority. Pass that compatibility path explicitly to `upgrade-diagnose`, `upgrade-propose`, and `upgrade-apply`. Never use the target knowledge base's `.project-kb/scripts/agent_kb_operation.py` or `.project-kb/compatibility.json` to decide whether a newer installed plugin offers a conversion: those files describe the target's embedded format generation and can only prove compatibility with themselves. The command report must identify the current installed `runtime_assets_root` and `compatibility_path`; if either points inside the target knowledge base, reject the result and rerun with the installed assets.

Prefer the canonical commands `upgrade-diagnose`, `upgrade-propose`, and `upgrade-apply`; legacy migration command names are compatibility aliases only. Do not ask the user to construct low-level file or content parameters.

Before apply, follow the runtime detection contract. Use the bundled Python executor when Python 3 is available. If deterministic execution or validation is unavailable, stop with zero formal writes; format upgrade must not use a best-effort host fallback.
